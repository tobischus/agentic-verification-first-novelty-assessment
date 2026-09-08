#!/usr/bin/env python3
"""
A claim-evidence map: which sentence of the submission does this prior paper already say?

The comparison this replaces ends in one word per (claim, paper) -- `substantial`,
`partial` -- and a pile of one-sided quotes from the prior work. Those quotes say what the
OTHER paper does. The reviewer is left to work out which part of their own contribution is
affected, once per paper, eleven times on one claim of the GraphRAG submission.

So the unit here is a PAIR: a verbatim span of the submission beside a verbatim span of the
prior paper, with one sentence saying why they are the same thing. Section 2.3 of the thesis
asks for exactly this, quoting You, Cao and Gurevych: "checkable verification artifacts,
such as claim-evidence maps". Two separate one-sided lists are the raw material for a map,
not the map.

Three decisions, each made against something that went wrong when it was made differently.

**Both sides are quoted from their own document.** Not from the claim. The claim text used
to sit in the corpus a claim quote was verified against, so a model could quote the claim
back and the check confirmed it against itself -- 94 of 141 "verified" claim quotes on
disk. The submission side is now drawn from the submission's own sections and verified
there, which is the only way the pair means anything.

**No score.** An earlier version split the claim into elements and scored coverage. It
produced numbers that looked precise and were not: bundle several requirements into one
element and any paper matches it; split them finely and every claim is novel. The map
reports what was found and lets the reader see how much of the claim it touches.

**The conclusion comes last, from the verified map only.** The old comparison asserted a
degree in the same call that produced the quotes -- before anything was checked -- and the
schema then permitted evidence pairs only when that assertion happened to be `can_refute`.
Grounding tracked the label rather than the overlap: 100% of refutations carried a pair,
0% of the substantial-but-not-refuting ones did.
"""
import re
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from . import evidence as ev


# ------------------------------- trimming ---------------------------------- #

_ABBR = re.compile(r"(?:et al|e\.g|i\.e|cf|vs|Fig|Sec|Tab|Eq|approx|resp|Dr|No|al|[A-Z])\.$")
_STOP = frozenset("a an the of to in for and or is are was were be been with on at by that this "
                  "it its as from we our their they can may not but which".split())


def _sentences(span: str) -> List[str]:
    """Split a span into sentences, leaving abbreviations and initials intact."""
    out, start = [], 0
    for m in re.finditer(r"[.!?]\s+(?=[A-Z(])", span):
        head = span[start:m.start() + 1]
        if _ABBR.search(head.strip()):
            continue
        out.append(span[start:m.end()].strip())
        start = m.end()
    tail = span[start:].strip()
    if tail:
        out.append(tail)
    return out or [span]


# A section heading swallowed by a quote: "... to respond to user queries. 2.1 ## Medical
# Graph Construction 2.1.1 ## Step1 ..." -- the numbering and the "##" come from the parsed
# document structure, not from the paper's prose.
_HEADING = re.compile(r"\s(?:\d+(?:\.\d+)*\s*)?##\s")


def trim_display_span(span: str, max_sentences: int = 3, max_chars: int = 700) -> str:
    """Cut a verified quote down to what a reviewer can actually read.

    The model is asked for one contiguous verbatim span and is given no ceiling, so it
    returns paragraphs: across the artifacts on disk the median realization quote grew to
    535 characters and the longest reached 2109, running through section headings picked up
    from the parsed structure. A quote that long is not evidence a reader checks, it is a
    page of the paper reproduced.

    Cutting happens at boundaries the text already has -- the heading that should never
    have been inside a quote, then whole sentences -- so what remains is still verbatim and
    still verifiable. Never returns empty: a single very long sentence is left alone rather
    than cut mid-clause.
    """
    t = " ".join((span or "").split())
    if not t:
        return span
    head = _HEADING.search(t)
    if head and head.start() > 80:          # keep the heading out, but only if prose precedes it
        t = t[:head.start()].strip()
    sents = _sentences(t)
    if len(sents) > max_sentences:
        t = " ".join(sents[:max_sentences])
    while len(t) > max_chars and len(_sentences(t)) > 1:
        t = " ".join(_sentences(t)[:-1])
    return t or span


def _clauses(sentence: str, min_words: int = 8) -> List[str]:
    """Split a sentence at the conjunctions that join separate claims, and nowhere else.

    A contribution is often stated once, as a sentence carrying every part of it: "features
    a comprehensive dataset with tasks of increasing difficulty, covering fact retrieval,
    complex reasoning, contextual summarize, and creative generation, and a systematic
    evaluation across the entire pipeline". Quoting all of it against a paper that matches
    one part shows the reviewer an overlap several times the real size, and it makes every
    entry carry the SAME anchor -- four of seven pairs in the last run -- so the map stops
    saying which part of the contribution each paper actually touches.

    The split is only taken where what FOLLOWS is a clause in its own right. The ", and "
    before a list's final item ("..., contextual summarize, and creative generation") joins
    an item, not a claim, and cutting there would end the quote mid-list: verbatim, and
    misleading about where the task list stops.
    """
    out, last = [], 0
    for mt in re.finditer(r",\s+and\s+", sentence):
        nxt = re.split(r",\s+and\s+", sentence[mt.end():])[0]
        if (len(nxt.split()) >= min_words
                and len(sentence[last:mt.start()].split()) >= min_words):
            out.append(sentence[last:mt.start()].strip())
            last = mt.end()
    out.append(sentence[last:].strip())
    return [x for x in out if x]


def trim_to_sentence(span: str, rationale: str, claim: str, min_tokens: int,
                     counterpart: str = "") -> str:
    """Cut a multi-sentence span down to the sentence that carries the correspondence.

    The model was asked for the shortest span that states the matched point and returned
    two- and three-sentence blocks anyway: 19 of 23 spans in the run before this function
    existed. A span that wide costs twice. It shows the reviewer more of their paper as
    matched than the pair actually matches, and it destroys granularity -- a block covering
    every component of a contribution is the same anchor for every correspondence, so the
    map stops localising anything.

    Which sentence to keep is not guessed: the model already wrote one sentence saying what
    the two spans share, so the sentence that overlaps that rationale most is the one the
    pair is about. The CLAIM is scored alongside it, because the rationale alone once picked
    the neighbouring sentence -- which belonged to a different claim of the same paper, and
    anchored claim 1's map on claim 2's contribution. Ties and short results fall back to the
    full span, because cutting below what can be verified would be worse than leaving it wide.
    """
    sents = _sentences(" ".join((span or "").split()))
    key = {w for w in re.findall(r"[a-z]{3,}", (rationale or "").lower()) if w not in _STOP}
    anchor = {w for w in re.findall(r"[a-z]{3,}", (claim or "").lower()) if w not in _STOP}
    if not key and not anchor:
        return span
    # A span of one sentence still goes through clause selection below: the sentence that
    # states a whole contribution in one breath is exactly the case this exists for, and it
    # never has a second sentence to choose between.
    if len(sents) < 2:
        best = sents[0] if sents else span
        return _pick_clause(best, key, min_tokens, counterpart)
    best, best_score = None, -1.0
    for s in sents:
        if len(s.split()) < min_tokens:
            continue
        words = {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in _STOP}
        score = (len(words & key) + len(words & anchor)) / (len(words) ** 0.5 or 1)
        if score > best_score:
            best, best_score = s, score
    if not best:
        return span
    # One sentence can still carry several parts of a contribution. Where it does, keep the
    # part this correspondence is actually about -- scored against the RATIONALE alone. The
    # claim is what picked the sentence; inside it every clause is on-claim by construction,
    # and scoring the claim again drowns out the only signal that separates the clauses,
    # sending every correspondence back to the same anchor.
    return _pick_clause(best, key, min_tokens)


def _drop_lead(clause: str) -> str:
    """Drop a dangling conjunction a clause was cut after.

    Splitting at ", and " leaves the next clause starting on "and", which reads as a
    fragment and makes two quotes of the SAME clause look like two different anchors. The
    result is still verbatim -- a shorter substring of the same span.
    """
    return re.sub(r"^(?:and|or|but|as well as)\s+", "", clause.strip(), flags=re.I)


def _pick_clause(sentence: str, key: set, min_tokens: int, counterpart: str = "") -> str:
    """Of a sentence's separable clauses, the one this correspondence is about.

    Scored against the RATIONALE alone. The claim is what picked the sentence; inside it
    every clause is on-claim by construction, and scoring the claim again drowns out the
    only signal that separates the clauses -- sending every correspondence back to the same
    anchor, which is the failure this is here to fix.
    """
    cl = [_drop_lead(c) for c in _clauses(sentence)]
    if len(cl) < 2 or not key:
        return sentence
    # The clause has to keep the PAIR intact. Scored on the rationale alone, narrowing the
    # submission side to one component produced spans that no longer answered to the prior
    # paper's sentence -- and the audit then rejected the pair, correctly, for a mismatch the
    # trim had introduced: it cost the strongest competitor on one claim. The counterpart is
    # scored alongside, and a clause that shares nothing with it is not used at all.
    other = {x for x in re.findall(r"[a-z]{3,}", (counterpart or "").lower()) if x not in _STOP}
    pick, ps = None, 0.0
    for c in cl:
        if len(c.split()) < min_tokens:
            continue          # too short to stand as evidence on its own
        w = {x for x in re.findall(r"[a-z]{3,}", c.lower()) if x not in _STOP}
        if other and len(w & other) < 2:
            # One shared word is coincidence -- "graph" appears in every clause of a GraphRAG
            # paper. Below two, narrowing to this clause would break the correspondence, and
            # keeping the whole sentence is the honest answer: the pair is about the
            # contribution as a whole, not about one of its parts.
            continue
        sc = (len(w & key) + len(w & other)) / (len(w) ** 0.5 or 1)
        if sc > ps:
            pick, ps = c, sc
    # A clause is only worth cutting to when it actually answers to the rationale. With the
    # short clauses skipped, the longest one would otherwise win by default and the quote
    # would narrow to a part the correspondence is not about -- worse than not cutting.
    return pick if pick else sentence


# ------------------------------- schemas ----------------------------------- #

class Correspondence(BaseModel):
    submission_quote: str = Field(
        description="ONE CONTIGUOUS verbatim span in which the SUBMISSION states something "
                    "IT CONTRIBUTES that this paper also delivers -- the shortest span that "
                    "states it, never its motivation, "
                    "its critique of existing work, or background. Copied character for "
                    "character, at least 10 words, never joined by an ellipsis.")
    paper_quote: str = Field(
        description="ONE CONTIGUOUS verbatim span of the PRIOR PAPER showing that it does "
                    "that. Copied character for character, at least 10 words, never joined "
                    "by an ellipsis. Must state what THIS paper does -- never what it says "
                    "about work it cites.")
    relation: str = Field(
        description="ONE sentence: what both spans deliver. Name the thing, not the topic.")
    strength: str = Field(
        description="same  (the paper delivers this outright)  |  "
                    "weaker  (a narrower version, a special case, or only part of it)")


class EvidenceMap(BaseModel):
    correspondences: List[Correspondence] = Field(
        default_factory=list,
        description="EVERY place where a sentence of the submission and a sentence of this "
                    "paper say the same thing -- a complete list, empty if there are none")
    submission_delta: str = Field(
        description="what the submission's contribution still holds that this paper does not")


MAP_PROMPT = """Put ONE prior paper beside ONE claimed contribution and find every place where they say the same thing.

You are building a map a reviewer can check: each entry pairs a sentence of the submission with a sentence of the prior paper. Both must be quoted verbatim from the texts below -- they are checked automatically against the two documents afterwards, and an entry whose quotes cannot be located is dropped.

What counts as a correspondence: both papers deliver the SAME THING AS THEIR CONTRIBUTION -- the same construction, the same artifact, the same property, the same finding.

Two things that look like correspondences and are not:

- SHARED MACHINERY. Both build a knowledge graph, both retrieve passages, both evaluate a pipeline, both call a model. Everything in this field does those. Ask: would this entry read the same if I swapped in almost any other paper from the area? Then it says nothing and does not belong in the map.
- MISMATCHED KIND. One side announces an artifact, the other reports a finding; one side evaluates a pipeline stage, the other merely has that stage. Those are different contributions even when they share vocabulary. Both spans must be the same kind of statement about the same thing.
- BUILDING vs USING. A paper that EVALUATES ITSELF ON benchmarks, corpora or datasets has not contributed one. "validated on 9 benchmarks", "we employ 11 datasets", "we test on three corpora" is a paper using resources, and it is no correspondence to a submission whose contribution is to BUILD such a resource. The same holds for methods: applying one is not proposing it.

Report every correspondence you can support, and none you cannot. Most prior papers retrieved for a claim share its field and not its contribution: an empty list is a normal and useful answer, and a list that could be written about any paper in the area describes the field rather than the overlap.

Quote rules, both sides:
- ONE CONTIGUOUS span, copied character for character, at least 10 words, inside ONE sentence.
- NEVER join separate parts with "..." -- a stitched span appears nowhere and cannot be checked. If one span does not cover the point, pick the single most telling one, or make it two entries.
- AS TIGHT AS THE CORRESPONDENCE. Quote the SHORTEST contiguous span that states the matched point, and stop there. A contribution is often stated as one long sentence listing several components; pairing that whole sentence with a paper that delivers one of them shows the reviewer an overlap three times the size of the real one. Quote the component.
- Each span must state what ITS OWN paper DOES. The paper span must never quote what that paper says about work it cites; the submission span must never quote the submission's motivation, its complaint about existing benchmarks, or its background -- those describe the problem, and a prior paper agreeing with your problem statement does not touch your contribution.

## The claimed contribution
{claim}

## The submission's own text (quote the submission side from here)
{submission}

## The prior paper: {title}
{paper}"""


CONCLUDE_PROMPT = """Decide what ONE prior paper does to the novelty of ONE claimed contribution.

Below is the verified evidence: every pair where a sentence of the submission and a sentence of that paper were found to say the same thing, each side confirmed against its own document. Nothing else is available to you, and nothing else may enter your reasoning.

  same          this paper by itself delivers the claimed contribution
  substantial   it delivers most of it; what is left is a refinement
  partial       it delivers a real part, and the claim clearly adds beyond it
  superficial   same area, different contribution
  none          nothing of the claimed contribution

An empty evidence map means `superficial` or `none` -- never more, whatever the paper's title suggests.

Weigh what the correspondences leave standing, not how many there are: one pair on the heart of the contribution outweighs four on its periphery. Say in `reasoning` which part is taken and which is not, in two or three sentences, and name the pairs you relied on.

## The claimed contribution
{claim}

## Verified correspondences
{pairs}

## What the submission still holds, according to the comparison
{delta}"""


class Conclusion(BaseModel):
    reasoning: str = Field(description="2-3 sentences: what is taken, what is left")
    degree: str = Field(description="same | substantial | partial | superficial | none")


# ------------------------------ operations --------------------------------- #

def build_map(struct_call: Callable, claim_str: str, submission_text: str,
              title: str, paper_text: str, verify_submission: str, verify_paper: str,
              min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0) -> dict:
    """The verified map for one (claim, paper), or an empty one.

    `submission_text` and `paper_text` are what the model may quote FROM; `verify_submission`
    and `verify_paper` are the full documents each side is checked AGAINST. They differ
    because the model sees a section selection while verification must run against the whole
    document -- a span trimmed at a section boundary is still in the paper.
    """
    parsed = struct_call(EvidenceMap, MAP_PROMPT.format(
        claim=claim_str[:1500], submission=submission_text[:14000],
        title=title, paper=paper_text))
    if parsed is None:
        # `failed` separates "the call did not come back" from "the model found nothing".
        # Both used to leave an empty map, and an empty map reads as `none` -- so an API
        # error was indistinguishable from a paper that genuinely shares nothing, which is
        # exactly the confusion a verification-first artifact must not contain.
        return {"pairs": [], "submission_delta": "", "dropped": 0, "returned": 0,
                "failed": True}

    pairs, dropped = [], 0
    for c in parsed.correspondences:
        s_chk, s_span = ev.verify_contiguous(
            c.submission_quote, verify_submission, min_quote_tokens, fuzzy_threshold)
        p_chk, p_span = ev.verify_contiguous(
            c.paper_quote, verify_paper, min_quote_tokens, fuzzy_threshold)
        if not (s_chk.verified and p_chk.verified):
            # Both sides or nothing. A pair with one confirmed half is not a claim-evidence
            # map entry, it is an assertion with a citation attached -- which is the thing
            # this module exists to replace.
            dropped += 1
            continue
        rel = (c.relation or "").strip()
        pairs.append({
            "claim_quote": trim_to_sentence(s_span, rel, claim_str, min_quote_tokens, p_span),
            "paper_quote": trim_to_sentence(p_span, rel, claim_str, min_quote_tokens, s_span),
            "rationale": rel,
            "strength": (c.strength or "").strip().lower(),
            "claim_quote_verified": True, "paper_quote_verified": True,
            "exact": True,               # already trimmed to one sentence; do not re-expand
        })
    return {"pairs": pairs, "submission_delta": (parsed.submission_delta or "").strip(),
            "dropped": dropped, "returned": len(parsed.correspondences), "failed": False}


class Audited(BaseModel):
    keep: List[int] = Field(
        description="1-based numbers of the entries that survive, in order. Empty if none do.")
    dropped: str = Field(default="", description="one clause per rejected entry: its number "
                                                 "and which test it failed")


AUDIT_PROMPT = """Each entry below pairs a sentence of a submission with a sentence of one prior paper, and asserts they deliver the same thing. Both quotes are already confirmed verbatim. Your job is the OTHER half of the check: whether the assertion holds.

Judge each entry BY ITS TWO SPANS. The question is whether the prior paper's span states something THAT PAPER ITSELF DELIVERS which is the same thing the submission's span says the submission delivers.

A claimed contribution usually has several parts, and each entry is about ONE of them. An entry that covers only part of the claim is a correct entry -- that is what a map is for. Whether the claim as a whole survives is decided elsewhere, from the entries you keep, so NEVER reject an entry for being narrower than the claim. The claim is printed below only so you can tell which part an entry is about.

Reject an entry only when its two spans fail one of these, and that thing must be a CONTRIBUTION:

1. SHARED MACHINERY. Would this entry read the same with almost any other paper in this area substituted? Constructing a knowledge graph, retrieving passages, running a pipeline, prompting a model -- everything here does those. Common practice is not a correspondence.
2. BUILDING vs USING. Contributing a benchmark, dataset, corpus or method is not the same as evaluating on one or applying one. "we validate on 9 benchmarks", "we employ 11 datasets", "we follow the standard approach" is a paper USING resources. This is about the ROLE the thing plays, not the word used: a paper whose own contribution IS a benchmark, testbed or evaluation framework DELIVERS that artifact, and does not fail this test merely because the shared contribution is an evaluation.
3. ARTIFACT vs FINDING. Announcing a resource is not reporting a result about it, and having a pipeline stage is not evaluating that stage.
4. DIFFERENT OBJECT. The two SPANS are about different things and merely share vocabulary. Compare span with span: an entry is not a different object because it fails to cover the rest of the claim.
5. BOILERPLATE. Artifact-availability and code/data-release statements, repository links, funding, acknowledgements, dataset licences, reproducibility notes. Nearly every paper carries these and they say nothing about what a paper contributes. Two papers both publishing a GitHub link is not an overlap.

Keep every entry that passes all five, and reject every entry that does not, naming the failed test in `dropped`. Rejecting all of them is a normal outcome: most prior work retrieved for a claim shares its field and not its contribution.

## The claimed contribution (context only -- an entry may cover just one part of it)
{claim}

## The prior paper: {title}

## Entries
{pairs}"""


def audit(struct_call: Callable, claim_str: str, title: str, pairs: List[dict],
          votes: int = 3) -> List[dict]:
    """Re-check each verified pair for what kind of statement its two spans make.

    Verification proves the two quotes exist. It cannot prove they are about the same kind of
    thing, and that is where this comparison actually fails: a paper that CONSTRUCTS a
    knowledge graph read as matching a submission that EVALUATES graph construction, a paper
    VALIDATED ON benchmarks read as matching one that CONTRIBUTES a benchmark.

    Those tests were first written into the mapping prompt and applied inconsistently -- the
    same paper came back `none` in one run and `substantial` in the next, on the strength of
    exactly the machinery pairs the prompt had ruled out. Asked separately, with the quotes
    fixed and nothing to find, the judgement is made once per paper against four named tests
    rather than in passing while composing thirty other things.

    Asked once, it is still a coin toss on the entries that matter. Over six repetitions of an
    identical run the two papers that share only the field were rejected every time, while the
    two genuine competitors were each lost once -- a paper is carried by one to three pairs, so
    a single flipped entry drops it from `substantial` to `none` and hides the prior work the
    reviewer most needs. Three votes per pair, majority keeps: it costs three short calls per
    paper and it is the same remedy the judge in the evaluation harness already uses.
    """
    if not pairs:
        return pairs
    sep = "\n\n"
    listed = sep.join(
        f"[{i + 1}] claimed correspondence: {p['rationale']}\n"
        f"    SUBMISSION: \u201c{' '.join(p['claim_quote'].split())[:320]}\u201d\n"
        f"    THIS PAPER: \u201c{' '.join(p['paper_quote'].split())[:320]}\u201d"
        for i, p in enumerate(pairs))
    prompt = AUDIT_PROMPT.format(claim=claim_str[:1200], title=title, pairs=listed)
    tally, cast, why = {i: 0 for i in range(1, len(pairs) + 1)}, 0, []
    for _ in range(max(1, votes)):
        got = struct_call(Audited, prompt)
        if got is None:                  # a failed call abstains; it does not veto
            continue
        cast += 1
        for i in (got.keep or []):
            if i in tally:
                tally[i] += 1
        if got.dropped:
            why.append(got.dropped.strip())
    if not cast:                         # every vote failed: pass them through unfiltered
        return pairs
    need = cast // 2 + 1
    for i, p in enumerate(pairs, 1):
        p["audit_votes"] = f"{tally[i]}/{cast}"
        p["audit_rejected"] = tally[i] < need
        if p["audit_rejected"] and why:
            p["audit_reason"] = why[0][:300]
    return [p for i, p in enumerate(pairs, 1) if tally[i] >= need]


# ------------------------------ the delta ---------------------------------- #

class DeltaClaim(BaseModel):
    submission_quote: str = Field(
        description="ONE CONTIGUOUS verbatim span of the SUBMISSION stating the thing it "
                    "delivers. Copied character for character, at least 10 words.")
    what_it_is: str = Field(
        description="the thing itself, named in a few words -- not a sentence")
    probe: str = Field(
        description="a SHORT search phrase, 3 to 12 words, in the words THAT paper would "
                    "use if it had this. A phrase to match, never an instruction: no "
                    "'search for', no OR/AND, no quotation marks, no alternatives.")


class DeltaProposal(BaseModel):
    deltas: List[DeltaClaim] = Field(
        default_factory=list,
        description="what the submission delivers that this paper may not -- at most four, "
                    "each one checkable, empty if the paper appears to deliver everything")


DELTA_PROMPT = """One prior paper has been compared against one claimed contribution. Name what the SUBMISSION delivers that this paper may NOT.

Each entry is a claim of ABSENCE about the prior paper, and absence cannot be quoted. So an entry is made checkable in two parts:

- the submission's own sentence stating the thing it delivers, quoted verbatim, and
- a `probe`: what to search this paper for, to find out whether it has the same thing.

Write the probe in the words the PRIOR PAPER would use if it did have this. Searching for the submission's own vocabulary finds nothing and proves nothing: a paper that built the same corpora may call them "datasets", and one that evaluates the same stages may call them "components".

A probe is a short phrase that would APPEAR IN that paper, three to twelve words -- "corpora of varying information density", "evaluation of graph construction quality". It goes to a passage retriever, not to a person: written as an instruction with alternatives and operators, the retriever matches on the instruction's own filler words and returns the wrong part of the paper, and the absence it then appears to show is an artifact of the query.

Name a CAPABILITY the claim promises, never the identity of the material used to build it. "Corpora that vary information density" is a capability another paper could have; "NCCN guidelines and Project Gutenberg novels" is this submission's implementation of it, and no other paper has those by definition -- so the entry is true, worthless, and it inflates what the submission appears to hold. The same goes for the name of a model or tool used ("ontologies built with GPT-4.1"), for dataset names, and for anything another group would have done differently while delivering the same thing.

The test: could a competing paper plausibly have this, and would the claim be weaker if it did? If not, it is not a delta.

Name only things that are part of the claimed contribution, that this paper plausibly lacks, and that a passage of that paper could settle. Not the submission's motivation, not the field's open problems, and not vague superiority ("more comprehensive", "more rigorous").

An empty list is a real answer: it says the correspondences already cover the claim.

## The claimed contribution
{claim}

## The submission's own text (quote from here)
{submission}

## The prior paper: {title}

## What was already found to correspond
{pairs}"""


class DeltaRuling(BaseModel):
    index: int = Field(description="which entry this rules on, 1-based")
    holds: bool = Field(description="true if the retrieved passages do NOT show this paper "
                                    "delivering the thing")
    paper_quote: str = Field(default="", description="if holds is false: ONE CONTIGUOUS "
                                                     "verbatim span from the passages showing "
                                                     "that it DOES deliver it")
    note: str = Field(description="one sentence: what the passages do and do not show")


class DeltaVerdict(BaseModel):
    rulings: List[DeltaRuling] = Field(default_factory=list)


DELTA_RULE_PROMPT = """For each entry below, the prior paper's own full text was searched for the thing the submission claims to deliver. The best-matching passages are printed under each entry -- they are the closest this paper comes to it.

Rule on each entry:

- holds = true: the passages do NOT show this paper delivering the thing. Retrieval looked, and this is the nearest it found.
- holds = false: they DO show it. Then quote the span that shows it, verbatim from the passages, and the entry is withdrawn -- the submission does not have this to itself.

Retrieval returns the closest passages whether or not anything matches, so passages that merely share the topic are the normal case for an entry that holds. What settles `holds = false` is a passage stating that THIS PAPER delivers the thing -- not one discussing it, citing others who do, or listing it as future work.

Be strict in both directions. An entry that holds is shown to a reviewer as something the submission still has to itself, and a wrong one there is worse than one never made.

## The claimed contribution
{claim}

## Entries, each with what the search found
{entries}"""


def check_delta(struct_call: Callable, search: Callable, claim_str: str, submission_text: str,
                title: str, pairs: List[dict], verify_submission: str, verify_paper: str,
                min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0,
                k: int = 4) -> dict:
    """What the submission still holds, established by looking rather than by asserting.

    `submission_delta` used to be one free sentence produced in the same breath as the
    correspondences and checked against nothing. It is the half of the comparison a reviewer
    leans on hardest -- it is what survives of their own contribution -- and it was the only
    half with no evidence behind it at all.

    A delta is a claim of ABSENCE, and absence cannot be quoted. So it is grounded in the two
    parts that can be: the submission's own sentence stating what it delivers, verified
    against the submission, and a SEARCH of the prior paper's full text for that same thing,
    phrased in the words that paper would use. What the search returns is shown either way --
    the closest this paper comes -- so a reviewer sees what the claim of absence was checked
    against instead of having to take it.

    A delta the search refutes is not silently dropped. The passage that refutes it is
    verified and kept: a paper that turns out to deliver what the submission thought was its
    own is the most important thing this comparison can find.
    """
    if not pairs:
        # Nothing corresponded, so everything is a delta and none of it is informative.
        # A comparison that found no overlap already tells the reviewer what they need.
        return {"deltas": [], "withdrawn": [], "probes": 0, "failed": False}
    listed = "\n".join(f"- {p['rationale']}" for p in (pairs or [])) or "(no correspondence found)"
    proposal = struct_call(DeltaProposal, DELTA_PROMPT.format(
        claim=claim_str[:1200], submission=submission_text[:12000],
        title=title, pairs=listed[:1500]))
    if proposal is None:
        return {"deltas": [], "withdrawn": [], "probes": 0, "failed": True}

    cand = []
    for d in (proposal.deltas or [])[:4]:
        chk, span = ev.verify_contiguous(
            d.submission_quote, verify_submission, min_quote_tokens, fuzzy_threshold)
        if not chk.verified:
            continue          # a delta whose own half cannot be located is not evidence
        try:
            hits = (search(d.probe or d.what_it_is, k) or [])[:k]
        except Exception:
            hits = []
        # Same sentence, three deltas: the contribution is stated once and every entry
        # quoted all of it, so the reviewer could not see which part each delta was about.
        what = (d.what_it_is or "").strip()
        key = {w for w in re.findall(r"[a-z]{3,}", (what + " " + (d.probe or "")).lower())
               if w not in _STOP}
        cand.append({"what": what,
                     "submission_quote": _pick_clause(
                         trim_display_span(span), key, min_quote_tokens),
                     "probe": (d.probe or "").strip(),
                     "found": [h.get("text", "")[:600] for h in hits]})
    if not cand:
        return {"deltas": [], "withdrawn": [], "probes": 0, "failed": False}

    entries = "\n\n".join(
        "[{}] {}\n    THE SUBMISSION: {}\n    SEARCHED FOR: {}\n    CLOSEST PASSAGES:\n{}".format(
            i + 1, c["what"], " ".join(c["submission_quote"].split())[:300], c["probe"],
            "\n".join("      - " + " ".join(t.split())[:300] for t in c["found"])
            or "      (nothing retrieved)")
        for i, c in enumerate(cand))
    verdict = struct_call(DeltaVerdict, DELTA_RULE_PROMPT.format(
        claim=claim_str[:1200], entries=entries))
    if verdict is None:
        return {"deltas": [], "withdrawn": [], "probes": len(cand), "failed": True}

    held, withdrawn = [], []
    ruled = {r.index: r for r in (verdict.rulings or [])}
    for i, c in enumerate(cand, 1):
        r = ruled.get(i)
        if r is None:
            continue          # nothing is asserted for an entry the model did not rule on
        if r.holds:
            held.append({**c, "note": (r.note or "").strip(),
                         "closest": c["found"][0] if c["found"] else ""})
            continue
        pchk, pspan = ev.verify_contiguous(
            r.paper_quote, verify_paper, min_quote_tokens, fuzzy_threshold)
        withdrawn.append({**c, "note": (r.note or "").strip(),
                          "paper_quote": trim_display_span(pspan) if pchk.verified else "",
                          "paper_quote_verified": bool(pchk.verified)})
    return {"deltas": held, "withdrawn": withdrawn, "probes": len(cand), "failed": False}


# --------------------------- the follow-up pass ----------------------------- #

class OpenQuestion(BaseModel):
    question: str = Field(description="what this comparison leaves unsettled, as a question "
                                      "a passage of the prior paper could answer")
    probe: str = Field(description="a SHORT search phrase, 3 to 12 words, in THAT paper's "
                                   "vocabulary -- a phrase to match, not an instruction")
    why: str = Field(description="one clause: what turns on the answer")


class OpenQuestions(BaseModel):
    questions: List[OpenQuestion] = Field(
        default_factory=list,
        description="at most three, ordered by how much the comparison depends on them; "
                    "empty when nothing material is left open")


FOLLOWUP_PROMPT = """Below are the correspondences found between one prior paper and one claimed contribution. Each pairs a sentence of the submission with a sentence of that paper.

For the correspondences that carry the most weight, ask what the pair itself does not settle. The paper's full text is searchable, so ask only what a passage of THAT paper could answer.

Every question must be ABOUT ONE OF THE PAIRS. Name it. Three shapes are worth asking:

- SCOPE. The pair shows this paper does the thing. Does it do it as broadly as the submission -- or only for one task, one dataset, one setting?
- A STRONGER STATEMENT. The quote came from the sections that happened to be read. Does the paper say something ELSEWHERE that puts it closer to the claim than this quote does?
- STATED LIMITS. Does the paper itself report this working only under conditions the submission does not share?

Do NOT ask whether the paper has something (that has already been searched for separately, and asking again returns the same passages). Ask how far what it HAS actually goes.

Ask nothing when the pairs settle it. Three is the maximum and fewer good ones are better.

## The claimed contribution
{claim}

## The prior paper: {title}

## The correspondences
{pairs}"""


class Answer(BaseModel):
    index: int = Field(description="which question, 1-based")
    answered: bool = Field(description="true only if the passages settle it")
    quote: str = Field(default="", description="if answered: ONE CONTIGUOUS verbatim span "
                                               "from the passages that settles it")
    answer: str = Field(description="one or two sentences; if the passages do not settle it, "
                                    "say what is still missing")
    refutes_delta: int = Field(
        default=0,
        description="1-based number of the listed delta this answer REFUTES -- set it only "
                    "when the passages show the prior paper does deliver that thing after "
                    "all. 0 when none is refuted.")


class Answers(BaseModel):
    answers: List[Answer] = Field(default_factory=list)


ANSWER_PROMPT = """Each question below was put to the prior paper's own full text. The passages retrieved for it are printed underneath.

Answer only from those passages. A question is `answered` only when a passage settles it, and then the span that settles it must be quoted verbatim -- it is checked against the paper afterwards and dropped if it cannot be found. When the passages do not settle it, say so and name what is missing: an unanswered question the reviewer can see is worth more than a confident answer that rests on nothing.

A question may turn out to settle one of the deltas listed below -- the things the submission is currently credited with having to itself. When the passages show this paper DOES deliver one of them, say so in `refutes_delta`. That entry is then withdrawn: it was reached by one search and yours found otherwise, and the reviewer must not be shown both.

## The prior paper: {title}

## Already searched for and ruled on -- do not ask about these again
{deltas}

## Questions and what the search returned
{entries}"""


def follow_up(struct_call: Callable, search: Callable, claim_str: str, title: str,
              pairs: List[dict], deltas: List[dict], verify_paper: str,
              min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0,
              k: int = 4, limit: int = 3) -> List[dict]:
    """Ask what the comparison left open, then go and look it up.

    The comparison reads the sections it picked once and concludes. Whatever those sections
    do not cover is simply absent from the result, and nothing in the pipeline notices --
    which is exactly the shape of the linear baseline this system is measured against: one
    pass, one judgement, no way to act on its own uncertainty.

    Here the model names what its own comparison leaves unsettled, and each question is put
    to the paper's full text by retrieval, not answered from memory. The answer is quoted and
    the quote is verified. A question the passages do not settle stays in the artifact
    unanswered, because a reviewer is better served by a named gap than by prose that covers
    it over.
    """
    # No correspondence, nothing to deepen: the questions worth asking are all about how far
    # a match goes, and there is no match. The delta pass has its own search for absence.
    if not pairs:
        return []
    # Numbered, because every question has to name the pair it is about.
    rows = ["[%d] %s" % (i + 1, p["rationale"]) for i, p in enumerate(pairs)]
    p_txt = chr(10).join(rows) or "(none)"
    asked = struct_call(OpenQuestions, FOLLOWUP_PROMPT.format(
        claim=claim_str[:1200], title=title, pairs=p_txt[:1600]))
    if asked is None or not (asked.questions or []):
        return []

    qs = []
    for q in (asked.questions or [])[:limit]:
        try:
            hits = (search(q.probe or q.question, k) or [])[:k]
        except Exception:
            hits = []
        qs.append({"question": (q.question or "").strip(), "probe": (q.probe or "").strip(),
                   "why": (q.why or "").strip(),
                   "found": [h.get("text", "")[:600] for h in hits]})
    entries = "\n\n".join(
        "[{}] {}\n    SEARCHED FOR: {}\n    PASSAGES:\n{}".format(
            i + 1, q["question"], q["probe"],
            "\n".join("      - " + " ".join(t.split())[:300] for t in q["found"])
            or "      (nothing retrieved)")
        for i, q in enumerate(qs))
    d_list = "\n".join(f"[{i + 1}] {d['what']}" for i, d in enumerate(deltas or [])) or "(none)"
    got = struct_call(Answers, ANSWER_PROMPT.format(
        title=title, deltas=d_list[:600], entries=entries))
    if got is None:
        return [{**q, "answered": False, "answer": "", "quote": ""} for q in qs]

    by = {a.index: a for a in (got.answers or [])}
    out = []
    for i, q in enumerate(qs, 1):
        a = by.get(i)
        if a is None:
            out.append({**q, "answered": False, "answer": "", "quote": ""})
            continue
        quote, ok = "", False
        if a.answered and a.quote:
            chk, span = ev.verify_contiguous(
                a.quote, verify_paper, min_quote_tokens, fuzzy_threshold)
            ok = bool(chk.verified)
            quote = trim_display_span(span) if ok else ""
        # A retraction only counts when the answer that carries it is itself grounded --
        # otherwise an unverifiable sentence could delete a delta that was checked.
        ref = int(a.refutes_delta or 0)
        out.append({**q, "answered": bool(a.answered and ok),
                    "answer": (a.answer or "").strip(), "quote": quote,
                    "refutes_delta": ref if (ok and 1 <= ref <= len(deltas or [])) else 0})
    return out


def apply_retractions(deltas: List[dict], followups: List[dict]) -> tuple:
    """Move every delta a grounded follow-up refuted out of the deltas and into withdrawn.

    The delta check and the follow-up pass can reach opposite conclusions about the same
    thing -- on the first run they did, one holding that the prior paper has no end-to-end
    pipeline evaluation while the other answered, from the same retrieved passage and with a
    verified quote, that it does. Showing a reviewer both is worse than showing neither.

    The follow-up wins, because it asked about that one thing and read the passages that
    answer it, where the delta check ruled on four entries at once. That the system revises
    its own claim on the strength of a lookup it chose to make is the point of the pass.
    """
    if not (deltas and followups):
        return deltas, []
    pulled = {q["refutes_delta"] for q in followups if q.get("refutes_delta")}
    if not pulled:
        return deltas, []
    kept, retracted = [], []
    for i, d in enumerate(deltas, 1):
        if i in pulled:
            q = next(x for x in followups if x.get("refutes_delta") == i)
            retracted.append({**d, "note": q["answer"], "paper_quote": q["quote"],
                              "paper_quote_verified": True, "retracted_by": q["question"]})
        else:
            kept.append(d)
    return kept, retracted


def conclude(struct_call: Callable, claim_str: str, mapping: dict) -> dict:
    """The novelty judgement for one paper, from the verified map and nothing else.

    Deliberately a second call. Asked together, the model states a degree in the same breath
    as the quotes -- before either has been checked -- and the quotes then exist to support a
    conclusion already drawn. Here the conclusion is drawn from evidence that has already
    survived verification, which is what "verification-first" has to mean at this level.
    """
    pairs = mapping.get("pairs") or []
    if not pairs:
        return {"degree": "none", "reasoning": "No correspondence between this paper and the "
                                               "claimed contribution could be evidenced."}
    listed = "\n\n".join(
        f"[{i + 1}] ({p['strength']}) {p['rationale']}\n"
        f"    SUBMISSION: “{' '.join(p['claim_quote'].split())[:400]}”\n"
        f"    THIS PAPER: “{' '.join(p['paper_quote'].split())[:400]}”"
        for i, p in enumerate(pairs))
    parsed = struct_call(Conclusion, CONCLUDE_PROMPT.format(
        claim=claim_str[:1200], pairs=listed,
        delta=(mapping.get("submission_delta") or "(not stated)")[:800]))
    if parsed is None:
        return {"degree": "partial", "reasoning": ""}
    degree = (parsed.degree or "").strip().lower()
    if degree not in ("same", "substantial", "partial", "superficial", "none"):
        degree = "partial"
    return {"degree": degree, "reasoning": (parsed.reasoning or "").strip()}

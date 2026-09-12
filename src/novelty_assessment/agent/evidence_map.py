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
_TAIL_NOISE = re.compile(r"(?:\s*(?:\d+\s*)?##[^.]*|\s+\d{1,4}(?:\s*##.*)?)\s*\.?\s*$")
_HEADING = re.compile(r"\s(?:\d+(?:\.\d+)*\s*)?##\s")


def _strip_structure(span: str) -> str:
    """Drop parser structure a quote ran into: a section heading, a page number, a year.

    Both ends. A heading in the MIDDLE ("... transducer. 1 ## Introduction Many modern ...")
    is the worse case: it starts with a digit, so the sentence splitter does not see a
    boundary there and the entire following section rides along inside what is shown as one
    sentence of evidence.
    """
    t = " ".join((span or "").split())
    if not t:
        return t
    head = _HEADING.search(t)
    if head and head.start() > 80:      # only when prose precedes it
        t = t[:head.start()].strip()
    return _TAIL_NOISE.sub("", t).strip()


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
    t = _strip_structure(span)
    if not t:
        return span
    # The same structure debris at the END of a span: a page number, a running head, a year
    # picked up where the parser ran one block into the next -- "...facilitate future
    # studies. 11 ## 2025." A quote is not wrong because of it, but it reads as though the
    # system does not know where the sentence stopped.
    t = _TAIL_NOISE.sub("", t).strip()
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
    # Structure debris first. A heading the parser ran into the text ("... transducer.
    # 1 ## Introduction Many modern NLP systems ...") is not a sentence boundary to the
    # splitter -- it starts with a digit -- so the whole block survived as ONE sentence and
    # the pair carried a paragraph of the next section with it. The cleanup existed, but
    # only on the display path; pair spans never saw it.
    sents = _sentences(_strip_structure(span))
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
        description=(
            "One contiguous verbatim span where the submission states "
            "a substantive component it contributes."
        )
    )

    paper_quote: str = Field(
        description=(
            "One contiguous verbatim span where the prior paper itself "
            "contributes the corresponding component."
        )
    )

    relation: str = Field(
        description=(
            "One concise sentence naming the substantive component "
            "instantiated by both spans."
        )
    )

    strength: str = Field(
        description=(
            "same | weaker. `same` means this component is directly delivered; "
            "`weaker` means the prior paper delivers a narrower or partial version."
        )
    )

class EvidenceMap(BaseModel):
    correspondences: List[Correspondence] = Field(
        default_factory=list,
        description=(
            "All substantive component-level correspondences for which both "
            "the submission and this prior paper state something they themselves contribute."
        ),
    )

MAP_PROMPT = """Identify every substantive component-level correspondence between ONE claimed contribution and ONE prior paper.

Your task is evidence extraction, not an overall novelty judgment.
The proposed semantic comparison below is a hypothesis to verify, not a fact.

First identify the specific shared contribution asserted in "What is shared"
and the assessment. Search the provided source texts for evidence of THAT
assertion. Do not substitute a different, easier-to-match contribution.

Keep the current claim as the scope of the comparison. Contributions elsewhere
in the submission are relevant only when you explain their direct bearing on
this claim.

For an empirical claim, distinguish a shared research activity from a shared
finding. "Both conduct experiments" does not by itself establish that both
answer the same scientific question or deliver the same empirical knowledge.
For other claim types, apply the same distinction to their actual contribution.

Use the proposed comparison to direct the search, but do not force agreement.
If the sources establish a different substantive overlap within the current
claim, report that correspondence and explicitly state how it differs from
the proposed rationale. If the proposed overlap has no supporting spans,
do not manufacture a substitute pair.

In each relation, state the concrete shared contribution established by the
two quotes and how it bears on the current claim. Do not merely repeat the
proposed assessment.

## Proposed semantic comparison — unverified
{comparison}
A correspondence exists when:
1. the submission states a substantive component of its claimed contribution;
2. the prior paper itself contributes something that instantiates the same substantive component; and
3. both statements can be supported by verbatim spans from the provided texts.

Judge the matched component, not whether the two papers make the same overall contribution. A prior paper may differ in its overall purpose, framing, scope, or design and still contribute a substantive component of the claim.

Do not report a correspondence when the relationship is only:
- shared topic, terminology, background, motivation, or common technical machinery;
- use, application, evaluation, or discussion of something that the other paper contributes;
- a statement about work cited by the paper rather than the paper's own contribution;
- semantic relatedness without both spans supporting the same substantive claimed component.

For every supported correspondence:
- quote the submission side verbatim;
- quote the prior-paper side verbatim;
- state briefly which substantive component the two spans correspond on;
- mark the relation as `same` when the prior paper directly delivers that component, or `weaker` when it delivers a narrower or partial version.

Report all supported correspondences and no unsupported ones. An empty list is a valid result.

Quote constraints:
- each quote must be ONE contiguous verbatim span;
- each quote must contain at least 10 words;
- each quote must lie within one sentence;
- never join separate spans;
- use the shortest span that still expresses the correspondence;
- each span must state what its own paper contributes, not merely what it discusses.

Do not assign an overall overlap degree in this step.

## Claimed contribution
{claim}

## Submission text
{submission}

## Prior paper: {title}
{paper}"""


CONCLUDE_PROMPT = """Determine what ONE prior paper does to the novelty of ONE claimed contribution.

You may use:
1. the claimed contribution;
2. the prior semantic comparison proposal; and
3. the verified component-level correspondences.

The comparison proposal is a semantic assessment based on the paper text.
It is not verified evidence and may be wrong.

The correspondences are verified evidence:
- both quoted spans have been verified against the source documents;
- the prior-paper span has passed ownership checking.

Use the comparison proposal to understand the role and context of the matched components.
Use the verified correspondences to determine what overlap is actually supported.

Do not simply copy the comparison degree.
Do not infer substantive overlap from a correspondence merely because it is verified.

If the verified evidence supports a different degree from the comparison proposal,
state explicitly why the semantic assessment should be revised.

Determine the overall degree:

same
    The prior paper by itself delivers essentially the claimed contribution.

substantial
    The prior paper delivers most of the substantive contribution; what remains is mainly
    a refinement or narrower distinction.

partial
    The prior paper delivers a substantive part of the contribution, while important
    claimed components remain.

superficial
    Verified relationships exist, but they do not amount to substantive contribution overlap.

none
    No substantive component of the claimed contribution is supported as overlap.

Judge the role and importance of the matched components, not the number of correspondences.

## Claimed contribution
{claim}

## Prior semantic comparison
{comparison}

## Verified correspondences
{pairs}
"""


class Conclusion(BaseModel):
    reasoning: str = Field(description="2-3 sentences: what is taken, what is left")
    degree: str = Field(description="same | substantial | partial | superficial | none")


# ------------------------------ operations --------------------------------- #

# --------------------------------------------------------------------------- #
# Ownership: does the paper's span say what THAT paper contributes?
#
# Verification proves that a span stands in a document. It cannot prove who it
# belongs to, and those are different questions. A survey that cites the
# submission carries the submission's own sentence verbatim; both sides then
# verify, and the pair reads as the strongest kind of evidence while showing
# nothing but a citation. That is what happened to "A Survey of Graph
# Retrieval-Augmented Generation": the agent's own narrative said the paper
# "lists GraphRAG-Bench among many benchmarks as a referenced item rather than
# presenting [it] as the paper's original contribution", and the pair was kept
# and the degree set to `substantial` regardless.
#
# Two checks, because neither covers the other:
#
#   identity   free and exact. Two independent papers do not write the same ten
#              words. Where the paper's span IS the submission's span, the paper
#              is quoting it, and no reading of the sentence changes that.
#   attribution one batched model call for the pairs that survive. A reference
#              is usually paraphrased, not copied: "X et al. propose a benchmark
#              of multi-hop queries" verifies, differs from the submission's
#              wording, and still belongs to X.
# --------------------------------------------------------------------------- #


class _OwnItem(BaseModel):
    index: int = Field(description="the pair's number, as given")
    own_contribution: bool = Field(
        description="true only if the span states what THIS paper does or delivers")
    why: str = Field(default="", description="one clause")


class _Ownership(BaseModel):
    verdicts: List[_OwnItem] = Field(default_factory=list)


OWNERSHIP_PROMPT = """Below are spans taken from ONE paper, each with the text around it. For each, decide whether the span states what THIS PAPER ITSELF does or delivers.

It does NOT, if the span:

- describes work the paper cites -- another system, dataset, benchmark or finding, however it is worded, and whether or not a citation marker survives in the excerpt
- reports a resource the paper merely USES or evaluates on, rather than one it built
- states background, a problem, or a position the field holds
- appears in a related-work summary, a table of other systems, or a list of prior approaches

It does, if the span states this paper's own construction, artifact, method, property or finding -- what a reader would attribute to these authors.

The surrounding text is what decides it: a sentence naming an artifact can be the paper announcing its own, or the paper describing someone else's, and only the context tells them apart.

## Paper: {title}

{spans}"""


def _norm_span(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _context_of(span: str, document: str, window: int = 320) -> str:
    """The span with the text around it, so attribution can be read off the page."""
    doc = document or ""
    n = _norm_span(span)[:60]
    if not n:
        return span
    flat = _norm_span(doc)
    i = flat.find(n)
    if i < 0:
        return span
    # map back approximately: the normalised text is close enough in length to index by ratio
    j = int(i / max(len(flat), 1) * len(doc))
    lo, hi = max(0, j - window), min(len(doc), j + len(span) + window)
    return "..." + " ".join(doc[lo:hi].split()) + "..."


def check_ownership(struct_call: Callable, pairs: List[dict], title: str,
                    verify_paper: str) -> List[dict]:
    """Mark each pair with why it was kept or dropped. Returns the surviving pairs.

    Dropping happens here rather than in `conclude`, because a pair that shows a
    citation is not weaker evidence to be weighed -- it is not evidence of an
    overlap at all, and leaving it in the map would put it in front of a reviewer
    as though it were.
    """
    if not pairs:
        return pairs
    kept, need = [], list(pairs)

    spans = "\n\n".join(
        f"[{i + 1}] SPAN: {p.get('paper_quote', '')}\n"
        f"    CONTEXT: {_context_of(p.get('paper_quote', ''), verify_paper)}"
        for i, p in enumerate(need))

    parsed = struct_call(
        _Ownership,
        OWNERSHIP_PROMPT.format(title=title, spans=spans)
    )
    if parsed is None:
        # The call did not come back. Keeping the pairs is the honest failure: this gate
        # removes evidence, and a gate that removes on silence would turn an API error
        # into a finding of no overlap.
        for p in need:
            p["ownership"] = "unchecked"
        return need
    verdict = {v.index: v for v in (parsed.verdicts or [])}

    for i, p in enumerate(need, start=1):
        v = verdict.get(i)

        # Missing verdict = not verified, not positive ownership.
        if v is None:
            p["ownership"] = "unchecked"
            kept.append(p)
            continue

        if not v.own_contribution:
            p["ownership"] = (
                f"describes_cited_work: {(v.why or '').strip()[:160]}"
            )
            continue

        p["ownership"] = "own_contribution"
        kept.append(p)

    return kept


def build_map(struct_call: Callable, claim_str: str, submission_text: str,
              title: str, paper_text: str, verify_submission: str, verify_paper: str,
              min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0,
              comparison: Optional[dict] = None) -> dict:
    """The verified map for one (claim, paper), or an empty one.

    `submission_text` and `paper_text` are what the model may quote FROM; `verify_submission`
    and `verify_paper` are the full documents each side is checked AGAINST. They differ
    because the model sees a section selection while verification must run against the whole
    document -- a span trimmed at a section boundary is still in the paper.
    """
    parsed = struct_call(
        EvidenceMap,
        MAP_PROMPT.format(
            claim=claim_str,
            submission=submission_text,
            title=title,
            paper=paper_text,
            comparison=_fmt_comparison(comparison or {}),
        ),
    )
    if parsed is None:
        # `failed` separates "the call did not come back" from "the model found nothing".
        # Both used to leave an empty map, and an empty map reads as `none` -- so an API
        # error was indistinguishable from a paper that genuinely shares nothing, which is
        # exactly the confusion a verification-first artifact must not contain.
        return {
            "pairs": [],
            "dropped": 0,
            "returned": 0,
            "not_owned": 0,
            "ownership_unchecked": 0,
            "failed": True,
        }

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
    # Verified, but not yet shown to belong to this paper. Counted separately from
    # `dropped`: a span that cannot be found and a span that belongs to someone else
    # fail for different reasons, and a diagnosis that merges them hides which.
    verified = len(pairs)

    ownership_result = check_ownership(
        struct_call,
        pairs,
        title,
        verify_paper,
    )

    unchecked = [
        p for p in ownership_result
        if p.get("ownership") == "unchecked"
    ]

    owned = [
        p for p in ownership_result
        if p.get("ownership") == "own_contribution"
    ]

    # Pairs that disappeared from check_ownership were either cited work,
    # quotes of the submission, or otherwise rejected as not this paper's contribution.
    not_owned = verified - len(ownership_result)

    return {
        # IMPORTANT: only ownership-verified pairs enter the evidence map.
        "pairs": owned,
        "dropped": dropped,
        "returned": len(parsed.correspondences),
        "not_owned": not_owned,
        "ownership_unchecked": len(unchecked),
        "failed": False,
    }


def _list_pairs(pairs: List[dict], start: int = 1) -> str:
    return "\n\n".join(
        "[{}] ({}) {}\n"
        "    SUBMISSION: \u201c{}\u201d\n"
        "    THIS PAPER: \u201c{}\u201d".format(
            i, p.get("strength", "?"), p.get("rationale", ""),
            " ".join(p["claim_quote"].split()),
            " ".join(p["paper_quote"].split()))
        for i, p in enumerate(pairs, start))


def _fmt_comparison(comparison: dict) -> str:
    """Render the raw compare's own narrative for CONCLUDE_PROMPT's `{comparison}` slot.

    Added when the prompt grew a section asking the model to weigh the map's verified
    pairs against what the FIRST, unverified pass already said the paper was about --
    context conclude() did not have before, since it only ever saw `mapping`."""
    if not comparison:
        return "(not available)"
    lines = [f"Proposed degree: {comparison.get('overlap_degree', '')}"]
    if comparison.get("what_is_shared"):
        lines.append(f"What is shared: {comparison['what_is_shared']}")
    if comparison.get("submission_delta"):
        lines.append(f"Submission delta: {comparison['submission_delta']}")
    if comparison.get("assessment"):
        lines.append(f"Assessment: {comparison['assessment']}")
    return chr(10).join(lines)





class EvidenceCheck(BaseModel):
    status: str = Field(
        description="material | nonmaterial | insufficient"
    )

    supporting_pair_indices: List[int] = Field(
        default_factory=list,
        description=(
            "1-based indices of grounded pairs that establish substantive "
            "overlap within the CURRENT claim. Include only pairs whose "
            "quoted spans actually support the stated relation."
        ),
    )

    proposed_degree_supported: Optional[bool] = Field(
        default=None,
        description=(
            "For proposed partial/substantial/same: whether the grounded "
            "evidence supports the decision-relevant overlap assertion "
            "at the proposed degree. Do not require every sentence of the "
            "assessment or delta to be established by correspondence pairs. "
            "An unsupported delta assertion makes this false only when "
            "resolving it could change the overlap degree; explain that "
            "dependency in unresolved_question. Otherwise record the "
            "limitation in reasoning. For none/superficial return null. "
            "Do not assign a replacement degree."
        ),
    )

    unresolved_question: str = Field(
        default="",
        description=(
            "Only a question whose resolution could change the overlap "
            "decision or establish its currently missing evidential basis. "
            "Name the contested assertion, relevant pair indices, and why "
            "the answer matters to the decision. Prioritize the conflict "
            "between the proposal and valid evidence, not an irrelevant "
            "rejected pair. Put non-blocking delta limitations in reasoning. "
            "Empty when no decision-relevant conflict remains."
        ),
    )

    reasoning: str = Field(default="")


EVIDENCE_CHECK_PROMPT = """Check whether grounded evidence supports the
specific overlap asserted by a semantic comparison of ONE claim and ONE
prior paper.

The comparison is a hypothesis, not evidence.
The quoted spans have passed source-grounding and ownership checks.
The proposed relation between two spans may still be wrong.

Perform these checks:

1. CLAIM SCOPE
Identify the actual contribution under review.
Do not use a neighboring contribution to establish overlap or preserve novelty
unless its relevance to this claim is explicitly justified.

2. PAIR VALIDITY
For each pair, judge what the quoted spans themselves establish.
A relation is supported only when both spans express the asserted shared
contribution in compatible semantic roles.
Constructing, using, evaluating, and surveying something are not interchangeable.

For empirical claims, distinguish:
- conducting a similar research activity;
- answering the same scientific question;
- establishing the same finding under comparable conditions.

Shared evaluation activity alone is not sufficient evidence of shared findings.
Different conditions may support a narrower overlap; explain the limitation.
Apply equivalent reasoning to methodological, theoretical, resource, and other
contribution types.

3. SUPPORT FOR THE PROPOSED RATIONALE
Check the specific assertion in "What is shared" and the assessment.
Evidence for another component does not automatically support that assertion.
If a different substantive overlap is evidenced within the current claim,
identify it, but do not silently substitute it for the proposed rationale.

4. SUPPORT FOR THE PROPOSED DEGREE
For proposed partial, substantial, or same, assess whether the valid evidence
justifies the proposed rationale at that degree:

partial:
    A meaningful part of the current contribution is already delivered.
    The overlap must be more than a shared topic or generic research activity.

substantial:
    The evidence reaches the central contribution of the current claim.
    A match on a subordinate component alone is not sufficient.

same:
    The evidence supports equivalence of the current claimed contribution
    in its scientifically relevant content and scope.

Use scientific relevance, not the number of pairs or matched phrases.
Do not require every detail to match for partial or substantial overlap.
Do not assign a replacement degree.

A different dataset, implementation, or experimental setting does not by itself
establish a scientifically meaningful residual contribution. Conversely, a
difference can matter when it changes capabilities, assumptions, findings, or
the scope in which a result holds.

5. DISTINGUISH OVERLAP SUPPORT FROM DELTA LIMITATIONS

Correspondence pairs provide positive evidence of overlap.
They are not an exhaustive account of either paper.

Absence of a correspondence does not prove that the prior paper lacks a
component. Do not endorse such an absence claim merely because no pair
demonstrates that component.

However, an unsupported absence claim in the delta does not automatically
invalidate independently supported overlap.

Apply this decision test:
Would resolving the disputed assertion change the proposed overlap degree,
or is the assertion necessary to establish the overlap itself?

If yes:
    Identify the specific dependency in unresolved_question.
    For a material proposal, set proposed_degree_supported=false when
    the available evidence cannot resolve that decision-relevant issue.

If no:
    Do not block the overlap decision because of that assertion.
    Explain in reasoning which delta statement must remain qualified.
    Do not present the unverified difference as established novelty.

For partial overlap, evidence must establish a meaningful shared component.
It need not prove that every other component is absent from the prior paper.
If the evidence leaves a concrete ambiguity about whether the shared
contribution is central rather than partial, explain that ambiguity.
Do not invent such an ambiguity solely because the pairs are non-exhaustive.

For substantial or same, a subordinate match is insufficient to establish
the proposed degree. Missing evidence about centrality or relevant scope
can therefore remain a blocking issue.

When the comparison proposes none/superficial but valid pairs establish
material overlap, the unresolved question must address why that demonstrated
contribution overlap is being treated as nonmaterial.

A rejected pair is not automatically a reason to repeat the comparison.
If other valid pairs independently support the decision, identify the
rejected pair in reasoning without making it the repair target.
It becomes blocking only if the decision depends on its assertion.

Return:

status:
    material: at least one valid pair establishes substantive overlap within
              the current claim.
    nonmaterial: the pairs establish only non-substantive relationships.
    insufficient: available evidence does not permit a reliable determination.

supporting_pair_indices:
    All 1-based indices of valid material pairs.
    Empty for nonmaterial or insufficient.

proposed_degree_supported:
    For proposed partial/substantial/same, true when the valid evidence
    supports the decision-relevant overlap assertion at that degree.
    False when its evidential basis or a decision-relevant scope issue
    remains unresolved.
    Do not set false solely because a nonessential delta statement is
    unsupported or an unused candidate pair is invalid.
    For proposed none/superficial, return null.

unresolved_question:
    State only a decision-relevant conflict.
    Identify the contested assertion and relevant pair indices.
    Explain how resolving it would affect the overlap decision.
    For none/superficial contradicted by material evidence, address that
    contradiction directly.
    Do not request evidence merely to prove all remaining differences absent.
    Do not assume that additional reading is necessary.
    Empty when no decision-relevant conflict remains.

reasoning:
    Explain what the valid pairs establish and what they do not establish.
    Identify rejected pairs and non-blocking limitations separately.
    Explicitly qualify unsupported delta assertions; do not certify residual
    novelty from missing correspondence pairs.

## Current claim
{claim}

## Proposed semantic comparison
{comparison}

## Grounded pairs
{pairs}
"""

def check_evidence(
    struct_call: Callable,
    claim_str: str,
    mapping: dict,
    comparison: Optional[dict] = None,
) -> dict:
    comparison = comparison or {}
    pairs = mapping.get("pairs") or []

    proposed_degree = (
        comparison.get("overlap_degree") or ""
    ).lower()

    material_proposal = proposed_degree in {
        "partial",
        "substantial",
        "same",
    }

    def unresolved(reason):
        return {
            "status": "insufficient",
            "supporting_pair_indices": [],
            "reasoning": reason,
            "proposed_degree_supported": (
                False if material_proposal else None
            ),
            "unresolved_question": reason,
        }

    if not pairs:
        return unresolved(
            "No grounded ownership-verified pair supports the proposed overlap. "
            "Check the specific shared contribution in the comparison against "
            "the source passages; do not substitute a different contribution."
        )

    parsed = struct_call(
        EvidenceCheck,
        EVIDENCE_CHECK_PROMPT.format(
            claim=claim_str,
            comparison=_fmt_comparison(comparison),
            pairs=_list_pairs(pairs),
        ),
    )

    if parsed is None:
        return unresolved("The evidence check did not complete.")

    status = (parsed.status or "").strip().lower()

    if status not in {"material", "nonmaterial", "insufficient"}:
        status = "insufficient"

    indices = sorted({
        i
        for i in (parsed.supporting_pair_indices or [])
        if type(i) is int and 1 <= i <= len(pairs)
    })

    if status == "material" and not indices:
        status = "insufficient"

    if status != "material":
        indices = []

    degree_supported = parsed.proposed_degree_supported

    if material_proposal:
        degree_supported = (
            degree_supported is True
            and status == "material"
            and bool(indices)
        )
    else:
        degree_supported = None

    question = (parsed.unresolved_question or "").strip()

    if material_proposal and not degree_supported and not question:
        question = (
            "Which grounded correspondence supports the specific shared "
            "contribution and the proposed overlap degree? Reassess the "
            "comparison if the existing evidence supports only a narrower claim."
        )

    return {
        "status": status,
        "supporting_pair_indices": indices,
        "reasoning": (parsed.reasoning or "").strip(),
        "proposed_degree_supported": degree_supported,
        "unresolved_question": question,
    }
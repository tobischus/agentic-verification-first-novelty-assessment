#!/usr/bin/env python3
"""
A claim as a set of atomic required elements, and what each prior paper discloses of them.

Today a comparison ends in one scalar per (claim, paper): `overlap_degree`. It cannot say
WHICH part of the contribution is already taken, which is the one thing a reviewer needs --
"substantial overlap" over a claim that promises a benchmark, two corpora, an ontology,
four task types and stage-wise metrics leaves them to work out for themselves which of the
five is contested.

So the claim is split into the features that must ALL hold for it to be new, and each prior
paper is scored feature by feature. What comes out is a map: element x paper, every filled
cell carrying a verbatim span from that paper.

Two things keep this honest.

**Both sides are quoted.** An element's `text` is written by the model and is therefore not
evidence; each element also carries `claim_quote`, a verbatim span of the submission that
states it. A cell then pairs that with a verbatim span of the prior paper, and both are
checked against their own document by the same verifier the rest of the pipeline uses. An
element whose claim_quote does not verify is not a requirement of the paper -- it is
something the model made up -- and it is dropped.

**Core and peripheral are separated.** This is the trap in the whole approach: decompose a
claim finely enough and every claim becomes novel, because no single prior paper ever shows
all six of anything. That is an artefact of the method, not a finding. Only elements that
say what the contribution IS (method, artifact, theory) count toward anticipation; those
that say where it was demonstrated (scope, result) are recorded and shown, never scored.
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from . import evidence as ev

# What the contribution IS. Only these count toward anticipation -- see the module note.
CORE_KINDS = ("method", "artifact", "theory")


# ------------------------------- schemas ----------------------------------- #

class Element(BaseModel):
    text: str = Field(description="ONE atomic feature the claim requires, as a single short sentence")
    kind: str = Field(description="method | artifact | theory  (CORE: what the contribution IS) "
                                  "| scope | result  (PERIPHERAL: where it was demonstrated)")
    anchor: int = Field(
        description="1-based number of the submission passage below that states this "
                    "feature. Pick the passage, do not retype it.")


class Decomposition(BaseModel):
    elements: List[Element] = Field(description="3-8 atomic features THIS claim requires")


class Cell(BaseModel):
    element_index: int = Field(description="1-based index of the element this is about")
    status: str = Field(description="disclosed | partial | absent")
    paper_quote: str = Field(
        default="",
        description="VERBATIM span from THIS paper's text showing it, copied character for "
                    "character. Empty only when status is absent.")
    note: str = Field(default="", description="one short clause: what this paper does for this element")


class Coverage(BaseModel):
    cells: List[Cell] = Field(description="exactly one cell per element, in order")
    relevance: str = Field(default="", description="one sentence: what this paper is, and how it relates")


# ------------------------------- prompts ----------------------------------- #

DECOMPOSE_PROMPT = """Split ONE claimed contribution into the atomic features that must ALL hold for it to be new.

A feature is atomic when a prior paper can have it or lack it INDEPENDENTLY of the others. If a sentence of the claim joins several properties with "and", that is several features, not one. Aim for 3-8.

Name the DISTINGUISHING PROPERTY, never the category. The category is what makes a feature useless: almost every paper in the field has "a benchmark", "a framework", "an evaluation", so a feature written that way is disclosed by everything and separates nothing.

  BAD   "A benchmark artifact with graded tasks, several corpus types and pipeline evaluation."
        -- three properties in one, and the head noun is a category every rival also has.
  GOOD  "Tasks graded by required depth of synthesis, from fact retrieval to creative generation."
  GOOD  "Two corpora of deliberately contrasting information density: clinical guidelines and narrative fiction."
  GOOD  "Metrics reported separately for graph construction, retrieval and generation."

Every feature must be a feature OF THE CLAIM BELOW. The submission's own text usually describes more of the paper than this one claim asserts; anything it describes that the claim does not assert is NOT a feature here, however prominent it is in that text. Read the claim first, and use the surrounding text only to find the spans you quote.

Mark each feature's kind:
- method / artifact / theory -- what the contribution IS. These decide novelty.
- scope / result -- where it was demonstrated, on which data, with which numbers. Record these, but they never decide novelty on their own.

For EVERY feature give `anchor`: the number of the submission passage below that states it. Do not retype the passage -- point at it. If no passage states a feature, do not invent that feature.

## THE CLAIM to decompose -- the features must be features of THIS
{claim}

## Numbered passages of the submission -- `anchor` is one of these numbers
{passages}"""


COVER_PROMPT = """Decide, feature by feature, what ONE prior paper discloses of a claimed contribution.

For each numbered feature give exactly one cell:
- disclosed: this paper itself presents THAT SPECIFIC PROPERTY.
- partial: it presents a weaker, narrower or partly different version of that property.
- absent: the text below does not show it.

Belonging to the same category is NOT disclosure. A paper that has a benchmark, but not the property the feature names, is `absent` for that feature -- not `disclosed`, and not `partial`. Ask of every cell: does the quote show THIS property, or only that the paper works on the same kind of thing? If the latter, the answer is absent.

`paper_quote` must be copied VERBATIM from the paper text below -- character for character, at least 10 words -- and must state what THIS PAPER does, never what it says about work it cites. Required for disclosed and partial; leave empty for absent.

Judge only from the text below. If the text does not show a feature, that is `absent`: it means "not in what was read", not "not in the paper".

## The claimed contribution
{claim}

## Its required features
{elements}

## The prior paper: {title}
{sections}"""


# ------------------------------ operations --------------------------------- #

def decompose(struct_call, claim_str: str, passages: List[str]) -> List[dict]:
    """Elements of a claim, each anchored to a passage of the submission by REFERENCE.

    An earlier version asked the model to copy a verbatim span per element and verified it.
    That silently halved the decomposition: of six elements the model proposed, two to four
    were dropped because it could not reproduce a span character for character -- so the
    coverage score collapsed onto two elements and became almost binary. The failure was in
    asking at all. These passages are already verified against the submission, so the model
    only has to say WHICH one states a feature, and the anchor is sound by construction.

    `struct_call(schema, prompt)` is the caller's structured-output helper, so this module
    stays free of any model client.
    """
    if not passages:
        return []
    numbered = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
    parsed = struct_call(Decomposition, DECOMPOSE_PROMPT.format(
        claim=claim_str[:1500], passages=numbered[:16000]))
    if parsed is None:
        return []
    out = []
    for el in parsed.elements:
        i = (el.anchor or 0) - 1
        if not (0 <= i < len(passages)):          # points nowhere: not a stated requirement
            continue
        kind = (el.kind or "").strip().lower()
        out.append({"text": el.text.strip(), "kind": kind,
                    "claim_quote": passages[i], "anchor": i, "core": kind in CORE_KINDS})
    return out


def cover(struct_call, claim_str: str, elements: List[dict], title: str, sections_text: str,
          paper_text: str, min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0) -> dict:
    """One paper against every element, each non-absent cell carrying a verified quote.

    A cell whose quote does not verify is demoted to `unsupported` rather than kept at its
    claimed status. That is the whole point of the exercise: a coverage matrix whose cells
    are model assertions would be a worse artifact than the scalar it replaces, because it
    looks precise.
    """
    numbered = "\n".join(
        f"{i + 1}. [{el['kind']}] {el['text']}" for i, el in enumerate(elements))
    parsed = struct_call(Coverage, COVER_PROMPT.format(
        claim=claim_str[:1200], elements=numbered, title=title, sections=sections_text))
    if parsed is None:
        return {"cells": [], "relevance": ""}

    by_index = {}
    for c in parsed.cells:
        i = (c.element_index or 0) - 1
        if not (0 <= i < len(elements)) or i in by_index:
            continue
        status = (c.status or "absent").strip().lower()
        quote, verified = (c.paper_quote or "").strip(), False
        if status in ("disclosed", "partial") and quote:
            chk = ev.verify_quote(quote, paper_text, min_quote_tokens, fuzzy_threshold)
            verified = chk.verified
            if verified:
                quote = ev.expand_to_sentence(quote, paper_text)
        if status in ("disclosed", "partial") and not verified:
            status = "unsupported"          # claimed, but nothing in the paper backs it
        by_index[i] = {"element_index": i, "status": status, "paper_quote": quote if verified else "",
                       "quote_verified": verified, "note": (c.note or "").strip()}

    cells = [by_index.get(i, {"element_index": i, "status": "absent", "paper_quote": "",
                              "quote_verified": False, "note": ""})
             for i in range(len(elements))]
    return {"cells": cells, "relevance": (parsed.relevance or "").strip()}


# ------------------------------- scoring ----------------------------------- #

_WEIGHT = {"disclosed": 1.0, "partial": 0.5}


def coverage_score(elements: List[dict], cells: List[dict]) -> Optional[float]:
    """Share of the CORE elements this paper discloses, partials at half weight.

    None when the claim has no core element at all, which means the decomposition found
    nothing that says what the contribution is -- a result to report, not to score.
    """
    core = [i for i, el in enumerate(elements) if el["core"]]
    if not core:
        return None
    return sum(_WEIGHT.get(cells[i]["status"], 0.0) for i in core) / len(core)


def degree_from_coverage(score: Optional[float], n_core: int) -> str:
    """The existing overlap vocabulary, derived from the matrix rather than asserted.

    The bands are set against ONE core element rather than at fixed cut-points: with three
    core elements a single disclosed one is 0.33 and must not read the same as 0.33 out of
    nine. `same` demands every core element; `substantial` demands more than half; anything
    non-zero is at least `partial`, because a reviewer wants to see a paper that takes even
    one required feature.
    """
    if score is None:
        return "none"
    cell = 1.0 / max(1, n_core)
    if score >= 0.999:
        # `same` is single-reference anticipation and must not rest on one cell: with one
        # core element the score is binary, and one coarse feature matching would announce
        # that a paper published the whole contribution.
        return "same" if n_core >= 2 else "substantial"
    if score >= 0.5 + cell / 2:
        return "substantial"
    if score > 0.0:
        return "partial"
    return "none"


# ======================================================================== #
# Free comparison: the model decides the shape, the verifier checks it     #
# ======================================================================== #
#
# The decomposition above imposes a grid: split the claim into N features, then answer N
# questions per paper. That guarantees an answer for every cell whether or not the cell is
# a real question, and it makes the model manufacture distinctions -- on one claim it split
# "a benchmark with graded tasks" into a peripheral element and a core element with the
# same anchor, because the schema asked for more parts than the claim has.
#
# So here the model is asked what it would say anyway: where do these two actually meet?
# It returns as many points of contact as it finds, possibly none, each one carrying the
# evidence for itself. Nothing forces a point to exist and nothing caps how many there are.
#
# The invariant does not move. What the model may decide is WHAT to report; whether the
# report is grounded is still settled by the verifier, against the two documents, outside
# the model. Reasoning chooses the shape; verification keeps it honest.


def sentences_of(passages: List[str], min_words: int = 8) -> List[str]:
    """Verified passages cut into sentences, so an anchor can point at a claim, not a page.

    Anchoring at paragraph granularity degenerates: given four contacts and one passage that
    mentions the benchmark, the model anchored all four to that passage, and the anchor then
    said nothing about WHICH part of the claim each contact touched. A sentence taken from a
    span already verified against the submission is itself in the submission, so nothing is
    given up by cutting them.
    """
    import re
    out = []
    for para in passages:
        text = " ".join((para or "").split())
        # Sentence ends first, then the enumerations papers write inside one sentence.
        # A single run-on listing every part of a contribution -- "features (i) tasks of
        # increasing difficulty ... and (ii) real-world corpora ..." -- otherwise becomes a
        # catch-all every contact anchors to, which is the failure this splitting exists to
        # prevent.
        parts = re.split(r"(?<=[.!?])\s+", text)
        parts = [q for part in parts
                 for q in re.split(r"\s*(?:,\s*)?(?:and\s+)?(?:\(\s*(?:i{1,3}|iv|v|vi{0,3})\s*\)"
                                   r"|[❶-❿①-⑳])\s*", part)]
        parts = [q for part in parts for q in re.split(r"\s*;\s*", part)]
        for sent in parts:
            sent = sent.strip(" ,;")
            if len(sent.split()) >= min_words:
                out.append(sent)
    return out


class ContactPoint(BaseModel):
    what_is_shared: str = Field(
        description="ONE specific sentence: the concrete thing both the claim and this "
                    "paper deliver. Not the topic they share -- the thing.")
    submission_sentence: int = Field(
        description="1-based number of the ONE submission sentence below that states the "
                    "claim side of this contact. Point at it, do not retype it. Two "
                    "contacts must not point at the same sentence -- if they would, they "
                    "are one contact.")
    paper_quote: str = Field(
        description="VERBATIM span from the paper text below showing the paper's side, "
                    "copied character for character, at least 10 words")
    strength: str = Field(
        description="full  (the paper delivers this outright)  |  "
                    "weaker  (narrower, partial, or a special case)")


class FreeComparison(BaseModel):
    reasoning: str = Field(description="2-4 sentences: how you weighed this paper against the claim")
    contacts: List[ContactPoint] = Field(
        default_factory=list,
        description="EVERY point where the two genuinely meet -- a complete list, not a "
                    "selection; empty only if they do not meet at all")
    submission_delta: str = Field(description="what the claim delivers that this paper does not")
    degree: str = Field(description="same | substantial | partial | superficial | none")


FREE_PROMPT = """Judge how far ONE prior paper anticipates ONE claimed contribution.

Work it out as a reviewer would. Read the claim, read what the paper actually does, and decide where the two genuinely meet. Do not manufacture a point to fill space, and do not compress two real ones into one.

Report EVERY point you can support from the text below -- this is a complete list, not a selection of the best ones. Two reviewers given the same two papers should arrive at the same list, so do not stop early because the picture is already clear: a point you leave out is one the next reader has to find again. Where several passages support the same point, that is still ONE point; pick the passage that shows it most directly.

A point of contact is a CONCRETE thing both deliver AS THEIR CONTRIBUTION: the same construction, the same artifact, the same property. Working on the same topic is not a point of contact. Neither is using the same standard machinery -- both building a knowledge graph, both retrieving passages, both calling an LLM -- when the claimed contribution is something else entirely.

Most papers retrieved for a claim share its field and not its contribution. `superficial` is therefore the ordinary answer, not a rare one, and reporting no contacts at all is a normal outcome you should reach often. A list of contacts that could be written about almost any paper in the area is a sign you have described the field rather than the overlap.

Evidence for every point:
- `submission_sentence`: the number of the ONE sentence below that states the claim's side. Point at it. If two of your contacts would point at the same sentence, they are the same contact -- merge them.
- `paper_quote`: ONE CONTIGUOUS span copied VERBATIM from the paper text below, character for character, at least 10 words, stating what THIS PAPER does -- never what it says about work it cites. Do not join separate parts of the text with "..." or any other gap: a stitched quote appears nowhere in the paper and cannot be checked. If one span does not cover the point, pick the single most telling one.

`degree` follows from the points you found and how much of the claim they leave standing:
- same / substantial: this paper by itself delivers most or all of the claimed contribution.
- partial: it delivers a real part, and the claim clearly adds beyond it.
- superficial: same area, different contribution.
- none: unrelated to what is claimed.

Judge only from the text below. If it does not show something, that is not evidence that the paper lacks it -- say so in the reasoning rather than counting it against the paper.

## The claim
{claim}

## Numbered sentences of the submission -- `submission_sentence` is one of these numbers
{passages}

## The prior paper: {title}
{sections}"""


def _verify_span(quote: str, paper_text: str, min_quote_tokens: int, fuzzy_threshold: float):
    """Verify a quote, salvaging the longest real fragment if the model stitched one.

    Models join distant parts of a paper with an ellipsis to show more in one quote. Every
    fragment is genuine; the concatenation is in no document, so it fails verification and
    a sound point of contact is lost with it. Rather than discard the point, the fragments
    are checked separately and the longest one that holds is kept -- an unbroken span the
    reviewer can find. The prompt asks for a contiguous span in the first place; this is
    what happens when it is not obeyed.
    """
    q = (quote or "").strip()
    chk = ev.verify_quote(q, paper_text, min_quote_tokens, fuzzy_threshold)
    if chk.verified:
        return chk, ev.expand_to_sentence(q, paper_text)
    import re
    parts = [x.strip() for x in re.split(r"\s*(?:\.\s*){3,}\s*|\s*…\s*", q) if x.strip()]
    if len(parts) > 1:
        for frag in sorted(parts, key=lambda x: -len(x)):
            c2 = ev.verify_quote(frag, paper_text, min_quote_tokens, fuzzy_threshold)
            if c2.verified:
                return c2, ev.expand_to_sentence(frag, paper_text)
    return chk, q


def compare_free(struct_call, claim_str: str, passages: List[str], title: str,
                 sections_text: str, paper_text: str,
                 min_quote_tokens: int = 10, fuzzy_threshold: float = 90.0) -> dict:
    """One paper against one claim, shaped by the model, grounded by the verifier.

    A contact whose paper_quote cannot be found in the paper is kept but marked, never
    silently dropped: that the model asserted it is itself part of what a reviewer should
    see, and hiding it would make the output look cleaner than the evidence warrants.
    """
    numbered = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
    parsed = struct_call(FreeComparison, FREE_PROMPT.format(
        claim=claim_str[:1500], passages=numbered[:12000], title=title, sections=sections_text))
    if parsed is None:
        return {"contacts": [], "degree": "", "reasoning": "", "submission_delta": ""}

    contacts = []
    for c in parsed.contacts:
        i = (c.submission_sentence or 0) - 1
        anchor = passages[i] if 0 <= i < len(passages) else ""
        chk, quote = _verify_span(c.paper_quote, paper_text, min_quote_tokens, fuzzy_threshold)
        contacts.append({
            "what_is_shared": (c.what_is_shared or "").strip(),
            "strength": (c.strength or "").strip().lower(),
            "claim_quote": anchor,
            "claim_anchored": bool(anchor),
            "paper_quote": quote,
            "paper_quote_verified": chk.verified,
            "grounded": bool(anchor) and chk.verified,
        })
    # Cap the degree at what the grounded contacts can carry. Across 37 comparisons the
    # model never once returned `superficial` or `none`, so everything it examined entered
    # the reviewer's overlap list -- the same over-inclusion this design set out to fix,
    # moved one stage later. The prompt now says superficial is the ordinary answer; these
    # two rules only refuse a verdict the evidence does not reach, and deliberately no more.
    # A third rule -- capping a single weaker contact at superficial -- was tried and
    # removed: it demoted a genuine substantial overlap on the strength of a count.
    degree = (parsed.degree or "").strip().lower()
    grounded = [c for c in contacts if c["grounded"]]
    full = [c for c in grounded if c["strength"].startswith("full")]
    if not grounded:
        degree = "none" if not contacts else "superficial"
    elif not full and degree in ("same", "substantial"):
        degree = "partial"          # only weaker contacts cannot carry anticipation

    return {
        "reasoning": (parsed.reasoning or "").strip(),
        "contacts": contacts,
        "submission_delta": (parsed.submission_delta or "").strip(),
        "degree": degree,
    }

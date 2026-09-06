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

#!/usr/bin/env python3
"""
The one place where a comparison becomes a judgement.

Artifact A records, for each (claim, prior paper) pair, how much the paper overlaps the
claim and whether it can refute it. Turning those records into what a reader finally sees
-- which papers are listed as overlapping, in which order, under which label -- is a rule,
and that rule had been written out separately in every module that needed it: the export,
the synthesis, the API, and twice in the frontend. Nothing forced the copies to agree, and
they had already started to drift (the API's rank table was missing two of the five
degrees).

That matters beyond tidiness. The agent and the linear baseline are meant to differ in ONE
respect -- which papers they choose to examine and how deeply -- so that any difference in
their output is attributable to that choice. A rule that lives in four places is a second
way for them to differ, and a silent one. Keeping it here makes "same rules, different
policy" true by construction rather than by coincidence, and gives the thesis one function
to describe instead of four copies to reconcile.

What is NOT here yet: the per-claim verdict itself. Today it is produced by the model in
Artifact B, not derived from the evidence by a rule, so there is nothing deterministic to
move. This module is where that rule belongs once it exists.
"""
from typing import Iterable, List

# --------------------------------------------------------------- the rule --
# How much of the claimed contribution a prior paper delivers. Recorded per comparison by
# the model; these are the only values it may emit.
DEGREES = ("same", "substantial", "partial", "superficial", "none")

# The degrees that count as "this prior work overlaps the claim" and put the paper in front
# of the reader. `superficial` means same topic, different contribution -- deliberately not
# an overlap, because listing topical neighbours as overlapping prior work is what makes a
# novelty report unreadable.
OVERLAP_DEGREES = ("same", "substantial", "partial")

# Lower is stronger. Used to order the overlap list and to pick a paper's strongest overlap
# across several claims. Degrees outside the table (an older artifact that recorded none)
# sort last.
DEGREE_RANK = {"same": 0, "substantial": 1, "partial": 2, "superficial": 3, "none": 4}
UNRANKED = 9

DEGREE_LABEL = {
    "same": "same contribution", "substantial": "substantial overlap",
    "partial": "partial overlap", "superficial": "no overlap", "none": "no overlap",
}

VERDICT_LABEL = {
    "challenged": "challenged by prior work",
    "not_challenged": "not challenged in the examined literature",
    "uncertain": "uncertain",
}


# ------------------------------------------------------------- predicates --
def degree(comparison: dict) -> str:
    """The comparison's overlap degree, normalised. Missing or unset reads as ""."""
    return (comparison.get("overlap_degree") or "").lower()


def challenges(comparison: dict) -> bool:
    """Whether this paper was found to refute the claim.

    The evidence-grounding invariant is enforced upstream: a `can_refute` that carries no
    both-sides-verified quote pair has already been downgraded by the time it is written to
    Artifact A, so this reads a decision rather than making one.
    """
    return comparison.get("refutation_status") == "can_refute"


def is_overlap(comparison: dict) -> bool:
    """Whether this comparison belongs in front of the reader as overlapping prior work.

    A refuting paper qualifies whatever its degree says: the two fields are written by
    different steps, and a refutation with a weak or missing degree is still a refutation.
    """
    return challenges(comparison) or degree(comparison) in OVERLAP_DEGREES


def overlapping(comparisons: Iterable[dict]) -> List[dict]:
    """The overlapping comparisons, in the order they were recorded."""
    return [c for c in (comparisons or []) if is_overlap(c)]


def evidence_status(comparison: dict) -> str:
    """The evidence check's own verdict on this comparison, normalised; "" if none ran."""
    return str(((comparison or {}).get("evidence_check") or {}).get("status") or "").strip().lower()


def degree_confirmed(comparison: dict) -> bool:
    """Whether the evidence check confirmed the overlap the comparison proposed.

    The check answers TWO questions and a summary that merges them misreports the record:
    `status == "material"` says the stored pairs establish a substantive shared element,
    while `proposed_degree_supported` says whether that element carries the overlap AT THE
    PROPOSED DEGREE for this claim. A comparison can be the first without being the second
    -- the check then names what is missing in `unresolved_question` -- and showing it as
    an established overlap claims more than was found.

    For a proposed none/superficial the field is null by construction (check_evidence
    normalises it), so this is False there: those propose no overlap to confirm. Callers
    that want "a shared element was found at all", irrespective of degree, should test
    `evidence_status(c) == "material"` instead -- the two are deliberately separate, and
    the gap between them is exactly what must not be summarised away.
    """
    return (evidence_status(comparison) == "material"
            and ((comparison or {}).get("evidence_check") or {})
            .get("proposed_degree_supported") is True)


def conflicts(comparison: dict) -> bool:
    """Whether the proposed degree and the evidence check disagree about this comparison.

    Two independent steps write these fields: the comparison proposes how much of the
    claim the prior paper delivers, the evidence check rules on whether stored passages
    actually carry that. Either can contradict the other and neither silently wins -- the
    reader is shown both halves. This predicate is what makes such a pair findable: the
    export keeps every conflicting comparison inspectable even when its degree alone would
    not qualify, and the paper-level synthesis lists them as decision-relevant, precisely
    so a proposed `substantial` without material evidence is never summarised as an
    established overlap.
    """
    overlap = degree(comparison) in OVERLAP_DEGREES
    status = evidence_status(comparison)
    return (overlap and status == "nonmaterial") or (not overlap and status == "material")


# ---------------------------------------------------------------- ordering --
def degree_rank(deg: str) -> int:
    return DEGREE_RANK.get((deg or "").lower(), UNRANKED)


def sort_key(comparison: dict):
    """Refuting papers first, then by decreasing strength of overlap."""
    return (not challenges(comparison), degree_rank(degree(comparison)))


# ------------------------------------------------------------------ labels --
def degree_label(deg: str) -> str:
    """Reader-facing wording for a degree; unknown values are passed through unchanged."""
    d = (deg or "").lower()
    return DEGREE_LABEL.get(d, deg)


def overlap_label(deg: str) -> str:
    """As `degree_label`, but blank unless the degree actually counts as an overlap --
    for lists where a non-overlapping degree should carry no annotation at all."""
    d = (deg or "").lower()
    return DEGREE_LABEL.get(d, deg) if d in OVERLAP_DEGREES else ""


def verdict_label(v: str) -> str:
    return VERDICT_LABEL.get(v, v)

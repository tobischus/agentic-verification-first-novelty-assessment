"""Turns a comparison into a judgement."""

OVERLAP_DEGREES = ("same", "substantial", "partial")

DEGREE_RANK = {"same": 0, "substantial": 1, "partial": 2, "superficial": 3, "none": 4}
UNRANKED = 9

DEGREE_LABEL = {
    "same": "same contribution",
    "substantial": "substantial overlap",
    "partial": "partial overlap",
    "superficial": "no overlap",
    "none": "no overlap",
}

VERDICT_LABEL = {
    "challenged": "challenged by prior work",
    "not_challenged": "not challenged in the examined literature",
    "uncertain": "uncertain",
}


def degree(comparison: dict) -> str:
    """The comparison's overlap degree, normalised. Missing or unset reads as ""."""
    return (comparison.get("overlap_degree") or "").lower()


def challenges(comparison: dict) -> bool:
    """Whether this paper was found to refute the claim."""
    return comparison.get("refutation_status") == "can_refute"


def is_overlap(comparison: dict) -> bool:
    """Whether this comparison belongs in front of the reader as overlapping prior work."""
    return challenges(comparison) or degree(comparison) in OVERLAP_DEGREES


def evidence_status(comparison: dict) -> str:
    """The evidence check's own verdict on this comparison, normalised; "" if none ran."""
    return str(((comparison or {}).get("evidence_check") or {}).get("status") or "").strip().lower()


def degree_confirmed(comparison: dict) -> bool:
    """Whether the evidence check confirmed the overlap the comparison proposed."""
    return (
        evidence_status(comparison) == "material"
        and ((comparison or {}).get("evidence_check") or {}).get("proposed_degree_supported")
        is True
    )


def conflicts(comparison: dict) -> bool:
    """Whether the proposed degree and the evidence check disagree about this comparison."""
    overlap = degree(comparison) in OVERLAP_DEGREES
    status = evidence_status(comparison)
    return (overlap and status == "nonmaterial") or (not overlap and status == "material")


def degree_rank(deg: str) -> int:
    return DEGREE_RANK.get((deg or "").lower(), UNRANKED)


def sort_key(comparison: dict):
    """Refuting papers first, then by decreasing strength of overlap."""
    return (not challenges(comparison), degree_rank(degree(comparison)))


def overlap_label(deg: str) -> str:
    """The degree label, blank unless the degree counts as an overlap."""
    d = (deg or "").lower()
    return DEGREE_LABEL.get(d, deg) if d in OVERLAP_DEGREES else ""


def verdict_label(v: str) -> str:
    return VERDICT_LABEL.get(v, v)

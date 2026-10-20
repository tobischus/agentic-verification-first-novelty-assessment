#!/usr/bin/env python3
"""The short id ("R7") a prior paper carries throughout one report.

The reviewer export, the paper-level synthesis and both frontends name prior work by these
ids, and they have to agree: a summary that cites R7 while the table below calls that same
paper R9 sends the reader to the wrong comparison, and does it invisibly. So the assignment
lives here instead of inside whichever module happened to need it first.

Deterministic and independent of the order comparisons happen to be recorded in: papers are
sorted by title (case-insensitively), ties broken by their own id, and numbered R1, R2, …
in that order. Callers pass the SAME claim order they display, so two callers reading the
same artifact cannot disagree.
"""
from typing import Iterable, Optional


def paper_id(comparison: dict) -> str:
    """The key a comparison is filed under. Mirrors battle_export._pid exactly."""
    return str(comparison.get("paper_id") or comparison.get("title") or "unidentified source")


def titles(artifact_a: dict, claim_order: Optional[Iterable[str]] = None) -> dict:
    """{paper_id: title}, taking the first title recorded for each paper.

    `claim_order` is the order the claims are presented in (the claims document's order,
    which is what the export walks). It matters only in the rare case where two claims
    recorded different titles for the same paper: then "first" has to mean the same thing
    for every caller. Pass None to use the artifact's own order.
    """
    entries = (artifact_a or {}).get("claims", []) or []
    if claim_order is not None:
        by_id = {e.get("claim_id"): e for e in entries}
        entries = [by_id[cid] for cid in claim_order if cid in by_id]
    out = {}
    for entry in entries:
        for c in entry.get("comparisons", []) or []:
            pid = paper_id(c)
            out.setdefault(pid, c.get("title") or pid)
    return out


def order_from_titles(title_map: dict) -> list:
    return sorted(title_map, key=lambda p: (str(title_map[p]).casefold(), p))


def assign_from_titles(title_map: dict) -> dict:
    """{paper_id: "R#"} from an already-built {paper_id: title} map."""
    return {pid: f"R{i}" for i, pid in enumerate(order_from_titles(title_map), 1)}


def refs_for(artifact_a: dict, claim_order: Optional[Iterable[str]] = None) -> dict:
    """{paper_id: "R#"} for every prior paper any claim was compared against."""
    return assign_from_titles(titles(artifact_a, claim_order))

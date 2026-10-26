"""The short id ("R7") a prior paper carries throughout one report."""

from pathlib import Path
from typing import Iterable, Optional


def variant_path(sub_dir: Path, submission_id: str, kind: str, variant: str = "") -> Path:
    """{id}_{kind}.json, or {id}_{kind}_{variant}.json for the agent and linear variants."""
    tail = f"_{variant}" if variant else ""
    return sub_dir / f"{submission_id}_{kind}{tail}.json"


def paper_id(comparison: dict) -> str:
    """The key a comparison is filed under, as in battle_export._pid."""
    return str(comparison.get("paper_id") or comparison.get("title") or "unidentified source")


def titles(artifact_a: dict, claim_order: Optional[Iterable[str]] = None) -> dict:
    """{paper_id: title}, taking the first title recorded for each paper."""
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

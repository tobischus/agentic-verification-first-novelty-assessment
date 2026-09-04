#!/usr/bin/env python3
"""
The system's final output as plain text -- the artifact that goes into the comparison
against other novelty assessment systems.

Nothing here is generated. Every line is copied from artifacts that already exist:
the overall assessment and per-claim verdicts from Artifact B, and the claim text,
the submission's own realization and the per-paper comparisons from Artifact A.
Rendering the deliverable from a template rather than from a model call is what makes
it reproducible: running this twice on the same run yields byte-identical text.

Verbatim quotations are rendered as blockquotes ("> ") and everything else as plain
prose, so the two are distinguishable without a legend. A quote is only marked as such
when its verification flag says it was found in the source document; a quote the checker
could not confirm is demoted to prose rather than presented as quoted evidence.

Deliberately omitted, because they are reader aids rather than content: the checkmarks,
the "quote appears verbatim" legend, and the list of sections read for a comparison.

Usage
-----
  python src/novelty_assessment/battle_export.py --data-dir data --submission-id ID
  python src/novelty_assessment/battle_export.py --data-dir data --submission-id ID \
      --out battle/ID.md
"""
import argparse
import json
from pathlib import Path
from typing import List, Optional

_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
             "Eighth", "Ninth", "Tenth"]

_DEGREE_LABEL = {
    "same": "same contribution", "substantial": "substantial overlap",
    "partial": "partial overlap", "superficial": "no overlap", "none": "no overlap",
}
_VERDICT_LABEL = {
    "challenged": "challenged by prior work",
    "not_challenged": "not challenged in the examined literature",
    "uncertain": "uncertain",
}
# Which prior work counts as overlapping this claim -- the same rule the review UI and
# artifact_b use, so all three show the same set of papers.
_OVERLAP_DEGREES = ("same", "substantial", "partial")


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ordinal(i: int) -> str:
    return f"{_ORDINALS[i]} extracted claim" if i < len(_ORDINALS) else f"Extracted claim {i + 1}"


def _cite(authors: str, year) -> str:
    names = [n.strip() for n in (authors or "").split(",") if n.strip()]
    cite = ""
    if names:
        surname = names[0].split()[-1] if names[0].split() else names[0]
        cite = f"{surname} et al." if len(names) > 1 else names[0]
    return " · ".join(x for x in (cite, str(year or "")) if x)


def _segments(segs, out: List[str]) -> None:
    """Prose as paragraphs, verified verbatim spans as blockquotes."""
    for s in segs or []:
        content = (s.get("content") or "").strip()
        if not content:
            continue
        if s.get("kind") == "quote" and s.get("verified"):
            out.append("> " + content.replace("\n", "\n> "))
        else:
            out.append(content)
        out.append("")


def build(data_dir: str, submission_id: str) -> str:
    sub = Path(data_dir) / submission_id
    a = _load(sub / f"{submission_id}_artifact_a.json")
    if a is None:
        raise FileNotFoundError(f"{submission_id}_artifact_a.json not found")
    b = _load(sub / f"{submission_id}_artifact_b.json") or {}
    meta = _load(sub / f"{submission_id}.json") or {}
    claims_doc = _load(sub / f"{submission_id}_claims.json") or {"claims": []}
    ranked = _load(sub / "related_work_data" / "ranked_papers.json") or []
    pool = {p.get("paper_id"): p for p in ranked}

    order = [c["id"] for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    b_by = {v.get("claim_id"): v for v in b.get("per_claim", [])}
    if not order:                     # claims file gone or rewritten: fall back to A's order
        order = [e.get("claim_id") for e in a.get("claims", [])]

    out: List[str] = ["# Novelty Assessment"]
    title = meta.get("title") or claims_doc.get("title") or ""
    if title:
        out.append(title)
    out.append("")

    if b.get("overall_assessment"):
        out += ["## Overall assessment", "", b["overall_assessment"].strip(), ""]

    n = 0
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        v = b_by.get(cid) or {}
        out.append("---")
        out.append("")
        out.append(f"## {_ordinal(n)}")
        out.append("")
        out.append((e.get("claim_text") or e.get("claim_name") or "").strip())
        out.append("")
        n += 1

        if v.get("verdict"):
            out += [f"**Verdict:** {_VERDICT_LABEL.get(v['verdict'], v['verdict'])}", ""]
        if v.get("rationale"):
            out += [v["rationale"].strip(), ""]

        real = e.get("claim_realization") or []
        if real:
            out += ["### What the submission does for this claim", ""]
            _segments(real, out)

        overlaps = [c for c in (e.get("comparisons") or [])
                    if c.get("refutation_status") == "can_refute"
                    or (c.get("overlap_degree") or "").lower() in _OVERLAP_DEGREES]
        if not overlaps:
            out += ["### Overlapping prior work", "",
                    f"None found among the {len(e.get('comparisons') or [])} papers compared.", ""]
            continue

        out += ["### Overlapping prior work", ""]
        for c in overlaps:
            pm = pool.get(c.get("paper_id"), {})
            out.append(f"#### {c.get('title', '')}")
            deg = (c.get("overlap_degree") or "").lower()
            head = [_DEGREE_LABEL.get(deg, deg)] if deg else []
            cite = _cite(c.get("authors") or pm.get("authors", ""), c.get("year") or pm.get("year"))
            if cite:
                head.append(cite)
            if head:
                out += [" · ".join(head), ""]

            pr = c.get("paper_realization") or []
            if pr:
                out += ["How this paper realizes the claim", ""]
                _segments(pr, out)
            if c.get("assessment"):
                out += ["Comparison with the submission", "", c["assessment"].strip(), ""]
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="Render the final assessment as plain text")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--out", default=None, help="write here instead of stdout")
    args = ap.parse_args()
    text = build(args.data_dir, args.submission_id)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"written: {p}  ({len(text)} chars)")
    else:
        print(text)


if __name__ == "__main__":
    main()

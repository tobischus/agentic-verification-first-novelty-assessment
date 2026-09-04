#!/usr/bin/env python3
"""
Give Afzal et al.'s assessment stage the inputs it expects, produced by this pipeline.

Their pipeline reads a paper's introduction from `introductions/{id}_intro.txt`, written by
their `extract_introductions.py` out of Nougat MMD files. This tree parses with GROBID and
stores sections instead, so those files never exist and their step 6 cannot start.

This writes them from the GROBID output. That is a deliberate choice about WHAT is being
compared: both systems then work from the same documents, the same retrieved pool and the
same preprocessing, so a difference in the assessment is a difference between the assessment
methods rather than between two OCR stacks. It is therefore an assessment-stage comparison
("their method on our inputs"), not an end-to-end system comparison, and has to be reported
as such.

Usage
-----
  python eval/afzal_adapter.py --data-dir data --submission-id ID
"""
import argparse
import json
import re
from pathlib import Path

# GROBID section titles that begin a paper's introduction. Matched case-insensitively
# against the whole title, with optional leading numbering.
_INTRO_TITLE = re.compile(r"^\s*(?:[IVX0-9]+[.\s)]*)?(introduction|background)\b", re.I)


def _from_sections(sections, max_chars: int) -> str:
    """Text of the first introduction-like section (falls back to the first section)."""
    for sec in sections or []:
        if _INTRO_TITLE.match((sec.get("section") or "").strip()):
            text = (sec.get("text") or "").strip()
            if text:
                return text[:max_chars]
    for sec in sections or []:                       # no such heading: take the opening body
        text = (sec.get("text") or "").strip()
        if text:
            return text[:max_chars]
    return ""


def _from_markdown(text: str, max_chars: int) -> str:
    """Introduction out of a '## Heading'-delimited GROBID dump."""
    blocks = re.split(r"^##\s*(.+)$", text, flags=re.M)
    # re.split with one group yields [pre, title, body, title, body, ...]
    for i in range(1, len(blocks) - 1, 2):
        if _INTRO_TITLE.match(blocks[i].strip()):
            body = blocks[i + 1].strip()
            if body:
                return body[:max_chars]
    for i in range(1, len(blocks) - 1, 2):           # else the first non-abstract section
        if not blocks[i].strip().lower().startswith("abstract"):
            body = blocks[i + 1].strip()
            if body:
                return body[:max_chars]
    return text[:max_chars]


def build(data_dir: str, submission_id: str, max_chars: int = 20000) -> dict:
    sub = Path(data_dir) / submission_id
    out_dir = sub / "introductions"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"submission": False, "papers_written": 0, "papers_missing_fulltext": 0}

    ft = sub / f"{submission_id}_fulltext.json"
    if ft.exists():
        intro = _from_sections(json.loads(ft.read_text(encoding="utf-8")).get("sections"), max_chars)
        if intro:
            (out_dir / f"{submission_id}_intro.txt").write_text(intro, encoding="utf-8")
            stats["submission"] = True

    ranked = sub / "related_work_data" / "ranked_papers.json"
    for p in (json.loads(ranked.read_text(encoding="utf-8")) if ranked.exists() else []):
        pid = p.get("paper_id")
        if not pid:
            continue
        src = sub / "related_work_data" / "grobid_fulltext" / f"{pid}.txt"
        if not src.exists():
            stats["papers_missing_fulltext"] += 1
            continue
        intro = _from_markdown(src.read_text(encoding="utf-8", errors="ignore"), max_chars)
        if intro:
            (out_dir / f"{pid}_intro.txt").write_text(intro, encoding="utf-8")
            stats["papers_written"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser(description="Write introductions/ for Afzal et al.'s pipeline")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--max-chars", type=int, default=20000)
    args = ap.parse_args()
    s = build(args.data_dir, args.submission_id, args.max_chars)
    print(f"submission intro written: {s['submission']}")
    print(f"related-paper intros    : {s['papers_written']} "
          f"({s['papers_missing_fulltext']} pool papers have no parsed full text)")


if __name__ == "__main__":
    main()

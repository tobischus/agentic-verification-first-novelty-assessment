#!/usr/bin/env python3
"""Set a submission's first-disclosure date by hand and invalidate the retrieval that
used the wrong one.

Document processing looks the date up on arXiv (v1) and Semantic Scholar. A paper that
exists only on OpenReview is found by neither, so the date falls back to TODAY -- and
retrieval then admits everything published up to today as "prior work". The flag for
that is `DATE?` in `eval/human_study_prep.py --status`.

Setting the date alone is not enough: retrieval and fetch_pdfs already ran against the
wrong cutoff. This script

  1. writes the date into {id}.json and {id}_claims.json (as api.py's date endpoint does),
     with the source and a note saying where it came from;
  2. MOVES (never deletes) related_work_data/ and {id}_pdf_status.json into
     data/_invalid_cutoff_backup/<id>/, together with the per-PDF cache entry, which
     would otherwise restore the old pool on the next run;
  3. removes retrieval and fetch_pdfs from the pipeline state.

The next `human_study_prep.py --run` then re-runs exactly those two stages; the GROBID
parse and the claims are kept.

Usage
-----
  python eval/fix_submission_date.py --submission td_moe --date 2025-10-08 \
      --source openreview_public --note "ICLR 2026 submission public on OpenReview, forum D9cnZNZfxX"
  add --dry-run to see what would happen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, first public disclosure")
    ap.add_argument("--source", default="reviewer")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    time.strptime(args.date, "%Y-%m-%d")

    k = args.submission
    sub = DATA / k
    state_p = sub / f"{k}_pipeline_state.json"
    if not state_p.is_file():
        raise SystemExit(f"no pipeline state for {k}")
    state = json.loads(state_p.read_text(encoding="utf-8"))
    backup = DATA / "_invalid_cutoff_backup" / k / time.strftime("%Y%m%d-%H%M%S")

    moves = [p for p in (sub / "related_work_data", sub / f"{k}_pdf_status.json") if p.exists()]
    pdf = Path(state.get("pdf_path") or "")
    cache = (DATA / "_cache" / hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
             if pdf.is_file() else None)
    if cache is not None and cache.exists():
        moves.append(cache)

    print(f"{k}: date -> {args.date} ({args.source})")
    for p in moves:
        print(f"  move {p.relative_to(REPO)} -> {backup.relative_to(REPO)}/")
    print(f"  stages_done: {state['stages_done']} -> "
          f"{[s for s in state['stages_done'] if s not in ('retrieval', 'fetch_pdfs')]}")
    if args.dry_run:
        return 0

    for f in (sub / f"{k}.json", sub / f"{k}_claims.json"):
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        d.update(publication_date=args.date, year=args.date[:4], date_source=args.source,
                 date_needs_review=False)
        if args.note:
            d["date_note"] = args.note
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    backup.mkdir(parents=True, exist_ok=True)
    for p in moves:
        shutil.move(str(p), str(backup / (p.name if p.parent != DATA / "_cache"
                                          else "_cache_entry")))
    state["stages_done"] = [s for s in state["stages_done"] if s not in ("retrieval", "fetch_pdfs")]
    state["status"] = "pending"
    state_p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

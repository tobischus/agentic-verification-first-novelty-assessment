#!/usr/bin/env python3
"""Invalidate the REVIEW for one submission, and nothing above it.

A change to the agent invalidates the per-claim Artifact A and everything synthesised
from it. It does NOT invalidate the GROBID parse, the extracted claims or the retrieval
-- which is the slow, paid part, and the part worth keeping. Deleting the whole cache
entry to see a review change throws all of that away for no reason.

The file list is imported from the orchestrator (`_DOWNSTREAM`) rather than repeated
here, so it cannot drift away from what the cache actually stores.

Both places have to be cleared: the submission directory, and the per-PDF-hash cache
entry that would otherwise restore the old files on the next upload.

Usage
-----
  python eval/reset_review.py --submission 15574_When_to_use_Graphs_in_RA__20260907-173144
  python eval/reset_review.py --submission ID --yes      # actually delete
  python eval/reset_review.py --list                     # what is cached, and how big
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))
from orchestrator import _DOWNSTREAM                                    # noqa: E402


def _mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def _entries(data_dir: Path):
    for d in sorted((data_dir / "_cache").glob("*/")):
        meta = d / "_cache_meta.json"
        if not meta.exists():
            continue
        try:
            cid = json.loads(meta.read_text(encoding="utf-8")).get("cached_id", "")
        except Exception:
            cid = ""
        yield d, cid


def main():
    ap = argparse.ArgumentParser(description="Drop the review, keep the expensive upstream")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--yes", action="store_true", help="delete; without it, only report")
    args = ap.parse_args()
    data = REPO / args.data_dir

    if args.list or not args.submission:
        print(f"{'cache entry':>18}  {'size':>7}  submission")
        for d, cid in _entries(data):
            print(f"{d.name:>18}  {_mb(d):6.1f}M  {cid}")
        if not args.submission:
            return

    targets = []
    sub = data / args.submission
    if sub.is_dir():
        targets += [sub / f.replace("{id}", args.submission) for f in _DOWNSTREAM]

    # Inside a cache entry, match by SUFFIX and not by the current cached_id. One entry
    # accumulates files under every submission id that ever hashed to this PDF, and
    # _save_to_cache carries files from a previous prefix forward under the new one --
    # so a stale artifact_a left under an old prefix comes back on the next upload.
    suffixes = [f.replace("{id}", "") for f in _DOWNSTREAM]
    for d, cid in _entries(data):
        if cid != args.submission:
            continue
        for f in sorted((d / "files").glob("*")):
            if f.is_file() and any(f.name.endswith(sfx) for sfx in suffixes):
                targets.append(f)

    present = [p for p in targets if p.exists()]
    if not present:
        print(f"\nnothing to drop for {args.submission} "
              f"(no review artifacts in the submission dir or the cache)")
        return
    print(f"\n{'DELETING' if args.yes else 'would delete'} {len(present)} file(s), "
          f"{sum(p.stat().st_size for p in present)/1e6:.1f} MB:")
    for p in present:
        where = "cache " if "_cache" in p.parts else "submission"
        print(f"  [{where}] {p.name}")
        if args.yes:
            p.unlink()
    kept = 0.0
    for d, cid in _entries(data):
        if cid == args.submission:
            kept = _mb(d)
    print(f"\nupstream kept: {kept:.1f} MB of cache "
          f"(GROBID parse, full text, claims, retrieval, downloaded PDFs)")
    if not args.yes:
        print("re-run with --yes to delete")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render DeepReviewer's own report PDF for a finished job, WITHOUT the submission.

DeepReviewer's native export merges the review with the full annotated submission: a
measured 47-page PDF over a 34-page paper is ~13 pages of review plus the paper again.
For the human study that is the wrong object twice over -- the participant is already
given the submission separately, and a report four times longer than every other system's
is a presentation difference on top of the ones PROTOCOL.md already concedes.

So this re-renders the SAME report through DeepReviewer's OWN builder
(`build_review_report_pdf`, their layout, their fonts, their branding) with
`source_pdf_bytes=None`. Their own `_merge_report_with_annotated_source_pdf_pages`
short-circuits on a falsy value, so nothing is stripped after the fact and no output of
theirs is edited -- the merge step simply never runs. What the participant sees is
DeepReviewer's real system output, bounded at the report.

Nothing in `DeepReviewer-v2/` is modified, and no job is re-run: this reads a completed
job's `final_report.md` and writes a sibling file next to it.

Must run on DeepReviewer's own interpreter, which has reportlab/markdown-it/pymupdf:

    DeepReviewer-v2/.venv/Scripts/python.exe eval/deepreviewer_review_pdf.py \
        --job-dir DeepReviewer-v2/data/jobs/<id>

    ... --all                 every completed job that has no review-only PDF yet
    ... --out <path>          a different destination for a single job
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DR_ROOT = REPO / "DeepReviewer-v2"
sys.path.insert(0, str(DR_ROOT))

from deepreview.report.review_report_pdf import build_review_report_pdf  # noqa: E402

#: Written next to `final_report.pdf`, never over it -- their native export stays intact.
OUT_NAME = "final_report_review_only.pdf"


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def render(job_dir: Path, out_path: Path | None = None) -> Path:
    md_path = job_dir / "final_report.md"
    if not md_path.is_file():
        raise FileNotFoundError(f"no final_report.md in {job_dir}")
    job = _load_json(job_dir / "job.json", {}) or {}
    # job.json nests the counters one level down (`usage.token`), and the runner passes
    # exactly that sub-dict to the builder. Reading `usage` directly printed a title page
    # saying "Input 0 | Output 0" next to a native export showing 8.6M -- the same report
    # with its own provenance zeroed out.
    usage = ((job.get("usage") or {}).get("token")
             if isinstance(job.get("usage"), dict) else None) or {}
    meta = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}

    pdf_bytes = build_review_report_pdf(
        workspace_title=str(job.get("title") or job_dir.name),
        source_pdf_name=str(job.get("source_pdf_name") or "source.pdf"),
        run_id=str(job.get("id") or job.get("job_id") or job_dir.name),
        status="completed",
        decision=None,
        estimated_cost=0,
        actual_cost=None,
        exported_at=datetime.now(timezone.utc),
        meta_review={},
        reviewers=[],
        raw_output=None,
        final_report_markdown=md_path.read_text(encoding="utf-8"),
        # The whole point. Their builder skips the merge entirely on a falsy value, so
        # the submission pages and their annotations are never added in the first place.
        source_pdf_bytes=None,
        source_annotations=None,
        review_display_id=None,
        owner_email=None,
        token_usage={k: int(usage.get(k) or 0)
                     for k in ("requests", "input_tokens", "output_tokens", "total_tokens")},
        agent_model=str(meta.get("agent_model") or job.get("agent_model")
                        or meta.get("llm_api_mode") or ""),
    )
    out = out_path or (job_dir / OUT_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf_bytes)
    return out


def _pages(path: Path) -> int:
    try:
        import fitz
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return -1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job-dir", help="one DeepReviewer job directory")
    ap.add_argument("--all", action="store_true",
                    help="every completed job under DeepReviewer-v2/data/jobs")
    ap.add_argument("--out", help="destination for a single job (default: next to the job)")
    ap.add_argument("--force", action="store_true", help="re-render even if one exists")
    args = ap.parse_args()

    if args.all:
        jobs = sorted(p for p in (DR_ROOT / "data" / "jobs").glob("*")
                      if (p / "final_report.md").is_file())
    elif args.job_dir:
        jobs = [Path(args.job_dir) if Path(args.job_dir).is_absolute()
                else REPO / args.job_dir]
    else:
        ap.error("pass --job-dir or --all")
        return 2

    if not jobs:
        print("no completed jobs found")
        return 1

    failed = 0
    for job_dir in jobs:
        target = Path(args.out) if (args.out and len(jobs) == 1) else job_dir / OUT_NAME
        if target.exists() and not args.force:
            print(f"{job_dir.name[:8]}  skip (exists, --force to redo)  {target.name}")
            continue
        try:
            out = render(job_dir, target)
        except Exception as e:  # one broken job must not stop a batch
            failed += 1
            print(f"{job_dir.name[:8]}  FAILED  {e!r}"[:160])
            continue
        native = job_dir / "final_report.pdf"
        native_n = _pages(native) if native.exists() else -1
        print(f"{job_dir.name[:8]}  {_pages(out):3d}p review-only"
              + (f"  (native: {native_n}p with the submission)" if native_n > 0 else "")
              + f"  -> {out.relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

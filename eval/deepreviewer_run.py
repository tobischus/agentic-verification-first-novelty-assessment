"""Run DeepReviewer on human-study submissions and record what each job cost."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DR = REPO / "DeepReviewer-v2"
JOBS = DR / "data" / "jobs"
OUT = REPO / "eval" / "out" / "human_study" / "deepreviewer"
VENV_PY = DR / ".venv" / "Scripts" / "python.exe"
if not VENV_PY.is_file():
    VENV_PY = DR / ".venv" / "bin" / "python"


def _usd(model: str, pt: int, ct: int) -> float:
    sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))
    from agent.claim_agent import _usd as price
    return price(model, pt or 0, ct or 0)


def papers(config: str, sources: str) -> dict:
    sys.path.insert(0, str(REPO / "eval"))
    from human_study_submission_text import papers as p
    return p(config, sources)


def agent_model() -> str:
    """The model DeepReviewer is configured to use, read from its settings."""
    cwd = Path.cwd()
    sys.path.insert(0, str(DR))
    import os
    os.chdir(DR)
    try:
        from deepreview.config import get_settings
        return get_settings().agent_model
    finally:
        os.chdir(cwd)


def job_record(job_id: str, model: str) -> dict:
    j = json.loads((JOBS / job_id / "job.json").read_text(encoding="utf-8"))
    tok = ((j.get("usage") or {}).get("token") or {})
    pt = tok.get("input_tokens") or tok.get("prompt_tokens") or 0
    ct = tok.get("output_tokens") or tok.get("completion_tokens") or 0
    art = JOBS / job_id
    return {
        "job_id": job_id, "status": j.get("status"), "title": j.get("title"),
        "source_pdf_name": j.get("source_pdf_name"),
        "created_at": j.get("created_at"), "updated_at": j.get("updated_at"),
        "model": model,
        "prompt_tokens": pt, "completion_tokens": ct,
        "requests": tok.get("requests"),
        "usd": round(_usd(model, pt, ct), 4),
        "tool_calls": ((j.get("usage") or {}).get("tool") or {}).get("total_calls"),
        "papers_found": ((j.get("usage") or {}).get("paper_search") or {}).get("papers_found"),
        "annotation_count": j.get("annotation_count"),
        "final_report_ready": j.get("final_report_ready"),
        "error": j.get("error"),
        "job_dir": f"DeepReviewer-v2/data/jobs/{job_id}",
        "has_final_report_md": (art / "final_report.md").is_file(),
        "has_final_report_pdf": (art / "final_report.pdf").is_file(),
        "has_review_only_pdf": (art / "final_report_review_only.pdf").is_file(),
    }


def submit(key: str, pdf: Path, wait: int, model: str) -> dict:
    before = {p.name for p in JOBS.iterdir()} if JOBS.is_dir() else set()
    t0 = time.time()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n=== {key} ===\n  {pdf.name}  ({pdf.stat().st_size:,} B)", flush=True)
    proc = subprocess.run(
        [str(VENV_PY), "main.py", "submit", "--pdf", str(pdf),
         "--wait-seconds", str(wait)],
        cwd=str(DR), capture_output=True, text=True)
    out = (proc.stdout or "").strip()
    try:
        resp = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        resp = {}
    job_id = resp.get("job_id") or resp.get("id")
    if not job_id:
        new = ({p.name for p in JOBS.iterdir()} - before) if JOBS.is_dir() else set()
        job_id = next(iter(new), None)
    if not job_id:
        print(f"  FAILED to submit: {(proc.stderr or out)[:300]}")
        return {"paper": key, "status": "submit_failed",
                "stderr": (proc.stderr or out)[-800:]}
    rec = job_record(job_id, model)
    rec.update({"paper": key, "started_at": started,
                "wall_clock_seconds": round(time.time() - t0, 1)})
    print(f"  job {job_id}  status={rec['status']}  {rec['wall_clock_seconds']:.0f}s")
    print(f"  tokens: in {rec['prompt_tokens']:,} / out {rec['completion_tokens']:,}"
          f"  -> ${rec['usd']:.4f}  ({rec['requests']} requests, "
          f"{rec['tool_calls']} tool calls)")
    print(f"  final_report.md={rec['has_final_report_md']} "
          f"final_report.pdf={rec['has_final_report_pdf']}")
    if rec.get("error"):
        print(f"  error: {str(rec['error'])[:200]}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma-separated paper keys")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true", help="summarise recorded runs, run nothing")
    ap.add_argument("--wait-seconds", type=int, default=3000)
    ap.add_argument("--force", action="store_true",
                    help="re-run papers that already have a completed job")
    ap.add_argument("--config", default="final_evaluation/config/main.yaml",
                    help="study config naming the papers (E1-only: config/e1_extra.yaml)")
    ap.add_argument("--sources", default="final_evaluation/config/sources.main.yaml",
                    help="its sources file (E1-only: config/sources.e1_extra.yaml)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ledger = OUT / "jobs.json"
    recs = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}

    if args.report:
        tot = 0.0
        for k, r in recs.items():
            print(f"{k[:46]:<48} {r.get('status','?'):<10} "
                  f"${r.get('usd',0):>7.4f}  {r.get('prompt_tokens',0):>10,} in  "
                  f"{r.get('wall_clock_seconds',0):>6.0f}s  {r.get('job_id','')[:8]}")
            tot += r.get("usd", 0) or 0
        print(f"\n{len(recs)} Jobs, zusammen ${tot:.4f}")
        return 0

    if not VENV_PY.is_file():
        raise SystemExit(f"DeepReviewer interpreter not found: {VENV_PY}")
    sel = papers(args.config, args.sources)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        sel = {k: v for k, v in sel.items() if k in want}
    elif not args.all:
        ap.error("--only, --all or --report")
    if not sel:
        print("no paper selected"); return 1

    if not args.force:
        already = [k for k in sel if (recs.get(k) or {}).get("status") == "completed"]
        for k in already:
            print(f"{k}: already completed (${recs[k]['usd']:.4f}, "
                  f"job {recs[k]['job_id'][:8]}) -- skipping; --force to re-run")
        sel = {k: v for k, v in sel.items() if k not in already}
        if not sel:
            print("nothing left to run"); return 0

    model = agent_model()
    print(f"DeepReviewer agent_model = {model}   ({len(sel)} Paper)")
    for key, pdf in sel.items():
        recs[key] = submit(key, pdf, args.wait_seconds, model)
        ledger.write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    done = [r for r in recs.values() if r.get("status") == "completed"]
    print(f"\nLedger: {ledger.relative_to(REPO).as_posix()}  "
          f"({len(done)}/{len(recs)} completed, "
          f"zusammen ${sum(r.get('usd', 0) or 0 for r in recs.values()):.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

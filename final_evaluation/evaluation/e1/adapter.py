"""E1: plan the LLM-judge calls for the SAME six pilot tasks the humans rate, and (only
on explicit request) run them against the dashboard's frozen inputs.

This is a thin adapter over the existing pilot judge (eval/pilot_judge.py,
eval/prompts/novelty_report_judge_v1.txt), NOT a second implementation of it -- it
reuses that module's request/response/validation code and only supplies a different
report source: `final_evaluation/inputs/pilot/<paper>/{system}.md|.pdf` (the FROZEN
dashboard content, via battle_export for agent/linear) instead of
`comparison/outputs/<paper>__<system>.md`. For OpenNovelty, the E1 text input is
`opennovelty.e1_text.md` (the PDF-to-text extraction), never the PDF itself, since the
judge model only accepts text -- see PROTOCOL.md for why this is flagged as
"needs_manual_check" rather than "equivalent" to what the human sees.

Planning mode needs no API key and makes no calls -- it only enumerates and prints what
WOULD be sent. `--execute` is the only path that calls a model, is never imported by the
dashboard's FastAPI app (grep dashboard/backend for "e1_execute" or "adapter.execute" --
there is none), and refuses to run without OPENAI_API_KEY.
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
FE_ROOT = REPO_ROOT / "final_evaluation"


def _report_file(paper: str, system: str) -> Path:
    d = FE_ROOT / "inputs" / "pilot" / paper
    md = d / f"{system}.md"
    if md.is_file():
        return md
    e1 = d / f"{system}.e1_text.md"
    if e1.is_file():
        return e1
    raise FileNotFoundError(f"no text input for {paper}/{system} -- run import-pilot first")


def build_plan(config_path: str) -> dict:
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    calls = []
    idx = 0
    for t in cfg["tasks"]:
        paper, (sys_a, sys_b) = t["paper"], t["pair"]
        for a, b in ((sys_a, sys_b), (sys_b, sys_a)):
            idx += 1
            missing = []
            for s in (a, b):
                try:
                    _report_file(paper, s)
                except FileNotFoundError as e:
                    missing.append(str(e))
            calls.append({
                "call_index": idx, "paper_id": paper, "system_a": a, "system_b": b,
                "ready": not missing, "problems": missing,
            })
    return {
        "config_path": config_path,
        "rubric_path": "final_evaluation/prompts/novelty_report_judge_v3.txt",
        "model": "gpt-5.6-terra", "effort": "medium",
        "calls": calls,
    }


def print_plan(plan: dict) -> None:
    print(f"E1 plan: {len(plan['calls'])} calls, rubric={plan['rubric_path']}, "
         f"model={plan['model']} (effort={plan['effort']})")
    for c in plan["calls"]:
        status = "ready" if c["ready"] else "NOT READY: " + "; ".join(c["problems"])
        print(f"  #{c['call_index']:02d} {c['paper_id']:28} A={c['system_a']:12} "
             f"B={c['system_b']:12} {status}")


def execute_plan(plan: dict, out_dir: str) -> None:
    """Runs the calls for real. Never called by the web app -- only by this CLI with
    --execute. Reuses eval/pilot_judge.py's request/validation machinery so the same
    JSON-shape and locator checks apply to dashboard-pilot calls as applied to the
    original eval/out/pilot_v1 run."""
    import os
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set -- refusing to execute E1 calls. "
                        "(Plan mode needs no key; this message only appears with --execute.)")

    sys.path.insert(0, str(REPO_ROOT / "eval"))
    import pilot_judge  # the existing, already-tested judge harness

    rubric = (FE_ROOT / "prompts" / "novelty_report_judge_v3.txt").read_text(encoding="utf-8")
    llm = pilot_judge.make_llm()

    out_path = Path(out_dir) / "judge_calls.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        raise SystemExit(f"{out_path} already exists -- old eval results are never "
                        "overwritten. Move it aside or pass a different --out-dir.")

    # Submission text: the same frozen files import_pilot.py already wrote.
    def load(paper, system):
        return _report_file(paper, system).read_text(encoding="utf-8")

    with out_path.open("w", encoding="utf-8") as fh:
        for c in plan["calls"]:
            if not c["ready"]:
                print(f"skipping #{c['call_index']}: not ready"); continue
            paper = c["paper_id"]
            sub_path = FE_ROOT / "inputs" / "pilot" / paper / "submission.txt"
            sub = pilot_judge.with_line_ids(sub_path.read_text(encoding="utf-8"), "S")
            a_txt = pilot_judge.with_line_ids(load(paper, c["system_a"]), "A")
            b_txt = pilot_judge.with_line_ids(load(paper, c["system_b"]), "B")
            call = {"paper_id": paper, "system_a": c["system_a"], "system_b": c["system_b"],
                   "call_index": c["call_index"]}
            docs = {paper: {"submission": sub, "reports": {c["system_a"]: a_txt, c["system_b"]: b_txt}}}
            rec = pilot_judge.run_call(llm, rubric, call, docs)
            rec["pilot_version"] = "dashboard_pilot_v1_e1"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
            print(f"#{c['call_index']:02d} {paper} {c['system_a']}/{c['system_b']}: "
                 f"{'ok' if not rec.get('failed') else 'FAILED'}")
    print(f"\nwritten: {out_path}")

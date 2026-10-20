#!/usr/bin/env python3
"""Single entry point: `python -m final_evaluation.cli <command> ...` from the repo root.

Every subcommand is documented in final_evaluation/README.md with its exact invocation.
This file only parses arguments and calls into scripts/*.py and evaluation/*/*.py --
none of the actual logic lives here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def cmd_inventory(args):
    from final_evaluation.scripts import inventory
    report = inventory.run(args.config)
    inventory.print_report(report)


def cmd_import_pilot(args):
    from final_evaluation.scripts import import_pilot
    manifest = import_pilot.run(args.sources, args.config)
    import_pilot.print_report(manifest)
    if manifest["blockers"]:
        sys.exit(1)


def cmd_validate_inputs(args):
    from final_evaluation.scripts import validate_inputs
    result = validate_inputs.run(args.study, args.config)
    validate_inputs.print_report(result)
    if not result["ok"]:
        sys.exit(1)


def cmd_init_db(args):
    from final_evaluation.scripts import seed
    applied = seed.init_db()
    print(f"migrations applied: {applied}" if applied else "schema already up to date")


def cmd_seed_pilot(args):
    from final_evaluation.scripts import seed
    print(seed.seed_pilot(args.config))


def cmd_refresh_reports(args):
    import json
    from .scripts import seed
    systems = tuple(x.strip() for x in args.systems.split(",") if x.strip())
    res = seed.refresh_reports(args.config, systems, dry_run=args.dry_run)
    print(json.dumps(res, indent=1, default=str))


def cmd_create_participants(args):
    from final_evaluation.scripts import seed
    result = seed.create_participants(args.study, args.count, prefix=args.prefix,
                                      is_test=not args.not_test, config_path=args.config)
    print(result)
    if result["created"]:
        print(f"\n{result['created']} new participant code(s) written to {result['codes_path']}")
        print("Distribute these manually. They are shown in full exactly once, in that file.")
    else:
        print("No new participants created (already exist for this study).")


def cmd_create_admin(args):
    from final_evaluation.scripts import seed
    result = seed.create_admin(args.study, display=args.display)
    print(result)
    if result["created"]:
        print(f"Admin code written to {result['code_path']} (shown once).")


def _sync_instructions_text():
    """The ONE source of truth for the instruction text and the rubric descriptions is
    `prompts/` -- this copies them into the frontend's public/ dir (as plain text/JSON)
    so the UI fetches the same bytes the consent hash is computed over, in dev mode and
    in the built dist/ alike. Never edit the copies under frontend/public/ by hand; they
    are regenerated on every build-frontend."""
    import re
    import shutil
    prompts = REPO_ROOT / "final_evaluation" / "prompts"
    dest_dir = REPO_ROOT / "final_evaluation" / "dashboard" / "frontend" / "public"
    dest_dir.mkdir(parents=True, exist_ok=True)
    text = (prompts / "human_instructions.md").read_text(encoding="utf-8")
    text = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)
    (dest_dir / "instructions.txt").write_text(text, encoding="utf-8")
    shutil.copyfile(prompts / "criteria.json", dest_dir / "criteria.json")


def cmd_build_frontend(args):
    import shutil
    import subprocess
    _sync_instructions_text()
    fe_dir = REPO_ROOT / "final_evaluation" / "dashboard" / "frontend"
    node = shutil.which("node")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print("npm not found on PATH -- install Node.js 18+ to build the dashboard frontend.")
        sys.exit(1)
    print(f"node: {subprocess.run([node, '--version'], capture_output=True, text=True).stdout.strip() if node else 'not found'}")
    if not (fe_dir / "node_modules").is_dir() or args.reinstall:
        print("installing frontend dependencies (npm ci)...")
        r = subprocess.run([npm, "ci"], cwd=fe_dir)
        if r.returncode != 0:
            print("npm ci failed; trying npm install...")
            subprocess.run([npm, "install"], cwd=fe_dir, check=True)
    print("building frontend (npm run build)...")
    subprocess.run([npm, "run", "build"], cwd=fe_dir, check=True)
    dist = fe_dir / "dist"
    print(f"built: {dist} ({'ok' if (dist/'index.html').is_file() else 'MISSING index.html'})")


def cmd_serve(args):
    import uvicorn
    uvicorn.run("final_evaluation.dashboard.backend.app:create_app", factory=True,
               host=args.host, port=args.port, reload=args.reload)


def cmd_export(args):
    from final_evaluation.dashboard.backend import db as db_mod
    from final_evaluation.dashboard.backend.routers.admin import _build_export
    from final_evaluation.dashboard.backend.settings import get_settings
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    try:
        data = _build_export(db, args.study)
    finally:
        db.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"written: {out} ({len(data)} bytes)")


def cmd_analyze_human(args):
    from final_evaluation.evaluation.e2 import analyze
    result = analyze.run(args.input, include_test=args.include_test)
    out_path = Path(args.out) if args.out else Path(args.input).with_suffix("").parent / "analysis.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    analyze.print_report(result)
    print(f"\nwritten: {out_path}")


def cmd_plan_e1(args):
    from final_evaluation.evaluation.e1 import adapter
    plan = adapter.build_plan(args.config, papers=args.papers, pairs=args.pairs)
    if args.execute:
        adapter.execute_plan(plan, out_dir=args.out_dir, limit=args.limit,
                             service_tier="" if args.standard else "flex",
                             cache=not args.no_cache)
    else:
        adapter.print_plan(plan, verbose=args.verbose)
        print("\n(plan mode -- no API calls made. Pass --execute to run them; "
             "requires OPENAI_API_KEY and is never invoked by the web process.)")


def cmd_analyze_e1(args):
    from final_evaluation.evaluation.e1 import adapter, analyze
    recs, corr = analyze.load(args.e1)
    plan = adapter.build_plan(args.config) if args.config else None
    res = analyze.analyze(recs, corr, plan)
    analyze.print_report(res, args.paper_set)
    out = Path(args.out) if args.out else Path(args.e1).parent / "e1_analysis.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print()
    print(f"written: {out}")


def cmd_sensitivity_e1(args):
    from final_evaluation.evaluation.e1 import analyze, sensitivity
    recs, _ = analyze.load(args.e1)
    res = sensitivity.analyze(recs)
    sensitivity.print_report(res)
    out = Path(args.out) if args.out else Path(args.e1).parent / "e1_sensitivity.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print()
    print(f"written: {out}")


def cmd_agent_linear(args):
    from final_evaluation.evaluation import agent_linear
    res = agent_linear.analyze(Path(args.config))
    agent_linear.print_report(res)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print()
    print(f"written: {out}")


def cmd_adjudication_packet(args):
    from final_evaluation.scripts import adjudication_packet
    res = adjudication_packet.build(Path(args.out_dir), Path(args.config))
    print(f"{res['cases']} divergent claims -> {res['out_dir']}")
    print(f"fill in: {res['decisions']}")


def cmd_source_audit(args):
    from final_evaluation.evaluation.e3 import source_audit
    res = source_audit.analyze(Path(args.config))
    source_audit.print_report(res)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"written: {out}")


def cmd_figures(args):
    from final_evaluation.scripts import presentation_figures
    for p in presentation_figures.build(Path(args.out_dir), Path(args.e1_dir), minimal=args.minimal):
        print(f"written: {p}")


def cmd_compare_e1(args):
    from final_evaluation.evaluation.e2 import analyze
    result = analyze.compare_to_e1(args.input, args.e1, include_test=args.include_test)
    out_path = Path(args.out) if args.out else Path(args.e1).parent / "e1_vs_human.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    analyze.print_e1_comparison(result)
    print(f"\nwritten: {out_path}")


def cmd_upload_assets(args):
    from final_evaluation.scripts import upload_assets
    upload_assets.run(args.study)


def cmd_backup(args):
    from final_evaluation.scripts import backup_restore
    path = backup_restore.backup(args.study, args.out)
    print(f"backup written: {path}")


def cmd_restore(args):
    from final_evaluation.scripts import backup_restore
    backup_restore.restore(args.input, args.target_local)
    print(f"restored into: {args.target_local}")


def main():
    ap = argparse.ArgumentParser(prog="python -m final_evaluation.cli")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inventory"); p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("import-pilot")
    p.add_argument("--sources", default="final_evaluation/config/sources.pilot.yaml")
    p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.set_defaults(func=cmd_import_pilot)

    p = sub.add_parser("validate-inputs")
    p.add_argument("--study", required=True)
    p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.set_defaults(func=cmd_validate_inputs)

    p = sub.add_parser("init-db"); p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("seed-pilot")
    p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.set_defaults(func=cmd_seed_pilot)

    p = sub.add_parser("refresh-reports",
                       help="replace report content from the current manifest where no one has rated it")
    p.add_argument("--config", required=True)
    p.add_argument("--systems", default="agent,linear")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_refresh_reports)

    p = sub.add_parser("create-participants")
    p.add_argument("--study", required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--prefix", default="R")
    p.add_argument("--not-test", action="store_true", help="mark as real (non-test) participants")
    p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.set_defaults(func=cmd_create_participants)

    p = sub.add_parser("create-admin")
    p.add_argument("--study", required=True)
    p.add_argument("--display", default="ADMIN")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("build-frontend")
    p.add_argument("--reinstall", action="store_true")
    p.set_defaults(func=cmd_build_frontend)

    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8010)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("export")
    p.add_argument("--study", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("analyze-human")
    p.add_argument("--input", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--include-test", action="store_true",
                  help="include responses from test participants -- required for the "
                       "pilot, whose two raters are deliberately test accounts")
    p.set_defaults(func=cmd_analyze_human)

    p = sub.add_parser("plan-e1")
    p.add_argument("--config", default="final_evaluation/config/e1_main.yaml",
                   help="e1_main.yaml (all papers x all pairs) or pilot.yaml (the pilot's tasks)")
    p.add_argument("--papers", default="", help="narrow to these paper keys (comma-separated)")
    p.add_argument("--pairs", default="", help="narrow to these pairs, e.g. agent:linear,agent:afzal")
    p.add_argument("--limit", type=int, default=0, help="with --execute: run at most N calls")
    p.add_argument("--verbose", action="store_true", help="list every planned call")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--out-dir", default=None, help="default: the config's out_dir")
    p.add_argument("--standard", action="store_true",
                   help="standard service tier instead of flex (2x price; e.g. if flex stays unavailable)")
    p.add_argument("--no-cache", action="store_true",
                   help="the pilot's exact request: one user string, seed-shuffled order, no breakpoints")
    p.set_defaults(func=cmd_plan_e1)

    p = sub.add_parser("analyze-e1", help="E1 judge results: stability, pairs, ranking, bias, cost")
    p.add_argument("--e1", default="final_evaluation/results/main/e1/judge_calls.jsonl")
    p.add_argument("--config", default="final_evaluation/config/e1_main.yaml",
                   help="the plan the results are checked against for completeness ('' to skip)")
    p.add_argument("--paper-set", default="all", help="all | main | e1_only (what is printed)")
    p.add_argument("--out", default=None, help="default: e1_analysis.json next to the results")
    p.set_defaults(func=cmd_analyze_e1)

    p = sub.add_parser("sensitivity-e1", help="E1 post-hoc sensitivity: length- and coverage-adjusted rankings")
    p.add_argument("--e1", default="final_evaluation/results/main/e1/judge_calls.jsonl")
    p.add_argument("--out", default=None, help="default: e1_sensitivity.json next to the results")
    p.set_defaults(func=cmd_sensitivity_e1)

    p = sub.add_parser("agent-linear", help="agent vs linear run metrics on the E1 papers, paired sign tests")
    p.add_argument("--config", default="final_evaluation/config/e1_main.yaml")
    p.add_argument("--out", default="final_evaluation/results/main/agent_linear/agent_linear.json")
    p.set_defaults(func=cmd_agent_linear)

    p = sub.add_parser("adjudication-packet", help="blind side-by-side packet for the claims agent and linear judge differently")
    p.add_argument("--config", default="final_evaluation/config/e1_main.yaml")
    p.add_argument("--out-dir", default="final_evaluation/results/main/agent_linear/adjudication")
    p.set_defaults(func=cmd_adjudication_packet)

    p = sub.add_parser("source-audit", help="E3 automatic part: grounding, verifiability and a re-check of every shown quote")
    p.add_argument("--config", default="final_evaluation/config/e1_main.yaml")
    p.add_argument("--out", default="final_evaluation/results/main/e3/source_audit.json")
    p.set_defaults(func=cmd_source_audit)

    p = sub.add_parser("figures", help="slide figures from the E1 and agent-linear analysis outputs")
    p.add_argument("--out-dir", default="final_evaluation/results/main/figures")
    p.add_argument("--e1-dir", default="final_evaluation/results/main/e1",
                   help="the E1 run to draw (holds e1_analysis.json and e1_sensitivity.json)")
    p.add_argument("--minimal", action="store_true",
                   help="one short caption line per figure, built from the data only")
    p.set_defaults(func=cmd_figures)

    p = sub.add_parser("compare-e1", help="human ratings vs the E1 judge on the same tasks")
    p.add_argument("--input", required=True, help="the admin export ZIP")
    p.add_argument("--e1", required=True, help="judge_calls.jsonl written by plan-e1 --execute")
    p.add_argument("--include-test", action="store_true")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_compare_e1)

    p = sub.add_parser("upload-assets")
    p.add_argument("--study", required=True)
    p.set_defaults(func=cmd_upload_assets)

    p = sub.add_parser("backup")
    p.add_argument("--study", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("restore")
    p.add_argument("--input", required=True)
    p.add_argument("--target-local", required=True)
    p.set_defaults(func=cmd_restore)

    args = ap.parse_args()
    if args.command in {"init-db", "seed-pilot", "refresh-reports", "create-participants",
                        "create-admin", "upload-assets", "backup", "export", "serve"}:
        # Say which database and storage this command acts on -- the local study and the
        # cloud one differ only by ENV_FILE, and a missed ENV_FILE is otherwise silent.
        from final_evaluation.dashboard.backend.settings import get_settings
        st = get_settings()
        db = st.database_url.rsplit("@", 1)[-1] if "@" in st.database_url else st.database_url
        print(f"[target] database: {db.split('?')[0]} | storage: {st.storage_backend} | "
              f"env file: {os.getenv('ENV_FILE') or 'final_evaluation/.env'}", file=sys.stderr)
    args.func(args)


if __name__ == "__main__":
    main()

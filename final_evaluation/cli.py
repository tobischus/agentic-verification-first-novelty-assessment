#!/usr/bin/env python3
"""Single entry point: `python -m final_evaluation.cli <command> ...` from the repo root.

Every subcommand is documented in final_evaluation/README.md with its exact invocation.
This file only parses arguments and calls into scripts/*.py and evaluation/*/*.py --
none of the actual logic lives here.
"""
from __future__ import annotations

import argparse
import json
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
    plan = adapter.build_plan(args.config)
    if args.execute:
        adapter.execute_plan(plan, out_dir=args.out_dir)
    else:
        adapter.print_plan(plan)
        print("\n(plan mode -- no API calls made. Pass --execute to run them; "
             "requires OPENAI_API_KEY and is never invoked by the web process.)")


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
    p.add_argument("--config", default="final_evaluation/config/pilot.yaml")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--out-dir", default="final_evaluation/results/pilot/e1")
    p.set_defaults(func=cmd_plan_e1)

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
    args.func(args)


if __name__ == "__main__":
    main()

"""Local CLI backup/restore, on top of (not instead of) the admin export.

The admin export (`/api/admin/export`, `cli.py export`) is the RESEARCH data --
pseudonymised, no auth secrets, ready to analyse. A backup is the OPERATIONAL data: every
row of every table for the study, including `participants.code_hash` and `sessions` --
enough to fully reconstitute the study, which is exactly why it must never be treated as
a research export (see README.md's export vs. backup distinction) and why it is
gitignored (`final_evaluation/backups/`) rather than something that could reasonably ship
in a repository.

Table dump order respects foreign keys both ways: Assets and Papers/Reports/Tasks before
anything referencing them on backup does not matter (backup just reads), but RESTORE
writes them back in FK-safe order -- Study, then Asset, then Paper/Report/Task, then
Participant, then Session/Assignment, then FinalResponse/PaperFamiliarity/AuditEvent/
TechnicalIssue.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect

from ..dashboard.backend import db as db_mod, models
from ..dashboard.backend.settings import get_settings

FE_ROOT = Path(__file__).resolve().parents[1]

# Backup order (safe for both dump and restore in this sequence).
TABLES = [models.Study, models.Asset, models.Paper, models.Report, models.Task,
         models.Participant, models.Session_, models.Assignment, models.FinalResponse,
         models.PaperFamiliarity, models.AuditEvent, models.TechnicalIssue]


def _row_to_dict(row) -> dict:
    out = {}
    for col in inspect(row).mapper.columns:
        v = getattr(row, col.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        out[col.name] = v
    return out


def _rows_for_study(db, model, study_id: str) -> list:
    q = db.query(model)
    if hasattr(model, "study_id"):
        q = q.filter(model.study_id == study_id)
    elif model is models.FinalResponse:
        q = q.join(models.Assignment, models.Assignment.id == models.FinalResponse.assignment_id) \
            .filter(models.Assignment.study_id == study_id)
    elif model is models.Session_:
        q = q.join(models.Participant, models.Participant.id == models.Session_.participant_id) \
            .filter(models.Participant.study_id == study_id)
    return q.all()


def backup(study_id: str, out_path: str) -> Path:
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    try:
        dump = {"study_id": study_id, "backed_up_at": datetime.now(timezone.utc).isoformat(),
               "database_url_host": settings.database_url.split("@")[-1]
                                    if "@" in settings.database_url else "sqlite",
               "tables": {}}
        for model in TABLES:
            rows = _rows_for_study(db, model, study_id)
            dump["tables"][model.__tablename__] = [_row_to_dict(r) for r in rows]
    finally:
        db.close()

    dest = Path(out_path)
    if dest.exists():
        # Never silently clobber an existing backup -- append a timestamp instead.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = dest.with_name(f"{dest.stem}_{stamp}{dest.suffix}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", json.dumps(dump, ensure_ascii=False, indent=1))
    return dest


def restore(input_path: str, target_local: str) -> None:
    target = Path(target_local).resolve()
    if target.exists():
        raise SystemExit(f"refusing to restore into an existing file: {target}. "
                        "Restore only ever targets a NEW local sqlite file -- pick a "
                        "path that does not exist yet (this is a safety rail, not a "
                        "limitation: it can never overwrite an active study database).")
    if not str(target).startswith(str(FE_ROOT)):
        print(f"note: {target} is outside final_evaluation/ -- proceeding, but the brief's "
             "own examples restore under final_evaluation/private/.")

    with zipfile.ZipFile(input_path) as z:
        dump = json.loads(z.read("backup.json").decode("utf-8"))

    target_url = f"sqlite:///{target}"
    engine = db_mod.make_engine(target_url)
    db_mod.run_migrations(engine)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    try:
        for model in TABLES:
            rows = dump["tables"].get(model.__tablename__, [])
            for r in rows:
                for col in inspect(model).columns:
                    if col.type.python_type is datetime and r.get(col.name):
                        r[col.name] = datetime.fromisoformat(r[col.name])
                db.add(model(**r))
        db.commit()
    finally:
        db.close()
    print(f"restored {sum(len(v) for v in dump['tables'].values())} row(s) across "
         f"{len(dump['tables'])} tables from study {dump['study_id']!r} "
         f"(backed up {dump['backed_up_at']}) into {target}")

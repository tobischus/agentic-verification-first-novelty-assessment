"""init-db, seed-pilot, create-participants, create-admin.

Every function here is written to be re-run safely: it looks for the row it is about to
create by its natural key first, and either leaves an existing row untouched or reports
why it will not overwrite one (an already-final Assignment, in particular, is never
touched by re-seeding -- see seed_pilot()'s Task upsert and create_participants()'s
Assignment creation, both of which skip rather than recreate).
"""
from __future__ import annotations

import csv
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..dashboard.backend import db as db_mod, models, security, storage
from ..dashboard.backend.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
FE_ROOT = REPO_ROOT / "final_evaluation"


def init_db() -> list:
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    applied = db_mod.run_migrations(engine)
    return applied


def _content_type_for(kind: str, path: Path) -> str:
    if kind == "markdown":
        return "text/markdown; charset=utf-8"
    if kind == "json":
        return "application/json"
    guess, _ = mimetypes.guess_type(str(path))
    return guess or "application/octet-stream"


def _put_asset(db, backend: storage.StorageBackend, study_id: str, kind: str,
              file_entry: dict, source_note: str) -> models.Asset:
    src = FE_ROOT / file_entry["path"]
    content_type = _content_type_for(kind, src)
    asset_id = "asset_" + file_entry["sha256"][:24]
    existing = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if existing:
        return existing
    storage_key = backend.put(study_id, asset_id, src, content_type)
    asset = models.Asset(id=asset_id, study_id=study_id, kind=kind, storage_backend=backend.name,
                         storage_key=storage_key, sha256=file_entry["sha256"],
                         byte_size=file_entry["bytes"], content_type=content_type,
                         source_path=source_note)
    db.add(asset)
    return asset


def seed_pilot(config_path: str = "final_evaluation/config/pilot.yaml") -> dict:
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    manifest = json.loads((FE_ROOT / "manifests" / "pilot" / "reports.json").read_text(encoding="utf-8"))
    if manifest.get("blockers"):
        raise RuntimeError(f"reports.json has {len(manifest['blockers'])} blocker(s) -- "
                          "run validate-inputs and fix them before seeding")

    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    backend = storage.backend_from_env()
    db = Session()
    summary = {"papers": 0, "reports": 0, "tasks_created": 0, "tasks_existing": 0}
    try:
        sid = cfg["study"]["id"]
        study = db.query(models.Study).filter(models.Study.id == sid).first()
        if study is None:
            study = models.Study(id=sid, title=cfg["study"]["title"],
                                 is_pilot=cfg["study"].get("is_pilot", True),
                                 rubric_version=cfg["study"]["rubric_version"],
                                 instructions_version=cfg["study"]["instructions_version"],
                                 ui_version=cfg["study"]["ui_version"],
                                 assignment_seed=cfg["study"]["assignment_seed"], status="draft")
            db.add(study)
            db.flush()
        else:
            # A rubric/instructions revision has to reach an already-seeded study, but it
            # must never rewrite the version a finalised answer was given under. So the
            # update happens only while no FinalResponse exists for this study; after
            # that, the mismatch is reported and the stored versions stay as they are --
            # the stale study is then the one to close and re-seed under a NEW id.
            wanted = {"rubric_version": cfg["study"]["rubric_version"],
                     "instructions_version": cfg["study"]["instructions_version"],
                     "ui_version": cfg["study"]["ui_version"]}
            drift = {k: (getattr(study, k), v) for k, v in wanted.items() if getattr(study, k) != v}
            if drift:
                n_final = (db.query(models.FinalResponse)
                          .join(models.Assignment,
                                models.Assignment.id == models.FinalResponse.assignment_id)
                          .filter(models.Assignment.study_id == sid).count())
                if n_final == 0:
                    for k, (_old, new) in drift.items():
                        setattr(study, k, new)
                    summary["versions_updated"] = {k: f"{o} -> {n}" for k, (o, n) in drift.items()}
                else:
                    summary["version_drift_kept"] = {
                        k: f"stored {o!r} != config {n!r}" for k, (o, n) in drift.items()}
                    summary["version_drift_note"] = (
                        f"{n_final} finalised response(s) exist -- stored versions left "
                        "untouched so those answers keep the version they were given under.")

        report_ids: dict[tuple[str, str], str] = {}
        for paper_key, pcfg in cfg["papers"].items():
            paper_id = f"{sid}::{paper_key}"
            paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
            man = manifest["papers"][paper_key]
            sub = man["submission"]
            if paper is None:
                paper = models.Paper(id=paper_id, study_id=sid, paper_key=paper_key,
                                     title=pcfg["title"])
                db.add(paper); db.flush()
                summary["papers"] += 1
            if "pdf_file" in sub and paper.submission_pdf_asset_id is None:
                a = _put_asset(db, backend, sid, "pdf", sub["pdf_file"], f"{paper_key}/submission.pdf")
                paper.submission_pdf_asset_id = a.id
            if "text_file" in sub and paper.submission_text_asset_id is None:
                a = _put_asset(db, backend, sid, "markdown", sub["text_file"], f"{paper_key}/submission.txt")
                paper.submission_text_asset_id = a.id

            for system_id, r in man["systems"].items():
                if r.get("blocker"):
                    continue
                report_id = f"{paper_id}::{system_id}"
                report_ids[(paper_key, system_id)] = report_id
                existing = db.query(models.Report).filter(models.Report.id == report_id).first()
                if existing is not None:
                    continue
                content_entry = r.get("text_file") or r.get("content_file")
                content_kind = "markdown" if r["view_type"] == "markdown" else "pdf"
                content_asset = _put_asset(db, backend, sid, content_kind, content_entry,
                                           f"{paper_key}/{system_id}")
                qidx_asset_id = None
                if r.get("quote_index_file"):
                    qidx_asset = _put_asset(db, backend, sid, "json", r["quote_index_file"],
                                            f"{paper_key}/{system_id}.quote_index")
                    qidx_asset_id = qidx_asset.id
                db.add(models.Report(id=report_id, study_id=sid, paper_id=paper_id,
                                     system_id=system_id, view_type=r["view_type"],
                                     content_asset_id=content_asset.id,
                                     quote_index_asset_id=qidx_asset_id,
                                     content_version=r["content_version"]))
                summary["reports"] += 1
        db.flush()

        for t in cfg["tasks"]:
            paper_key = t["paper"]
            sys_a, sys_b = sorted(t["pair"])  # canonical alphabetical order
            pair_key = f"{paper_key}::{sys_a}::{sys_b}"
            existing = db.query(models.Task).filter(models.Task.study_id == sid,
                                                     models.Task.pair_key == pair_key).first()
            if existing is not None:
                summary["tasks_existing"] += 1
                continue
            rid_a = report_ids.get((paper_key, sys_a))
            rid_b = report_ids.get((paper_key, sys_b))
            if not rid_a or not rid_b:
                raise RuntimeError(f"cannot create task {pair_key}: report missing for "
                                  f"{sys_a if not rid_a else sys_b}")
            task_id = models.new_id()
            db.add(models.Task(id=task_id, study_id=sid, paper_id=f"{sid}::{paper_key}",
                               system_a=sys_a, system_b=sys_b, report_a_id=rid_a, report_b_id=rid_b,
                               pair_key=pair_key, is_practice=False))
            summary["tasks_created"] += 1

        if study.status == "draft":
            study.status = "active"
        db.commit()
    finally:
        db.close()
    return summary


def _db_tag(database_url: str) -> str:
    """A short, filename-safe tag for the database a credential belongs to.

    Codes are issued per DATABASE, not per study id: seeding a throwaway test database
    with the same study id used to overwrite the real pilot's `admin_code.txt` and append
    a second, indistinguishable R01 row to `participant_codes.csv` -- so a credential
    file could silently stop matching the database it was meant for.
    """
    if database_url.startswith("sqlite"):
        return Path(database_url.replace("sqlite:///", "")).stem
    host = database_url.split("@")[-1].split("/")[0]
    return "".join(ch if ch.isalnum() else "_" for ch in host)[:40] or "remote"


def create_participants(study_id: str, count: int, prefix: str = "R", is_test: bool = True,
                        config_path: str = "final_evaluation/config/pilot.yaml") -> dict:
    """Create `count` participants AND their frozen assignments to every existing Task
    in the study, using the seeded orientation/order (security.orientation_for /
    block_and_task_order). Re-running with the same count is a no-op for participants and
    assignments that already exist -- see the two `if existing:` early-returns below."""
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    private_dir = FE_ROOT / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    db_tag = _db_tag(settings.database_url)
    codes_path = private_dir / f"participant_codes__{study_id}__{db_tag}.csv"
    created_rows = []
    try:
        tasks = db.query(models.Task).filter(models.Task.study_id == study_id).all()
        by_paper: dict[str, list[str]] = {}
        for t in tasks:
            by_paper.setdefault(t.paper_id, []).append(t.id)
        paper_ids = [p.id for p in db.query(models.Paper).filter(models.Paper.study_id == study_id)]

        existing_count = db.query(models.Participant).filter(
            models.Participant.study_id == study_id, models.Participant.role == "participant").count()

        for i in range(1, count + 1):
            display = f"{prefix}{i:02d}"
            p = db.query(models.Participant).filter(models.Participant.study_id == study_id,
                                                     models.Participant.code_display == display).first()
            ordinal = existing_count + i if p is None else p.ordinal
            if p is None:
                full_code = security.generate_code(display)
                p = models.Participant(id=models.new_id(), study_id=study_id, code_display=display,
                                       code_hash=security.hash_code(full_code, settings.access_code_pepper),
                                       role="participant", ordinal=ordinal, is_test=is_test)
                db.add(p); db.flush()
                created_rows.append({"code_display": display, "code": full_code, "study_id": study_id})
            else:
                full_code = None  # not re-shown for an already-existing participant

            order_seed = cfg["study"].get("order_seed_base", 100) + ordinal
            ordered_task_ids = security.block_and_task_order(order_seed, paper_ids, by_paper)
            assignment_seed = cfg["study"]["assignment_seed"]
            for idx, task_id in enumerate(ordered_task_ids):
                exists = db.query(models.Assignment).filter(
                    models.Assignment.study_id == study_id, models.Assignment.task_id == task_id,
                    models.Assignment.participant_id == p.id).first()
                if exists is not None:
                    continue  # never reroll -- see module docstring
                task = db.query(models.Task).get(task_id)
                orientation = security.orientation_for(assignment_seed, task.pair_key, ordinal)
                db.add(models.Assignment(id=models.new_id(), study_id=study_id, task_id=task_id,
                                         participant_id=p.id, orientation=orientation,
                                         order_index=idx, is_practice=task.is_practice))
        db.commit()
    finally:
        db.close()

    if created_rows:
        write_header = not codes_path.is_file()
        with open(codes_path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["code_display", "code", "study_id", "database"])
            if write_header:
                w.writeheader()
            for row in created_rows:
                row["database"] = db_tag
            w.writerows(created_rows)
    return {"created": len(created_rows), "codes_path": str(codes_path) if created_rows else None}


def create_admin(study_id: str, display: str = "ADMIN") -> dict:
    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    private_dir = FE_ROOT / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    try:
        existing = db.query(models.Participant).filter(models.Participant.study_id == study_id,
                                                        models.Participant.role == "admin",
                                                        models.Participant.code_display == display).first()
        if existing is not None:
            return {"created": False, "reason": "admin already exists for this study/display"}
        full_code = security.generate_code(display)
        p = models.Participant(id=models.new_id(), study_id=study_id, code_display=display,
                               code_hash=security.hash_code(full_code, settings.access_code_pepper),
                               role="admin", ordinal=0, is_test=False)
        db.add(p)
        db.commit()
    finally:
        db.close()
    # Per database AND study, never overwritten -- see _db_tag's docstring for the
    # failure this prevents.
    admin_path = private_dir / f"admin_code__{study_id}__{_db_tag(settings.database_url)}.txt"
    if admin_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        admin_path = admin_path.with_name(f"{admin_path.stem}__{stamp}{admin_path.suffix}")
    admin_path.write_text(f"{full_code}\n", encoding="utf-8")
    return {"created": True, "code_path": str(admin_path)}

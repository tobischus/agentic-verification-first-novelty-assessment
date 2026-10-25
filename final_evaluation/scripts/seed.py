"""Database setup: init-db, seed-study, create-participants, create-admin."""
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


def _study_config(config_path: str) -> dict:
    """A study config -- never an E1-only paper list (config/e1_extra.yaml), whose papers must not reach the study database."""
    cfg = yaml.safe_load((REPO_ROOT / config_path).read_text(encoding="utf-8"))
    if cfg.get("e1_only"):
        raise SystemExit(f"{config_path} is E1-only (e1_only: true) -- it is never seeded "
                         "into a study; use it with import-inputs, validate-inputs and plan-e1.")
    return cfg


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


def seed_study(config_path: str = "final_evaluation/config/main.yaml") -> dict:
    cfg = _study_config(config_path)
    study_dir = cfg.get("inputs_dir") or "main"
    manifest = json.loads(
        (FE_ROOT / "manifests" / study_dir / "reports.json").read_text(encoding="utf-8"))
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
            sys_a, sys_b = sorted(t["pair"])
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
    """A short, filename-safe tag for the database a credential belongs to."""
    if database_url.startswith("sqlite"):
        return Path(database_url.replace("sqlite:///", "")).stem
    host = database_url.split("@")[-1].split("/")[0]
    return "".join(ch if ch.isalnum() else "_" for ch in host)[:40] or "remote"


def create_participants(study_id: str, count: int, prefix: str = "R", is_test: bool = True,
                        config_path: str = "final_evaluation/config/main.yaml") -> dict:
    """Create `count` participants AND their frozen assignments to every existing Task in the study, using the seeded orientation/order (security.orientation_for / block_and_task_order). Re-running with the same count is a no-op for participants and assignments that already exist -- see the two `if existing:` early-returns below."""
    cfg = _study_config(config_path)
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
                full_code = None

            order_seed = cfg["study"].get("order_seed_base", 100) + ordinal
            ordered_task_ids = security.block_and_task_order(order_seed, paper_ids, by_paper)
            assignment_seed = cfg["study"]["assignment_seed"]
            for idx, task_id in enumerate(ordered_task_ids):
                exists = db.query(models.Assignment).filter(
                    models.Assignment.study_id == study_id, models.Assignment.task_id == task_id,
                    models.Assignment.participant_id == p.id).first()
                if exists is not None:
                    continue
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
    admin_path = private_dir / f"admin_code__{study_id}__{_db_tag(settings.database_url)}.txt"
    if admin_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        admin_path = admin_path.with_name(f"{admin_path.stem}__{stamp}{admin_path.suffix}")
    admin_path.write_text(f"{full_code}\n", encoding="utf-8")
    return {"created": True, "code_path": str(admin_path)}


def refresh_reports(config_path: str, systems=("agent", "linear"), dry_run: bool = False) -> dict:
    """Point a study's reports at the content of its CURRENT manifest -- only where no one has rated against the old content."""
    cfg = _study_config(config_path)
    study_dir = cfg.get("inputs_dir") or "main"
    manifest = json.loads(
        (FE_ROOT / "manifests" / study_dir / "reports.json").read_text(encoding="utf-8"))
    if manifest.get("blockers"):
        raise RuntimeError(f"reports.json has {len(manifest['blockers'])} blocker(s)")
    sid = cfg["study"]["id"]

    settings = get_settings()
    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    backend = storage.backend_from_env()
    db = Session()
    summary = {"study": sid, "dry_run": dry_run, "replaced": [], "unchanged": [],
               "kept_because_rated": [], "test_drafts_affected": []}
    try:
        people = {p.id: p for p in db.query(models.Participant)
                  .filter(models.Participant.study_id == sid)}
        all_tasks = db.query(models.Task).filter(models.Task.study_id == sid).all()
        for paper_key, entry in manifest["papers"].items():
            paper = (db.query(models.Paper).filter(models.Paper.study_id == sid,
                                                   models.Paper.paper_key == paper_key).first())
            if paper is None:
                continue
            for system_id in systems:
                r = (entry.get("systems") or {}).get(system_id) or {}
                if not r or r.get("blocker"):
                    continue
                rep = db.query(models.Report).filter(
                    models.Report.id == f"{paper.id}::{system_id}").first()
                if rep is None:
                    continue
                tag = f"{paper_key}/{system_id}"
                if rep.content_version == r["content_version"]:
                    summary["unchanged"].append(tag)
                    continue
                task_ids = [t.id for t in all_tasks if rep.id in (t.report_a_id, t.report_b_id)]
                assigns = (db.query(models.Assignment)
                           .filter(models.Assignment.task_id.in_(task_ids)).all()
                           if task_ids else [])
                finals = ({f.assignment_id for f in db.query(models.FinalResponse).filter(
                    models.FinalResponse.assignment_id.in_([a.id for a in assigns]))}
                    if assigns else set())
                blocking = [a for a in assigns if a.id in finals or (
                    not people[a.participant_id].is_test
                    and (a.status != "not_started" or a.draft))]
                if blocking:
                    summary["kept_because_rated"].append(
                        {"report": tag, "content_version": rep.content_version,
                         "assignments": [(people[a.participant_id].code_display, a.status,
                                          a.id in finals) for a in blocking]})
                    continue
                for a in assigns:
                    if people[a.participant_id].is_test and (a.status != "not_started" or a.draft):
                        summary["test_drafts_affected"].append(
                            (tag, people[a.participant_id].code_display, a.status))
                row = {"report": tag, "old": rep.content_version, "new": r["content_version"]}
                if not dry_run:
                    content_entry = r.get("text_file") or r.get("content_file")
                    content_kind = "markdown" if r["view_type"] == "markdown" else "pdf"
                    content_asset = _put_asset(db, backend, sid, content_kind, content_entry,
                                               f"{paper_key}/{system_id}")
                    qidx_id = None
                    if r.get("quote_index_file"):
                        qidx_id = _put_asset(db, backend, sid, "json", r["quote_index_file"],
                                             f"{paper_key}/{system_id}.quote_index").id
                    row["old_asset"] = rep.content_asset_id
                    row["new_asset"] = content_asset.id
                    rep.content_asset_id = content_asset.id
                    rep.quote_index_asset_id = qidx_id
                    rep.content_version = r["content_version"]
                    rep.imported_at = datetime.now(timezone.utc)
                    db.add(models.AuditEvent(
                        id=models.new_id(), study_id=sid, actor="cli:refresh-reports",
                        event_type="report_content_replaced",
                        payload={**row, "manifest_git_head": manifest.get("git_head"),
                                 "reason": "no final response and no started or drafted "
                                           "assignment by a non-test participant"}))
                summary["replaced"].append(row)
        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    return summary

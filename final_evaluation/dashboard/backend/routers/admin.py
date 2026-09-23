"""Admin-only endpoints: study/participant overview, code reset, session lock, closing
the study, and the full research export. Every route depends on `current_admin`
(deps.py), which is `current_participant` plus a `role == "admin"` check -- an admin
session is a normal session for a Participant row with `role="admin"`, created only by
`cli.py create-admin`, never by self-service.

No system ranking is computed or returned here while a study is `active` (see
`overview()`): section 7 of the protocol is explicit that the standard admin screen must
not show one during data collection. `export_zip()` is the one place system identity and
a comparable ranking are legitimately produced, and it is a file download an admin
requests deliberately, not a number sitting on a dashboard screen.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, security
from ..deps import current_admin, get_db, require_csrf

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _csv_safe(v) -> str:
    """Neutralise formula injection: a cell starting with = + - @ is prefixed with a
    tab, which spreadsheet programs treat as inert text instead of a formula. Applied to
    every free-text field written into a CSV export (reasons, issue messages, notes)."""
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@"):
        return "\t" + s
    return s


@router.get("/overview")
def overview(db: Session = Depends(get_db), admin: models.Participant = Depends(current_admin)):
    study = db.query(models.Study).filter(models.Study.id == admin.study_id).first()
    participants = db.query(models.Participant).filter(
        models.Participant.study_id == admin.study_id, models.Participant.role == "participant").all()
    assignments = db.query(models.Assignment).filter(models.Assignment.study_id == admin.study_id).all()
    issues = db.query(models.TechnicalIssue).filter(
        models.TechnicalIssue.study_id == admin.study_id, models.TechnicalIssue.resolved == False).all()  # noqa: E712

    by_participant = {}
    for a in assignments:
        d = by_participant.setdefault(a.participant_id, {"not_started": 0, "in_progress": 0, "submitted": 0})
        d[a.status] = d.get(a.status, 0) + 1

    people = []
    for p in participants:
        counts = by_participant.get(p.id, {"not_started": 0, "in_progress": 0, "submitted": 0})
        total = sum(counts.values())
        people.append({
            "participant_id": p.id, "code_display": p.code_display, "is_test": p.is_test,
            "consented": p.consent_at is not None, "locked": security.is_locked(p.locked_until),
            "counts": counts, "total_assignments": total,
        })

    return {
        "study": {"id": study.id, "title": study.title, "status": study.status,
                  "is_pilot": study.is_pilot} if study else None,
        "participants": people,
        "open_technical_issues": len(issues),
        # No system-level ranking here -- see module docstring.
    }


@router.get("/technical-issues")
def technical_issues(db: Session = Depends(get_db), admin: models.Participant = Depends(current_admin)):
    rows = db.query(models.TechnicalIssue).filter(
        models.TechnicalIssue.study_id == admin.study_id).order_by(
        models.TechnicalIssue.created_at.desc()).all()
    return {"issues": [{"id": r.id, "participant_id": r.participant_id,
                        "assignment_id": r.assignment_id, "message": r.message,
                        "created_at": r.created_at.isoformat(), "resolved": r.resolved}
                       for r in rows]}


class ResolveIssueBody(BaseModel):
    issue_id: str


@router.post("/technical-issues/resolve", dependencies=[Depends(require_csrf)])
def resolve_issue(body: ResolveIssueBody, db: Session = Depends(get_db),
                  admin: models.Participant = Depends(current_admin)):
    row = db.query(models.TechnicalIssue).filter(
        models.TechnicalIssue.id == body.issue_id, models.TechnicalIssue.study_id == admin.study_id).first()
    if row is None:
        raise HTTPException(404, "issue not found")
    row.resolved = True
    db.commit()
    return {"ok": True}


class ResetCodeBody(BaseModel):
    participant_id: str


@router.post("/participants/reset-code", dependencies=[Depends(require_csrf)])
def reset_code(body: ResetCodeBody, db: Session = Depends(get_db),
              admin: models.Participant = Depends(current_admin)):
    from ..settings import get_settings
    p = db.query(models.Participant).filter(models.Participant.id == body.participant_id,
                                             models.Participant.study_id == admin.study_id).first()
    if p is None:
        raise HTTPException(404, "participant not found")
    new_code = security.generate_code(p.code_display)
    p.code_hash = security.hash_code(new_code, get_settings().access_code_pepper)
    p.failed_logins = 0
    p.locked_until = None
    db.query(models.Session_).filter(models.Session_.participant_id == p.id,
                                     models.Session_.revoked_at.is_(None)).update(
        {"revoked_at": datetime.now(timezone.utc)})
    db.add(models.AuditEvent(id=models.new_id(), study_id=admin.study_id, actor=f"admin:{admin.id}",
                             event_type="reset_code", payload={"participant_id": p.id}))
    db.commit()
    # Returned once, exactly like at creation time -- not stored anywhere in plaintext.
    return {"ok": True, "new_code": new_code, "code_display": p.code_display}


class LockBody(BaseModel):
    participant_id: str
    locked: bool


@router.post("/participants/lock", dependencies=[Depends(require_csrf)])
def lock_participant(body: LockBody, db: Session = Depends(get_db),
                     admin: models.Participant = Depends(current_admin)):
    p = db.query(models.Participant).filter(models.Participant.id == body.participant_id,
                                             models.Participant.study_id == admin.study_id).first()
    if p is None:
        raise HTTPException(404, "participant not found")
    if body.locked:
        p.locked_until = datetime.now(timezone.utc) + security.SESSION_TTL_PARTICIPANT  # far future
        db.query(models.Session_).filter(models.Session_.participant_id == p.id,
                                         models.Session_.revoked_at.is_(None)).update(
            {"revoked_at": datetime.now(timezone.utc)})
    else:
        p.locked_until = None
        p.failed_logins = 0
    db.add(models.AuditEvent(id=models.new_id(), study_id=admin.study_id, actor=f"admin:{admin.id}",
                             event_type="lock" if body.locked else "unlock",
                             payload={"participant_id": p.id}))
    db.commit()
    return {"ok": True}


class CloseStudyBody(BaseModel):
    confirm: str  # must equal the study id, so this cannot be triggered by a stray click


@router.post("/study/close", dependencies=[Depends(require_csrf)])
def close_study(body: CloseStudyBody, db: Session = Depends(get_db),
                admin: models.Participant = Depends(current_admin)):
    if body.confirm != admin.study_id:
        raise HTTPException(400, "confirm must equal the study id")
    study = db.query(models.Study).filter(models.Study.id == admin.study_id).first()
    study.status = "closed"
    db.add(models.AuditEvent(id=models.new_id(), study_id=admin.study_id, actor=f"admin:{admin.id}",
                             event_type="close_study"))
    db.commit()
    return {"ok": True, "status": study.status}


# --------------------------------------------------------------------------- #
# Full research export -- the ONLY place system identity + orientation are exposed.
# --------------------------------------------------------------------------- #

def _build_export(db: Session, study_id: str) -> bytes:
    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    papers = {p.id: p for p in db.query(models.Paper).filter(models.Paper.study_id == study_id)}
    reports = {r.id: r for r in db.query(models.Report).filter(models.Report.study_id == study_id)}
    tasks = {t.id: t for t in db.query(models.Task).filter(models.Task.study_id == study_id)}
    participants = {p.id: p for p in db.query(models.Participant).filter(
        models.Participant.study_id == study_id, models.Participant.role == "participant")}
    assignments = db.query(models.Assignment).filter(models.Assignment.study_id == study_id).all()
    finals = {f.assignment_id: f for f in db.query(models.FinalResponse).join(
        models.Assignment, models.Assignment.id == models.FinalResponse.assignment_id).filter(
        models.Assignment.study_id == study_id)}
    issues = db.query(models.TechnicalIssue).filter(models.TechnicalIssue.study_id == study_id).all()
    familiarity = db.query(models.PaperFamiliarity).filter(
        models.PaperFamiliarity.study_id == study_id).all()
    readings = {(r.participant_id, r.paper_id): r for r in db.query(models.PaperReading).filter(
        models.PaperReading.study_id == study_id)}

    ratings_jsonl_lines = []
    long_rows = []  # one row per task x rater x criterion
    assignments_rows = []
    completion_counter = {}  # participant_id -> {submitted, total}

    for a in assignments:
        t = tasks.get(a.task_id)
        paper = papers.get(t.paper_id) if t else None
        participant = participants.get(a.participant_id)
        if not (t and paper and participant):
            continue
        final = finals.get(a.id)
        # A/B -> real systems, using the FROZEN orientation on this assignment.
        sys_a, sys_b = ((t.system_a, t.system_b) if a.orientation == "forward"
                       else (t.system_b, t.system_a))
        rep_a, rep_b = ((t.report_a_id, t.report_b_id) if a.orientation == "forward"
                       else (t.report_b_id, t.report_a_id))

        completion_counter.setdefault(participant.id, {"submitted": 0, "total": 0})
        completion_counter[participant.id]["total"] += 1
        if final:
            completion_counter[participant.id]["submitted"] += 1

        criteria = (final.criteria if final else a.draft) or {}
        record = {
            "study_id": study_id, "assignment_id": a.id, "task_id": t.id,
            "paper_id": paper.paper_key, "pair_key": t.pair_key,
            "system_a": sys_a, "system_b": sys_b,
            "report_a_id": rep_a, "report_b_id": rep_b, "orientation": a.orientation,
            "participant_id": participant.id, "participant_code": participant.code_display,
            "is_test_participant": participant.is_test, "is_practice": a.is_practice,
            "status": a.status, "revision": a.revision,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "active_ms": a.active_ms,
            "receipt_id": final.receipt_id if final else None,
            "submitted_at": final.submitted_at.isoformat() if final else None,
            "criteria": criteria,
        }
        ratings_jsonl_lines.append(json.dumps(record, ensure_ascii=False))

        assignments_rows.append([a.id, t.id, paper.paper_key, sys_a, sys_b, a.orientation,
                                 participant.code_display, a.is_practice, a.status])

        for key, c in (criteria or {}).items():
            if key not in ("submission_fidelity", "comparison_specificity", "presented_evidence",
                          "conclusion_warrant", "reviewer_usefulness"):
                continue
            winner_system = None
            if c.get("winner") == "A":
                winner_system = sys_a
            elif c.get("winner") == "B":
                winner_system = sys_b
            long_rows.append([
                study_id, t.id, paper.paper_key, sys_a, sys_b, participant.code_display,
                key, c.get("winner"), winner_system, _csv_safe(c.get("reason")),
                c.get("unclear_reason") or "", a.status,
            ])

    completion_rows = [[participants[pid].code_display, d["submitted"], d["total"]]
                       for pid, d in completion_counter.items()]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ratings.jsonl", "\n".join(ratings_jsonl_lines) + ("\n" if ratings_jsonl_lines else ""))

        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["study_id", "task_id", "paper_id", "system_a", "system_b", "participant_code",
                   "criterion", "winner_ab", "winner_system", "reason", "unclear_reason", "status"])
        w.writerows(long_rows)
        z.writestr("ratings_long.csv", out.getvalue())

        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["assignment_id", "task_id", "paper_id", "system_a", "system_b", "orientation",
                   "participant_code", "is_practice", "status"])
        w.writerows(assignments_rows)
        z.writestr("assignments.csv", out.getvalue())

        tasks_out = [{"task_id": t.id, "paper_id": papers[t.paper_id].paper_key,
                     "system_a": t.system_a, "system_b": t.system_b, "pair_key": t.pair_key,
                     "is_practice": t.is_practice} for t in tasks.values()]
        z.writestr("tasks.json", json.dumps(tasks_out, ensure_ascii=False, indent=1))

        manifest = {"study_id": study_id, "rubric_version": study.rubric_version if study else None,
                   "instructions_version": study.instructions_version if study else None,
                   "ui_version": study.ui_version if study else None,
                   "assignment_seed": study.assignment_seed if study else None,
                   "exported_at": datetime.now(timezone.utc).isoformat(),
                   "reports": [{"report_id": r.id, "paper_id": papers[r.paper_id].paper_key,
                               "system_id": r.system_id, "content_version": r.content_version}
                              for r in reports.values() if r.paper_id in papers]}
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))

        try:
            from pathlib import Path
            rubric_path = (Path(__file__).resolve().parents[3] / "prompts"
                           / f"{study.rubric_version if study else 'novelty_report_judge_v3'}.txt")
            z.writestr("rubric.txt", rubric_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        try:
            from pathlib import Path
            protocol_path = Path(__file__).resolve().parents[3] / "PROTOCOL.md"
            z.writestr("protocol.md", protocol_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["issue_id", "participant_code", "assignment_id", "message", "created_at", "resolved"])
        for i in issues:
            pcode = participants.get(i.participant_id).code_display if i.participant_id in participants else ""
            w.writerow([i.id, pcode, i.assignment_id or "", _csv_safe(i.message),
                       i.created_at.isoformat(), i.resolved])
        z.writestr("technical_issues.csv", out.getvalue())

        # One row per participant x paper: the two background answers (asked once per
        # paper) and, in a non-pilot study, the reading step before the paper's tasks.
        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["participant_code", "is_test_participant", "paper_id", "familiarity",
                    "read_before", "familiarity_at", "reading_opened_at", "reading_confirmed_at",
                    "reading_active_ms"])
        keys = {(f.participant_id, f.paper_id) for f in familiarity} | set(readings)
        fam_by = {(f.participant_id, f.paper_id): f for f in familiarity}
        for pid, paper_id in sorted(keys):
            if pid not in participants or paper_id not in papers:
                continue
            f = fam_by.get((pid, paper_id)); r = readings.get((pid, paper_id))
            w.writerow([participants[pid].code_display, participants[pid].is_test,
                        papers[paper_id].paper_key,
                        f.familiarity if f else "", f.read_before if f else "",
                        f.created_at.isoformat() if f else "",
                        r.opened_at.isoformat() if r and r.opened_at else "",
                        r.confirmed_at.isoformat() if r and r.confirmed_at else "",
                        r.active_ms if r else ""])
        z.writestr("paper_background.csv", out.getvalue())

        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["participant_code", "submitted", "total_assigned"])
        w.writerows(completion_rows)
        z.writestr("completion.csv", out.getvalue())

        # The raters' own background (asked once, at consent) -- needed to describe the
        # rater pool; the codes stay pseudonymous.
        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["participant_code", "is_test_participant", "review_experience",
                    "system_involvement", "system_involvement_note", "consent_at",
                    "consent_instructions_sha256"])
        for pt in sorted(participants.values(), key=lambda x: x.code_display):
            w.writerow([pt.code_display, pt.is_test, pt.review_experience or "",
                        pt.system_involvement or "", _csv_safe(pt.system_involvement_note),
                        pt.consent_at.isoformat() if pt.consent_at else "",
                        pt.consent_instructions_sha256 or ""])
        z.writestr("participants.csv", out.getvalue())

    return buf.getvalue()


@router.get("/export")
def export_zip(db: Session = Depends(get_db), admin: models.Participant = Depends(current_admin)):
    data = _build_export(db, admin.study_id)
    db.add(models.AuditEvent(id=models.new_id(), study_id=admin.study_id, actor=f"admin:{admin.id}",
                             event_type="export"))
    db.commit()
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{admin.study_id}_export.zip"'})

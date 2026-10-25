"""Participant endpoints: consent, tasks, autosave, submit, familiarity, technical issues and data export."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, security
from ..deps import SESSION_COOKIE, current_participant, get_db, require_csrf
from ..settings import get_settings as get_settings

router = APIRouter(prefix="/api", tags=["participant"])


@router.get("/public/config")
def public_config():
    """Unauthenticated configuration for the login page."""
    return {"study_contact": get_settings().study_contact}

CRITERIA_KEYS = ("submission_fidelity", "comparison_specificity", "presented_evidence",
                "conclusion_warrant", "reviewer_usefulness")
WINNER_VALUES = {"A", "B", "tie", "unclear"}
UNCLEAR_REASONS = {"Insufficient report evidence", "Insufficient domain expertise",
                   "Ambiguous criterion", "Other"}
IDLE_CAP_S = 120

_ACTIVE_LOCK_STATUS = {"submitted"}


def _audit(db: Session, study_id: str, actor: str, event_type: str, payload: dict | None = None):
    db.add(models.AuditEvent(id=models.new_id(), study_id=study_id, actor=actor,
                             event_type=event_type, payload=payload))



class LoginBody(BaseModel):
    code: str = Field(min_length=4, max_length=120)


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    if security.ip_rate_limited(ip):
        raise HTTPException(429, "too many login attempts from this address, try again shortly")

    code = body.code.strip()
    display = code.split("-", 1)[0] if "-" in code else code
    candidates = db.query(models.Participant).filter(models.Participant.code_display == display).all()

    match = None
    for p in candidates:
        if security.is_locked(p.locked_until):
            continue
        if security.codes_match(code, p.code_hash, settings.access_code_pepper):
            match = p
            break

    if match is None:
        for p in candidates:
            if not security.is_locked(p.locked_until):
                p.failed_logins += 1
                locked = security.lockout_after_failure(p.failed_logins)
                if locked:
                    p.locked_until = locked
        db.commit()
        raise HTTPException(401, "invalid access code")

    match.failed_logins = 0
    match.locked_until = None
    token = security.new_session_token()
    ttl = security.SESSION_TTL_ADMIN if match.role == "admin" else security.SESSION_TTL_PARTICIPANT
    sess = models.Session_(id=models.new_id(), participant_id=match.id,
                           token_hash=security.hash_token(token),
                           expires_at=datetime.now(timezone.utc) + ttl,
                           user_agent=(request.headers.get("user-agent") or "")[:300])
    db.add(sess)
    _audit(db, match.study_id, match.id, "login")
    db.commit()

    csrf = security.new_csrf_token()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=int(ttl.total_seconds()))
    response.set_cookie("fe_csrf", csrf, httponly=False, samesite="lax",
                        secure=settings.cookie_secure, max_age=int(ttl.total_seconds()))
    return {"participant_id": match.id, "code_display": match.code_display, "role": match.role,
           "csrf": csrf}


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response, db: Session = Depends(get_db),
          participant: models.Participant = Depends(current_participant),
          fe_session: str | None = None):
    db.query(models.Session_).filter(models.Session_.participant_id == participant.id,
                                     models.Session_.revoked_at.is_(None)).update(
        {"revoked_at": datetime.now(timezone.utc)})
    _audit(db, participant.study_id, participant.id, "logout")
    db.commit()
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie("fe_csrf")
    return {"ok": True}


@router.get("/me")
def me(db: Session = Depends(get_db), participant: models.Participant = Depends(current_participant)):
    study = db.query(models.Study).get(participant.study_id)
    return {
        "participant_id": participant.id, "code_display": participant.code_display,
        "role": participant.role, "study_id": participant.study_id,
        "study_title": study.title if study else "", "is_pilot": study.is_pilot if study else True,
        "consented": participant.consent_at is not None,
        "instructions_version": study.instructions_version if study else None,
        "study_contact": get_settings().study_contact,
    }



class ConsentBody(BaseModel):
    accept: bool
    instructions_sha256: str
    review_experience: str | None = None
    system_involvement: str | None = None
    system_involvement_note: str | None = None


@router.post("/consent", dependencies=[Depends(require_csrf)])
def consent(body: ConsentBody, db: Session = Depends(get_db),
           participant: models.Participant = Depends(current_participant)):
    if not body.accept:
        raise HTTPException(400, "consent not accepted")
    participant.consent_at = datetime.now(timezone.utc)
    participant.consent_instructions_sha256 = body.instructions_sha256
    participant.review_experience = body.review_experience
    participant.system_involvement = body.system_involvement
    participant.system_involvement_note = (body.system_involvement_note or "")[:2000]
    _audit(db, participant.study_id, participant.id, "consent", {
        "instructions_sha256": body.instructions_sha256})
    db.commit()
    return {"ok": True}



def _reading_required(db: Session, participant: models.Participant) -> bool:
    study = db.query(models.Study).get(participant.study_id)
    return bool(study) and not study.is_pilot


def _reading(db: Session, participant_id: str, paper_id: str) -> models.PaperReading | None:
    return (db.query(models.PaperReading)
            .filter(models.PaperReading.participant_id == participant_id,
                    models.PaperReading.paper_id == paper_id).first())


def _gate_open(db: Session, participant: models.Participant, paper_id: str) -> bool:
    if not _reading_required(db, participant):
        return True
    r = _reading(db, participant.id, paper_id)
    return r is not None and r.confirmed_at is not None


def _enforce_gate(db: Session, participant: models.Participant, a: models.Assignment) -> None:
    """A submitted task stays viewable read-only; anything else waits for the reading."""
    if a.status == "submitted":
        return
    paper_id = db.query(models.Task.paper_id).filter(models.Task.id == a.task_id).scalar()
    if not _gate_open(db, participant, paper_id):
        raise HTTPException(409, {"error": "read_submission_first", "paper_id": paper_id})


def _owns_paper(db: Session, participant: models.Participant, paper_id: str) -> bool:
    return (db.query(models.Assignment)
            .join(models.Task, models.Task.id == models.Assignment.task_id)
            .filter(models.Assignment.participant_id == participant.id,
                    models.Task.paper_id == paper_id).first()) is not None



def _paper_view(db: Session, paper: models.Paper) -> dict:
    return {"paper_id": paper.id, "title": paper.title,
           "submission_pdf_asset_id": paper.submission_pdf_asset_id,
           "submission_text_asset_id": paper.submission_text_asset_id}


def _report_view(db: Session, report: models.Report) -> dict:
    """A report as participants see it, without system_id."""
    return {"report_ref": report.id, "view_type": report.view_type,
           "content_asset_id": report.content_asset_id,
           "quote_index_asset_id": report.quote_index_asset_id}


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db),
              participant: models.Participant = Depends(current_participant)):
    rows = (db.query(models.Assignment, models.Task, models.Paper)
           .join(models.Task, models.Task.id == models.Assignment.task_id)
           .join(models.Paper, models.Paper.id == models.Task.paper_id)
           .filter(models.Assignment.participant_id == participant.id)
           .order_by(models.Assignment.order_index.asc()).all())
    required = _reading_required(db, participant)
    confirmed = {r.paper_id for r in db.query(models.PaperReading).filter(
        models.PaperReading.participant_id == participant.id,
        models.PaperReading.confirmed_at.isnot(None))}
    out = []
    for a, t, paper in rows:
        out.append({
            "assignment_id": a.id, "paper_id": paper.id, "paper_title": paper.title,
            "status": a.status, "order_index": a.order_index, "is_practice": a.is_practice,
            "paper_read_confirmed": paper.id in confirmed,
        })
    return {"tasks": out, "reading_required": required}


@router.get("/tasks/{assignment_id}")
def get_task(assignment_id: str, db: Session = Depends(get_db),
            participant: models.Participant = Depends(current_participant)):
    a = db.query(models.Assignment).filter(models.Assignment.id == assignment_id,
                                           models.Assignment.participant_id == participant.id).first()
    if a is None:
        raise HTTPException(404, "task not found")
    _enforce_gate(db, participant, a)
    t = db.query(models.Task).get(a.task_id)
    paper = db.query(models.Paper).get(t.paper_id)
    rep_a_id, rep_b_id = ((t.report_a_id, t.report_b_id) if a.orientation == "forward"
                          else (t.report_b_id, t.report_a_id))
    rep_a = db.query(models.Report).get(rep_a_id)
    rep_b = db.query(models.Report).get(rep_b_id)

    fam = (db.query(models.PaperFamiliarity)
          .filter(models.PaperFamiliarity.participant_id == participant.id,
                  models.PaperFamiliarity.paper_id == paper.id).first())

    final = db.query(models.FinalResponse).filter(models.FinalResponse.assignment_id == a.id).first()

    return {
        "assignment_id": a.id, "status": a.status, "revision": a.revision,
        "is_practice": a.is_practice,
        "paper": _paper_view(db, paper),
        "report_a": _report_view(db, rep_a), "report_b": _report_view(db, rep_b),
        "familiarity": ({"familiarity": fam.familiarity, "read_before": fam.read_before}
                       if fam else None),
        "draft": a.draft,
        "final": ({"criteria": final.criteria, "receipt_id": final.receipt_id,
                  "submitted_at": final.submitted_at.isoformat()} if final else None),
        "criteria_keys": list(CRITERIA_KEYS),
    }



class FamiliarityBody(BaseModel):
    paper_id: str
    familiarity: str
    read_before: bool


@router.post("/familiarity", dependencies=[Depends(require_csrf)])
def set_familiarity(body: FamiliarityBody, db: Session = Depends(get_db),
                    participant: models.Participant = Depends(current_participant)):
    if body.familiarity not in ("low", "moderate", "high"):
        raise HTTPException(400, "invalid familiarity value")
    if not _owns_paper(db, participant, body.paper_id):
        raise HTTPException(404, "paper not found")
    existing = (db.query(models.PaperFamiliarity)
               .filter(models.PaperFamiliarity.participant_id == participant.id,
                       models.PaperFamiliarity.paper_id == body.paper_id).first())
    if existing:
        return {"ok": True, "already_recorded": True}
    db.add(models.PaperFamiliarity(id=models.new_id(), study_id=participant.study_id,
                                   participant_id=participant.id, paper_id=body.paper_id,
                                   familiarity=body.familiarity, read_before=body.read_before))
    db.commit()
    return {"ok": True, "already_recorded": False}



def _reading_view(db: Session, participant: models.Participant, paper: models.Paper) -> dict:
    fam = (db.query(models.PaperFamiliarity)
           .filter(models.PaperFamiliarity.participant_id == participant.id,
                   models.PaperFamiliarity.paper_id == paper.id).first())
    r = _reading(db, participant.id, paper.id)
    return {
        "paper": _paper_view(db, paper),
        "reading_required": _reading_required(db, participant),
        "familiarity": ({"familiarity": fam.familiarity, "read_before": fam.read_before}
                        if fam else None),
        "reading": ({"opened_at": r.opened_at.isoformat() if r.opened_at else None,
                     "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None}
                    if r else None),
    }


def _owned_paper_or_404(db: Session, participant: models.Participant, paper_id: str) -> models.Paper:
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id,
                                          models.Paper.study_id == participant.study_id).first()
    if paper is None or not _owns_paper(db, participant, paper_id):
        raise HTTPException(404, "paper not found")
    return paper


@router.get("/papers/{paper_id}/reading")
def get_reading(paper_id: str, db: Session = Depends(get_db),
                participant: models.Participant = Depends(current_participant)):
    paper = _owned_paper_or_404(db, participant, paper_id)
    return _reading_view(db, participant, paper)


@router.post("/papers/{paper_id}/reading/open", dependencies=[Depends(require_csrf)])
def open_reading(paper_id: str, db: Session = Depends(get_db),
                 participant: models.Participant = Depends(current_participant)):
    """Record the first visit to the reading page."""
    paper = _owned_paper_or_404(db, participant, paper_id)
    if _reading(db, participant.id, paper.id) is None:
        db.add(models.PaperReading(id=models.new_id(), study_id=participant.study_id,
                                   participant_id=participant.id, paper_id=paper.id))
        db.commit()
    return _reading_view(db, participant, paper)


class ReadingConfirmBody(BaseModel):
    active_ms: int = Field(default=0, ge=0, le=7 * 24 * 3600 * 1000)


@router.post("/papers/{paper_id}/reading/confirm", dependencies=[Depends(require_csrf)])
def confirm_reading(paper_id: str, body: ReadingConfirmBody, db: Session = Depends(get_db),
                    participant: models.Participant = Depends(current_participant)):
    """Unlock the paper's tasks once the background questions are answered. Repeated confirmations keep the first timestamp."""
    paper = _owned_paper_or_404(db, participant, paper_id)
    fam = (db.query(models.PaperFamiliarity)
           .filter(models.PaperFamiliarity.participant_id == participant.id,
                   models.PaperFamiliarity.paper_id == paper.id).first())
    if fam is None:
        raise HTTPException(422, "answer the two background questions first")
    r = _reading(db, participant.id, paper.id)
    if r is None:
        r = models.PaperReading(id=models.new_id(), study_id=participant.study_id,
                                participant_id=participant.id, paper_id=paper.id)
        db.add(r)
    if r.confirmed_at is None:
        r.confirmed_at = datetime.now(timezone.utc)
        r.active_ms = body.active_ms
        _audit(db, participant.study_id, participant.id, "paper_read_confirmed",
               {"paper_id": paper.id, "active_ms": body.active_ms})
    db.commit()
    return _reading_view(db, participant, paper)



def _validate_criteria(criteria: dict, require_complete: bool) -> list[str]:
    problems = []
    for key in CRITERIA_KEYS:
        c = criteria.get(key) or {}
        winner = c.get("winner")
        reason = (c.get("reason") or "").strip()
        if require_complete or winner or reason:
            if winner not in WINNER_VALUES:
                problems.append(f"{key}: winner must be one of {sorted(WINNER_VALUES)}")
            if reason and len(reason.split()) > 50:
                problems.append(f"{key}: reason exceeds 50 words")
            if winner == "unclear":
                if (c.get("unclear_reason") not in UNCLEAR_REASONS) and require_complete:
                    problems.append(f"{key}: unclear_reason is required when winner is unclear")
    return problems


class DraftBody(BaseModel):
    criteria: dict
    expected_revision: int
    idempotency_key: str


def _touch_activity(a: models.Assignment) -> None:
    now = datetime.now(timezone.utc)
    if a.started_at is None:
        a.started_at = now
    if a.last_activity_at is not None:
        last = a.last_activity_at if a.last_activity_at.tzinfo else a.last_activity_at.replace(tzinfo=timezone.utc)
        gap = (now - last).total_seconds()
        a.active_ms += int(min(max(gap, 0), IDLE_CAP_S) * 1000)
    a.last_activity_at = now


@router.post("/tasks/{assignment_id}/draft", dependencies=[Depends(require_csrf)])
def save_draft(assignment_id: str, body: DraftBody, db: Session = Depends(get_db),
              participant: models.Participant = Depends(current_participant)):
    a = db.query(models.Assignment).filter(models.Assignment.id == assignment_id,
                                           models.Assignment.participant_id == participant.id).first()
    if a is None:
        raise HTTPException(404, "task not found")
    if a.status == "submitted":
        raise HTTPException(409, "task already submitted -- draft cannot be changed")
    _enforce_gate(db, participant, a)
    if a.revision != body.expected_revision:
        return Response(status_code=409, content=json.dumps({
            "error": "revision_conflict", "server_revision": a.revision, "server_draft": a.draft,
        }), media_type="application/json")

    problems = _validate_criteria(body.criteria, require_complete=False)
    if problems:
        raise HTTPException(422, {"validation_errors": problems})

    a.draft = body.criteria
    a.status = "in_progress" if a.status == "not_started" else a.status
    a.revision += 1
    _touch_activity(a)
    db.commit()
    return {"ok": True, "revision": a.revision, "status": a.status}



class SubmitBody(BaseModel):
    criteria: dict
    expected_revision: int
    idempotency_key: str


@router.post("/tasks/{assignment_id}/submit", dependencies=[Depends(require_csrf)])
def submit_task(assignment_id: str, body: SubmitBody, db: Session = Depends(get_db),
                participant: models.Participant = Depends(current_participant)):
    a = db.query(models.Assignment).filter(models.Assignment.id == assignment_id,
                                           models.Assignment.participant_id == participant.id).first()
    if a is None:
        raise HTTPException(404, "task not found")

    existing = db.query(models.FinalResponse).filter(
        models.FinalResponse.assignment_id == a.id).first()
    if existing is not None:
        if existing.idempotency_key == body.idempotency_key:
            return {"ok": True, "receipt_id": existing.receipt_id,
                   "submitted_at": existing.submitted_at.isoformat(), "already_final": True}
        raise HTTPException(409, "task already submitted")

    if a.status == "submitted":
        raise HTTPException(409, "task already submitted")
    _enforce_gate(db, participant, a)
    if a.revision != body.expected_revision:
        raise HTTPException(409, {"error": "revision_conflict", "server_revision": a.revision})

    problems = _validate_criteria(body.criteria, require_complete=True)
    if problems:
        raise HTTPException(422, {"validation_errors": problems})

    paper_id = db.query(models.Task.paper_id).filter(models.Task.id == a.task_id).scalar()
    fam = (db.query(models.PaperFamiliarity)
          .filter(models.PaperFamiliarity.participant_id == participant.id,
                  models.PaperFamiliarity.paper_id == paper_id).first())
    if fam is None:
        raise HTTPException(422, "paper familiarity must be recorded before submitting")

    receipt = security.new_receipt_id()
    _touch_activity(a)
    a.draft = body.criteria
    a.status = "submitted"
    a.revision += 1

    db.add(models.FinalResponse(id=models.new_id(), assignment_id=a.id, criteria=body.criteria,
                                receipt_id=receipt, idempotency_key=body.idempotency_key,
                                revision=a.revision))
    _audit(db, participant.study_id, participant.id, "submit", {"assignment_id": a.id,
                                                                "receipt_id": receipt})
    db.commit()
    return {"ok": True, "receipt_id": receipt,
           "submitted_at": datetime.now(timezone.utc).isoformat(), "already_final": False}



class IssueBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    assignment_id: str | None = None


@router.post("/issues", dependencies=[Depends(require_csrf)])
def report_issue(body: IssueBody, db: Session = Depends(get_db),
                 participant: models.Participant = Depends(current_participant)):
    if body.assignment_id:
        owns = db.query(models.Assignment).filter(
            models.Assignment.id == body.assignment_id,
            models.Assignment.participant_id == participant.id).first()
        if owns is None:
            raise HTTPException(404, "task not found")
    db.add(models.TechnicalIssue(id=models.new_id(), study_id=participant.study_id,
                                 participant_id=participant.id, assignment_id=body.assignment_id,
                                 message=body.message))
    db.commit()
    return {"ok": True}



@router.get("/export/mine")
def export_mine(db: Session = Depends(get_db),
                participant: models.Participant = Depends(current_participant)):
    rows = (db.query(models.Assignment, models.Task, models.Paper, models.FinalResponse)
           .join(models.Task, models.Task.id == models.Assignment.task_id)
           .join(models.Paper, models.Paper.id == models.Task.paper_id)
           .outerjoin(models.FinalResponse, models.FinalResponse.assignment_id == models.Assignment.id)
           .filter(models.Assignment.participant_id == participant.id).all())
    out = []
    for a, t, paper, final in rows:
        out.append({
            "paper_title": paper.title, "status": a.status,
            "receipt_id": final.receipt_id if final else None,
            "submitted_at": final.submitted_at.isoformat() if final else None,
            "criteria": (final.criteria if final else a.draft),
        })
    return {"participant_code": participant.code_display, "responses": out}

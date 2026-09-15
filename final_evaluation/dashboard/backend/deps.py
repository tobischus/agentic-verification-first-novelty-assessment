"""FastAPI dependencies: a DB session per request, the authenticated participant (if
any), and a CSRF check for mutating requests. Every router imports these rather than
touching cookies or the session table directly -- one place decides "who is this
request", so an authorization bug cannot come from one endpoint reading the cookie
differently than another.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from . import models, security
from .settings import Settings, get_settings

SESSION_COOKIE = "fe_session"
CSRF_HEADER = "x-fe-csrf"


def get_db(request: Request):
    db: Session = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def get_settings_dep() -> Settings:
    return get_settings()


def current_participant(
    fe_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> models.Participant:
    if not fe_session:
        raise HTTPException(401, "not logged in")
    token_hash = security.hash_token(fe_session)
    sess = db.query(models.Session_).filter(models.Session_.token_hash == token_hash).first()
    if sess is None or sess.revoked_at is not None:
        raise HTTPException(401, "session invalid")
    now = datetime.now(timezone.utc)
    exp = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
    if exp < now:
        raise HTTPException(401, "session expired")
    p = db.query(models.Participant).filter(models.Participant.id == sess.participant_id).first()
    if p is None:
        raise HTTPException(401, "session invalid")
    return p


def current_admin(p: models.Participant = Depends(current_participant)) -> models.Participant:
    if p.role != "admin":
        raise HTTPException(403, "admin access required")
    return p


def require_csrf(
    request: Request,
    x_fe_csrf: str | None = Header(default=None, alias=CSRF_HEADER),
    fe_csrf: str | None = Cookie(default=None, alias="fe_csrf"),
):
    """Double-submit CSRF check for cookie-authenticated mutating requests. The session
    cookie alone is not enough (that's exactly what CSRF exploits -- the browser sends
    it automatically); the header must be read by JS from a non-HttpOnly cookie the
    frontend echoes back, which a cross-site form post cannot do."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not fe_csrf or not x_fe_csrf or fe_csrf != x_fe_csrf:
        raise HTTPException(403, "csrf check failed")

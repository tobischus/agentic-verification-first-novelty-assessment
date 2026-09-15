"""One endpoint serves every asset -- submission PDFs, report text/PDF, quote indexes --
because one endpoint is one place to get authorization right, instead of N endpoints
that each have to remember to check it. See deps.py / current_participant for how the
session cookie resolves to a participant; this module adds the per-asset ownership check
on top: a participant may fetch an asset only if it is reachable from one of THEIR
assignments (a Task whose Report or Paper references it) -- never by asset id alone.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models, storage
from ..deps import current_participant, get_db

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _participant_may_access(db: Session, participant: models.Participant, asset_id: str) -> bool:
    """True iff `asset_id` is reachable from one of this participant's assignments.

    Admins bypass this (see admin.py's own asset route) -- this function is for the
    participant-facing endpoint only, and intentionally does not special-case role, so a
    participant account can never read another participant's-only-visible asset even if
    one existed (today all assets on a task are visible to whoever holds that task).
    """
    task_ids = [row[0] for row in db.query(models.Assignment.task_id)
               .filter(models.Assignment.participant_id == participant.id).all()]
    if not task_ids:
        return False
    tasks = db.query(models.Task).filter(models.Task.id.in_(task_ids)).all()
    report_ids = {t.report_a_id for t in tasks} | {t.report_b_id for t in tasks}
    paper_ids = {t.paper_id for t in tasks}
    if report_ids:
        reports = db.query(models.Report).filter(models.Report.id.in_(report_ids)).all()
        for r in reports:
            if r.content_asset_id == asset_id or r.quote_index_asset_id == asset_id:
                return True
    if paper_ids:
        papers = db.query(models.Paper).filter(models.Paper.id.in_(paper_ids)).all()
        for p in papers:
            if p.submission_pdf_asset_id == asset_id or p.submission_text_asset_id == asset_id:
                return True
    return False


def _serve(request, asset: models.Asset):
    backend = storage.backend_from_env()
    if asset.kind in ("markdown", "json"):
        resolved = backend.resolve(asset.storage_key, asset.content_type)
        if resolved.kind == "redirect":
            return RedirectResponse(resolved.url)
        text = resolved.path.read_text(encoding="utf-8")
        media = "application/json" if asset.kind == "json" else "text/plain; charset=utf-8"
        return PlainTextResponse(text, media_type=media)
    resolved = backend.resolve(asset.storage_key, asset.content_type)
    if resolved.kind == "redirect":
        return RedirectResponse(resolved.url)
    return FileResponse(resolved.path, media_type=asset.content_type,
                        filename=f"{asset.id}{resolved.path.suffix}")


@router.get("/{asset_id}")
def get_asset(asset_id: str, request=None, db: Session = Depends(get_db),
             participant: models.Participant = Depends(current_participant)):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if asset is None:
        raise HTTPException(404, "asset not found")
    if participant.role != "admin" and not _participant_may_access(db, participant, asset_id):
        # A prior-work PDF is never wired to any Paper/Report asset field in the first
        # place (import_pilot.py never imports one), so there is no asset id that would
        # even need blocking here -- the boundary is enforced by what gets IMPORTED, not
        # by a blocklist of forbidden ids. This branch is the general "not yours" case.
        raise HTTPException(403, "not authorized for this asset")
    try:
        return _serve(request, asset)
    except FileNotFoundError:
        raise HTTPException(404, "asset file missing on this server")

"""One endpoint serves every asset, so authorization is checked in one place."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models, storage
from ..deps import current_participant, get_db

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _participant_may_access(db: Session, participant: models.Participant, asset_id: str) -> bool:
    """True if the asset belongs to one of the participant's assignments."""
    task_ids = [
        row[0]
        for row in db.query(models.Assignment.task_id)
        .filter(models.Assignment.participant_id == participant.id)
        .all()
    ]
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


def _serve(asset: models.Asset):
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
    return FileResponse(
        resolved.path, media_type=asset.content_type, filename=f"{asset.id}{resolved.path.suffix}"
    )


@router.get("/{asset_id}")
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    participant: models.Participant = Depends(current_participant),
):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if asset is None:
        raise HTTPException(404, "asset not found")
    if participant.role != "admin" and not _participant_may_access(db, participant, asset_id):
        raise HTTPException(403, "not authorized for this asset")
    try:
        return _serve(asset)
    except FileNotFoundError:
        raise HTTPException(404, "asset file missing on this server")

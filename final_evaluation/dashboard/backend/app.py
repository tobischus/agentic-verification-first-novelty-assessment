"""The study app: FastAPI serving the study API and the built frontend from one origin."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db as db_mod
from .routers import admin, assets, participant
from .settings import get_settings

FE_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = FE_ROOT / "dashboard" / "frontend" / "dist"


def create_app() -> FastAPI:
    settings = get_settings()
    problems = settings.require_for_start()
    if problems:
        joined = "\n  - ".join(problems)
        raise RuntimeError(
            f"final_evaluation cannot start in APP_ENV={settings.app_env!r}:\n  - {joined}\n"
            "Fix these in final_evaluation/.env (copy from .env.example) and retry. "
            "See final_evaluation/README.md.")

    app = FastAPI(title="Novelty Report Evaluation Dashboard", docs_url=None, redoc_url=None)

    engine = db_mod.make_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = db_mod.make_session_factory(engine)
    app.state.settings = settings

    app.include_router(participant.router)
    app.include_router(admin.router)
    app.include_router(assets.router)

    @app.get("/api/health")
    def health():
        return {"ok": True, "app_env": settings.app_env, "storage_backend": settings.storage_backend}

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        print(f"[unhandled] {request.method} {request.url.path}: {exc!r}", file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    if FRONTEND_DIST.is_dir():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": "not_found"})
            revalidate = {"Cache-Control": "no-cache"}
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate, headers=revalidate)
            return FileResponse(FRONTEND_DIST / "index.html", headers=revalidate)
    else:
        @app.get("/")
        def no_frontend():
            return JSONResponse(status_code=503, content={
                "error": "frontend_not_built",
                "hint": "run: python -m final_evaluation.cli build-frontend",
            })

    return app

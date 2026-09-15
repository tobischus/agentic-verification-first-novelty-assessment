"""Engine, session factory, and a small portable migration runner.

One SQLAlchemy model definition (models.py) targets both SQLite (local dev,
`final_evaluation/private/local_study.sqlite`) and PostgreSQL (Supabase, cloud). No
per-backend fork of the schema or the queries exists anywhere in this package — the
portability requirement is met by NOT writing dialect-specific SQL, not by maintaining
two copies.

Migrations are plain Python functions rather than raw `.sql` files on purpose: SQLite and
PostgreSQL disagree on enough DDL (autoincrement syntax, native ENUM, etc.) that a single
`.sql` file is not actually portable, and maintaining two dialects of hand-written SQL is
exactly the "separate fachliche Implementierung" the brief rules out. Each migration gets
`Base.metadata` and a `Connection` and applies its change with SQLAlchemy Core, which
compiles to the right dialect for whichever engine it's given. Applied migrations are
recorded in `schema_migrations`, so re-running `init-db` is a no-op after the first time
and this doubles as a lightweight "have I already got the current schema?" check.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from . import models

MIGRATIONS_PACKAGE = "final_evaluation.dashboard.migrations"


def make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        # check_same_thread=False: FastAPI's threadpool may hand a request to a
        # different thread than the one that opened the file-based connection; the ORM
        # session itself is not shared across threads, only the pooled engine is.
        connect_args = {"check_same_thread": False}
        Path(database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    # A small, explicit pool: Supabase's free-tier pooler has few connections to hand
    # out, and a Render free instance runs one worker anyway -- there is no benefit to
    # a large local pool and a real cost to exhausting the shared one.
    kwargs = dict(connect_args=connect_args, future=True)
    if not database_url.startswith("sqlite"):
        kwargs.update(pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300)
    return create_engine(database_url, **kwargs)


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _ensure_migration_table(conn) -> None:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "id VARCHAR(64) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"
    ))


def _applied(conn) -> set:
    _ensure_migration_table(conn)
    return {row[0] for row in conn.execute(text("SELECT id FROM schema_migrations"))}


def _discover_migrations():
    """(migration_id, module) pairs, sorted by id -- filename order is the apply order."""
    pkg = importlib.import_module(MIGRATIONS_PACKAGE)
    out = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{MIGRATIONS_PACKAGE}.{info.name}")
        out.append((info.name, mod))
    return out


def run_migrations(engine) -> list:
    """Apply every not-yet-applied migration, in filename order. Returns ids applied."""
    applied_now = []
    with engine.begin() as conn:
        already = _applied(conn)
        for mig_id, mod in _discover_migrations():
            if mig_id in already:
                continue
            if not hasattr(mod, "upgrade"):
                continue
            mod.upgrade(conn)
            conn.execute(
                text("INSERT INTO schema_migrations (id, applied_at) VALUES (:id, :ts)"),
                {"id": mig_id, "ts": __import__("datetime").datetime.utcnow().isoformat()},
            )
            applied_now.append(mig_id)
    return applied_now


def session_scope(factory: sessionmaker) -> Iterator[Session]:
    db = factory()
    try:
        yield db
    finally:
        db.close()

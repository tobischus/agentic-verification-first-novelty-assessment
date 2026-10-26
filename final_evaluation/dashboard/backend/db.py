"""Engine, session factory, and a small portable migration runner."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


MIGRATIONS_PACKAGE = "final_evaluation.dashboard.migrations"


def make_engine(database_url: str):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        Path(database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(connect_args=connect_args, future=True)
    if not database_url.startswith("sqlite"):
        kwargs.update(pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300)
    return create_engine(database_url, **kwargs)


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _ensure_migration_table(conn) -> None:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id VARCHAR(64) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"
        )
    )


def _applied(conn) -> set:
    _ensure_migration_table(conn)
    return {row[0] for row in conn.execute(text("SELECT id FROM schema_migrations"))}


def _discover_migrations():
    """(migration_id, module) pairs in filename order."""
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

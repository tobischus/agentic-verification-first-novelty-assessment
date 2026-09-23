"""Environment configuration, loaded once. See .env.example for every variable this
reads and what each one is for. Fails loudly and specifically at startup rather than
letting a missing secret surface later as an opaque 500 -- "fehlende Cloud-Zugangsdaten
blockieren nur das Deployment, nicht die lokale Implementierung" means local dev (APP_ENV
!= production, STORAGE_BACKEND=local, DATABASE_URL=sqlite:///...) must work with an
almost-empty .env, while a cloud deploy is checked strictly.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    # final_evaluation/.env by default; ENV_FILE picks another one, e.g. the cloud
    # settings in final_evaluation/.env.cloud for CLI commands against Supabase, so the
    # local .env (and the local study) stays untouched.
    _env_file = os.getenv("ENV_FILE")
    if _env_file and not Path(_env_file).is_file():
        raise SystemExit(f"ENV_FILE={_env_file} does not exist")
    load_dotenv(Path(_env_file) if _env_file else Path(__file__).resolve().parents[2] / ".env")
except SystemExit:
    raise
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[3]
FE_ROOT = Path(__file__).resolve().parents[2]  # final_evaluation/


@dataclass
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", f"sqlite:///{FE_ROOT / 'private' / 'local_study.sqlite'}"))
    session_secret: str = field(default_factory=lambda: os.getenv("SESSION_SECRET", ""))
    access_code_pepper: str = field(default_factory=lambda: os.getenv("ACCESS_CODE_PEPPER", ""))
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "local"))
    local_asset_root: str = field(default_factory=lambda: os.getenv(
        "LOCAL_ASSET_ROOT", str(FE_ROOT / "private" / "assets")))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    supabase_bucket: str = field(default_factory=lambda: os.getenv("SUPABASE_BUCKET", ""))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", ""))
    study_contact: str = field(default_factory=lambda: os.getenv("STUDY_CONTACT", ""))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8010")))

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        # Only relax Secure on localhost dev; any cloud deploy sets APP_ENV=production.
        return self.is_production

    def require_for_start(self) -> list[str]:
        """Configuration errors that must block startup, given the CURRENT mode.
        Returns human-readable problem strings; empty = OK to start."""
        problems = []
        if not self.session_secret:
            problems.append("SESSION_SECRET is not set (any long random string; "
                            "`python -c \"import secrets;print(secrets.token_hex(32))\"`).")
        if not self.access_code_pepper:
            problems.append("ACCESS_CODE_PEPPER is not set (any long random string, "
                            "distinct from SESSION_SECRET).")
        if self.is_production:
            # STUDY_CONTACT is optional: the login page no longer shows a contact line
            # (raters are recruited personally and contact the study author directly).
            if self.storage_backend == "supabase":
                for name, val in (("SUPABASE_URL", self.supabase_url),
                                  ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
                                  ("SUPABASE_BUCKET", self.supabase_bucket)):
                    if not val:
                        problems.append(f"{name} is not set (STORAGE_BACKEND=supabase requires it).")
            if self.database_url.startswith("sqlite"):
                problems.append("APP_ENV=production but DATABASE_URL is still sqlite:// -- "
                                "cloud mode must use the Supabase PostgreSQL connection string, "
                                "never local SQLite (Render's filesystem is not durable).")
        return problems


def get_settings() -> Settings:
    return Settings()


def dev_default_secret_warning(settings: Settings) -> str | None:
    if not settings.is_production and not settings.session_secret:
        return None  # main.py fills in an ephemeral one for pure local convenience
    return None

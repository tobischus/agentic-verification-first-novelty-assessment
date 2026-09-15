"""Where an Asset's bytes actually live, and how the API hands them to an authorized
browser -- the one place that knows the difference between "local" and "supabase".

Every other module talks to `StorageBackend`, never to a filesystem path or a bucket
name directly. That is what makes "same code, either database, either storage" true: the
asset ROW (models.Asset) is identical either way, and only `resolve()`'s two branches
differ.

Local mode serves bytes itself (FastAPI's `FileResponse`, which already supports Range
requests) from a directory that is never under the app's static-files mount -- see
app.py's comment on why `private/` and `inputs/` are never `app.mount()`ed. Cloud mode
hands back a short-lived Supabase signed URL and the caller 302s the browser to it; the
service-role key that produced that URL never leaves this process.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class ResolvedAsset:
    kind: str  # "file" -> serve `path` locally; "redirect" -> 302 to `url`
    path: Optional[Path] = None
    url: Optional[str] = None
    content_type: str = "application/octet-stream"


class StorageBackend:
    name = "base"

    def put(self, study_id: str, asset_id: str, src_path: Path, content_type: str) -> str:
        """Copy a local file into the backend; returns the `storage_key` to persist."""
        raise NotImplementedError

    def resolve(self, storage_key: str, content_type: str) -> ResolvedAsset:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Files live under `<LOCAL_ASSET_ROOT>/<study_id>/<asset_id>__<basename>`.

    `LOCAL_ASSET_ROOT` defaults to `final_evaluation/private/assets` -- inside
    `private/`, which .gitignore, the Docker build (.dockerignore) and app.py's static
    mount all exclude. A participant's browser reaches these bytes ONLY through
    routers/assets.py, which authorizes the request first.
    """
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, study_id: str, asset_id: str, src_path: Path, content_type: str) -> str:
        dest_dir = self.root / study_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}__{src_path.name}"
        shutil.copyfile(src_path, dest)
        return str(dest.relative_to(self.root))

    def resolve(self, storage_key: str, content_type: str) -> ResolvedAsset:
        p = self.root / storage_key
        if not p.is_file():
            raise FileNotFoundError(storage_key)
        return ResolvedAsset(kind="file", path=p, content_type=content_type)


class SupabaseStorage(StorageBackend):
    """Private bucket via Supabase's Storage REST API, service-role key, server-side only.

    Implemented against the documented REST shape
    (https://supabase.com/docs/guides/storage/buckets/fundamentals); not exercised
    against a live project in this session -- see ACCEPTANCE.md for what IS verified
    (the local backend, end to end) versus what is implemented-but-cloud-untested.
    """
    name = "supabase"

    def __init__(self, url: str, service_role_key: str, bucket: str):
        self.base = url.rstrip("/")
        self.key = service_role_key
        self.bucket = bucket
        self._client = httpx.Client(timeout=30.0, headers={
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
        })

    def put(self, study_id: str, asset_id: str, src_path: Path, content_type: str) -> str:
        key = f"{study_id}/{asset_id}__{src_path.name}"
        with open(src_path, "rb") as fh:
            r = self._client.post(
                f"{self.base}/storage/v1/object/{self.bucket}/{key}",
                content=fh.read(),
                headers={"Content-Type": content_type, "x-upsert": "true"},
            )
        r.raise_for_status()
        return key

    def resolve(self, storage_key: str, content_type: str, expires_in: int = 120) -> ResolvedAsset:
        r = self._client.post(
            f"{self.base}/storage/v1/object/sign/{self.bucket}/{storage_key}",
            json={"expiresIn": expires_in},
        )
        r.raise_for_status()
        signed_path = r.json()["signedURL"]  # e.g. "/object/sign/<bucket>/<key>?token=..."
        url = f"{self.base}/storage/v1{signed_path}" if signed_path.startswith("/") else signed_path
        return ResolvedAsset(kind="redirect", url=url, content_type=content_type)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backend_from_env() -> StorageBackend:
    kind = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if kind == "supabase":
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        bucket = os.getenv("SUPABASE_BUCKET", "")
        missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_SERVICE_ROLE_KEY", key),
                                  ("SUPABASE_BUCKET", bucket)) if not v]
        if missing:
            raise RuntimeError(
                f"STORAGE_BACKEND=supabase but missing: {', '.join(missing)} -- "
                "set these in the environment (Render secret settings in the cloud, "
                ".env locally). Local development can use STORAGE_BACKEND=local instead.")
        return SupabaseStorage(url, key, bucket)
    root = Path(os.getenv("LOCAL_ASSET_ROOT", "final_evaluation/private/assets"))
    return LocalStorage(root)

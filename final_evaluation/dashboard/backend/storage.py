"""Storage backends for asset bytes: local files or Supabase."""
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
    kind: str
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
    """Files live under `<LOCAL_ASSET_ROOT>/<study_id>/<asset_id>__<basename>`."""
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, study_id: str, asset_id: str, src_path: Path, content_type: str) -> str:
        dest_dir = self.root / study_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}__{src_path.name}"
        shutil.copyfile(src_path, dest)
        return dest.relative_to(self.root).as_posix()

    def resolve(self, storage_key: str, content_type: str) -> ResolvedAsset:
        p = self.root / storage_key
        if not p.is_file():
            raise FileNotFoundError(storage_key)
        return ResolvedAsset(kind="file", path=p, content_type=content_type)


class SupabaseStorage(StorageBackend):
    """Private Supabase Storage bucket, accessed server-side with the service-role key."""
    name = "supabase"

    def __init__(self, url: str, service_role_key: str, bucket: str):
        self.base = url.rstrip("/")
        self.key = service_role_key
        self.bucket = bucket
        headers = {"apikey": self.key}
        if self.key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.key}"
        self._client = httpx.Client(timeout=30.0, headers=headers)

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
        signed_path = r.json()["signedURL"]
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

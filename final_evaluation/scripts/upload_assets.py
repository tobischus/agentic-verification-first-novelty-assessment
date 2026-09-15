"""Push locally-materialised assets to Supabase Storage and repoint the Asset rows in
whatever DATABASE_URL is currently configured -- normally the cloud Postgres database,
set in the environment before running this (see SETUP_HOSTING.md).

Requires the study to have been seeded LOCALLY first (STORAGE_BACKEND=local), so each
Asset has bytes sitting under LOCAL_ASSET_ROOT to read and re-hash before upload; this
script never re-derives an asset from `inputs/pilot/` on its own, so what gets uploaded
is provably the same bytes the local pilot already ran against.

Reports total size and the largest file BEFORE uploading anything, against Supabase
Free's published limits (500MB DB / 1GB storage / 50MB per file -- see
SETUP_HOSTING.md's cited sources), and stops with a clear message rather than uploading
partway if a limit would be exceeded. It never upgrades a plan or trims content to fit.

Usage
-----
  STORAGE_BACKEND=supabase DATABASE_URL=<supabase postgres url> \\
    python -m final_evaluation.cli upload-assets --study dashboard_pilot_v1
"""
from __future__ import annotations

from pathlib import Path

from ..dashboard.backend import db as db_mod, models, storage
from ..dashboard.backend.settings import get_settings

SUPABASE_FREE_FILE_LIMIT = 50 * 1024 * 1024
SUPABASE_FREE_STORAGE_LIMIT = 1024 * 1024 * 1024


def run(study_id: str) -> None:
    settings = get_settings()
    if settings.storage_backend != "supabase":
        raise SystemExit("STORAGE_BACKEND must be 'supabase' for this command "
                        f"(currently {settings.storage_backend!r}). Set it in the "
                        "environment before running upload-assets -- see SETUP_HOSTING.md.")

    engine = db_mod.make_engine(settings.database_url)
    Session = db_mod.make_session_factory(engine)
    db = Session()
    try:
        assets = db.query(models.Asset).filter(models.Asset.study_id == study_id).all()
        if not assets:
            print(f"No assets found for study {study_id!r} in {settings.database_url}. "
                 "Did you seed this database (init-db/seed-pilot) first?")
            return

        local_root = Path(get_settings().local_asset_root)
        local = storage.LocalStorage(local_root)
        total = 0
        largest = (0, "")
        plan = []
        for a in assets:
            if a.storage_backend == "supabase":
                continue
            try:
                resolved = local.resolve(a.storage_key, a.content_type)
            except FileNotFoundError:
                print(f"SKIP {a.id}: no local file at {local_root / a.storage_key} -- "
                     "this asset was never materialised locally; re-run seed-pilot with "
                     "STORAGE_BACKEND=local against this same study first.")
                continue
            size = resolved.path.stat().st_size
            total += size
            if size > largest[0]:
                largest = (size, str(resolved.path))
            plan.append((a, resolved.path, size))

        print(f"{len(plan)} asset(s) to upload, {total / 1e6:.1f} MB total, "
             f"largest: {largest[1]} ({largest[0] / 1e6:.1f} MB)")

        if largest[0] > SUPABASE_FREE_FILE_LIMIT:
            print(f"\nSTOPPING: {largest[1]} is {largest[0] / 1e6:.1f} MB, over Supabase "
                 f"Free's 50 MB per-file upload limit. Not uploading anything. "
                 "See https://supabase.com/pricing for current limits.")
            return
        if total > SUPABASE_FREE_STORAGE_LIMIT:
            print(f"\nSTOPPING: total {total / 1e6:.1f} MB exceeds Supabase Free's 1 GB "
                 "storage limit. Not uploading anything. See https://supabase.com/pricing.")
            return

        backend = storage.backend_from_env()
        uploaded = 0
        for a, path, size in plan:
            actual_sha = storage.sha256_file(path)
            if actual_sha != a.sha256:
                print(f"SKIP {a.id}: local file hash changed since it was recorded "
                     f"({a.sha256[:12]} -> {actual_sha[:12]}) -- re-run seed-pilot before uploading.")
                continue
            key = backend.put(study_id, a.id, path, a.content_type)
            a.storage_backend = "supabase"
            a.storage_key = key
            uploaded += 1
            print(f"  uploaded {a.id} ({size/1e6:.2f} MB) -> {key}")
        db.commit()
        print(f"\n{uploaded}/{len(plan)} asset(s) uploaded and repointed to supabase in "
             f"{settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}.")
    finally:
        db.close()

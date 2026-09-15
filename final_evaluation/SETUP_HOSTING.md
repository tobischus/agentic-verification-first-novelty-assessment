# Hosting the pilot for free: Render Free + Supabase Free

Everything below is a manual step **you** perform — this repository creates no accounts,
accepts no terms, and enables no paid plan. Nothing here is required for local use.

Free-tier facts checked **2026-09-14**. Check them again before you deploy; free tiers
change, and "free" only holds inside the published limits.

- Render Free web service: spins down after ~15 minutes idle, cold start ≈ 1 minute,
  **ephemeral filesystem**, free `.onrender.com` HTTPS URL. Render's free PostgreSQL
  expires after 30 days, which is why this setup does **not** use it.
  <https://render.com/docs/free>
- Supabase Free: 500 MB database, 1 GB file storage, **50 MB max per uploaded file**,
  5 GB egress plus 5 GB cached egress, project may be paused after ~1 week of
  inactivity, **no included automatic database backups**.
  <https://supabase.com/pricing> ·
  <https://supabase.com/docs/guides/storage/buckets/fundamentals>

Consequences designed into this app rather than papered over: no SQLite and no local
files in cloud mode (Render's disk is ephemeral), no keepalive pinging to dodge
spin-down, and backups are a manual CLI step you run daily during an active study.

## 1. Supabase project

1. Create a free Supabase account and a project; choose an **EU region** if your data
   protection expectations call for one.
2. Storage → **New bucket** → name it (e.g. `study-assets`) → **keep it private**
   (public = off). Never make it public: assets are served only through the study API.
3. Project Settings → Database → **Connection string** → use the **Session pooler / 
   Transaction pooler** URI (port 6543), not the direct 5432 connection: free-tier
   projects have very few direct connections, and this app deliberately opens a small
   pool (`pool_size=3`, `pool_pre_ping`, `pool_recycle=300` — see `backend/db.py`).
   Convert it to SQLAlchemy form:
   `postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require`
4. Project Settings → API → copy the **service_role** key. It is server-side only; it
   must never appear in the frontend, in git, or in a browser request.

## 2. Local .env pointing at the cloud

Do not put secrets on the command line. Put them in `final_evaluation/.env`:

```
APP_ENV=production
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
SESSION_SECRET=<32+ random bytes, hex>
ACCESS_CODE_PEPPER=<a different 32+ random bytes, hex>
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
SUPABASE_BUCKET=study-assets
PUBLIC_BASE_URL=https://<your-service>.onrender.com
STUDY_CONTACT=<a real address you monitor>
```

`STUDY_CONTACT` is mandatory in production — the app refuses to start without it rather
than showing participants a login page with no way to report a problem.

## 3. Migrate the cloud database and upload assets

```
python -m final_evaluation.cli init-db                                   # creates the schema in Supabase
python -m final_evaluation.cli seed-pilot                                # study, papers, reports, tasks
python -m final_evaluation.cli upload-assets --study dashboard_pilot_v1  # local files -> private bucket
```

`upload-assets` prints total size, the largest file, and **stops without uploading
anything** if a file would exceed 50 MB or the total would exceed 1 GB. It does not
upgrade a plan and does not shorten content to fit — if it stops, decide what to do
yourself.

It requires the study to have been seeded **locally first** (`STORAGE_BACKEND=local`),
because it re-reads and re-hashes the exact bytes the local pilot ran against before
uploading them.

## 4. Participants and admin against the cloud database

```
python -m final_evaluation.cli create-participants --study dashboard_pilot_v1 --count 2
python -m final_evaluation.cli create-admin        --study dashboard_pilot_v1
```

Run these **locally** with the cloud `DATABASE_URL` — no Render shell is needed, and the
codes file and the optional name key stay on your machine.

## 5. Deploy to Render

1. Push this repository to a **private** Git repository. `inputs/`, `manifests/`,
   `private/`, `results/`, `backups/` and `.env` are gitignored; verify with
   `git status --porcelain` before the first push.
2. Render → New → **Web Service** → connect the repo → it will pick up
   `final_evaluation/render.yaml` (Docker runtime, free plan, Frankfurt region,
   health check `/api/health`, autoDeploy off).
3. Enter the eight `sync: false` environment variables in Render's dashboard with the
   same values as your local `.env`.
4. Deploy, then confirm `https://<service>.onrender.com/api/health` returns
   `{"ok": true, "app_env": "production", "storage_backend": "supabase"}`.

## 6. Full online test before sharing the URL

Do all of this yourself, once, before anyone else sees the link:

1. Open the URL in a **fresh browser profile**; log in with a real participant code.
2. Accept the instructions, open a task, open the submission PDF, page and search in it.
3. Enter answers; watch the status go *Unsaved changes* → *Saving…* → *Saved at …*.
4. Reload the page: the answers must come back from the server.
5. Submit; note the receipt id.
6. **Wait 20+ minutes** (Render free spins down), then reload: after the ~1 minute cold
   start the submitted task must still be there. This is the test that the data is in
   Supabase and not on Render's ephemeral disk.
7. Log in as admin, download the export, and open it.

Then distribute the URL and the individual codes yourself.

## 7. Backups during the study

Free Supabase includes **no automatic database backups**. Run this daily while the study
is active and once immediately after it ends:

```
python -m final_evaluation.cli backup --study dashboard_pilot_v1 --out final_evaluation/backups/pilot_backup.zip
```

Existing files are never overwritten — a timestamp is appended and the actual path is
printed. Verify a backup restores at least once:

```
python -m final_evaluation.cli restore --input final_evaluation/backups/<file>.zip \
       --target-local final_evaluation/private/restore_check.sqlite
```

`restore` refuses an existing target and never touches the live study database.

If a Supabase project is paused (inactivity) it must be resumed from the dashboard
before the dashboard works again. If you ever recreate the cloud project: sessions must
be revoked and participant codes re-issued (`create-participants` against the new
database writes a new credential file; old codes hash against the old pepper/DB and will
simply stop working).

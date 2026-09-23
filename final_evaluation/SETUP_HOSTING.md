# Hosting the study for free: Render Free + Supabase Free

> **Main study (`main_study_v2`).** Use `--config final_evaluation/config/main.yaml` and
> `--study main_study_v2` wherever a command below names the pilot. The cloud database is
> a *new* database: participant codes created locally do **not** work there -- create
> M01/M02 (and the PV01 test account) against the cloud database and hand out those codes.
> Checked 2026-09-23 on a fresh local database: `init-db` + `seed-pilot --config main.yaml`
> build 10 papers, 50 reports, 20 tasks and 90 assets (43.4 MB, largest file 11.9 MB --
> inside Supabase Free's 1 GB / 50 MB limits).

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

1. Create a free Supabase account and a project (plan Free, region **Central EU
   (Frankfurt)**). Choose a database password of letters and digits only -- it goes into
   a URL, where special characters would need escaping -- and keep it.
2. Storage → **New bucket** → `study-assets` → **public off**. Never make it public:
   assets are served only through the study API (short-lived signed URLs).
3. **Connect** (top of the project page) → connection string, type URI, method
   **Transaction pooler** (port 6543), not the direct connection (IPv6 only on Free).
   Replace `[YOUR-PASSWORD]`, change the scheme to `postgresql+psycopg2://` and append
   `?sslmode=require`:
   `postgresql+psycopg2://postgres.<ref>:<password>@aws-<n>-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require`
4. Project Settings → **API Keys** → a **secret key** (`sb_secret_...`) or the legacy
   `service_role` key. Server-side only: never in the frontend, in git or in a browser.
   Both kinds work (`storage.py` sends a secret key on `apikey` only, as Supabase asks).
5. The **Project URL** `https://<ref>.supabase.co`.

## 2. The cloud settings file

Keep the local `.env` as it is (it runs the local study). Put the cloud values in
`final_evaluation/.env.cloud` (gitignored and dockerignored by `.env.*`):

```
APP_ENV=production
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-<n>-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require
SESSION_SECRET=<python -c "import secrets;print(secrets.token_hex(32))">
ACCESS_CODE_PEPPER=<a second, different token_hex(32)>
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<secret key>
SUPABASE_BUCKET=study-assets
```

A CLI command reads it when `ENV_FILE` points at it (`settings.py`):
`$env:ENV_FILE = "final_evaluation/.env.cloud"` in PowerShell; `Remove-Item Env:ENV_FILE`
afterwards. **`ACCESS_CODE_PEPPER` must be identical here and on Render** -- the codes
are hashed with it when you create them locally and checked with it on Render.

## 3. Build the study in the cloud database

With `ENV_FILE` set, from the repository root:

```
python -m final_evaluation.cli init-db
python -m final_evaluation.cli seed-pilot --config final_evaluation/config/main.yaml
python -m final_evaluation.cli upload-assets --study main_study_v2
```

With `STORAGE_BACKEND=supabase`, `seed-pilot` already uploads every file into the bucket
(it reads the local frozen inputs); `upload-assets` then reports 0 files to upload and is
only a check. Expected: 10 papers, 50 reports, 20 tasks, 90 files (43 MB).

## 4. Participants and admin

Still with `ENV_FILE` set:

```
python -m final_evaluation.cli create-participants --study main_study_v2 --count 2 --prefix M --not-test --config final_evaluation/config/main.yaml
python -m final_evaluation.cli create-participants --study main_study_v2 --count 1 --prefix PV --config final_evaluation/config/main.yaml
python -m final_evaluation.cli create-admin --study main_study_v2
```

The codes are written once to `final_evaluation/private/` (file names carry the cloud
host). These are the codes to hand out; the local ones do not work in the cloud.

## 5. Deploy to Render

The image is built from the Git repository, so everything under `final_evaluation/` that
the Dockerfile copies must be committed and pushed first (`inputs/`, `private/`,
`manifests/`, `.env*` stay out -- they are gitignored). Then:

1. Render → **New → Web Service** → connect the GitHub repository (or "Public Git
   Repository" with its URL) → branch = the pushed branch.
2. Language **Docker**; Region **Frankfurt**; Instance type **Free**.
3. Advanced: Dockerfile Path `final_evaluation/Dockerfile`, Docker Build Context
   Directory `.` (the repository root), Health Check Path `/api/health`, Auto-Deploy
   **off** (no redeploy during a live study).
4. Environment variables: the eight lines of `.env.cloud`, same values.
5. Create; the first build takes a few minutes. Then
   `https://<service>.onrender.com/api/health` must answer
   `{"ok": true, "app_env": "production", "storage_backend": "supabase"}`.

Verified locally on 2026-09-24 without a cloud account: the image builds from a
copy of exactly these files; the container in `APP_ENV=production` against PostgreSQL 16
passes the whole rater flow (consent, reading step, PDF, autosave, reload, submit,
re-login, admin export with A/B mapped to systems, umlauts intact) and backup/restore
round-trips. Not verified: Supabase Storage itself -- `seed-pilot` in step 3 is its first
real use and fails loudly on a wrong key or bucket.

## 6. Full online test before sharing the URL

Do all of this yourself, once, before anyone else sees the link:

1. Open the URL in a **private window**; log in with the **PV01** code.
2. Accept the instructions, read a submission, open a task, open the submission PDF,
   page and search in it.
3. Enter answers; watch the status go *Unsaved changes* → *Saving…* → *Saved at …*.
4. Reload the page: the answers must come back from the server.
5. Submit.
6. **Wait 20+ minutes** (Render free spins down), then reload: after the ~1 minute cold
   start the submitted task must still be there. This is the test that the data is in
   Supabase and not on Render's ephemeral disk.
7. Log in with the admin code, download the export, and open it.

PV01 is a test participant (`is_test`); its answers stay in the export marked as test and
are excluded from the analysis. Then send each rater the URL and their own code.

## 7. Backups during the study

Free Supabase includes **no automatic database backups**. Run this daily while the study
is active and once immediately after it ends (with `ENV_FILE` pointing at `.env.cloud`,
otherwise it backs up the local database):

```
python -m final_evaluation.cli backup --study main_study_v2 --out final_evaluation/backups/main_backup.zip
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

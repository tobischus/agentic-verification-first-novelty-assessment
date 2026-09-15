# final_evaluation — human rating dashboard + evaluation harness

A small, self-contained study application: participants compare two novelty reports
about the same submission and rate them on five criteria. It shares **nothing** at
runtime with the assessment pipeline in `src/` — no model calls, no retrieval, no PDF
parsing — it only serves files that were frozen once by `import-pilot` and stores
ratings.

Everything runs from the **repository root**.

```
python -m pip install -r final_evaluation/requirements.txt
cp final_evaluation/.env.example final_evaluation/.env     # then fill in two secrets
python -m final_evaluation.cli inventory        --config final_evaluation/config/pilot.yaml
python -m final_evaluation.cli import-pilot     --sources final_evaluation/config/sources.pilot.yaml
python -m final_evaluation.cli validate-inputs  --study dashboard_pilot_v1
python -m final_evaluation.cli init-db
python -m final_evaluation.cli seed-pilot
python -m final_evaluation.cli create-participants --study dashboard_pilot_v1 --count 2
python -m final_evaluation.cli create-admin        --study dashboard_pilot_v1
python -m final_evaluation.cli build-frontend
python -m final_evaluation.cli serve --host 127.0.0.1 --port 8010
```

Then open <http://127.0.0.1:8010>. Requires Python 3.11+ and Node 18+ (tested on
Python 3.11.2 / Node 18.15.0 on Windows).

`.env` needs only two values locally:

```
SESSION_SECRET=<python -c "import secrets; print(secrets.token_hex(32))">
ACCESS_CODE_PEPPER=<a second, different one>
```

Everything else defaults to local SQLite (`private/local_study.sqlite`) and local file
storage (`private/assets/`). Missing cloud credentials block only deployment, never
local use.

## Where the credentials go

`create-participants` and `create-admin` print the **file path**, not the secrets:

```
private/participant_codes__dashboard_pilot_v1__local_study.csv
private/admin_code__dashboard_pilot_v1__local_study.txt
```

The filename carries the study id *and* the database, because a code only works against
the database it was created in — seeding a throwaway test database with the same study
id must not overwrite the real pilot's credentials. Codes are stored only as
HMAC-SHA256; these files are the one and only copy. Distribute them by hand — the
application sends no email and has no invite flow. An optional name↔code key belongs in
`private/participant_key.csv` (gitignored, never exported).

## Day-to-day commands

| Command | What it does |
|---|---|
| `inventory` | Read-only scan for existing pilot materials; flags ambiguous multi-candidate files |
| `import-pilot` | Freezes reports/submissions into `inputs/pilot/` + `manifests/pilot/reports.json` |
| `validate-inputs --study ID` | Hashes, all five systems per paper, anchors, E1/E2 pairing |
| `init-db` | Applies migrations (idempotent) |
| `seed-pilot` | Study, papers, reports, assets, the six tasks (idempotent) |
| `create-participants --study ID --count N` | Participants **and** their frozen assignments |
| `create-admin --study ID` | A separate admin credential |
| `build-frontend` | Syncs instructions/rubric into `public/`, `npm ci`, `npm run build` |
| `serve --host --port` | Runs API + built frontend on one origin |
| `export --study ID --out X.zip` | The research export (same bytes the admin UI downloads) |
| `analyze-human --input X.zip [--include-test]` | E2 tallies, agreement, Krippendorff's α |
| `plan-e1 --config …` | Lists the judge calls; `--execute` (only) runs them |
| `upload-assets --study ID` | Pushes local assets to Supabase and repoints the DB rows |
| `backup --study ID --out X.zip` | Operational backup (includes auth tables) |
| `restore --input X.zip --target-local Y.sqlite` | Restores into a **new** local file |

`export` vs `backup`: the export is the pseudonymised **research** data (no code
hashes, no sessions) and is what goes into analysis; the backup is the **operational**
copy of every table, including auth material, and never belongs in a research dataset.

## Running the tests

The live suite drives a running server over real HTTP, so it must point at a
**throwaway database** — never the study's own:

```
# one-time: build a test database with the same shape
DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite python -m final_evaluation.cli init-db
DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite python -m final_evaluation.cli seed-pilot
DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite python -m final_evaluation.cli create-participants --study dashboard_pilot_v1 --count 2
DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite python -m final_evaluation.cli create-admin --study dashboard_pilot_v1

# serve it on a second port, then run the suites
DATABASE_URL=sqlite:///final_evaluation/private/test_study.sqlite python -m final_evaluation.cli serve --port 8011
FE_TEST_BASE=http://127.0.0.1:8011 python -m pytest final_evaluation/tests/ -v
```

`test_e2_stats.py` needs no server. `test_flow_live.py` skips itself when no server is
listening, and skips when the test database's credential files are absent.

## Layout

```
config/       pilot.yaml, main.template.yaml, sources.pilot.yaml (explicit source binding)
prompts/      novelty_report_judge_v2.txt, criteria.json, human_instructions.md
inputs/       frozen report/submission files            (gitignored)
manifests/    hashes, provenance, content versions      (gitignored)
dashboard/    backend (FastAPI + SQLAlchemy), frontend (Vite/React), migrations
evaluation/   e1 (judge adapter), e2 (analysis), e3/e4 (schema + plan only)
results/      exports and analyses                       (gitignored)
private/      codes, name key, local DB, assets, secrets (gitignored)
backups/      operational backups                        (gitignored)
tests/        live HTTP suite + statistics unit tests
```

`inputs/`, `manifests/`, `results/`, `private/` and `backups/` are excluded from git,
from the Docker image, and from every static mount — the only route to an asset's bytes
is the authenticated `/api/assets/{id}` endpoint.

## Going online

See `SETUP_HOSTING.md` (Render Free + Supabase Free, step by step, with the current free
tier limits and what to check before sharing the URL). `PROTOCOL.md` is the frozen study
protocol; `ACCEPTANCE.md` records what was actually executed and verified, and what is
explicitly not done yet.

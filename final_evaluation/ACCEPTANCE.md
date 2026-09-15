# Acceptance record — what was actually executed, what passed, what is still open

Run on Windows 11, Python 3.11.2, Node 18.15.0, 2026-09-15, from the repository root.
Every command below was executed; the outputs quoted are the real ones.

## 1. Commands executed, in order

```
python -m pip install -r final_evaluation/requirements.txt
python -m final_evaluation.cli inventory        --config final_evaluation/config/pilot.yaml
python -m final_evaluation.cli import-pilot     --sources final_evaluation/config/sources.pilot.yaml
python -m final_evaluation.cli validate-inputs  --study dashboard_pilot_v1
python -m final_evaluation.cli init-db
python -m final_evaluation.cli seed-pilot
python -m final_evaluation.cli create-participants --study dashboard_pilot_v1 --count 2
python -m final_evaluation.cli create-admin        --study dashboard_pilot_v1
python -m final_evaluation.cli build-frontend
python -m final_evaluation.cli serve --host 127.0.0.1 --port 8010
python -m final_evaluation.cli export        --study dashboard_pilot_v1 --out final_evaluation/results/pilot/test_export.zip
python -m final_evaluation.cli analyze-human --input final_evaluation/results/pilot/test_export.zip --include-test
python -m final_evaluation.cli plan-e1       --config final_evaluation/config/pilot.yaml
python -m final_evaluation.cli backup  --study dashboard_pilot_v1 --out final_evaluation/backups/pilot_backup.zip
python -m final_evaluation.cli restore --input final_evaluation/backups/pilot_backup.zip \
       --target-local final_evaluation/private/restore_test.sqlite
```

Local URL: **<http://127.0.0.1:8010>** (study database), plus a second instance on
**8011** pointed at the throwaway test database for the automated suite.

Credentials (shown once, gitignored, not reproduced here):

- `final_evaluation/private/participant_codes__dashboard_pilot_v1__local_study.csv`
- `final_evaluation/private/admin_code__dashboard_pilot_v1__local_study.txt`

Exports / analyses produced: `final_evaluation/results/pilot/test_export.zip`,
`final_evaluation/results/pilot/test_analysis.json`,
`final_evaluation/backups/pilot_backup.zip`.

## 2. Results

**inventory** found all five systems for both papers and flagged one genuine ambiguity:
`graphrag_when_to_use/agent` has four undocumented variants
(`__agent.md`, `__agent_v2.md`, `__agent_v3.md`, `__agent_v4.md`), none named in
`comparison/outputs/PROVENANCE.md`. Resolution is written into
`config/sources.pilot.yaml`: none of the four is used. Agent and linear reports are
**re-rendered at import time** by `battle_export.build()` from the frozen
`artifact_a/b_{agent,linear}.json` (deterministic, zero model calls), with the renderer's
own sha256 and both artifact hashes recorded in `content_version`. This also avoided a
silent trap — a fresh render matches *none* of the four files, because `battle_export.py`
kept changing locally while those snapshots were taken.

**import-pilot**: 2 papers × 5 systems + 2 submissions, no blockers.

**validate-inputs**: `0 error(s), 2 warning(s)`, verdict `VALID`.
Anchor resolution (agent/linear blockquotes resolving against their quote index):
171/173, 184/190, 109/112, 191/194. The two warnings are the OpenNovelty E1/E2 pair on
both papers, flagged `needs_manual_check` — deliberate, see §4.

**seed-pilot / create-participants** are idempotent: re-running left 2 participants,
12 assignments (6 tasks × 2 raters), 6 tasks — nothing rerolled, no duplicate codes.

**Orientation is opposite for R01/R02 on every one of the six pairs** (verified by
listing all assignments), and each rater's task order differs (seeds 101 / 102).

**build-frontend**: `npm ci` (lockfile committed) + `vite build` → `dist/` with
`index.html`, hashed JS/CSS, the PDF worker, plus the synced `instructions.txt` and
`criteria.json`.

**Backup/restore**: 52 rows across 12 tables backed up and restored into a fresh SQLite
file; restoring onto an existing file is refused.

**analyze-human**: produced per-criterion / per-pair tallies, exact agreement and
Krippendorff's α, correctly reporting `not estimable` where a pair had too little data.
The numbers in `test_analysis.json` come from **synthetic answers submitted by the
automated suite into the test database** — they are a functional check of the pipeline,
not results.

## 3. Tests

```
FE_TEST_BASE=http://127.0.0.1:8011 python -m pytest final_evaluation/tests/ -v
```

`test_flow_live.py` — 14 passed (live HTTP against a running server + real DB):

| Risk from the brief | Test | Result |
|---|---|---|
| Wrong code rejected, generic message | `test_login_rejects_bad_code` | pass |
| No session → no tasks/assets/admin/export | `test_unauthenticated_cannot_read_tasks_or_assets` | pass |
| A cannot read B's task (id manipulation) | `test_participant_cannot_open_another_participants_task` | pass (404, not 403 — existence not confirmed) |
| A cannot write to B's task | `test_participant_cannot_write_to_another_participants_task` | pass |
| CSRF required for cookie-auth mutations | `test_csrf_required_for_mutations` | pass |
| Participant cannot reach admin | `test_participant_is_not_admin` | pass |
| Submission + report assets load for own task | `test_submission_and_report_assets_load_for_own_task` | pass |
| System identity never sent to participant | `test_task_detail_never_reveals_system_identity` | pass |
| **No prior-work PDF exists to serve** | `test_no_prior_work_pdf_asset_exists_in_this_study` | pass (checked against the DB itself) |
| Autosave round-trip; stale revision → 409 + server copy | `test_autosave_roundtrip_and_revision_conflict` | pass |
| 50-word reason limit enforced server-side | `test_reason_word_limit_rejected` | pass |
| Familiarity required; submit idempotent; finalised = read-only | `test_submit_requires_familiarity_then_succeeds_and_is_idempotent` | pass |
| A/B orientation stable per rater, opposite between raters | `test_ab_orientation_is_stable_across_reads_and_opposite_between_raters` | pass |
| Export complete, no auth secrets, A/B resolved to systems | `test_admin_export_contains_everything_and_no_secrets` | pass |

`test_e2_stats.py` — 7 passed, including Krippendorff's α **= 0.7434 against the
published textbook value 0.743**, `not estimable` instead of a fabricated number when
there is no variation or too little data, `unclear` treated as missing rather than as a
category, and the bootstrap refusing to produce an interval from two papers.

Additional manual probes against the running server:

```
/inputs/pilot/graphrag_when_to_use/agent.md  -> SPA fallback, no file content
/private/local_study.sqlite                  -> SPA fallback, no file content
/manifests/pilot/reports.json                -> SPA fallback, no file content
/api/../private/local_study.sqlite           -> SPA fallback, no file content
/api/assets/<submission pdf>                 -> 200 application/pdf, 3 547 663 bytes
  with Range: bytes=0-1023                   -> 206, Content-Range bytes 0-1023/3547663
```

**A bug the tests caught and that is now fixed:** `final_responses.idempotency_key` was
globally unique, so submitting a *different* task that reused a key returned HTTP 500.
Fixed in `models.py` (indexed, not unique — `assignment_id` is what guarantees one
response per task) with portable migration `0002_idempotency_key_not_unique.py`, applied
to the existing database without losing the stored response.

**A second bug found and fixed:** seeding a throwaway test database with the same study
id overwrote the real pilot's `admin_code.txt` and appended an indistinguishable second
`R01` row to the shared codes CSV. Credential files are now per study **and** per
database (`..__dashboard_pilot_v1__local_study.csv`), and `create-admin` never
overwrites an existing file.

## 4. Open items — not done, and not claimed to be

1. **No real-browser click-through.** The flows above were driven over real HTTP with a
   cookie/CSRF client, and the built frontend, its assets and the PDF byte-serving were
   verified; but no automated GUI browser was available in this environment, so nobody
   has yet *visually* confirmed the rendered layout, the PDF highlight jump, or the
   overlay at 1366×768. That walkthrough (and the screenshots the brief asks for) is the
   first thing to do manually — §6 of `SETUP_HOSTING.md` is the same checklist.
2. **Supabase and PostgreSQL are implemented but not live-tested.** `SupabaseStorage`,
   the Postgres URL handling, pooling and `upload-assets` are written against the
   documented APIs and the schema is dialect-neutral, but there was no Supabase project
   or Postgres instance in this session. Treat §§1–5 of `SETUP_HOSTING.md` as *untested
   on real infrastructure* until you run them once. The local SQLite + local storage
   path **is** fully exercised.
3. **DeepReviewer's in-PDF annotations on appended submission pages are not imported.**
   The dashboard uses `final_report.md` (the complete text review, references included),
   which excludes the appended submission by construction. If that PDF carries reviewer
   marks that exist nowhere in the markdown, they are currently missing from both E2 and
   E1 for that system.
4. **OpenNovelty E1 text is not verified equivalent to its E2 view.** The participant
   sees the native PDF including the taxonomy graphic; E1 would get
   `opennovelty.e1_text.md` (a `pdf_to_md` extraction). `validate-inputs` marks this
   `needs_manual_check` and warns; it is not claimed to be content-equal.
5. **The existing E1 judge results are not comparable to this pilot.** 
   `eval/out/pilot_v1/judge_calls.jsonl` was produced on older renderings of the
   agent/linear reports; `analyze.compare_to_e1` says so in its own output. Re-run
   `plan-e1 --execute` against the current frozen inputs before comparing humans to the
   judge.
6. **E3 and E4 are directories, READMEs and schemas only** — no importer, no analysis,
   not wired into the CLI. Stated as such in `PROTOCOL.md` §9 and in each README.
7. **Rate limiting is per process.** One Render Free instance makes the in-memory
   counter effective; a multi-instance deployment would need a shared store.
8. **`eval/prompts/novelty_report_judge_v1.txt` already contained the three agreed
   substitutions** when this work started (someone had edited v1 in place rather than
   creating a v2). It was copied verbatim to
   `final_evaluation/prompts/novelty_report_judge_v2.txt`
   (sha256 `4b839942…`, identical); the original was not modified.
9. **No demo answers are in the study database.** All synthetic submissions went into
   `private/test_study.sqlite`; `private/local_study.sqlite` holds the seeded study with
   zero responses, ready for the real R01/R02 walkthrough.

## 5. Untouched by this work

The assessment pipeline (`src/novelty_assessment/**`), retrieval, evidence checking and
every existing review result. The only interaction is read-only: `import-pilot` imports
`battle_export` and calls `build()`/`quote_index()` to render already-frozen artifacts,
and `evaluation/e1/adapter.py` imports `eval/pilot_judge.py` when explicitly asked to
execute. The main frontend (`frontend/`) is untouched; its three PDF-viewer files were
**copied** into `dashboard/frontend/src/vendor/pdf/` (with a README recording the source
commit) rather than imported or modified.

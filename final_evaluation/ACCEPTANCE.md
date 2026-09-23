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

`test_security_time.py` — 4 passed. A stored `locked_until` must read the same on SQLite
(naive) and PostgreSQL (aware); see the defect recorded in §6.

`test_renderer_parity.py` — 3 passed. The study dashboard and the pipeline's own Summary
tab must colour and fold the same report the same way: the two apps' copies of
`components/assessmentStyle.js` and of the shared colour block in `styles.css` must be
byte-identical, and every class the module can emit must have a rule.

Browser walkthroughs, both needing a running server and a throwaway database
(`CHECK_BASE` / `CHECK_CODES`): `browser_check.py` — 22 passed on a freshly seeded
database (instructions, quote marks, background carry-over, autosave/resume/submit; 19 of
them when the consent page has already been passed); `browser_check_layout.py` — 34
passed (§6).

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

1. ~~**No real-browser click-through.**~~ **Done on 2026-09-15** — see §5 below. What
   remains unverified by machine is subjective legibility (font sizes, colour contrast,
   how the two panels feel side by side on a real 1366×768 laptop); the flow, the
   rendering and the PDF jump are now checked in a real Chrome.
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

## 5. Browser walkthrough — 2026-09-15 (dashboard + instructions revision)

Real Chrome (system install, driven by Playwright; Playwright's own Chromium build is not
downloaded on this machine), viewport 1366×768, against `cli serve` on the local pilot
database. 22 of 22 checks passed.

The check is reproducible: `final_evaluation/tests/browser_check.py` (run it with the
dashboard serving, e.g. `python final_evaluation/tests/browser_check.py <shot-dir>`). Its
screenshots are in `final_evaluation/results/pilot/browser_check_2026-09-15/` — ten
images including element shots of a verified and an unverified quote. That directory is
**gitignored** like the rest of `results/`: the images are study screens, so they stay
local rather than being published with the code.

| Checked in the browser | Result |
|---|---|
| Instructions show v2's replaced sentence, the added "Verification labels…" sentence, and no longer the v1 sentence | pass |
| Background questions asked once, with the new wording | pass |
| Second task on the **same paper** does not ask again and shows the stored answers | pass |
| ✓ count equals verified-quote count; unverified quotes get "–" | pass (300 verified / 6 unverified, ticks and dashes match) |
| "⤴ PDF" is a separate control, and never appears on a quote with no target | pass (87 jump controls) |
| Contents navigation present; per-source comparisons collapsed by default and expandable with full content | pass (47 sections) |
| No validation errors before interaction; errors appear after a submit attempt | pass |
| Autosave reaches "Saved"; draft and chosen option survive a reload | pass |
| Submit reaches the confirmation page | pass |

**Two real defects the walkthrough found, both fixed:**

1. A page reload on a task returned to the task list instead of the task being rated.
   The draft was never lost (the server holds it), but "refresh and carry on" looked
   like lost work. `App.jsx` now restores the open task from `history.state` on mount.
2. The background answers were only written at submit time, so a reload before
   submitting discarded them and asked again. They are now saved the moment both are
   answered (`TaskRate.saveFamiliarity`); the endpoint still refuses to overwrite an
   existing answer, so an early save cannot change what an earlier task recorded.

Full suite after the change, against a **fresh** throwaway database
(`private/test_study2.sqlite`, server on :8012): `21 passed`.

**Noticed, not changed (outside this brief):** `create-participants` derives a new
participant's `ordinal` from the number of participants already in the study, so creating
R03 in a later batch gave it ordinal 5, not 3. Ordinal parity drives A/B orientation, so a
participant added in a later batch can end up sharing orientations with an earlier one
instead of mirroring them. It does not affect the frozen R01/R02 pilot assignment, and
touching assignment logic is exactly what must not happen silently — flagged here for a
decision.

## 6. Browser walkthrough — 2026-09-18 (report layout: links, colour, folding)

The export's own layout changed (`battle_export.py`: linked assessments, two-column
closest-comparison table, prior-work summary moved above the comparison, supporting and
non-supporting evidence pairs separated) and both renderers changed with it. Checked in
real Chrome at 1600×950 against `cli serve --port 8011` on a **throwaway** database
(`private/test_study3.sqlite`): **34 of 34**.

| Checked in the browser | Result |
|---|---|
| Related work: substantial-or-higher rows highlighted, and no other row is | pass |
| Related work: every assessment that has a detail section carries a jump link; none dead | pass (16 of 96 cells linked — the rest have no section to link to) |
| Links are panel-scoped: panel A's link opens panel A's section, B's opens B's | pass |
| Closest comparisons: exactly `Source` (with title) and `Assessment`, both dropped fields gone | pass |
| Clicking an assessment scrolls to the comparison **and unfolds it** | pass |
| Inside a comparison: metadata + assessment above, then priorwork / comparison / pairs / unused / check in that order | pass |
| Prior-work summary, unused pairs and the evidence-check record start folded; comparison and supporting pairs start open | pass |
| Each block has its own tint, and the folded section's summary shows its assessment in colour | pass (5 distinct tints) |
| Nothing dropped: folded blocks hold their full text in the DOM, pair numbers unchanged | pass |

The main app's Summary tab (`frontend/src/components/ReviewSummary.jsx`) was verified
separately by server-rendering it over the same export text and asserting the same
properties — 17 of 17, including "every prose line of the export appears in the rendered
page" and "150 of 150 blockquotes rendered". That harness is scratch, not committed; what
is committed is `final_evaluation/tests/test_renderer_parity.py`, which fails if the two
apps' copies of `components/assessmentStyle.js` or of the shared colour block in
`styles.css` ever differ (3 passed).

**One real defect found while re-running the suites, and fixed:** `security.is_locked`
compared a stored `locked_until` against an aware `datetime.now(timezone.utc)`. SQLite
returns that column **naive** even though it is declared `DateTime(timezone=True)`
(PostgreSQL returns it aware), so on SQLite the comparison raised `TypeError` — a 500.
The effect: once a participant had been locked out after failed logins, *every* later
login attempt crashed instead of being refused, and they could not get back in even after
the 15 minutes expired. `is_locked` now reads a naive value as UTC, the same normalisation
`deps.py` already applies to session expiry. Regression test:
`final_evaluation/tests/test_security_time.py` (4 passed). After the fix,
`test_flow_live.py` is **14 passed** against the throwaway database — including the admin
export check, which had never been reached before because login failed first.

**Consequences that are not bugs but must be stated:**

1. **This is a new `content_version`.** `import-pilot` now renders
   `battle_export:73ce6a9ef040`; the pilot responses R02 submitted earlier were given
   against the previous rendering. Per PROTOCOL §2 those ratings are **not** comparable to
   ratings collected on this one.
2. **`seed-pilot` does not swap a report under a running study**, by design — it skips any
   `Report` row that already exists. To show the new layout, seed a **fresh** database or a
   new study id; the existing `private/local_study.sqlite` still serves the old text, which
   is the correct behaviour for a study already in progress.
3. **Colour and folding reach only the reports `battle_export` renders** (agent, linear).
   DeepReviewer's and Afzal's markdown carry none of these phrases, so they render plain,
   and OpenNovelty is a PDF. Blinding was already partial (PROTOCOL §2: structure, length
   and voice identify a system); this adds one more presentation difference between the two
   families, which matters most for `reviewer_usefulness`. Nothing about the *content* of
   any report changed.

## 7. Paper-level novelty summary — 2026-09-19

A new pipeline step, `src/novelty_assessment/paper_synthesis.py`, writes the 120–180-word
summary that now opens an agent/linear report (`battle_export` layout `reviewer-v3.3`).

- **Context:** results only — every claim with its final verdict and recorded rationale,
  every substantial-or-stronger comparison with source id, claim, shared contribution,
  reported difference, novelty argument and evidence-check result, the open conflicts and
  evidence gaps, and — only when nothing strong was found — the strongest comparisons that
  were. No traces, no quotes. 716 words for `graphrag_when_to_use/agent`.
- **The distinction that mattered most** is structural, not a prompt request: the context
  splits substantial-or-stronger overlaps into *supported by the evidence check* and
  *proposed but not supported*, so a proposed `substantial` with inconclusive evidence
  cannot be summarised as an established one.
- **Where it runs:** after Artifact B, in the orchestrator's `artifact_b` stage, in the
  agentic re-entry path and behind `POST /review/conclusion`; a CLI (`--variant`) covers
  the agent/linear artifacts the eval scripts produce. Same prompt, same model for both.
- **Not in `battle_export`.** The export renders the stored summary and makes no model
  call. It also prints "**Out of date:**" when the claim results have changed since the
  summary was written, rather than dropping it or letting it stand silently.
- **Rationales were empty** in the pilot's `artifact_b_*.json` (`run_pilot.py` writes
  `rationale: ""`), so the context carries verdicts without rationales for these two
  papers. Nothing was invented to fill the gap; the field is simply omitted.

Generated so far: `graphrag_when_to_use`, agent (161 words) and linear (164 words). The
agent's summary names R13 **and** R7 as substantially overlapping Claim 2; the linear
baseline's names only R7 — a real difference between the two systems, not between two ways
of summarising. `transducing_language_models` has **not** been generated yet (see
PROTOCOL §2): until it is, its reports open without the section.

Checks — `python eval/paper_synthesis_test.py`, **28 passed**, no model call:

| Property | Result |
|---|---|
| A substantial/same overlap with insufficient or nonmaterial evidence never reaches the supported group | pass |
| Every listed comparison states its evidence status beside its degree | pass |
| The orientation group appears only when no strong overlap exists at all | pass |
| Staleness trips when a supported overlap flips to insufficient, or a shown field is reworded | pass |
| …and does **not** trip on a change the summary never saw (evidence pairs) | pass |
| The ids in the findings are the ids the report prints; every id the summary cites exists there | pass |
| The stored summaries are current and inside the word budget | pass (161, 164) |
| The export prints the section if and only if a summary is stored | pass (4 artifact pairs) |

Both renderers show it unchanged by construction — it is an `## H2` plus two bold-labelled
paragraphs, which they already handled. Verified: main app 17/17 over the new text, and the
dashboard's own parser puts "Novelty summary" second in the contents list, directly after
the document title and before "Extracted claims". `browser_check_layout.py` still 34/34.

One correctness fix found while wiring it: the export passed the **unfiltered** claim order
to the fingerprint while the synthesis used the filtered one, so any paper with a claim that
has no Artifact A entry would have shown "Out of date" on every single render. Both now
filter identically.

## 8. Report layout `reviewer-v4.0` — 2026-09-22

Presentation only: `battle_export.py` (export layout), `assessmentStyle.js` (one shared
grouping rule, byte-identical in both apps), both renderers and the shared CSS block. No
model call; no claim, comparison, evidence check or paper summary changed — the Artifact A/B
hashes inside every `content_version` are unchanged (`manifests/main/CONTENT_VERSIONS.md`).

What the reader gets: title, novelty summary, then every claim as its own closed section
(number, full claim text, verdict, number of detailed comparisons, open points); inside a
claim the full claim-level assessment, the submission passage and coverage (folded), then
every detailed comparison. Each comparison shows source id and title, version and date,
assessment, the full novelty argument and its open points; "Evidence check and
limitations" and "Full comparison and quoted passages · N pairs" are closed folds. A jump
from the related-work table opens every closed section on the way. The "Closest
comparisons" table was dropped — each of its sources is a detailed comparison of the same
claim.

Open points use four fixed sentences, derived only from structured fields:
insufficient evidence → "The available evidence did not resolve this comparison."; no
check → "No evidence check was recorded for this comparison."; `proposed_degree_supported`
is `False` (not `None`) for a same/substantial/partial overlap with material evidence →
"The evidence check does not support this overlap level."; recorded conflict → "The
comparison and evidence check disagree."

Checks:

| Check | Result |
|---|---|
| Export vs the v3.3 baseline, all 10 papers × agent/linear: same (claim, source) comparisons in the same order, same anchors | agent 231, linear 322 comparisons; 0 differences |
| Every stored text of every comparison (novelty argument, shared contribution, difference, prior-work context, both quotes and rationale of every pair, check reasoning) inside the section of that same comparison | 8,311 texts, 0 missing |
| Pair labels 1..n for the n stored pairs of each comparison | 0 problems |
| `browser_check_layout.py` — pilot reports still in their old layout | 34/34 |
| `browser_check_layout_v4.py` — AstaBench, Output Supervision, Train-before-Test, EDIT-Bench, both panels, on a copy of the study DB | 94/94 |
| Main frontend, Summary tab — AstaBench (50 comparisons) and Output Supervision: counts per claim equal the export, all closed, two folds per comparison, matrix jump opens its claim | 14/14 |
| Task texts regenerated; every agent/linear report embedded byte-identically | 33/33 (v3.3 texts archived in `archive/task_texts_reviewer-v3.3/`) |

Switching the study: `cli refresh-reports --config final_evaluation/config/main.yaml` →
`replaced: 20, kept_because_rated: 0`. The database before the switch is
`private/local_study.PRE_reviewer-v4_20260922_211317.sqlite`; the v3.3 texts are in
`archive/main_reports_reviewer-v3.3/` and remain in the asset store under their old ids.

## 9. Report layout `reviewer-v4.1` — 2026-09-23

Requested by the study author after reading v4.0; presentation only, same files as §8
plus `browser_check_layout_v4.py`. Changes: legend "How to read the assessments" and the
related-work table (both folded) moved directly after the novelty summary; claim row shows
the overlap levels of its detailed comparisons instead of an open-points count; "Coverage
and limitations" removed; in each comparison "Full comparison and quoted passages" now
precedes "Evidence check and limitations"; the summary labels and the claim-level
"Assessment" on their own line.

Checks:

| Check | Result |
|---|---|
| Export vs the v3.3 baseline (same script as §8): comparisons, order, anchors, pair labels, every stored comparison text inside its own section | agent 231, linear 322; 8,311 texts; 0 problems |
| Every line of the frozen v4.0 texts that is not in v4.1, classified (all 20 reports) | 590 coverage-section lines and 66 claim-row open-point lines removed as requested; 86 + 20 + 20 label lines split into paragraphs with unchanged text; 80 count lines extended; 20 table intros and legends replaced; **0 unexpected** |
| `browser_check_layout_v4.py` on a copy of the study DB: order summary → legend → table → claims, both folded; no coverage section; rows with levels and no open points; fold order pairs → check; counts, pair numbers, jumps, folded text present | 110/110 |
| Main frontend, Summary tab (AstaBench, Output Supervision) | 14/14 |
| Task texts regenerated; every agent/linear report embedded byte-identically; the 7 tasks without agent/linear unchanged | 33/33, 7/7 (v4.0 texts in `archive/task_texts_reviewer-v4.0/`) |
| `test_renderer_parity.py` (grouping rules identical in both apps) | 3/3 |

Switched with `cli refresh-reports` → `replaced: 20, kept_because_rated: 0`. Database
before the switch: `private/local_study.PRE_reviewer-v4.1_20260923_143557.sqlite`; v4.0
texts: `archive/main_reports_reviewer-v4.0/`. The pilot's layout check
(`browser_check_layout.py`) was not re-run: the only renderer change is one more folded
top-level section name, which the pilot's pre-v4 texts never reach.

## 10. Report layout `reviewer-v4.2` — 2026-09-23

Authors and publication date moved under the title; "# Metadata" removed (the renderers
now also recognise v4.x by "# How to read the assessments"). The study author's own edits
in `battle_export.py` removed the block-quotation note, the table intro sentence and the
legend's two sub-heading explanations. Line diff against v4.1 over all 20 reports: only
those lines and the moved metadata differ. Export check 231/322 comparisons, 8,311 texts,
0 problems; `browser_check_layout_v4.py` 110/110 on a DB copy; parity 3/3; task texts
33/33 embedded. Switched with `refresh-reports` → `replaced: 20, kept_because_rated: 0`;
DB before: `private/local_study.PRE_reviewer-v4.2_20260923_150512.sqlite`; v4.1 texts in
`archive/main_reports_reviewer-v4.1/` and `archive/task_texts_reviewer-v4.1/`.

## 11. Claim-level assessment, layout `reviewer-v4.3` — 2026-09-23

New step `src/novelty_assessment/claim_assessment.py`; export prints its text under
"Claim-level assessment" (marked out of date if the claim's comparisons change). Two
defects found on the AstaBench trial run and fixed before the full run: a level/evidence
conflict was paraphrased in the wrong direction (fixed by stating the direction in the
findings), and the model miscounted the comparisons it did not name (counts now
precomputed; ids of comparisons without a section no longer given).

| Check | Result |
|---|---|
| `eval/claim_assessment_test.py` (consistency checks, findings shape, all 86 stored texts current and printed) | 11/11 |
| Automated level audit: every sentence naming one source, level words vs recorded level | 2 hits, both false positives ("the same … pattern", a count of other comparisons) |
| Revisions triggered by the checks / still open after one revision | 11 / 1 (EditBench linear Claim 3 names 6 source ids: 3 decisive + 3 unestablished/conflicting; kept) |
| Novelty summaries still current (not stale) | 20/20 (`paper_synthesis_test` unchanged at 123/130 -- the same pre-existing word-budget failures) |
| Export vs v3.3 baseline: comparisons, order, anchors, pairs, 8,311 texts | 0 problems |
| `browser_check_layout_v4.py` on a DB copy | 110/110 |
| Task texts, agent/linear embedded byte-identically | 33/33 |

Switched with `refresh-reports` → `replaced: 20, kept_because_rated: 0`; DB before:
`private/local_study.PRE_reviewer-v4.3_20260923_160856.sqlite`.

## 12. Layout `reviewer-v4.4` and two PDF-jump defects — 2026-09-23

Export: the verdict gloss and the "Submission passages" section removed; line diff against
v4.3 over all 20 reports removes exactly 86 × (gloss sentence, section heading, "Claim
anchor" label, anchor quote) and adds nothing. The claim text links to its anchor.

Two pre-existing dashboard defects found while testing the link, both affecting EVERY
"⤴ PDF" jump, not only the new one, and fixed:

1. The submission overlay never scrolled to a passage. PdfViewer scrolls `.pdfscroll`, but
   in the dashboard that element was not a scroll container (`overflow: visible`, its height
   the whole document); the pane around it scrolled instead, so every jump left the PDF on
   page 1. `styles.css` now makes `.pdfscroll` the scroller inside `.study-pdf-pane`.
   Measured: scrollTop 0 → 2493 for AstaBench Claim 3.
2. Both reports number their quotes independently (`sub#0` …), and the overlay merged their
   highlights by that id -- a jump from report B could land on report A's passage of the
   same number. `TaskRate.jsx` now keys highlights by passage text and maps each panel's
   ids to those.

Checks: export vs v3.3 baseline 0 problems (all 86 anchors linked in the quote index);
`browser_check_layout_v4.py` 134/134 (adds: every claim text links, no passages section,
click marks the passage and leaves the claim closed); main frontend: 6/6 claim links,
PDF scrolls; dashboard tests 14/14; `claim_assessment_test.py` 11/11; task texts 33/33.
Switched with `refresh-reports` → `replaced: 20`; DB before:
`private/local_study.PRE_reviewer-v4.4_20260923_165350.sqlite`.

### 12a. Highlights not drawn on the page; jump target not distinguishable — 2026-09-23

Report content unchanged (no new content version, no DB switch). Two more display defects:

3. The dashboard never had the PDF viewer's styles. `vendor/pdf/PdfViewer.jsx` is a copy,
   its CSS (`.pdfpage { position: relative }`, `.pdfhl { position: absolute }`, …) lives
   only in the main app's `styles.css`. Every highlight was therefore an ordinary block
   below the page canvas, not over the text -- "111/112 quotes located", none visibly
   marked. The rules are now in the dashboard's `styles.css` (never present before, per
   `git log -S pdfhl`).
4. Every passage of both reports is highlighted in the same yellow, so after a jump the
   target could not be told from its neighbours. Now, in both apps, one colour per claim
   (on the claim text, a swatch on each quoted submission passage, and its passages in the
   PDF); the jump target in full colour, the others at a pale tint of their own claim's
   hue. The passage→claim rule is `claimOfPassages` in the shared `assessmentStyle.js`
   (anchor first, else the first claim the passage is quoted under); the dashboard merges
   both panels, whose claim numbers agree (same claim extraction). Viewer changes, made in
   `frontend/src/pdf/PdfViewer.jsx` and re-copied (see `vendor/pdf/README.md`): colours
   are read from the current highlights (the located list had frozen them), and the
   target is drawn first where passages share a line (it lost the colour otherwise).
5. Highlights covered whole text lines, so a quote starting mid-line also marked the
   words before it (Mixing Mechanisms: "based on its position in context." before "In
   this work, …"), and the order-free match could start a few words early on words the
   quote uses later. `locate.js` now cuts the first and last line at the quote's first and
   last character (placed by measured text width) and snaps the range to the quote's own
   first/last three words. Over all 538 submission quotes of the 10 study papers: found
   536 before and after; exact start 482 → 494, exact end 477 → 528; words marked before
   the quote 48 → 0, after it 107 → 0.

Checks: dashboard on a DB copy -- every claim anchor of both panels for Mixing Mechanisms
(18/18) and AstaBench (26/26): only the clicked claim's colour strong and at the top of
the view, the claim text in the same colour, colours distinct and identical in A and B;
earlier run of 34 jumps over three papers all landing; `browser_check_layout_v4.py`
134/134; `test_renderer_parity.py` 3/3; main frontend AstaBench 13/13. Note: some claim
anchors from claim extraction span two bullets (AstaBench claims 2–4), so neighbouring
anchors overlap in the PDF by design of the data, not of the renderer.

## 13. `main_study_v2`: agent vs external systems, and three pre-launch fixes — 2026-09-23

Study design (PROTOCOL.md sections 1 and 5): `main_study_v2` replaces `main_study_v1`
before any rating (v1: 0 final responses, no code handed out). 20 tasks, the agent against
two of the three external systems per paper by a fixed rotation (afzal 6, deepreviewer 7,
opennovelty 7); agent vs linear moves to E1 and run metrics. Seeded from the unchanged
main manifest: 10 papers, 50 reports (content versions identical to v1's), 20 tasks; M01,
M02 (real) and PV01 (test) with 20 assignments each, ADMIN. M01/M02 opposite orientation on
all 20 tasks; the agent is "A" in 11 and 9 tasks. v1 closed with an audit event; its code
file renamed `OBSOLETE__participant_codes__main_study_v1__local_study.csv`. DB before:
`private/local_study.PRE_main_study_v2_20260923_222055.sqlite`. Task texts regenerated (20
files); v1's 30 archived under `archive/task_texts_main_study_v1_reviewer-v4.4/`.

Fixes found in the pre-launch review:

1. The *Development pilot — excluded from final study* banner was shown on every page of
   the main study. `App.jsx` now shows it only when `/api/me` reports `is_pilot`.
2. Prior-work arXiv links in agent/linear reports ("Source used: [v2 · …](https://arxiv…)",
   57–70 per report) were live links in the dashboard, against PROTOCOL.md section 4.
   `ReportRenderer.jsx` renders every link leaving the report as its text.
3. The login page's contact line ("(contact not configured)") is removed, by the study
   author's decision; `STUDY_CONTACT` is no longer required in production
   (`settings.py`, `SETUP_HOSTING.md`, `render.yaml`).
4. `validate-inputs` read the pilot manifest whatever the config said, so it reported
   every main-study paper missing; it now reads the config's `inputs_dir`. Main study:
   VALID, 0 errors, 10 warnings (OpenNovelty E1 text extraction, known).

Checks: `browser_check_layout_v4.py`, adapted to agent-vs-external tasks (the v4 panel is
checked, the other must be external) and extended by: no contact line and no banner on the
login page, no banner and no `a[href^=http]` in either report panel -- 83/83 on a copy of
the v2 database; `pytest final_evaluation/tests` 14 passed, 14 skipped.

### 13a. Reading step before a paper's tasks — 2026-09-23

Study author's request: per paper, read the submission first, confirm, then the tasks.
Implemented as PROTOCOL.md section 5 describes: `models.PaperReading` + migration
`0003_paper_readings`; `/api/papers/{id}/reading`, `/reading/open`, `/reading/confirm`
(confirm requires the background answers); the gate on task detail, draft and submit for
non-pilot studies; `PaperRead.jsx` (questions first, plain PDF, checkbox), the locked task
list, and a task opened too early sends the rater back. The admin export gains
`paper_background.csv` -- the familiarity answers were not exported at all before.
Real DB migrated (before: `private/local_study.PRE_reading_step_20260923_224532.sqlite`);
dashboard on 8090 restarted with the new backend.

Checks, on a migrated copy: `browser_check_layout_v4.py` 107/107, adding per paper -- tasks
locked before reading, the server answers 409 for a task of an unread paper, no document
before both questions are answered, no highlight on the reading page, continuing needs the
checkbox, tasks open after confirming; `pytest final_evaluation/tests` 14 passed, 14
skipped.

### 13b. Rubric v4: `submission_fidelity` reworded — 2026-09-23

`prompts/novelty_report_judge_v4.txt` (v3 with only the `submission_fidelity` block
replaced; `diff` shows nothing else) and `criteria.json` (version, prompt sha256, the
criterion's short question and full description); `TaskRate.jsx` reads the short
questions from `criteria.json`; the admin export writes the study's own rubric file; the
E1 adapter takes the rubric file from the config's `rubric_version` (its inputs are still
the pilot's -- E1 for the main study is open). `main.yaml` -> v4, applied by `seed-pilot`
(no response existed); the pilot stays on v3. Task texts regenerated. Checks: served
`/criteria.json` carries the new question; on a DB copy the rating form shows it with the
other four unchanged; `pytest final_evaluation/tests` 14 passed, 14 skipped.

### 13c. Reason optional, locator removed; no stale form after a rebuild — 2026-09-23

Study author's request. `TaskRate.jsx`: the locator field is gone, the reason is labelled
optional and no longer blocks submission (the 50-word cap stays); `_validate_criteria` no
longer requires it. PROTOCOL.md section 3 records the change and that the pilot answered
under the old form. `app.py` serves `index.html` and the unhashed files (`criteria.json`)
with `Cache-Control: no-cache` -- after the v4 rebuild a normal reload still showed the v3
question from the browser cache. Checks on a DB copy (Chrome): the first question is v4,
five questions, no locator, five "optional" labels, a task submits with winners only;
`pytest final_evaluation/tests` 14 passed, 14 skipped; 8090 restarted.

Follow-up the same evening: the no-cache header does not evict a copy the browser already
cached, so a normal reload still showed the v3 question; the form now fetches
`/criteria.json` (and the instructions page `/instructions.txt`) with `cache: 'no-store'`.
The short question of `conclusion_warrant` is now "Which report better justifies its
novelty judgment through its comparisons?" (study author's wording; "and their
limitations" was ambiguous). Form wording only: its full description and the judge prompt
are unchanged, so the rubric stays v4 with the same sha256. Task texts regenerated.

### 13d. Pre-handover review from a rater's view — 2026-09-23

A fresh database built exactly as the cloud setup builds it (`init-db`, `seed-pilot
--config main.yaml`, `create-participants`, `create-admin`): 10 papers, 50 reports, 20
tasks, 90 assets (43.4 MB, largest 11.9 MB). Walked through as M01 in Chrome: consent ->
20 tasks in 10 paper groups -> reading step -> task -> answers autosave ("Saved at") ->
reload restores answers and reason -> submit -> the task reopens read-only; admin export:
5 submitted rows, A/B mapped to the systems of the assignment's frozen orientation
(cross-checked against the DB), reading recorded in `paper_background.csv`; no JS errors.

Fixed from that walk: the consent page promised a practice walkthrough and "six scored
tasks" (pilot text) -- replaced by a short how-it-works note; six paper titles had broken
capitalisation ("Astabench ... Of Ai Agents", "Llms") -- corrected in `main.yaml` and in
the real DB's `main_study_v2` papers (backup
`private/local_study.PRE_titles_20260923_2400.sqlite`); the export gains
`participants.csv` (review experience, system involvement, consent time and instructions
hash -- previously not exported). SETUP_HOSTING.md names the main-study commands and that
cloud codes are new codes. Task texts regenerated; `task_texts/ALL_TASK_TEXTS__main_study_v2.md`
concatenates the 20.

### 13e. Ready for hosting: PostgreSQL, Docker, Supabase keys, backup — 2026-09-24

Local rehearsal of the cloud setup without a cloud account: the Docker image built from a
copy of exactly the files the Dockerfile copies; PostgreSQL 16 in a container; `init-db`,
`seed-pilot --config main.yaml`, `create-participants`, `create-admin` against it; the
image run with `APP_ENV=production`. Found and fixed on the way:

- `reports.id` (and the task columns referencing it) was `String(64)`, but ids like
  `main_study_v2::llms_get_lost_in_multi_turn_conversation::deepreviewer` are 74 chars:
  SQLite ignores the length, PostgreSQL refused the seed. `papers.id`, `reports.id`,
  `tasks.id` -> `String(160)` (a fresh database gets them from `0001`'s `create_all`;
  the local SQLite is unaffected).
- `LocalStorage.put` wrote Windows separators into storage keys; now POSIX.
- `backup` did not include `paper_readings`; added (round trip checked: responses,
  readings, familiarity, 40 assignments restored).
- Supabase secret keys (`sb_secret_...`) must go on `apikey` only; the storage client
  now adds `Authorization: Bearer` only for a legacy JWT key.
- `ENV_FILE` selects the settings file, so cloud CLI commands read `.env.cloud` and the
  local `.env` stays untouched.
- The rating page's "Report technical issue / pause" link removed (study author's
  request; the endpoint and the admin list remain, unused).
- `task_texts/` and `archive/` gitignored (public repository; files named by system pair).

Result in the container: 12/12 -- consent, 20 tasks, reading step with the PDF served
from storage, autosave and reload, submit, re-login shows 1 of 20, admin export (11
files incl. `participants.csv`), A/B mapped to systems, umlauts intact. Supabase Storage
itself remains untested until the real seed (SETUP_HOSTING.md section 5).

## 14. Untouched by this work

The assessment pipeline's *decisions* (`agent`, retrieval, evidence checking) and every
existing review result: no model call, no re-review, no artifact rewritten. `battle_export`
changed only in which of the already-computed fields it prints and in what order —
`verdict.py`, the evidence check and Artifact A/B are untouched. `import-pilot` remains
read-only against the pipeline, and `evaluation/e1/adapter.py` imports `eval/pilot_judge.py`
only when explicitly asked to execute. The main frontend's three PDF-viewer files are still
**copies** in `dashboard/frontend/src/vendor/pdf/` (README records the source commit)
rather than imports.

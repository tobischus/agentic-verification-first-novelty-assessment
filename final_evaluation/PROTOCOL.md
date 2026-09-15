# Evaluation protocol — dashboard_pilot_v1

Frozen rules for the human-rating pilot. Anything not written here is not part of the
protocol; anything written here that the code does not do is a bug in the code, not a
liberty in the protocol.

## 1. Scope and status

- Study id: `dashboard_pilot_v1`. Every page shows: *Development pilot — excluded from
  final study.*
- Papers: `graphrag_when_to_use`, `transducing_language_models`. Both are **development
  papers** — the pipeline was built and debugged against them. No ranking read off this
  pilot generalises; it is a functional test of the instrument plus descriptive numbers.
- The main study gets a **new study id** and does not inherit a single pilot response
  (enforced structurally: every row is scoped by `study_id`, see `models.py`).
- Systems: `agent`, `linear`, `opennovelty`, `deepreviewer`, `afzal` (internal ids;
  participants see only "Report A" / "Report B").

## 2. Materials and their versions

Frozen under `inputs/pilot/`, described in `manifests/pilot/reports.json`, resolved by
`config/sources.pilot.yaml` (which records, per paper × system, the exact source and the
reason it was chosen).

| System | What the participant sees | Provenance |
|---|---|---|
| agent | Markdown report, rendered by `battle_export.build(variant="agent")` | Deterministic re-render of the frozen `artifact_a/b_agent.json`; zero model calls |
| linear | Same renderer, `variant="linear"` | Same, from `artifact_a/b_linear.json` |
| opennovelty | The authors' **native PDF**, including the taxonomy-tree graphic | Published report, unmodified |
| deepreviewer | The **complete** `final_report.md` (Summary … References … Scores) | Local DeepReviewer 2.0 job; the earlier novelty-matrix extract is NOT used |
| afzal | `summary.txt` + `---` + `novelty_delta_analysis.txt`, verbatim | Afzal et al.'s assessment stage on this pipeline's inputs |

Content versions are recorded per report (`content_version`, e.g.
`battle_export:<script sha>+a:<artifact sha>+b:<artifact sha>`). A report rendered by a
different renderer version is a **different output version** and may not be compared
against ratings collected on the earlier one.

**Known material limits, stated rather than papered over:**

- The current `eval/out/pilot_v1/judge_calls.jsonl` (the earlier LLM-judge pilot) was run
  on *older* renderings of the agent/linear reports. Those judge results are therefore
  **not comparable** to `dashboard_pilot_v1` human ratings. `evaluation/e2/analyze.py`'s
  `compare_to_e1` says so in its own output rather than matching by task id alone.
- OpenNovelty's E1 text (`opennovelty.e1_text.md`) is a text extraction of a PDF whose
  taxonomy is partly a **graphic**. It is marked `needs_manual_check`, never
  "equivalent": a text extraction near a diagram is not evidence that it states the same
  relationships the diagram draws.
- DeepReviewer's PDF appends the original submission (the `.md` does not). The dashboard
  imports the `.md`, so the report boundary excludes those appended pages by
  construction. Any reviewer annotations that exist only on those PDF pages are **not**
  imported — an open item, recorded in ACCEPTANCE.md, not silently dropped.
- Blinding is partial: report structure, length and voice still identify a system to
  anyone who knows them, and PDF-internal branding cannot be removed without changing
  content. No claim of full anonymity is made.

## 3. Rubric

`prompts/novelty_report_judge_v2.txt`, sha256
`4b839942e7d178a9327d85ea000bc2095c4e8e15c57ff0622c13b73fca0deacc` — a verbatim copy of
`eval/prompts/novelty_report_judge_v1.txt` as it stood on 2026-09-15, which already
contained the three agreed substitutions (shared topics/methods; what prior work
establishes; judge substance not terminology). No criterion was added, removed or
weighted. `prompts/criteria.json` carries the same five descriptions for the human UI and
must not diverge; `rubric_version = novelty_report_judge_v2` is stored on every study and
exported with every response.

Five criteria, judged independently, no overall winner, no numeric scale:
`submission_fidelity`, `comparison_specificity`, `presented_evidence`,
`conclusion_warrant`, `reviewer_usefulness`. Answer values: `A`, `B`, `tie`, `unclear`.
`tie` = comparable (including equally weak); `unclear` = no defensible preference.
Every criterion requires a free-text reason of at most 50 words; `unclear` additionally
requires one of four fixed reasons.

## 4. Information boundary during E2

Shown: the submission (full PDF, all pages), report A, report B, the reports' own
references and their own displayed evidence.

Never shown: original prior-work papers (not by button, link, direct URL or API — no
prior-work PDF is imported into the study database at all, so no asset id exists to
serve), expert reference assessments, internal traces, system costs, gold labels, LLM
judge results, previous rankings.

Prior-work bibliographies stay visible inside the reports; external navigation to them is
not offered. Submission anchors remain active — a quote in an agent/linear report jumps
to that passage in the submission PDF; quotes from cited prior work render as verified
blockquotes without a jump target, because the passage is already shown in the report and
no viewer for that document exists in this study.

## 5. Tasks and assignment

Six tasks:

| Paper | Pairs |
|---|---|
| graphrag_when_to_use | agent–linear; agent–opennovelty; deepreviewer–afzal |
| transducing_language_models | agent–linear; linear–deepreviewer; opennovelty–afzal |

Two pseudonymous test participants (R01, R02), each assigned all six → twelve possible
completed ratings.

- **Orientation** (which report is "A"): `security.orientation_for(seed=43, pair_key,
  participant_ordinal)`. Deterministic; guarantees R01 and R02 see every shared pair in
  **opposite** order.
- **Order** of paper blocks and of tasks inside a block: `security.block_and_task_order`
  with seed `100 + participant ordinal`.
- Both are computed **once**, at `create-participants` time, and stored on the
  `assignments` row. Re-running any seeding command never rerolls them (verified by
  test: re-running leaves 2 participants / 12 assignments / 6 tasks unchanged).
- No participant is assigned the same pair twice (unique constraint
  `(study_id, task_id, participant_id)`).

Main study (template only, not activated): 20 papers, 10 human-rated, agent–linear on each
plus two further pairs per paper = 30 tasks × 2 raters = 60 ratings; the 20 "further"
pairs spread across the nine other pairings, each used at least twice; selection frozen
before any main-study judge result is seen. The pilot papers become practice cases there.

## 6. Reliable storage

Server database is authoritative; the browser's IndexedDB copy is a recovery buffer only.

- Autosave ~2 s after typing stops and on field blur; requests per task are sequential.
- Status is shown literally: *Unsaved changes* / *Saving…* / *Saved at …* /
  *Connection problem — changes not yet saved*. "Saved" appears only after the server
  confirms a committed revision.
- Optimistic concurrency: every write carries `expected_revision`; a stale write gets
  409 with the server's revision **and** the server's copy of the draft, and the UI
  offers both versions rather than overwriting either.
- Idempotency: submit carries an idempotency key; replaying it returns the same receipt.
  A different key against an already-final task is rejected (409). One `FinalResponse`
  row per assignment, enforced by a unique constraint.
- Finalisation is one transaction: validate → store → status → receipt.
- Finalised responses are never silently edited. An admin correction would write a new
  revision plus an audit event; the original row is kept.

## 7. Access and pseudonymity

Individual access codes (`R01-<32 hex chars>`, 128 bits of secret), stored only as
HMAC-SHA256 with a server-side pepper. Codes are shown once, written to
`private/participant_codes.csv`, distributed by hand. Optional name key stays local in
`private/participant_key.csv` and is never exported. Assignment is pseudonymous, not
anonymous.

Sessions: opaque token in an HttpOnly, SameSite=Lax cookie (Secure in production),
server-side session rows, revocable, ≤ 7 days. Mutating requests additionally require a
double-submit CSRF header. Failed logins are rate-limited per code (lockout after 8) and
per IP; error messages are generic.

Admin is a separate credential created only by `create-admin`; there is no role selector
and no way to reach admin functions with a participant code. The admin screen shows
readiness, progress, technical issues and management actions — **no system ranking while
data collection is running**. System identity appears only in the downloaded export.

## 8. Analysis (E2)

- A/B is resolved back to real system ids using the assignment's stored orientation.
- Per criterion and pair: wins per system, ties, unclear, with denominators.
  agent–linear is reported separately.
- Papers are weighted equally; additional raters are not counted as additional papers.
- Human–human agreement: exact agreement over units where ≥2 raters gave a preference
  (`A`/`B`/`tie`); `unclear` is treated as **missing**, and reported separately.
- Nominal Krippendorff's α over {first system, second system, tie}, `unclear` = missing.
  Where there is no variation or too little data, the output says `not estimable` —
  never a fabricated 0 or 1. (Implementation verified against Krippendorff's textbook
  example: α = 0.7434 vs. the published 0.743.)
- Bootstrap CIs (1 000 resamples, resampling **papers**) are implemented for the main
  study; with two pilot papers the function reports "not meaningful" instead of a number.
- E1 comparison is optional, per-orientation, and only where report/submission/rubric
  versions match. Human and judge votes are never pooled.

## 9. What is NOT implemented (and is not claimed to be)

- E3 (source-fidelity checking against prior-work papers) and E4 (repeat-run robustness):
  directory, README, and input/output schema only. No importer, no analysis, not wired
  into the CLI.
- Supabase storage and PostgreSQL are implemented and configuration-checked but were not
  exercised against a live Supabase project in this session (see ACCEPTANCE.md).
- Reviewer annotations that exist only inside DeepReviewer's PDF (on appended submission
  pages) are not extracted.

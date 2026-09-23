# Evaluation protocol — dashboard_pilot_v1 and main_study_v2

Frozen rules for the human-rating pilot and the main study. Anything not written here is
not part of the protocol; anything written here that the code does not do is a bug in the
code, not a liberty in the protocol.

## 1. Scope and status

**Main study: `main_study_v2`** (seeded 2026-09-23, `config/main.yaml`). Ten papers, the
full system (`agent`) against the three external systems, 20 tasks, two raters (M01,
M02) plus one test account (PV01, excluded from analysis). Design and the reason it
replaced `main_study_v1` before any rating: section 5. Everything below that names only
the pilot applies to the pilot.

**Pilot:**

- Study id: `dashboard_pilot_v1`. Every page of a pilot study shows: *Development pilot —
  excluded from final study.* (A main study does not: the banner is shown only when the
  study is marked `is_pilot`.)
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

The agent/linear layout is `battle_export.EXPORT_LAYOUT_VERSION`. **`reviewer-v3.2`**
(2026-09-18) reorders and links what v3.1 printed — it adds no field and drops no recorded
text. **`reviewer-v3.3`** (2026-09-19) adds one section: the paper-level novelty summary,
rendered above "Extracted claims" when Artifact B carries one. Every agent/linear
`content_version` changed with each. Development-pilot responses collected before
2026-09-18 were given against v3.1 and are not comparable to any collected after.
`seed-pilot` never swaps a report under a study that already holds it: to serve a new
layout, seed a fresh database or a new study id.

**`reviewer-v4.0`** (2026-09-22) regroups the agent/linear report for reading; it changes
no recorded content. Title → novelty summary → one closed section per claim (the row shows
the claim text, verdict, number of detailed comparisons and recorded open points) → the
related-work table and the metadata, each folded. A comparison shows source, version,
assessment, novelty argument and open points directly; its evidence check and its full
comparison with all quoted pairs sit in two closed folds. Folding is not truncation: the
markdown export, and therefore the E1 text, carries every folded text in full. The
"Closest comparisons" table is gone; every source it listed is still a detailed comparison
of the same claim. Open points are derived from structured fields only (evidence status,
`proposed_degree_supported`, recorded conflict), never from prose. Only the main study (`main_study_v1`, now
`main_study_v2`) serves this layout: its 20 agent/linear reports were switched by `cli refresh-reports`,
which refuses to replace any report someone has rated or started — the record, including
every old and new `content_version`, is `manifests/main/CONTENT_VERSIONS.md`. The pilot's
reports are unchanged, and the renderers show them in the layout they were rated in.

**`reviewer-v4.1`** (2026-09-23), on top of v4.0: a
folded legend "How to read the assessments" (overlap levels in the wording of the
definitions the comparisons were made under, and the evidence-check statuses) and the
folded related-work table come directly after the novelty summary, before the claims; the
claim row shows the overlap levels of its detailed comparisons ("13 (12 partial overlap,
1 superficial)") and no open-points count; the per-claim "Coverage and limitations"
section is removed — its counts and lists are that claim's column of the related-work
table, the stopping reasons of dismissed comparisons without a detailed section are no
longer printed; inside a comparison the quoted pairs come before the evidence check that
refers to them by number; "Main novelty concern", "Remaining contribution" and the
claim-level "Assessment" stand on their own line. This is the one v4.x change that
removes recorded text (the coverage section), by the study author's decision.

**`reviewer-v4.2`** (2026-09-23): authors and
publication date stand directly under the title (the folded "Metadata" section is gone),
and — edited by the study author in `battle_export.py` — the closing note on block
quotations, the related-work table's intro sentence and the one-line explanations after
the legend's two sub-headings are removed. No comparison text changed.

**`reviewer-v4.3`** (2026-09-23) adds the second
model-written element of an agent/linear report: under "Claim-level assessment", between
the verdict and the general sentence on what that verdict means, a claim-specific
explanation of why the claim got its verdict -- which comparisons carry it, why the
strongest is partial rather than substantial (or why a challenging one anticipates it),
and which proposed overlaps stayed unestablished or in conflict. Before, every claim
showed the same template sentence: the claim-level `rationale` had been left empty on
purpose by the study run (`eval/run_pilot.py`). `claim_assessment.py` (prompt
`claim_assessment_v1`, gpt-5.6-luna, reasoning effort low -- the settings of the novelty
summary) writes it once per claim from that claim's recorded comparisons only, with the
counts precomputed; the same step, prompt and model for agent and linear. It may not change
a verdict, a level or an evidence-check result; deterministic checks (ids, word budget,
"confirmed" vs "not confirmed" per source, no "anticipated" under "not challenged") trigger
one revision. Stored in Artifact B as `per_claim[i].claim_assessment`, deliberately not in
`rationale`, which feeds the novelty summary's fingerprint -- the 20 approved summaries
stay current. 86 claims, 268k prompt / 19k completion tokens, ≤ $0.08, 128 s
(`eval/out/human_study/claim_assessment/run.json`; Artifact B before:
`…/claim_assessment/artifact_b_before/`).

**`reviewer-v4.4`** (2026-09-23) is what the main study serves (`main_study_v2`, seeded with
the same content versions `main_study_v1` held last). Removed, by the study
author's decision: the general sentence on what a verdict means (formerly printed after
every claim-level assessment, e.g. "… This does not establish novelty across the wider
literature …") and the per-claim "Submission passages" section, which only ever held one
passage -- the claim's anchor quote (all 43 claims have exactly one, all verified). The
claim text in each claim row is now the link to that anchor in the submission PDF
(`quote_index()["claim_anchors"]`); the markdown export no longer contains the anchor
text. Note for interpretation: `claim_assessment_v1` was told the general caveat follows
its text; since v4.4 it no longer does.

**The paper-level summary is the one model-written element of an agent/linear report that
is not a per-claim result.** `paper_synthesis.py` produces it once from the finished claim
reviews — same step, same prompt (`paper_synthesis_v1`) and same model for the agent and
for the linear baseline, so a difference between their reports stays a difference in their
reviews rather than in how those reviews were summarised. It is stored in Artifact B with a
fingerprint of the exact findings it was derived from; if those change, the export prints
the summary marked out of date rather than dropping it or letting it stand silently.

**Main study:** all 20 agent/linear reports carry an approved summary. **Pilot, not yet
generated for every report:** as of 2026-09-19 only `graphrag_when_to_use`
(agent and linear) has one. Until `transducing_language_models` has been given the same
two calls, its agent/linear reports open without the section while GraphRAG's open with it,
which is a presentation difference between the two papers and must not be carried into a
data-collecting study.

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
- The renderer's presentation layer — colour-coded assessments, collapsible blocks,
  assessment links — keys on wording only `battle_export` produces, so it reaches the
  agent and linear reports and not DeepReviewer's or Afzal's markdown. That is one more
  presentation difference between the two families, on top of the structural ones above;
  it bears on `reviewer_usefulness` in particular. No report's **content** differs because
  of it: the renderers parse the frozen text and never rewrite it.

## 3. Rubric

**Current (main study): `prompts/novelty_report_judge_v4.txt`**, sha256
`fcacd68e51234ae1749bf64bfe29efbeb2e1ab7847ec3740eb0cabd8b2d9e0f6`. The pilot stays on
**v3** (`prompts/novelty_report_judge_v3.txt`, sha256
`567819a36c0561411a5f5e4f3c1c17affd96c6984238fce69dad8edd3cec4ffa`), under which its
responses were given. `prompts/criteria.json` carries the same five descriptions and the
short questions the rating form shows (the form reads both from it) and must not diverge
from the judge prompt; `rubric_version` is stored on every study and exported with every
response, and the export's `rubric.txt` is the file of that version.

Version history (a revision never rewrites the version a finalised answer was given
under — `seed-pilot` updates a study's stored version only while it has no finalised
response, and reports the mismatch instead of overwriting once it has):

- **v2** (2026-09-15), sha256 `4b839942e7d178a9327d85ea000bc2095c4e8e15c57ff0622c13b73fca0deacc`
  — a verbatim copy of `eval/prompts/novelty_report_judge_v1.txt` as it stood that day,
  which already contained the three agreed substitutions (shared topics/methods; what
  prior work establishes; judge substance not terminology).
- **v3** (2026-09-15) — adds two help sentences to `submission_fidelity` and nothing
  else: assess descriptions of the submission *throughout both reports, including the
  comparisons, not only the extracted claims*, and *identical extracted claim text is not
  by itself a reason to choose tie*. Same five criteria, no weights, no other wording
  touched. Applied to the judge prompt and `criteria.json` together, so E1 and E2 read
  the same rubric.
- **v4** (2026-09-23, study author's decision) — rewords `submission_fidelity` only. v3
  asked which report represents the submission's "contributions, methods, assumptions,
  and scope" (the form's short question even said "limitations"); novelty reports do not
  systematically cover methods, assumptions or limitations, so a rater did not know what
  to judge. v4 asks *which report more accurately describes what the submission
  contributes* and says where to look -- wherever a report describes the submission (its
  list of contributions or claims, its summary, its comparisons) -- and what to check:
  central contributions captured, stated accurately (not inflated, narrowed, or attributed
  to the wrong part of the work), none important missing. "Claims" appears only as one
  of the places to look, never as the object: it is the agent/linear reports' own term.
  The identical-text sentence and the prior-work exclusion are kept. The other four
  criteria are unchanged. Also since v4: the rating form's short questions come from
  `criteria.json`, not from a second copy in `TaskRate.jsx` (the source of the v3
  "limitations"/"scope" mismatch). Applied before any main-study response (seed-pilot:
  `rubric_version: novelty_report_judge_v3 -> novelty_report_judge_v4`).

The human instructions are versioned in the same way: **`human_instructions_v2`**
(2026-09-15) replaces v1's "Do not favor matching terminology…" sentence with "Do not
prefer terminology, format, length, or positive or negative judgments by themselves.
Consider clarity and effort when assessing reviewer usefulness.", and adds "Verification
labels are system claims, not independent validation." Everything else is v1 verbatim.
A participant's consent record stores the sha256 of the text they actually saw
(`Participant.consent_instructions_sha256`), so a later revision cannot retroactively
claim they consented to it.

Five criteria, judged independently, no overall winner, no numeric scale:
`submission_fidelity`, `comparison_specificity`, `presented_evidence`,
`conclusion_warrant`, `reviewer_usefulness`. Answer values: `A`, `B`, `tie`, `unclear`.
`tie` = comparable (including equally weak); `unclear` = no defensible preference.
Every criterion takes an optional free-text reason of at most 50 words; `unclear`
requires one of four fixed reasons. (Until 2026-09-23 the reason was required and the form
had an optional "locator" field; the pilot's responses were given under that form. Both
were changed for the main study at the study author's request: with the agent in every
main-study task, a required reason per criterion asks the same rater to restate the same
observation 20 times, and the locator was rarely filled. A reason, where given, is kept
and exported; the analysis uses the winners.)

## 4. Information boundary during E2

Shown: the submission (full PDF, all pages), report A, report B, the reports' own
references and their own displayed evidence.

Never shown: original prior-work papers (not by button, link, direct URL or API — no
prior-work PDF is imported into the study database at all, so no asset id exists to
serve), expert reference assessments, internal traces, system costs, gold labels, LLM
judge results, previous rankings.

Prior-work bibliographies stay visible inside the reports; external navigation to them is
not offered. The agent/linear export links each source to its arXiv PDF ("Source used:
[v2 · 2023-07-18](…)"); the dashboard renders every link that leaves the report as its
text only (fixed 2026-09-23 -- before, these were live links opening the prior-work PDF). Submission anchors remain active — a quote in an agent/linear report jumps
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

**Main study, `main_study_v2`** (2026-09-23): 10 human-rated papers, two tasks each, the
agent against two of the three external systems -- paper i (in `config/main.yaml` order)
skips `[afzal, deepreviewer, opennovelty][i % 3]`. 20 tasks: agent–afzal 6,
agent–deepreviewer 7, agent–opennovelty 7. Two raters (M01, M02) each rate all 20 → 40
ratings; PV01 is a test account. Orientation and order as for the pilot (seed 43, order
seed 100 + ordinal): M01 and M02 see every task in opposite order, and the agent report
is "A" in 11/20 tasks for one rater and 9/20 for the other. No practice task. The pairing
was fixed before any main-study E1 (LLM judge) result was looked at.

**Reading step (main study only, 2026-09-23).** A paper's two tasks open only after the
rater has read the submission once: the task list shows "Read the submission" above them
and the tasks locked; the reading page asks the two background questions first
(familiarity with the area, read before -- asked once per paper, previously in the
paper's first task) and shows the submission PDF only once both are answered; the PDF is
shown plain, without the reports' highlights, so that no report's focus is seen before
the reports; a checkbox ("I have read or skimmed the submission") unlocks the tasks. The
server enforces it (a task of an unread paper returns 409 `read_submission_first`; a
submitted task stays viewable). Recorded per rater and paper (`paper_readings`): first
visit, confirmation time, and the time the page was visible and focused -- recorded, never
used to block. Exported with the background answers as `paper_background.csv`. The pilot
keeps its old flow (`is_pilot`).

Why it replaced `main_study_v1` (30 tasks: agent–linear on every paper plus two further
pairings): agent and linear share the claims, the prior-work pool, the renderer and the
summary and claim-assessment model; they reach the same verdict on 41 of 43 claims and
differ mainly inside folded comparison detail (number and selection of comparisons,
evidence status). A full-report A/B judgement of them costs a rater the most reading for
the least decidable difference. The agent–linear comparison is therefore made by E1 on
all papers, validated against the human ratings of the 20 tasks, and by run metrics
(number of comparisons, evidence status, quote verification, verdict agreement, cost,
time); abstaining human adjudication, verdict disagreements are reported as unresolved.
`main_study_v1` held 0 responses and no participant code had been handed out; it stays in
the database, closed, with an audit event (`close_study`, superseded_by
`main_study_v2`), and its code file is renamed `OBSOLETE__…`. DB before the change:
`private/local_study.PRE_main_study_v2_20260923_222055.sqlite`.

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
`private/participant_codes__<study>__<database>.csv` (main study:
`participant_codes__main_study_v2__local_study.csv`), distributed by hand. Optional name
key stays local in `private/participant_key.csv` and is never exported. Assignment is
pseudonymous, not anonymous. The login page shows no contact line: the raters are recruited
personally and contact the study author directly (`STUDY_CONTACT` is no longer required).

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
  agent–linear is reported separately (pilot; in the main study it is not a human task --
  see section 5).
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

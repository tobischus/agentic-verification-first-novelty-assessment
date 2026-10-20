# Evaluation protocol — dashboard_pilot_v1 and main_study_v2

Frozen rules for the human-rating pilot and the main study. Anything not written here is
not part of the protocol; anything written here that the code does not do is a bug in the
code, not a liberty in the protocol.

## 1. Scope and status

**Main study: `main_study_v2`** (seeded 2026-09-23, `config/main.yaml`). Ten papers, the
full system (`agent`) against the three external systems, 20 tasks, three raters (M01,
M02, and M03 added on 2026-10-01, section 5) plus one test account (PV01, excluded from
analysis). Design and the reason it
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

**Current (main study): `prompts/novelty_report_judge_v5.txt`**, sha256
`e266b00b2c744c076afcaf77c3ee616c2ac65f9094deda6f5a33093c381f6eef`. The raters read its
CRITERIA section: `prompts/criteria.json` carries the same five descriptions verbatim and
the short questions the rating form shows (the form reads both from it). Its other
sections are for the judge only (see the v5 entry below) and are never shown to a rater.
The pilot stays on **v3** (`prompts/novelty_report_judge_v3.txt`, sha256
`567819a36c0561411a5f5e4f3c1c17affd96c6984238fce69dad8edd3cec4ffa`), under which its
responses were given. `criteria.json` must not diverge from the judge prompt's CRITERIA
section; `rubric_version` is stored on every study and exported with every response, and
the export's `rubric.txt` is the rubric file of that study. `compare-e1` compares the
CRITERIA section of that file with the judge rubric's, by content.

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
- **v5** — the main study's rubric. Two parts:
  - *Criteria* (fixed 2026-09-23, study author's decision, before any main-study
    response; the text the raters read). Rewords `submission_fidelity` only. v3 asked
    which report represents the submission's "contributions, methods, assumptions, and
    scope" (the form's short question even said "limitations"); novelty reports do not
    systematically cover methods, assumptions or limitations, so a rater did not know what
    to judge. v5 asks *which report more accurately describes what the submission
    contributes* and says where to look -- wherever a report describes the submission (its
    list of contributions or claims, its summary, its comparisons) -- and what to check:
    central contributions captured, stated accurately (not inflated, narrowed, or
    attributed to the wrong part of the work), none important missing. "Claims" appears
    only as one of the places to look, never as the object: it is the agent/linear
    reports' own term. The identical-text sentence and the prior-work exclusion are kept.
    The other four criteria are unchanged from v3. Also since 2026-09-23: the rating
    form's short questions come from `criteria.json`, not from a second copy in
    `TaskRate.jsx` (the source of the v3 "limitations"/"scope" mismatch).
  - *Judge-only sections* (2026-10-01, before any E1 call; section 8a): a section LENGTH,
    COVERAGE AND PRECISION, two procedure sentences and an `inventory` block in the
    response. Never shown to a rater.

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

**Third rater M03 (2026-10-01, study author's decision).** Added to the running study on
the cloud database, after M02 had submitted all 20 tasks and those responses had been
exported and looked at; M01 had submitted none. Reason: agreement needs at least two
completed raters, and a third makes the human result less dependent on any single one.
Same 20 tasks, rubric, instructions and reports; nothing else in the study changed.
`create-participants --count 3 --prefix M --not-test` created M03 only, with its 20
assignments; M01, M02 and PV01 kept theirs. The code gives a new participant the ordinal
"participants already in the study + its number", here 3 + 3 = **6**: orientation as for
every even ordinal, so M03 sees every task in the same A/B orientation as M02 and the
opposite of M01 (agent report "A" in 9/20 tasks), and its own task order (order seed 106). The
ordinal follows from the code, never chosen by hand. Cloud backup immediately before:
`backups/main_study_v2__cloud__PRE_M03_20261001.zip`.

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
- E1 comparison (`compare-e1`) is per orientation -- a rater who saw X as A is compared
  with the judge call that saw X as A -- and only where the CRITERIA section of the judge
  call's rubric equals the one in the export's `rubric.txt` (compared by content) and both
  reports' `content_version` equal the export's `manifest.json`; everything else is
  listed as not comparable with its reason. `unclear` on either side is missing.
  Agreement is also reported on the position-stable judge verdicts (same winner in both
  orders). Human and judge votes are never pooled.

## 8a. E1 (LLM judge) on the main study

**Design.** `config/e1_main.yaml`, id `e1_main_v5`, results in `results/main/e1/`, as
designed on 2026-09-14: 20 papers, all five systems, all 10 pairs, each in both orders
(400 calls), rubric v5 (section 3), judge `gpt-6.1-sol` (effort medium) through
`eval/pilot_judge.py`. The ten human-rated papers are judged on the same frozen files the
raters see (`inputs/main/`); the ten further papers are E1 only (`config/e1_extra.yaml`,
frozen to `inputs/e1_extra/`, refused by `seed-pilot`/`create-participants`). Calls on a
human task are marked `human_task`; the judge is not told. The execution order is shuffled
with seed 42. The judge sees the submission text and both reports in full with line ids;
nothing is shortened, so the longest pairs are long (~348K tokens for astabench
agent/linear) -- whether they fit the judge's context is checked with a single narrowed
run before the full one, not by cutting text. The ten further papers were chosen before
any E1 result was seen; the two pilot papers were used to develop the agent and are not
among them.

**The judge-only sections of v5** (`prompts/novelty_report_judge_v5.txt`). The raters'
instructions (`human_instructions_v2`) say "Do not prefer terminology, format, length, or
positive or negative judgments by themselves"; v5 gives the judge the same rule and says
how to apply it. The CRITERIA section is the raters' text unchanged. Three additions:
1. A section LENGTH, COVERAGE AND PRECISION, before CRITERIA, for every criterion: more
   text, comparisons, sources or quotations are not by themselves better; off-point
   comparisons (shared topic or generic method only), repetition, evidence that does not
   support its stated correspondence and self-contradiction count against a report and are
   not excused by completeness; a missing comparison is a weakness only where the other
   report examines that contribution with relevant support, and is none where the other
   report's comparison is itself off-point or unsupported; a stated "no close prior work
   found" addresses a contribution (its warrant is judged under `conclusion_warrant`);
   added material earns a preference only if it would change a reviewer's novelty
   judgment.
2. PROCEDURE: list the submission's central contributions, take for each the strongest
   comparison each report offers, base `comparison_specificity`, `presented_evidence`
   and `conclusion_warrant` mainly on these, then weigh the rest under the section above.
3. OUTPUT: an `inventory` before `criteria` -- `central_contributions` (at most six) and,
   per report, `contributions_examined` (all/most/some/none), `off_point_material`,
   `repetition`, `unsupported_or_contradicted` (low/medium/high). A missing or malformed
   inventory is a technical error with the same bounded retries as any other.

The rules are symmetric: coverage of a central contribution still counts, so they can go
against either system.

**Requests -- billing only.** The calls run:

- on the **flex** service tier (same model, half price, slower; capacity 429s are waited
  out, are not billed and do not count as one of the three attempts);
- with the **same user text sent as three text parts** with cache breakpoints after the
  submission and after report A (`pilot_judge.user_parts`). The parts concatenate to the
  identical string -- checked for all 400 planned calls, and `prompt_sha256` is computed
  over it -- and a message sent as parts tokenizes identically to the single string
  (probe: same prompt token count, full cache hit across the two forms);
- in **`cache_order`**: all calls of a paper back to back, and within a paper the calls
  that share report A back to back. This adds no randomness: papers, groups and calls
  keep the relative order of the seed-42 shuffle. A drift of the API can now align with a
  paper -- whose ten pairs all run within minutes, under the same conditions -- but not
  with a system; position is still controlled by the two orders.

OpenAI states that prompt caching does not change how output tokens are generated. Each
record stores `service_tier`, `cache_tokens` (reads), `cache_write_tokens`,
`system_fingerprint` and `billed_usd`. Prices from the OpenAI price page on 2026-10-01:
$2.00 input, $0.10 cache read (0.05x), $2.50 cache write, $10.00 output per 1M; flex half;
above 272K input tokens 2x input, 1.5x output. The cache-write behaviour was measured with
probe calls for GPT-5.6 only (2026-09-24); the raw counts are stored, so `billed_usd` can
be recomputed. `--standard` / `--no-cache` restore the standard tier / the pilot's exact
request.

**Execution (2026-10-01).** 400/400 calls recorded without failure, the first being the
context check (#219 astabench linear/agent, 276,628 input tokens, valid on the first
attempt). Billed $15.21; 65% of 28.2M input tokens were cache reads; one call needed a
retry. The run stopped once when the account's API credit ran out: calls #44 and #172
failed on all three attempts with `insufficient_quota` (`credit_balance_exhausted`, no
model output). Both records stay in `judge_calls.jsonl`, which is why `analyze-e1`
reports 2 technical failures, and both calls succeeded when the same command was resumed
after the credit was topped up.

**Analysis.** `analyze-e1` reports stability, pairs and the Bradley-Terry fit on the Elo
scale (1000 = mean of the five systems, +400 = 10:1 odds) with 95% CIs from resampling
papers, per criterion and pooled over the five criteria, and arena-style online Elo (K=16,
mean over 1000 game orders) as a check on the ranking. The Elo scale rescales the
Bradley-Terry fit -- solved by Newton's method -- and adds no test; the pooled rating
treats the five criteria of one call as separate games and is a summary only. Each rating
also carries Chatbot Arena's rank (Chiang et al., 2024): 1 + the number of systems whose
95% CI lies entirely above its own, so systems the data cannot separate share a rank. It
reads the same CIs and adds no test. `compare-e1` compares the judge with the raters
(section 8) and names the judge rubric in its output; `figures --e1-dir` draws the
slides. The inventory is stored and described; no test is run on it.

**Sensitivity analysis -- post hoc, exploratory.** `sensitivity-e1`
(`evaluation/e1/sensitivity.py`) asks how much of the judge's verdicts is explained by how
much a report shows: Bradley-Terry with the log length ratio as covariate (all five
systems), and for agent vs linear -- same renderer -- the log ratio of detailed comparisons
shown. Both covariates are partly products of each system's design, so the adjusted
numbers answer "at equal coverage/length", never replace the unadjusted result, and are
reported next to it. Between our two systems and the three baselines the lengths barely
overlap (printed with the result), so the five-system adjustment extrapolates there; the
length slope is also reported from within-group pairs only, where lengths do overlap.

## 8b. Agent vs linear from the run records (2026-09-25) -- post hoc test

Section 5 names the run metrics by which agent and linear are compared (number of
comparisons, evidence status, quote verification, verdict agreement, cost, time).
`agent-linear` (`evaluation/agent_linear.py`) computes them for the 20 E1 papers and tests
them paired by paper. **Status, stated plainly:** the metrics were named on 2026-09-23;
the test was chosen on 2026-09-25, after the per-paper numbers had been computed once ad
hoc. Every metric is therefore reported whichever way it
points, with its p-value both unadjusted and Holm-adjusted across all tested metrics.

- Inputs: exactly the artifacts the frozen reports were rendered from -- every
  `artifact_a/b_<variant>.json` and report file is sha256-checked against
  `manifests/<set>/reports.json`; the run refuses on a mismatch. Per-variant numbers come
  from `eval/run_metrics.py`, the code that wrote the per-paper `__metrics.json` files.
- Unit: the paper (n = 20). Test: exact two-sided sign test, papers with equal values left
  out. Metrics that are zero for linear by construction (dismissal, re-entry, and
  "compared" = recorded minus dismissed) are descriptive only.
- How a (claim, prior paper) pair ended is read from the run log: dismissed before any
  comparison / passed the first evidence check / resolved by re-entry / unresolved.
- **Matched pairs** (added after the all-pairs table was seen): linear's single pass rates
  most of the pairs the agent dismissed as `none / insufficient`, so counts over all
  pairs mix how a flow handled a pair with which pairs it chose to handle. The grounding
  metrics are therefore also reported on the pairs both flows compared. Both blocks are
  in the Holm family.
- **Re-entry outcomes** (descriptive): for every pair the agent compared twice, the first
  and the last turn's proposed degree and evidence status, read from the per-turn trace
  lines `claim_agent` writes, classify how the pair ended (overlap confirmed / overlap
  rejected / still in disagreement) and what moved (degree, evidence status, both,
  neither). A resolution in which only the evidence status moved may reflect the
  evidence check's run-to-run variance as much as the additional reading; E4 (repeat
  runs) would separate the two and is not implemented.
- USD are the runs' list-price estimates, not billed amounts (section 8a); only the ratio
  between the flows is compared.

**Adjudication of the divergent verdicts (2026-09-25).** Section 5 reports verdict
disagreements as unresolved in the absence of human adjudication. The four E1-paper claims
on which the flows disagree (in every case the agent challenged and linear did not) are
now adjudicated by the study author with `adjudication-packet`
(`scripts/adjudication_packet.py`, output `results/main/agent_linear/adjudication/`), in
two stages: Part A shows the claim, the prior paper that makes the challenging side
challenge, and every verbatim-verified passage pair either flow grounded for it -- pooled,
without degree, strength or verdict -- and the author records a degree and a
challenged/not-challenged decision; only then Part B shows both assessments side by side
as X/Y (seed 2026), and the author records which reads the prior paper more accurately.
The key is opened last. Blinding is partial (the direction of the divergence is known and
a single-pass ending is recognisable), and the adjudicator built the system: this is an
**author adjudication, not an independent one**, reported as such. A case the author marks
`unsure` stays unresolved.

## 8c. E3, automatic part: source audit (2026-09-27) -- descriptive

`source-audit` (`evaluation/e3/source_audit.py`) reports, for agent and linear on the 20 E1
papers, the two judge-free metrics the midterm presentation announced -- the **grounding
rate** (overlap comparisons that show a quote pair) and the **verifiability rate** (proposed
quote pairs whose two sides the pipeline found in the sources) -- plus the ownership rate
and an audit of every quote a report shows. The audit does not reuse the pipeline's
verifier: each quote is looked up again in the source text it was verified against, after
that text has been tied to the run by its hash (the submission corpus against
`submission_selection.source_sha256`, the prior-work text against `parsed_text_sha256`).
A quote counts as exact (case- and whitespace-insensitive substring), near-verbatim
(rapidfuzz partial_ratio >= 90, the pipeline's own threshold) or not found; a source whose
text has no recorded hash (abstract + introduction only) is reported as not auditable.
Added post hoc; it adds no test and compares no system to another --
the numbers describe what the two flows' reports rest on. Artifacts are sha256-checked
against the manifests as in section 8b.

## 8d. E3 across systems: OpenNovelty's quotes (added 2026-10-01, after E1 and 8c)

Post hoc and descriptive, no test. Of the three external systems only OpenNovelty shows passages
from prior work ("Evidence – Original – Candidate" under each "Prior Art Analysis"). DeepReviewer
2.0 quotes the submission only (16 of 16 quoted spans found in it); Afzal et al. quote the
authors' phrases, titles and category names, no passage of a prior paper. 
`evaluation/e3/opennovelty_audit.py` parses OpenNovelty's PDF reports (the candidate's link
target is read from the PDF), fetches each candidate's full text (arXiv, else the Semantic
Scholar open-access PDF or the venue's PDF), and looks every candidate passage up with 8c's
rule (exact or partial_ratio >= 90; a quote elided with "..." is checked piece by piece). The
candidate's first public date is compared with the submission's `publication_date`. Fetched
PDFs are cached and their sha256 stored in `results/main/e3/opennovelty_audit.json`.

**Result.** 66 passages in 12 of the 20 papers. 55 of the 56 checkable passages were found
(10 could not be fetched). 62 candidates are dated: 60 predate the submission; the other 2
are the submission itself (AgentGym-RL, cited as prior art for its own ScalingInter-RL). For
comparison, the agent shows 2,750 quotes on all 20 papers (8c). The extraction differs from
8c (PyMuPDF on the fetched PDF, not the run's hash-pinned parsed text), so the two found-rates
are close but not identical measurements.

## 9. What is NOT implemented (and is not claimed to be)

- E3's manual part (whether what a report says about prior work -- including absence
  claims such as "paper X does not do Y", and anything in the external systems' free text
  -- holds when the prior-work paper is read) and E4 (repeat-run robustness): README and
  input/output schema only. E3's automatic part is section 8c.
- Supabase storage and PostgreSQL are implemented and configuration-checked but were not
  exercised against a live Supabase project in this session (see ACCEPTANCE.md).
- Reviewer annotations that exist only inside DeepReviewer's PDF (on appended submission
  pages) are not extracted.

# Evaluation protocol

Rules of the evaluation reported in the thesis: the LLM judge (E1), the human study
`main_study_v2` (E2), the comparison of agent and linear from the run records, and the
source audit (E3). All dates are 2026.

## 1. Scope

- **E2:** study `main_study_v2` (seeded 2026-09-23, `config/main.yaml`), ten papers,
  20 tasks. Three raters were invited (M01, M02, M03). M01 gave no rating. M02 and M03
  completed all 20 tasks. PV01 is a test account and is excluded from the analysis.
- **E1:** 20 papers, the ten of the study plus the ten of `config/e1_extra.yaml`.
- Systems: `agent`, `linear`, `opennovelty`, `deepreviewer`, `afzal`. Participants see
  only "Report A" and "Report B".

## 2. Materials

`import-inputs` freezes all reports and submission texts under `inputs/main/` and
`inputs/e1_extra/` and records their hashes in `manifests/<set>/reports.json`.
`config/sources.*.yaml` records the source of every report.

| System | What the participant sees | Provenance |
|---|---|---|
| agent | Markdown report rendered by `battle_export.build(variant="agent")` | Re-render of the frozen `artifact_a/b_agent.json`, no model call |
| linear | Same renderer, `variant="linear"` | Same, from `artifact_a/b_linear.json` |
| opennovelty | The authors' native PDF, including the taxonomy graphic | Published report, unmodified |
| deepreviewer | The complete `final_report.md` | Local DeepReviewer 2.0 job |
| afzal | `summary.txt` + `---` + `novelty_delta_analysis.txt`, verbatim | Assessment stage of Afzal et al. on this pipeline's inputs |

Every report carries a `content_version`. For agent and linear it is
`battle_export:<renderer sha>+a:<Artifact A sha>+b:<Artifact B sha>`.

Two parts of an agent or linear report are written by a model after the claim reviews:
the paper-level summary (`paper_synthesis.py`) and one claim-level assessment per claim
(`claim_assessment.py`, prompt `claim_assessment_v1`). Both use `gpt-5.6-luna` and read
only the recorded results. They cannot change a verdict, a degree or an evidence check.
The summaries of the ten study papers were written with `paper_synthesis_v2`, except the
linear summary of `astabench`, and all others with `paper_synthesis_v3`. Each summary
records its prompt version and hash. The
dashboard folds parts of these reports. The markdown export, and therefore the E1 text,
contains every folded text in full.

Known limits:

- OpenNovelty's E1 text (`opennovelty.e1_text.md`) is extracted from a PDF whose
  taxonomy is partly a graphic. `validate-inputs` marks it `needs_manual_check`.
- DeepReviewer's PDF appends the submission. The study imports the `.md`, which does not
  contain these pages.
- Blinding is partial. Structure, length and voice can identify a system, and branding
  inside a PDF cannot be removed without changing its content.
- The renderer's presentation layer (colour-coded assessments, folds, links) applies to
  the agent and linear reports only. It never changes the text of a report.

## 3. Rubric and instructions

Rubric: `prompts/novelty_report_judge_v5.txt`, sha256
`e266b00b2c744c076afcaf77c3ee616c2ac65f9094deda6f5a33093c381f6eef`. The raters read its
CRITERIA section. `prompts/criteria.json` holds the same five descriptions verbatim and
the short questions of the rating form. The other sections are for the judge only
(section 8a). The criteria were fixed on 2026-09-23, before any rating, and the
judge-only sections on 2026-10-01, before any E1 call. The export's `rubric.txt` is the
rubric of the study, and `compare-e1` compares its CRITERIA section with the judge's.

Instructions: `prompts/human_instructions.md` (`human_instructions_v2`). The consent
record stores the sha256 of the text the participant saw
(`Participant.consent_instructions_sha256`).

Five criteria, judged independently, with no overall winner and no numeric scale:
`submission_fidelity`, `comparison_specificity`, `presented_evidence`,
`conclusion_warrant`, `reviewer_usefulness`. Answers: `A`, `B`, `tie`, `unclear`. `tie`
means comparable, including equally weak. `unclear` means no defensible preference and
requires one of four fixed reasons. Every criterion takes an optional reason of at most
50 words.

## 4. Information boundary during E2

Shown: the submission (full PDF), report A, report B, and the references and evidence
the reports display themselves.

Never shown: prior-work papers, expert assessments, internal traces, system costs, LLM
judge results and rankings. No prior-work PDF is imported into the study database, so
no asset id exists to serve one. Links that leave a report are shown as text only.
Quotes from the submission link to their passage in the submission PDF.

## 5. Tasks and assignment

Ten papers with two tasks each. Each task pairs the agent with one of the three external
systems. Paper i (in `config/main.yaml` order) skips
`[afzal, deepreviewer, opennovelty][i % 3]`. This gives 20 tasks: agent–afzal 6,
agent–deepreviewer 7, agent–opennovelty 7. The pairing was fixed before any E1 result
was seen. There is no practice task.

- **Orientation** (which report is "A"):
  `security.orientation_for(seed=43, pair_key, participant_ordinal)`. Raters with even
  and odd ordinals see every task in opposite orientation.
- **Order** of paper blocks and of the tasks inside a block:
  `security.block_and_task_order` with seed `100 + participant ordinal`.
- Both are computed once by `create-participants` and stored on the assignment. Seeding
  again never changes them. A participant has each task at most once (unique constraint
  `(study_id, task_id, participant_id)`).
- M03 was added on 2026-10-01 with `create-participants --count 3 --prefix M --not-test`.
  The code gives a new participant the ordinal "participants already in the study + its
  number", here 3 + 3 = 6. M03 therefore sees the orientation of M02 and the opposite of
  M01, with its own task order (seed 106).

**Reading step.** A paper's tasks open only after the rater has read the submission. The
reading page asks two background questions (familiarity with the area, read before),
then shows the submission PDF without highlights. A checkbox unlocks the tasks. The
server enforces this (409 `read_submission_first`). The answers and the reading time are
exported as `paper_background.csv`.

**Agent vs linear.** The study contains no agent–linear task. The two flows share
claims, prior-work pool, renderer and the models of summary and claim assessment, so
their reports differ mainly in folded comparison detail. They are compared by E1 on all
papers and by run metrics: number of comparisons, evidence status, quote verification,
verdict agreement, cost and time (section 8b). The study replaced `main_study_v1`, which
contained agent–linear tasks, on 2026-09-23 before any rating was given.

## 6. Storage

The server database is authoritative. The browser keeps a recovery copy only.

- Autosave about 2 s after typing stops. "Saved" appears only after the server confirms
  a committed revision.
- Every write carries `expected_revision`. A stale write gets 409 with the server's
  copy, and the form offers both versions.
- Submit carries an idempotency key. One `FinalResponse` per assignment, enforced by a
  unique constraint. Finalised responses are never edited.

## 7. Access and pseudonymity

Individual access codes with 128 bits of secret, stored only as HMAC-SHA256 with a
server-side pepper and handed out personally. Codes are written once to `private/`,
which is not part of the repository or the data archive. Assignment is pseudonymous.

Sessions use an opaque HttpOnly cookie (SameSite=Lax, Secure in production) and expire
after 7 days. Mutating requests require a CSRF header. Failed logins are rate-limited
per IP, and a code is locked after 8 failures.

The admin account is created by `create-admin` and is separate from participant codes.
The admin screen shows progress and no ranking of systems. System
identities appear only in the export.

## 8. Analysis (E2)

- A and B are mapped back to the systems with the stored orientation.
- Per criterion and pair: wins per system, ties and unclear, counted in responses, also
  per paper.
- Agreement between raters: exact agreement over units where at least two raters gave
  `A`, `B` or `tie`, and nominal Krippendorff's α over {first system, second system,
  tie}. `unclear` is missing. Without variation or with too little data the output says
  `not estimable`.
- `compare-e1` compares each human response with the judge call of the same orientation,
  and only where the CRITERIA sections match and both reports' `content_version` equal
  the export's `manifest.json`. Agreement is also reported on the judge verdicts that are
  stable across both orders. Human and judge votes are never pooled.

## 8a. E1 (LLM judge)

**Design.** `config/e1_main.yaml`, id `e1_main_v5`, results in `results/main/e1/`. 20
papers, all five systems, all 10 pairs, each in both orders (400 calls), rubric v5,
judge `gpt-6.1-sol` (reasoning effort medium) through `eval/pilot_judge.py`. The ten
study papers are judged on the same frozen files the raters saw. The ten further papers
were chosen before any E1 result was seen. The judge sees the submission text and both
reports in full with line ids. Nothing is shortened.

**Judge-only sections of v5.** The CRITERIA section is the raters' text. v5 adds:

1. LENGTH, COVERAGE AND PRECISION: more text, comparisons, sources or quotations are not
   better by themselves. Off-point comparisons, repetition, unsupported evidence and
   self-contradiction count against a report. A missing comparison is a weakness only
   where the other report examines that contribution with relevant support.
2. PROCEDURE: list the central contributions, take for each the strongest comparison of
   each report, and base `comparison_specificity`, `presented_evidence` and
   `conclusion_warrant` mainly on these.
3. OUTPUT: an `inventory` before `criteria` with the central contributions (at most six)
   and per report `contributions_examined`, `off_point_material`, `repetition` and
   `unsupported_or_contradicted`. A missing inventory is a technical error with the same
   retries as any other.

**Requests.** The calls run on the flex service tier with the user text sent as three
parts with cache breakpoints after the submission and after report A
(`pilot_judge.user_parts`). The parts concatenate to the identical string, and
`prompt_sha256` is computed over it. The execution order is the seed-42 shuffle, grouped
by paper and by report A (`cache_order`) without changing the relative order. Each record
stores `service_tier`, cache tokens, `system_fingerprint` and `billed_usd`.

**Execution (2026-10-01).** 400 of 400 calls recorded, billed $15.21. Calls #44 and #172
first failed with `insufficient_quota` and succeeded after the credit was topped up. Their
failed records stay in `judge_calls.jsonl`, so `analyze-e1` reports 2 technical failures.

**Analysis.** `analyze-e1` reports position stability, pairs and a Bradley-Terry fit on
the Elo scale (1000 = mean of the five systems, +400 = 10:1 odds) with 95% CIs from 1,000
resamples of papers, per criterion and pooled. Ranks follow Chatbot Arena: 1 + the number
of systems whose CI lies entirely above. Online Elo (K = 16, mean over 1,000 game orders)
checks the ranking. `scripts/thesis_figures.py` draws the figures.

**Sensitivity, post hoc.** `sensitivity-e1` adds the log length ratio as a covariate (all
five systems) and, for agent vs linear, the log ratio of detailed comparisons. The
adjusted numbers are reported next to the unadjusted ones. The lengths of our two systems
and the three external systems barely overlap, so the five-system adjustment
extrapolates. The length slope is also reported from within-group pairs only.

## 8b. Agent vs linear from the run records

`agent-linear` (`evaluation/agent_linear.py`) computes the metrics of section 5 for the
20 E1 papers. The metrics were named on 2026-09-23. The test was chosen on 2026-09-25,
after the per-paper numbers had been computed once, so every metric is reported whichever
way it points.

- Inputs: the artifacts the frozen reports were rendered from, sha256-checked against
  `manifests/<set>/reports.json`. Per-variant numbers come from `eval/run_metrics.py`.
- Unit: the paper (n = 20). Test: exact two-sided sign test, papers with equal values left
  out, p-values unadjusted and Holm-adjusted across all tested metrics. Metrics that are
  zero for linear by construction (set aside, re-entry) are descriptive only.
- How a pair of claim and prior paper ended is read from the run log: set aside before
  comparison, passed the first evidence check, resolved by re-entry, or unresolved.
- Matched pairs: the grounding metrics are also reported on the pairs both flows
  compared. Both blocks are in the Holm family.
- Re-entry outcomes (descriptive): for every pair compared twice, the first and last
  proposed degree and evidence status classify how the pair ended.
- USD are list-price estimates from the logged tokens. Only the ratio between the flows
  is compared.

## 8c. E3: source audit

`source-audit` (`evaluation/e3/source_audit.py`) reports for agent and linear on the 20
E1 papers the grounding rate (overlap comparisons that show a quote pair), the
verifiability rate (proposed quote pairs whose two sides were found in the sources), the
ownership rate, and an audit of every quote a report shows. Each quote is looked up again
in the source text it was verified against, after that text has been tied to the run by
its hash. A quote counts as exact (case- and whitespace-insensitive substring),
near-verbatim (rapidfuzz `partial_ratio` >= 90) or not found. A source without a recorded
hash is not auditable. The audit also checks that every pinned prior-work version is
dated at least 90 days before the submission. Added post hoc, descriptive, no test.

## 8d. E3: OpenNovelty's quotes

Of the external systems only OpenNovelty shows passages from prior work. DeepReviewer 2.0
quotes only the submission, and Afzal et al. quote no passage of a prior paper.
`evaluation/e3/opennovelty_audit.py` parses OpenNovelty's PDF reports, fetches each
candidate's full text and looks every passage up with the rule of section 8c. It also
compares each candidate's first public date with the submission's. Results in
`results/main/e3/opennovelty_audit.json`. Post hoc, descriptive, no test.

## 9. Not implemented

- The manual part of E3 (whether what a report says about prior work holds when the
  prior paper is read) and repeat runs of the systems.
- Annotations that exist only on the submission pages appended to DeepReviewer's PDF.

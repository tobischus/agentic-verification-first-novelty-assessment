# Evaluation protocol

Rules of the evaluation in Chapter 5 of the thesis. All dates are 2026.

## 1. Scope

- **E1:** 20 papers (`config/main.yaml` and `config/e1_extra.yaml`), five systems: `agent`,
  `linear`, `opennovelty`, `deepreviewer`, `afzal`.
- **E2:** study `main_study_v2` on the ten papers of `config/main.yaml`. M02 and M03 rated
  all 20 tasks. M01 gave no rating. PV01 is a test account and is excluded.

## 2. Materials

`import-inputs` freezes every report and submission text under `inputs/` and records its
hash in `manifests/<set>/reports.json`. Sources are listed in `config/sources.*.yaml`.
Agent and linear reports are rendered from their artifacts without model calls.
OpenNovelty is shown as its original PDF, DeepReviewer as its `final_report.md`, and
Afzal et al. as `summary.txt` and `novelty_delta_analysis.txt`. Most paper summaries of the
ten study papers use `PROMPT_V2` in `paper_synthesis.py`, which lacks only consistency rule
10.

## 3. Rubric

`prompts/novelty_report_judge_v5.txt` (sha256 `e266b00b…`). Raters and judge read the
same CRITERIA section, copied verbatim into `prompts/criteria.json`. The criteria were
fixed on 2026-09-23 before any rating, the judge-only sections on 2026-10-01 before any
E1 call. Answers per criterion: `A`, `B`, `tie` or `unclear`. `unclear` needs one of four
reasons, and a free-text reason of at most 50 words is optional.

## 4. Information boundary during E2

Raters see the submission PDF and the two reports. Prior-work papers, traces, costs and
judge results are never shown, and links leaving a report are shown as text.

## 5. Tasks and assignment

Each of the ten papers has two tasks that pair the agent with two of the three external
systems. Paper i skips `[afzal, deepreviewer, opennovelty][i % 3]`. A/B orientation
(seed 43, opposite for raters of even and odd ordinal) and task order (seed 100 +
ordinal) are fixed when a participant is created. A paper's tasks open after the rater
has read the submission and answered two background questions.

Agent and linear are not compared by raters. They are compared by E1 and by run metrics:
number of comparisons, evidence status, quote verification, verdict agreement, cost and
time (section 8b).

## 6. Storage and access

The server database is authoritative. Every write carries a revision, submit is
idempotent, and a submitted response is never edited. Access codes are stored only as
HMAC-SHA256 and handed out personally. The admin view shows progress and no ranking.

## 7. E2 analysis

Counts of preferences, ties and unclear per criterion and pair. Agreement between
raters as exact agreement and nominal Krippendorff's α, with `unclear` as missing.
`compare-e1` matches each human response with the judge call of the same orientation.

## 8. Further analyses

**8a. E1.** 400 calls: all 10 pairs, both orders, judge `gpt-6.1-sol` (effort medium),
flex tier, execution order shuffled with seed 42. A verdict counts as stable if both
orders agree. Ranking by Bradley-Terry on the Elo scale with 95% CIs from 1,000
resamples of papers. `sensitivity-e1` adds the length ratio as covariate (post hoc).

**8b. Agent vs linear.** Exact two-sided sign test per metric over the 20 papers, Holm
correction across all tested metrics, also on the pairs both flows compared. The test
was chosen on 2026-09-25, after the per-paper numbers had been computed once.

**8c. E3 source audit** (post hoc, descriptive). Every quote shown by agent or linear is
looked up again in its hash-pinned source text: exact, near-verbatim (rapidfuzz
`partial_ratio` >= 90) or not found. Each pinned prior-work version must predate the
submission by at least 90 days.

**8d. OpenNovelty's quotes** (post hoc, descriptive). The passages in OpenNovelty's
reports are looked up in the cited papers with the rule of 8c.

## 9. Not implemented

The manual part of E3 and repeated runs of the systems.

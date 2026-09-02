# TODO

**Deadline: ~1 November 2026. Today: 1 September. Experiment freeze: 30 September.**
After the freeze: re-runs of failed jobs only, no new experiments.

What gets graded is the **written document**, not the code. No thesis document exists yet.
Writing is therefore a **parallel track starting now**, not a task in this queue — see *Writing*.

Status: **[ ]** open · **[~]** in progress · **[x]** done · **[deferred]** later ·
**[decision]** needs your call · **[lead time]** depends on someone else, start early.

---

## Research questions

**RQ1** — Does an agentic Explore–Verify–Synthesize–Judge workflow produce novelty assessments that
are more accurate and better evidence-grounded than **non-agentic baselines**?

**RQ2** — To what extent do AI-assisted prior-work verification and contribution-delta analysis
improve assessment quality?

RQ1 is answered by the controlled ablation **agent vs. own linear baseline** (same claims, same
pool, single pass). That is the only comparison in which the workflow is the sole variable.
Comparisons against Afzal / OpenNovelty / DeepReviewer are **system-level** — model, prompts and
retrieval all differ — and are therefore secondary evidence, not the answer to RQ1.

### Narrative constraint (advisor)

The thesis argues that human review verdicts are a **noisy reference** and must not become the
optimisation target; verdict-alignment evaluation was explicitly rejected. Every use of the human
assessments must therefore be framed as **evidence recall against a factual pointer**, never as
agreement with a human judgment:

> The reviewer names a specific prior work. We measure whether the pipeline surfaces that document.
> We do not measure whether the pipeline agrees with the reviewer's novelty verdict.

This sentence belongs in the evaluation design notes and in the Method chapter.

---

## THIS WEEK — 1–7 September

### [x] 1. Remote cleaned up
Both branches on GitHub now point at the same filtered history; `agent_sections` (the DEFAULT
branch, which is what feeds the Contributors list) was force-pushed from `257dd49` to the clean
tip. Authors on the default branch: tobischus (17), Osama Afzal (10), serviceosaurus[bot] (2) —
no Claude, no Anthropic, zero co-author trailers. The upstream commits are kept deliberately:
they document what was inherited from the baseline repo versus what is your own contribution.

The three `dependabot/*` branches are gone from the remote, which closes their PRs. Removed the
template automation that produced them: `.github/dependabot.yml`, plus
`.github/workflows/rename_project.yml` and `.github/rename_project.sh` — that workflow ran on every
push with `permissions: write-all` and ended in a `git-auto-commit-action` with
`push_options: --force`, which is not something to leave next to a freshly rewritten history.

Two notes: GitHub caches the Contributors list, so it can take hours to drop Claude even though the
data is already correct; and the old commits stay reachable by direct SHA for a while — only a fresh
repo removes them entirely, which is not worth doing for a thesis submission.

Left alone: `.github/workflows/{docs,main,tests}.yml` trigger on `main`, which does not exist on the
remote, so they never run. Delete them if you want the repo tidy.

### [x] 2. Grounding + verifiability analysis — done
`eval/verifiability_analysis.py`, judge-free: every evidence pair in every `artifact_a` is
RE-VERIFIED offline with the current rule, so runs written under different rules are comparable.
Over 49 artifacts / 105 claims / 1693 comparisons / **231 evidence pairs**:

| | verified | exact | fuzzy | near miss | absent | too short |
|---|---|---|---|---|---|---|
| claim side | **94.8%** | 198 | 21 | 0 | 10 | 2 |
| paper side | **92.6%** | 198 | 16 | 9 | 8 | 0 |
| **both sides** | **88.7%** | \multicolumn — 205 of 231 pairs | | | | |

**The verifiability rate for the thesis is 88.7%.**

Verification depends on parse quality, not on reading depth: pairs whose paper side came from an
abstract verify at **100%** (15 pairs), from parsed full text at **88.0%** (216). All 9 paper-side
near misses are parse noise, the same class of defect as the "RAG**Num**" artifact. Depth itself
barely matters (`targeted_sections` 86.3% vs `fulltext_available_targeted_read` 86.2%).

**The evidence gate is load-bearing but not dominant.** Of 79 refutations the model proposed, **6
(7.6%) were downgraded at run time** for lacking a both-sides-verified pair. Of the 73 that
survived, **0 violate the invariant** under re-checking — the gate is sound, and it does fire.
Note on method: the artifacts store the status AFTER the gate ran, so downgrades are read from the
marker the gate writes into the note; they cannot be re-derived from the stored status.

Old rule vs. new (the 47 pairs written when `artifact_a` checked one side by substring): 1 flip,
old-rejected → now-accepted.

One methodological trap found and handled: at run time a claim quote is checked against the
submission PLUS that claim's own text and description, but `artifact_a` does not store the
description. Rebuilding the corpus without it produced fuzzy scores of ~86 against a threshold of
90 — apparent failures that were ours, not the pipeline's. The script now reloads the claims doc
and refuses to score any claim whose stored text no longer matches it.

### [ ] 3. Ask the advisor two things now — **[lead time]**
Both gate later work, so send them this week rather than when you get there:
1. Do Afzal et al. already evaluate against `human_novelty_assessments/`? If yes, do we align with
   their protocol or depart from it deliberately? (gates task 5)
2. Confirm the framing above — evidence recall against a factual pointer, not verdict alignment.
   Also settle decision 10 (final verdict vs. analysis-only) while you are at it.

---

## Core evaluation — 8–30 September

### [ ] 4. Decide and freeze the evaluation corpus — **do before task 5**
**Target: 8 September.** Currently only **7 of 19** papers in `eval/out/data` carry human-named prior
work; the metric needs coverage of those 56 papers. Choose the set, freeze it, document the
selection rule, and process the missing papers (GROBID + retrieval, ~15 min each — budget the wall
clock). No changes to the corpus after this date, so that every later number refers to one set.

### [ ] 5. Evidence recall against human-named prior work
**Target: metric built 14 Sep · runs complete 21 Sep.**

The Afzal dataset carries ground truth the evaluation does not use yet:

| | |
|---|---|
| papers with `human_novelty_assessments/` | **182** of 185 |
| assessment files | 418 (2.3 per paper) |
| papers where the human **names specific prior work** | **56** (31%), ~1.9 works each |
| of those, already in the own eval corpus | **7 of 19** |

Example `09JVxsEZPf`: the reviewer calls novelty limited because the method rests on the SNIP score
of **Lee et al.** and merging techniques of **Yu et al.** and **Hui et al.**

Framing (non-negotiable, see *Narrative constraint*): the reviewer names a specific prior work; we
measure whether the pipeline surfaces that document. Not whether it agrees with the verdict.

Metric as a funnel over the pipeline stages, over ~106 (paper, prior-work) pairs:
**recall@pool** (retrieved at all?) → **recall@examined** (deep-dived?) → **recall@challenged**
(flagged as challenging novelty?).

Required amendments:
- **The own linear baseline is the PRIMARY comparison system** — same claims, same pool, single
  pass. This is the RQ1 ablation. External systems (Afzal, OpenNovelty, DeepReviewer) are secondary
  system-level comparisons and must be labelled as such.
- **Report pool size beside every recall number**, and precision wherever it is definable. Recall
  alone rewards indiscriminate retrieval — a system that returns everything scores 100%.
- **State the incompleteness limitation explicitly**: the reviewer names only the prior work they
  happened to know. A system that surfaces *better* or *additional* prior work receives no credit
  and may even look worse. The metric is a lower bound on retrieval quality, not a ceiling.
- **Prerequisites**: task 3 answered, task 4 frozen. (Verification parity: done, see below.)

### [ ] 6. RQ1 ablation: agent vs. own linear baseline
**Target: 21 September.** Same claims, same pool, single pass vs. the four-phase agent. Report the
task-2 grounding metrics and the task-5 recall funnel side by side. This is the thesis's primary
result — schedule it before the external comparisons, not after.

### [ ] 7. System-level comparison against external systems
**Target: 30 September (freeze).** Afzal, OpenNovelty, DeepReviewer. Injection feasibility is already
analysed (own + OpenNovelty clean, Afzal lossy, DeepReviewer PDF-only → end-to-end only). Label
explicitly as system-level: model, prompts and retrieval differ, so these do **not** isolate the
workflow. Stage A adapters for `afzal` / `opennovelty` exist in the harness but were never run —
they need `structured_representation.json` / `phase1_extracted.json` per paper.

### [ ] 8. Validate the judge — small, scheduled, **not dropped**
**Target: 28 September.** Every Stage-A result you already have rests on this judge — luna 7:0 deep,
luna 6:2 sol — and **position order decided 40% of outcomes** (6 of 7 ties in the luna-vs-sol run
were position-inconsistent). Rate **20–30 pairs yourself, blind**, and report Cohen's κ against the
LLM judge.

Keep it small. This is not a new experiment, it retroactively strengthens results already in hand,
and it converts a weakness into a methodological contribution. If you want a second human rater for
inter-annotator agreement, ask now — **[lead time]**.

---

## Writing — parallel track, starts now

Draft in LaTeX alongside the experiments. Chapters marked **NOW** need no further results.

| Chapter | Source material | Status |
|---|---|---|
| Introduction, motivation, RQs | exposé, midterm slides | **NOW** |
| Related Work | Afzal, OpenNovelty, DeepReviewer, agentic-review literature | **NOW** |
| Method — system design | four-phase agent, evidence invariant, HITL checkpoints | **NOW** |
| Method — implementation | GROBID step 1, retrieval, extractor, cache, backend/frontend | **NOW** |
| Evaluation design | three-stage design, judge protocol, the framing sentence above | **NOW** |
| Results — claim extraction | ablations, 3 rejected SOTA techniques, luna vs sol, truncation finding | **NOW** |
| Results — grounding / verifiability | task 2 | after 7 Sep |
| Results — RQ1 ablation | task 6 | after 21 Sep |
| Results — system comparison | task 7 | after 30 Sep |
| Discussion / Limitations | judge position bias, silver reference, parse quality, incompleteness | mostly **NOW** |
| Conclusion / Future Work | tasks 9–12 | last |

**Milestones:** Method + Related Work drafted by **15 Sep** · Results-extraction drafted by
**30 Sep** · full draft to the advisor by **15 October** — **[lead time]**, he needs reading time ·
revision 15–25 Oct · buffer and submission 25 Oct–1 Nov.

---

## Open — after the freeze, or if time allows

### [deferred] 9. Reconcile the "challenged" rule with the evidence invariant
Depends on task 2. `NOVELTY_CHALLENGE_ON_STRONG_OVERLAP` (default on) lets `overlap_degree ∈
{substantial, same}` count as challenged **without** a both-sides-verified quote pair, contradicting
"a refutation counts only when backed by a verified quote pair". After task 2's numbers: either
require a verified pair on that path too, or change the thesis wording. A wording change is cheap
and may be the right call this close to the deadline.

### [decision] 10. Final verdict vs. analysis-only — **[lead time]**, ask in task 3
Leaning (and what the UI already does): claim-level evidence-grounded findings, **no** paper-level
novelty verdict. Consistent with the narrative constraint. If confirmed, reframe
`artifact_b.py`'s `overall_assessment` as a structured summary of findings and update slide 12
("conservative verdicts" → analysis).

### [ ] 11. GOLD reference for ~20 papers
Serves Stage A only — a supporting contribution. The silver reference is demonstrably unreliable:
on `5GuhYMgaap` four of its seven "contributions" restate the same SolverLearner proposal, which
punishes any system that does not repeat itself. If there is no time, report this as a limitation
with that example as evidence rather than building the gold set.

### [ ] 12. Harden the evaluation harness
- Tighten the `redundancy` metric — it missed duplicate pairs a human sees immediately.
- Average over repeated judge runs (≥3) instead of one, and report the spread.
- Re-check `atomicity`: it now has TWO counter-examples (see *Findings*).

### [ ] 13. Bring exposé and midterm slides in line — **before the advisor draft, 15 Oct**
- "deep claim extraction" as a feature → becomes an **ablation result** (simple beats engineered).
- slide 6 "four phases" → now true (rerank and Phase 0b both gone).
- slide 12 "conservative verdicts" → depends on decision 10.

---

## Done

### [x] Claim extraction — free full-text extractor
`ClaimExtractor = FullTextClaimExtractor` (whole paper, ONE unconstrained call), default
`gpt-5.6-luna` via `DEFAULT_EXTRACTION_MODEL`. The orchestrator pins that model explicitly, not the
pipeline-wide `--model`. Losing variants kept as documented ablations (`DeepClaimExtractor`,
`ShallowClaimExtractor`, `claim_methods.py`).

### [x] Per-claim rerank removed
`_rerank`, `_RERANK_PROMPT`, `_Rerank`, the Phase-0 call and `set_rerank`/`rerank_pos` are gone.
Verified before removing (the old justification was wrong). Remaining effect is display-only:
`frontier = _ranked()[:20]`. The agent is now exactly four phases, matching midterm slide 6.

### [x] Dead `uncertain` / `evidence_sufficient` path removed
`_apply_sufficiency` + both call sites, the sufficiency note in the B prompt, and the
`evidence_sufficient=false ⇒ uncertain` check in the judge are gone. The agent still records the
flag for transparency. Re-running B or the judge over the July artifacts no longer forces
`uncertain`.

### [x] Realization for full-text claims
Per claim, what the submission itself does for it, as verified quotes. Full-text variant chosen by
measurement (5 papers / 18 claims, blind pairwise both orientations): 8:3 with half the calls, ~39%
more cost, quote-verification 93.0% vs 96.8%. The agent adopts it — `understand_submission` → 0.0 s.

### [x] Triage abstract truncation — fixed and validated
See *Findings*. `_TRIAGE_ABSTRACT_CHARS = 2500`.

### [x] Model comparison for extraction
`gpt-5.6-sol` vs `gpt-5.6-luna`, 15 papers. Sol does not win. Keep luna. `fulltext_terra` is
registered in the harness but deliberately not run.

### [x] Verification unified between agent and linear baseline
`artifact_a` now uses `evidence.verify_pair` with the agent's own `min_quote_tokens=10` and
`fuzzy_threshold=90.0`, and the same rule that a `can_refute` survives only on a
**both-sides-verified** pair. It previously checked the PAPER side only, by plain substring, with no
minimum length. The asymmetry ran in both directions — measured on four constructed cases:

| case | now | before |
|---|---|---|
| both sides long and present | `can_refute` | `can_refute` (agree) |
| paper quote real, **claim quote fabricated** | **`cannot_refute`** | `can_refute` — a hallucinated claim quote passed |
| paper quote only 3 tokens | **`cannot_refute`** | `can_refute` — too short, still accepted |
| paper quote with a typo | **`can_refute`** | downgraded — real evidence was discarded |

All fields verified identical to `evidence.verify_pair`. Dead `_normalize` helper and the then-unused
`re` import removed. Any baseline artifact computed before this must be recomputed before it enters
the RQ1 ablation.

### [x] Working tree committed
8 thematic commits on `feature/deep-claim-extraction`; history filtered so no commit carries an AI
attribution trailer; `refs/original` purged; reflogs expired. Not pushed — task 1.

---

## Findings (thesis material)

### Stage A — 10 papers, silver reference, judge gpt-4.1

| system | model | claims | ground | recall | prec | F1 | atomic | redund | $/paper |
|---|---|---|---|---|---|---|---|---|---|
| fulltext_luna | gpt-5.6-luna | 3.10 | 100% | 89.4% | 93.3% | 89.8% | 69.2% | 3.3% | 0.0048 |
| deep | gpt-5-mini | 4.90 | 99.1% | 91.1% | 94.5% | 91.2% | 83.5% | 6.5% | 0.0263 |
| oneshot | gpt-5-mini | 3.40 | 90.7% | 88.0% | 94.7% | 90.9% | 69.0% | 5.3% | 0.0028 |

Blind pairwise (both orientations): **luna 7 : deep 0**, 3 ties.

### Three established inference-time techniques on top of luna, same 10 papers

| method | reference | claims | ground | recall | prec | F1 | $/paper | battle vs. luna |
|---|---|---|---|---|---|---|---|---|
| self-consistency + USC | Wang 2023 / Chen 2023 | 3.40 | 100% | 90.2% | 93.3% | 90.3% | 0.0179 | 2 : 1 (7 ties) |
| chain-of-verification | Dhuliawala 2023 | 3.00 | 96.7% | 96.9% | 91.7% | **93.7%** | 0.0111 | 0 : 2 (8 ties) |
| self-refine | Madaan 2023 | 4.00 | 100% | 94.4% | 82.4% | 86.9% | 0.0116 | not run (loses on metrics) |

None beats the baseline decisively.

### Model comparison — 15 papers, same method, same reference and judge

| system | model | claims | ground | recall | prec | F1 | atomic | redund | $/paper |
|---|---|---|---|---|---|---|---|---|---|
| fulltext_luna | gpt-5.6-luna | 3.53 | 100% | **91.1%** | 91.7% | **90.9%** | 53.7% | **5.1%** | **0.0058** |
| fulltext_sol | gpt-5.6-sol | 3.53 | 100% | 86.2% | **94.8%** | 88.9% | **66.8%** | 8.0% | 0.1321 |

Blind battle: **luna 6 : sol 2**, 7 ties. Binomial over the 8 decided pairs: **p = 0.289, not
significant** — ~17 decided pairs (≈32 papers) would be needed at this win rate. The decision is
nevertheless clear because the burden of proof is asymmetric: sol costs **22.6×** and cannot even be
shown to be better. Both: 53 claims, 53/53 evidence quotes verified verbatim.

Qualitatively, sol is **inconsistent in granularity** — sometimes too fine (ALLoRA: 6 claims for 3
contributions, 27% redundancy; IntelLLM: 5 claims including empirical premises that are not claimed
contributions), sometimes too coarse (FISTAPruner: one four-part conjunction, atomicity 50%). Luna
hits "one contribution = one claim" more stably, which is what a per-claim verification pipeline
needs.

### Triage input length — controlled before/after on one claim

| | before (400 chars) | after (2500 chars) |
|---|---|---|
| deep dives | 3 / 19 | **14 / 19** |
| papers with verbatim verified evidence | 1 | **11** |
| verdict | `challenged` | `challenged` (same 2 `substantial`) |
| cost / claim | $0.026 | $0.133 |

The cut applied to **1270 of 1270** pool abstracts (median 1461) and removed exactly the contribution
sentence, because abstracts open with background. Concrete failure it produced: a paper was rejected
with "treat as topical/analytical unless full text shows dataset release" while the answer sat in
characters 400–700 of the abstract the system already held.

Evidence depth and verdict are **decoupled**: quadrupling the investigation did not change the
conclusion, it made it checkable. And the verifiability of a "verification-first" system hung on a
single preprocessing constant.

### Cross-cutting methodological findings

1. A simple whole-paper call with a strong reasoning model beats an engineered anchor +
   section-reading pipeline, and the engineered guards actively cost recall.
2. The model matters more than the method — but only up to a point: gpt-5-mini fragments findings
   into sub-claims (up to 12/paper, precision 66.6%), while the far more expensive gpt-5.6-sol buys
   nothing over gpt-5.6-luna. A capability threshold, not a monotone price/quality curve.
3. Reference-based precision is blind to redundancy when the reference restates contributions; the
   reference-free blind battle catches what the metric misses. Cleanest case: on ALLoRA both systems
   score 100% recall AND 100% precision while one produces 3 claims and the other 6.
4. **The atomicity metric does not measure what matters** — two independent counter-examples: luna
   had the lowest atomicity in the 5-paper run with the best remaining metrics, and sol wins average
   atomicity (66.8% vs 53.7%) while losing the battle. Atomicity is per claim, so fragmentation is
   not penalised.
5. Claim specificity biases verdicts toward "novel": a long conjunctive claim matches neither the
   reference nor any single prior paper. Seen in Stage A (PingPong: the same claim plus one clause
   drops recall 100% → 50%) and in the pipeline (a conjunctive GraphRAG-Bench claim triaged 18 of 19
   papers away).
6. Prefix-matching model names for pricing silently mispriced `gpt-5.6-luna` as `gpt-5` (~6× too
   high) — fixed in both price tables; the eval harness now recomputes USD from token counts.

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

### Narrative constraint — what is NOT evaluated

The thesis argues that human review verdicts are a **noisy reference** produced by overloaded
reviewers, and that a system optimised toward them inherits their blind spots. The system is an
**advisor**, not a predictor of reviewer judgments. This is already argued in Related Work 2.1 and
2.3 (You, Cao & Gurevych's truth-coupling) and stated in the midterm talk.

Consequence, decided 2 September: the dataset's `human_novelty_assessments/` are **not an
evaluation target in any form**.

- Not as verdict alignment. That is Afzal et al.'s protocol (see below) and it is exactly what this
  thesis argues against.
- **Also not as evidence recall against the prior work a reviewer names.** That framing was
  considered and rejected: the reviewer names the prior work they happened to know, so scoring
  against it still installs the human as the reference and penalises a system that finds better or
  additional work. A weaker bias channel is still a bias channel.

What replaces it, three legs, none of which needs a human verdict:

1. **Verifiability** — do the evidence quotes hold up against the source documents? (task 2, done,
   88.7%). Deterministic.
2. **Derivation** — does the paper-level summary follow from the per-claim evidence and nothing
   else? (task 5). Deterministic in its core check.
3. **Relative quality** — is the assessment better than what competing systems produce, judged
   blind by domain experts? (task 7, Elo). Human judgment of *assessment quality*, which is not the
   same as agreement with a novelty verdict.

### Does Afzal et al. already use these annotations? Yes.

From your own Related Work 2.2: on 182 ICLR 2025 submissions with annotated human novelty
assessments their pipeline reaches **86.5% alignment with human reasoning** and **75.3% agreement
on novelty conclusions**. That is verdict/reasoning alignment — precisely the protocol this thesis
departs from. The departure is therefore deliberate and already argued for in 2.3; it is a
positioning claim, not a gap in the evaluation.

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
| **both sides** | **88.7%** | 205 of 231 pairs fully verified | | | | |

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

### [ ] 3. Book the advisor as second rater — **[lead time], the critical path**
The Afzal question is answered (see below), so only one thing is left, and it needs the most notice
of anything in this plan: **the advisor has to rate battles** (task 7). Ask now for a slot and a
rough budget of hours, because the whole headline result depends on their availability.
Send along the rating protocol and the anchor design so they can object early.

---

## Core evaluation — 8–30 September

### [ ] 4. Decide and freeze the evaluation corpus
**Target: 8 September.** Pick the papers, freeze the set, document the selection rule, and process
whatever is missing (GROBID + retrieval, ~15 min each — budget the wall clock). No changes after
this date, so every later number refers to one set.

Size is now driven by task 7: every paper in the set must be rated by hand in the battles, so
**8–12 papers** is the realistic ceiling, not 56. Select for diversity of field and paper type, and
state the rule — a set chosen for where the system does well is the first thing an examiner probes.

### [ ] 5. Does the summary follow from the evidence?
**Target: 14 September.**

The paper-level summary stays, but what gets measured about it is **whether it is derived from
Artifact A and nothing else** — not whether its verdict matches a human. Most of this already
exists in `artifact_judge.py` and has simply never been run at scale:

- `_deterministic_checks` — every paper B names as challenging must appear among A's verified
  refuters (fuzzy title match ≥ 85), and the verdict must match whether A holds a verified
  `can_refute` at all. **No model involved.**
- `_llm_entailment` — an auditor model lists statements in B that A does not support.

To do: run both over every submission in the frozen corpus and report, as a companion to the
task-2 verifiability rate: share of claims whose B verdict is consistent with A, share of named
challenging papers that trace back to a verified refuter, and the rate and content of unsupported
statements. Split the deterministic result from the LLM one — the first is unassailable, the second
inherits judge noise and must be labelled as such.

This is the second judge-free pillar and it closes the chain: quotes verify against the sources
(task 2), and the synthesis verifies against the quotes (task 5).

### [ ] 6. RQ1 ablation: agent vs. own linear baseline
**Target: 21 September.** Same claims, same pool, single pass vs. the four-phase agent — the only
comparison where the workflow is the sole variable. Report the task-2 grounding metrics and the
task-5 derivation metrics side by side, plus the process measures the linear baseline structurally
cannot produce: re-entry events, papers escalated from triage to deep dive, and refutations
downgraded by the evidence gate. This is the thesis's primary controlled result.

### [ ] 7. Battle mode with Elo — the headline result
**Target: runs 21 Sep · rating 22-30 Sep (freeze).**

The paper-level assessment is **not** scored against human verdicts. It is ranked against competing
systems by blind pairwise comparison, rated by you and your advisor, aggregated to Elo (or
Bradley-Terry, which handles ties better at this sample size).

Field:

| system | kind |
|---|---|
| own four-phase agent | the thesis system |
| own linear baseline | RQ1 ablation partner |
| Afzal pipeline | the system this builds on |
| OpenNovelty | evidence-gated, no re-entry |
| DeepReviewer 2.0 | adaptive control, no evidence gate |
| frontier model, single pass | e.g. gpt-5.6-sol, claude-fable-5-1 — check what is current at run time |

**The combinatorics need deciding before anything runs.** Six systems is 15 pairs per paper; over
10 papers that is 150 comparisons, doubled to 300 if positions are swapped. At ~4 minutes to read
two full assessments, that is 10+ hours per rater. Not feasible. Two ways out:

- **Anchored** — compare every system against the own agent only: 5 pairs x 10 papers = 50
  judgments (~3.5 h per rater). Gives win rate against the anchor, which supports a ranking claim
  but is not a full Elo.
- **Hybrid, recommended** — the LLM judge rates the full round robin and produces the Elo; you and
  the advisor rate a **stratified subset** (~30 pairs) and Cohen's kappa against the LLM judge is
  reported alongside. The Elo then rests on a judge that was measured, not assumed, and task 8
  stops being optional and becomes the thing that licenses the headline number.

Protocol, fixed in advance: blind (no system names in the rendered assessments), randomized
presentation order, both orientations wherever the LLM judge is used, an explicit rating rubric
(evidence grounding, correctness of the comparison, usefulness to a reviewer), and ties allowed.

**Self-preference is the obvious attack.** You are the author of one of the systems. Mitigations to
state in the thesis: blinding, position swap, the advisor as an independent second rater, and
reported agreement between the two of you. Report your own ratings and the advisor's separately as
well as pooled.

Preparation: DeepReviewer is PDF-only, so it can only enter end-to-end. Stage-A adapters for
`afzal` / `opennovelty` exist in the harness but were never run — they need
`structured_representation.json` / `phase1_extracted.json` per paper.

### [ ] 8. Validate the judge — now load-bearing, not optional
**Target: 28 September.** Under the hybrid design in task 7 the LLM judge produces the Elo, so its
reliability is no longer a footnote: it is what makes the headline result citable.

Already measured, and it is not reassuring: **position order decided 40% of outcomes** (6 of 7 ties
in the luna-vs-sol run were position-inconsistent), tie rates of 70-80% between similar systems, and
~4 points of single-run noise on atomicity. Every Stage-A result in hand rests on this judge.

Rate a stratified subset blind, report Cohen's kappa against the LLM judge, and report the judge's
own position-consistency rate as a property of the instrument. If kappa is poor, the honest move is
to fall back to the anchored human-only design in task 7 and report fewer, better-founded numbers.

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

### [x] 10. Final verdict vs. analysis-only — decided 2 September
**There is a paper-level summary (Artifact B), and it keeps its verdict.** What changes is what is
claimed about it: the verdict is *not* validated against human judgments. It is checked for
**derivation** (task 5: does it follow from Artifact A and nothing else) and ranked for **relative
quality** (task 7: blind battles). `artifact_b.overall_assessment` therefore stays as it is.

Follow-ups: slide 12 ("conservative verdicts") needs rewording toward "verdict with an audited
derivation, ranked against alternatives", and the Method chapter needs the sentence that the
verdict is an advisory output, not a prediction of a reviewer decision.

### [ ] 11. GOLD reference for ~20 papers
Serves Stage A only — a supporting contribution. The silver reference is demonstrably unreliable:
on `5GuhYMgaap` four of its seven "contributions" restate the same SolverLearner proposal, which
punishes any system that does not repeat itself. If there is no time, report this as a limitation
with that example as evidence rather than building the gold set.

### [ ] 12. Split view: click a paper, get its PDF with the quotes highlighted
Reviewer-facing only, and explicitly NOT needed for the system comparison — the exported
assessment is plain text. In the Review tab, selecting a prior-work paper opens its PDF beside the
comparison, with the quotes used for that comparison highlighted; clicking a single quote scrolls
the PDF to that spot. The quotes are already verified against the parsed text and the PDFs are
already on disk, so the missing piece is the mapping from a verified span to a page and bounding
box — which GROBID's TEI coordinates or a PyMuPDF text search can supply.

Worth building only if time remains after the evaluation. It would, however, make the verification
claim tangible in a demo: the reviewer sees the sentence in the original paper rather than trusting
a checkmark.

### [ ] 13. Harden the evaluation harness
- Tighten the `redundancy` metric — it missed duplicate pairs a human sees immediately.
- Average over repeated judge runs (≥3) instead of one, and report the spread.
- Re-check `atomicity`: it now has TWO counter-examples (see *Findings*).

### [ ] 14. Bring exposé and midterm slides in line — **before the advisor draft, 15 Oct**
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

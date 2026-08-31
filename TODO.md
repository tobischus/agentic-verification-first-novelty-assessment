# TODO

Single canonical task list. Ordered by priority; work top-down.
Status: **[ ]** open · **[~]** in progress · **[x]** done · **[deferred]** later · **[decision]** needs your call.

---

## Done

### [x] 1. Claim extraction — replaced by the free full-text extractor
`ClaimExtractor = FullTextClaimExtractor` (whole paper, ONE unconstrained call), default model
`gpt-5.6-luna` via `DEFAULT_EXTRACTION_MODEL` (env `NOVELTY_EXTRACTION_MODEL`). The orchestrator
uses that model explicitly, NOT the pipeline-wide `--model`, so a cheap pipeline model cannot
silently degrade extraction. Chosen on evidence — see *Findings*. The losing variants stay in the
tree as documented ablations: `DeepClaimExtractor`, `ShallowClaimExtractor`, and `claim_methods.py`
(self-consistency / CoVe / self-refine).

### [x] 2. Per-claim rerank removed
`_rerank`, `_RERANK_PROMPT`, `_Rerank`, the Phase-0 call and `set_rerank`/`rerank_pos` are gone;
`_ranked()` sorts by claim similarity only. **Verified before removing** (the old TODO's
justification was wrong): triage reads the whole pool regardless of order; `closest_set()` /
`closest_covered()` / `list_related_work()` are dead code from the old free-tool-loop design; and
the report's "Closest examined" uses `max(comparisons, key=similarity)`, not `_ranked()`.
Remaining effect is display-only: `frontier = _ranked()[:20]` — with pools of 17-22 papers the
order decides which 1-2 papers are cut from the review UI list. The agent is now exactly 4 phases
(triage → deep dive → re-entry → verdict), matching midterm slide 6.

### [x] 3. Dead `uncertain` / `evidence_sufficient` path removed
`_apply_sufficiency` + both call sites in `artifact_b.py`, the sufficiency note in the B prompt, and
the `evidence_sufficient=false ⇒ uncertain` check in `artifact_judge.py` are gone. The agent still
RECORDS `evidence_sufficient` (transparency); nothing acts on it, because Phase 4 always emits
`True`.
> Consequence, accepted knowingly: historical artifacts from the July runs DO contain
> `evidence_sufficient: false`. Re-running Artifact B / the judge over those old files no longer
> forces their verdict to `uncertain`. Current runs are unaffected.

Verified by `scratchpad/verify_changes.py` (28 structural checks), live extraction runs with and
without realization, and two full agent runs on a cached submission (one deriving the realization,
one adopting it).

---

## Open — pipeline

### [x] 4. Realization for full-text claims — option (a) implemented
`FullTextClaimExtractor` now also reads, per claim, what the submission itself does for it:
sections picked from the section menu, read in full, turned into a verified-quote
`realization` + `sections_used`. Shared with the deep extractor via `build_realization()`
(no duplicated logic). On by default; `realize=False` for claim-only runs, which the
Stage-A harness uses since it scores claim TEXT only.

**Realization variant chosen by measurement** (`eval/eval_realization.py`, 5 papers / 18 claims,
same claims for both, blind pairwise in both orientations):

| variant | calls/paper | USD/paper | segs/claim | verified quotes/claim | quote-ver. rate | battle |
|---|---|---|---|---|---|---|
| fulltext (default) | 3.6 | 0.0146 | 8.5 | 4.2 | 93.0% | **8 wins** |
| sections | 7.2 | 0.0105 | 7.9 | 4.1 | **96.8%** | 3 wins |

7 ties, all of them position-inconsistent. Full text wins 8:3 among the decided claims with half
the calls; it costs ~39% more (the whole paper enters every call) and produces slightly more
quotes that fail verification and are demoted to prose. `sections_used` is now derived from where
the verified quotes actually occur, not from a model's up-front pick.

Cost: 1 + 1 call per claim at extraction (measured: 3 claims -> 7 calls, $0.017, 18/18
realization quotes verified). The agent then ADOPTS it: `understand_submission` drops to
0.0 s with no `read_sections` beforehand, and a claim run went $0.0239 -> $0.0202. So the
work happens once, is reviewable at the HITL checkpoint, and every prior-work comparison
gets the reading the reviewer approved.

### [ ] 5. Verification-consistency analysis (grounding + verifiability rate)
Script over `eval/out/data/*/*_artifact_a.json` + ledgers: % of quote checks passing, split by side
(claim vs. paper), failure reasons (below `min_quote_tokens`, not found, fuzzy below threshold, no
full text → abstract-only, GROBID gaps), and how often `can_refute` was downgraded. Produces the
thesis's **verifiability rate** — the data already exists, this is an analysis script only.

### [deferred] 6. Reconcile the "challenged" rule with the evidence invariant
Depends on 5. `NOVELTY_CHALLENGE_ON_STRONG_OVERLAP` (default on) lets `overlap_degree ∈
{substantial, same}` count as challenged **without** a both-sides-verified quote pair, contradicting
"a refutation counts only when backed by a verified quote pair". After 5's numbers: either require a
verified pair on that path too, or change the thesis wording.

### [decision] 7. Final verdict vs. analysis-only
Leaning (and what the UI already does): claim-level evidence-grounded findings, **no** paper-level
novelty verdict. If confirmed, reframe `artifact_b.py`'s `overall_assessment` as a structured
summary of findings and update slide 12 ("conservative verdicts" → analysis).

---

## Open — evaluation

### [ ] 8. Compare gpt-5.6-sol and gpt-5.6-terra as extraction models
Same free full-text method, same 10-paper set, same silver reference and judge — only the model
changes, so the comparison isolates the model. Prices are already in both tables (per 1k tokens:
sol 0.0050/0.0300, terra 0.0020/0.0120, luna 0.0002/0.0012). Register `fulltext_sol` /
`fulltext_terra` in the harness, extract, then battle each against `fulltext_luna`. Report quality
**and** cost: luna is 25x cheaper than sol on input, so sol has to win clearly to be worth adopting.

### [ ] 9. GOLD reference for ~20 papers  ← highest leverage
`eval/gold_contributions.json` = `{submission_id: [verbatim statement, ...]}`, checked by hand.
Everything measured so far rests on a SILVER reference that is demonstrably incomplete (it missed
the `CodeNet-Test` benchmark that gpt-5 correctly found), and reference-based precision is blind to
redundancy because the silver reference restates contributions across abstract/intro/conclusion.
Without gold, no Stage-A number is thesis-grade. ~2-3 h of manual work; candidate statements can be
prepared per paper so it becomes checkbox work.

### [ ] 10. Validate the judge (human study)
Measured: 70-80% ties and 3-5 position-inconsistent verdicts per 10 papers in the luna-vs-method
battles — the judge can barely separate similar systems — and single-run noise moved atomicity
72.5% → 68.8% between two identical runs. Rate 20-30 pairs yourself, blind, and report Cohen's κ
against the LLM judge. Turns a weakness into a methodological contribution, and is the
truth-coupling argument applied to your own evaluation.

### [ ] 11. Harden the evaluation harness
- Tighten the `redundancy` metric — it missed duplicate pairs a human sees immediately
  (5GuhYMgaap: two duplicate pairs scored 6.5%).
- Average over repeated judge runs (>= 3) instead of one, and report the spread.
- Re-check `atomicity`: luna had the LOWEST atomicity (45.8%) in the 5-paper run yet the best
  metrics and the battle wins — the metric may not measure what matters.

### [ ] 12. Stage A for `afzal` and `opennovelty`
Adapters exist in the harness but were never run — needs their claim files per paper
(`structured_representation.json` / `phase1_extracted.json`).

### [ ] 13. Stage B / C — the thesis core
Fixed-claim injection (B) and end-to-end (C) comparison against Afzal, OpenNovelty,
DeepReviewer 2.0 and the own linear baseline. Injection feasibility per system is already analysed
(own + OpenNovelty clean, Afzal lossy, DeepReviewer PDF-only → Stage C only). **Most of the
remaining time belongs here, not in extraction.**

---

## Housekeeping

### [ ] 14. Commit the working tree
Nothing is committed on `feature/deep-claim-extraction`: 6 modified source files, the whole `eval/`
tree, `claim_methods.py`, `TODO.md`. Several days of work plus all measurement results are
unversioned.

### [ ] 15. Bring exposé and midterm slides in line
- "deep claim extraction" as a feature → becomes an **ablation result** (simple beats engineered).
- slide 6 "four phases" → now true (rerank and Phase 0b both gone).
- slide 12 "conservative verdicts" → depends on decision 7.

---

## Findings (thesis material)

**Stage A, 10 papers, silver reference, judge gpt-4.1.**

| system | model | claims | ground | recall | prec | F1 | atomic | redund | $/paper |
|---|---|---|---|---|---|---|---|---|---|
| fulltext_luna | gpt-5.6-luna | 3.10 | 100% | 89.4% | 93.3% | 89.8% | 69.2% | 3.3% | 0.0048 |
| deep | gpt-5-mini | 4.90 | 99.1% | 91.1% | 94.5% | 91.2% | 83.5% | 6.5% | 0.0263 |
| oneshot | gpt-5-mini | 3.40 | 90.7% | 88.0% | 94.7% | 90.9% | 69.0% | 5.3% | 0.0028 |

Blind pairwise (both orientations): **luna 7 : deep 0**, 3 ties. Judge reasons match manual
inspection — deep "includes inflated, redundant, and non-contribution claims" and "splits a single
contribution into multiple overlapping claims" (11 claims on two papers).

**Three established inference-time techniques on top of luna, same 10 papers:**

| method | reference | claims | ground | recall | prec | F1 | $/paper | battle vs. luna |
|---|---|---|---|---|---|---|---|---|
| self-consistency + USC | Wang 2023 / Chen 2023 | 3.40 | 100% | 90.2% | 93.3% | 90.3% | 0.0179 | 2 : 1 (7 ties) |
| chain-of-verification | Dhuliawala 2023 | 3.00 | 96.7% | 96.9% | 91.7% | **93.7%** | 0.0111 | 0 : 2 (8 ties) |
| self-refine | Madaan 2023 | 4.00 | 100% | 94.4% | 82.4% | 86.9% | 0.0116 | not run (loses on metrics) |

None beats the baseline decisively. CoVe wins on reference-based F1 (driven by recall 96.9%) but
not in the battle; the high tie rate says the judge cannot separate systems this similar at n=10.

**Cross-cutting methodological findings** (worth a subsection of their own):
1. A simple whole-paper call with a strong reasoning model beats an engineered anchor +
   section-reading pipeline, and the engineered guards actively cost recall.
2. The model matters more than the method: the same free prompt on gpt-5-mini fragments findings
   into sub-claims (up to 12/paper) and precision collapses to 66.6%.
3. Reference-based precision is blind to redundancy when the reference restates contributions; the
   reference-free blind battle catches what the metric misses.
4. Prefix-matching model names for pricing silently mispriced `gpt-5.6-luna` as `gpt-5` (~6x too
   high) — fixed in both price tables; a cautionary note for cost reporting.

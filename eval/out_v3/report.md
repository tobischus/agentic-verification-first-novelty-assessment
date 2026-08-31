# Grading Re-derivation Experiment — Fix A (v3)

_Generated 2026-07-19 23:11:07 · dataset: C:\Users\tobis\OneDrive\Desktop\Studium\M.Sc. Artificial Intelligence and Machine Learning\4. Semester\Masterarbeit\Afzal Dataset\data_for_release_

**What changed vs out_v2:** ONLY the per-claim CHALLENGED verdict, re-derived from the EXISTING Artifact-A evidence (Fix A). The agent was NOT re-run; the conclusion prompt (central-contribution weighting) and models are identical to out_v2, so the delta below isolates the GRADING fix.

- Fix: **A** (mechanical: substantial/same overlap counts as challenged)
- conclusion model: `gpt-5.1` · judge: `gpt-4.1`
- cost — conclusions $0.0000 · judge $0.3874

## Scores vs. human assessments

| Dimension | Afzal | Mine v2 (old grading) | Mine v3 (Fix A) | Δ v2→v3 |
|---|---|---|---|---|
| Judgment similarity (0-1) | 0.892 | 0.704 | 0.686 | -0.018 ⚠️ |
| Core judgments found (0-1) | 1.0 | 0.784 | 0.765 | -0.019 ⚠️ |
| Conclusion agreement | 82.4% | 41.2% | 52.9% | +11.7 ✅ |
| Positive shift (over-claims) ↓ | 11.8% | 47.1% | 41.2% | -5.9 ✅ |
| Negative shift (under-claims) ↓ | 5.9% | 11.8% | 11.8% | +0.0 |
| Prior-work engagement (0-2) | 1.412/2 | 1.765/2 | 1.765/2 | +0.0 |
| Depth of analysis (0-2) | 1.412/2 | 1.882/2 | 1.765/2 | -0.117 ⚠️ |

_Judgments: 17 (paper×human-ref). Baseline = out_v2._

## Per-paper verdicts (human vs v2 old-grading vs v3 new-grading)

| forum_id | ref | human | Afzal | mine v2 | mine v3 | claims re-challenged |
|---|---|---|---|---|---|---|
| 09JVxsEZPf | review_1.txt | INSUFFICIENT | MIXED | INSUFFICIENT | INSUFFICIENT | 0 |
| 1XxNbecjXe | review_2.txt | MIXED | MIXED | INSUFFICIENT | INSUFFICIENT | 0 |
| 2NqssmiXLu | review_0.txt | MIXED | MIXED | SUFFICIENT | SUFFICIENT | 0 |
| 328vch6tRs | review_2.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | 0 |
| 3xjc9PhEPd | review_3.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT | SUFFICIENT | 0 |
| 4QWPCTLq20 | review_3.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | 0 |
| 5GuhYMgaap | review_3.txt | MIXED | MIXED | INSUFFICIENT | INSUFFICIENT | 1 |
| 5bUy4F59mk | review_2.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | 0 |
| 7X65yoKl3Y | review_1.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT | SUFFICIENT | 0 |
| 8zxGruuzr9 | review_3.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT | SUFFICIENT | 0 |
| 996aKQIom0 | review_3.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | 0 |
| AAjCYWXC5I | review_0.txt | SUFFICIENT | INSUFFICIENT | SUFFICIENT | SUFFICIENT | 0 |
| AAjCYWXC5I | review_1.txt | MIXED | MIXED | SUFFICIENT | SUFFICIENT | 0 |
| BINwUtUGuq | review_0.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT | SUFFICIENT | 0 |
| BUpdp5gETF | review_1.txt | INSUFFICIENT | MIXED | SUFFICIENT | MIXED | 0 |
| BVCGTsgpOS | review_1.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | 1 |
| CvGqMD5OtX | review_0.txt | INSUFFICIENT | INSUFFICIENT | MIXED | INSUFFICIENT | 1 |

> `claims re-challenged` = how many claims Fix A flipped not_challenged→challenged (or back) vs the agent's stored verdict. If the scores jump, the evidence was sound and only the rule was wrong (no agent re-run needed).

# Conclusion Re-scoring Experiment (v2)

_Generated 2026-07-19 20:55:57 · dataset: C:\Users\tobis\OneDrive\Desktop\Studium\M.Sc. Artificial Intelligence and Machine Learning\4. Semester\Masterarbeit\Afzal Dataset\data_for_release_

**What changed:** only the final conclusion paragraph was rebuilt from each paper's existing Artifact A, using a _critical reviewer_ prompt that faithfully carries the agent's per-claim verdicts. The pipeline / Artifact A was NOT re-run. Afzal's baseline and the human references are unchanged and re-judged with the identical Fig 13/14 judge.

- Papers: **16** (succeeded: 16) · conclusion model: `gpt-5.1` · judge model: `gpt-4.1`
- Cost — new conclusions: $0.0000 · judge: $0.3847 · total: $0.3847

## Alignment scores vs. human assessments — NEW conclusion

Higher is better except the two Shift rows (lower = better calibration).

| Dimension                       | Afzal (baseline) | Ours    |
| ------------------------------- | ---------------- | ------- |
| Judgment similarity (0-1)       | 0.889            | 0.704   |
| Core judgments found (0-1)      | 1.0              | 0.784   |
| Conclusion agreement            | 82.4%            | 41.2%   |
| Positive shift (over-claims) ↓  | 11.8%            | 47.1%   |
| Negative shift (under-claims) ↓ | 5.9%             | 11.8%   |
| Prior-work engagement (0-2)     | 1.353/2          | 1.765/2 |
| Depth of analysis (0-2)         | 1.294/2          | 1.882/2 |

_Judgments: Afzal 17, Mine 17 (paper×human-ref pairs)._

## Did it improve? OLD vs NEW conclusion (mine only)

| Dimension                       | Mine v1 (original) | Mine v2 (critical) | Δ         |
| ------------------------------- | ------------------ | ------------------ | --------- |
| Judgment similarity (0-1)       | 0.639              | 0.704              | +0.065 ✅ |
| Core judgments found (0-1)      | 0.745              | 0.784              | +0.039 ✅ |
| Conclusion agreement            | 35.3%              | 41.2%              | +5.9 ✅   |
| Positive shift (over-claims) ↓  | 64.7%              | 47.1%              | -17.6 ✅  |
| Negative shift (under-claims) ↓ | 0.0%               | 11.8%              | +11.8 ⚠️  |
| Prior-work engagement (0-2)     | 1.882/2            | 1.765/2            | -0.117 ⚠️ |
| Depth of analysis (0-2)         | 1.824/2            | 1.882/2            | +0.058 ✅ |

## Per-paper novelty verdicts (human vs Afzal vs mine v1 vs mine v2)

| forum_id   | human ref    | human        | Afzal        | mine v1      | mine v2      |
| ---------- | ------------ | ------------ | ------------ | ------------ | ------------ |
| 09JVxsEZPf | review_1.txt | INSUFFICIENT | MIXED        | SUFFICIENT   | INSUFFICIENT |
| 1XxNbecjXe | review_2.txt | MIXED        | MIXED        | MIXED        | INSUFFICIENT |
| 2NqssmiXLu | review_0.txt | MIXED        | MIXED        | SUFFICIENT   | SUFFICIENT   |
| 328vch6tRs | review_2.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT |
| 3xjc9PhEPd | review_3.txt | INSUFFICIENT | INSUFFICIENT | MIXED        | SUFFICIENT   |
| 4QWPCTLq20 | review_3.txt | INSUFFICIENT | INSUFFICIENT | MIXED        | INSUFFICIENT |
| 5GuhYMgaap | review_3.txt | MIXED        | MIXED        | MIXED        | INSUFFICIENT |
| 5bUy4F59mk | review_2.txt | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT |
| 7X65yoKl3Y | review_1.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT   | SUFFICIENT   |
| 8zxGruuzr9 | review_3.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT   | SUFFICIENT   |
| 996aKQIom0 | review_3.txt | INSUFFICIENT | INSUFFICIENT | MIXED        | INSUFFICIENT |
| AAjCYWXC5I | review_0.txt | SUFFICIENT   | INSUFFICIENT | SUFFICIENT   | SUFFICIENT   |
| AAjCYWXC5I | review_1.txt | MIXED        | MIXED        | SUFFICIENT   | SUFFICIENT   |
| BINwUtUGuq | review_0.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT   | SUFFICIENT   |
| BUpdp5gETF | review_1.txt | INSUFFICIENT | MIXED        | MIXED        | SUFFICIENT   |
| BVCGTsgpOS | review_1.txt | INSUFFICIENT | INSUFFICIENT | MIXED        | INSUFFICIENT |
| CvGqMD5OtX | review_0.txt | INSUFFICIENT | INSUFFICIENT | SUFFICIENT   | MIXED        |

> Same GPT-4.1 judge for all systems. `mine v1` = the original pipeline conclusion (from eval/out); `mine v2` = this experiment's critical, Artifact-A-grounded conclusion. Prior-work/depth judged on prose only.

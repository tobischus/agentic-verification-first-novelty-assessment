# Retrieval Recall vs. Human-Cited Prior Work

_Generated 2026-07-19 20:24:35 · model: `gpt-4.1`_

Answers: when a human judged a paper 'not novel enough', did my pool contain the prior work they based it on — and did the agent grade the overlap?

## Why each paper over/under-claims — the causes

Over **17** (paper × human-ref) pairs:

| Situation | Count | Meaning |
|---|---|---|
| **agent_challenged** | 10 | the agent DID flag overlap (challenged ≥1 claim) — no over-claim on the overlap axis, even if the human's exact named paper was not the one it used |
| **B — not a retrieval problem** | 4 | agent challenged 0; human objection is obviousness / marginal delta / lack of rigor — no specific paper to retrieve |
| **A1 — retrieval miss** | 1 | agent challenged 0; human names a prior work, ABSENT from my pool (recall problem) |
| **A2 — grading miss** | 2 | agent challenged 0; named prior work IS in my pool, but agent graded the overlap too leniently |

**Pool recall on human-named prior work: 6/24 = 25.0%** (of the specific prior works humans cite, this fraction was in my pool).

## Objection type distribution

| Primary basis of the human's novelty judgment | Count |
|---|---|
| OVERLAP_SPECIFIC | 11 |
| MARGINAL_DELTA | 3 |
| OBVIOUSNESS | 2 |
| POSITIVE | 1 |

## Per paper × human-ref

| forum_id | ref | human | basis | named | in pool | agent chal | situation |
|---|---|---|---|---|---|---|---|
| 2NqssmiXLu | review_0.txt | MIXED | OVERLAP_SPECIFIC | 1 | 0/1 | 0/3 | A1_retrieval_miss |
| 8zxGruuzr9 | review_3.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 4 | 1/4 | 0/4 | A2_grading_miss |
| CvGqMD5OtX | review_0.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 2 | 2/2 | 0/3 | A2_grading_miss |
| 3xjc9PhEPd | review_3.txt | INSUFFICIENT | OBVIOUSNESS | 0 | 0/0 | 0/4 | B_not_retrieval |
| 7X65yoKl3Y | review_1.txt | INSUFFICIENT | MARGINAL_DELTA | 0 | 0/0 | 0/3 | B_not_retrieval |
| AAjCYWXC5I | review_0.txt | SUFFICIENT | POSITIVE | 0 | 0/0 | 0/2 | B_not_retrieval |
| AAjCYWXC5I | review_1.txt | MIXED | MARGINAL_DELTA | 0 | 0/0 | 0/2 | B_not_retrieval |
| 09JVxsEZPf | review_1.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 3 | 0/3 | 1/3 | agent_challenged |
| 1XxNbecjXe | review_2.txt | MIXED | OVERLAP_SPECIFIC | 1 | 1/1 | 3/4 | agent_challenged |
| 328vch6tRs | review_2.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 2 | 1/2 | 2/4 | agent_challenged |
| 4QWPCTLq20 | review_3.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 2 | 0/2 | 1/3 | agent_challenged |
| 5GuhYMgaap | review_3.txt | MIXED | OVERLAP_SPECIFIC | 3 | 1/3 | 2/3 | agent_challenged |
| 5bUy4F59mk | review_2.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 2 | 0/2 | 3/3 | agent_challenged |
| 996aKQIom0 | review_3.txt | INSUFFICIENT | MARGINAL_DELTA | 0 | 0/0 | 1/1 | agent_challenged |
| BINwUtUGuq | review_0.txt | INSUFFICIENT | OBVIOUSNESS | 0 | 0/0 | 1/4 | agent_challenged |
| BUpdp5gETF | review_1.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 1 | 0/1 | 1/3 | agent_challenged |
| BVCGTsgpOS | review_1.txt | INSUFFICIENT | OVERLAP_SPECIFIC | 3 | 0/3 | 2/4 | agent_challenged |

## Named prior works & pool match (papers where the human cited specifics)

**09JVxsEZPf / review_1.txt** (human=INSUFFICIENT, agent challenged 1/3):
- ❌ SNIP (Lee et al.) [ABSENT]
- ❌ Model merging (Yu et al.) [ABSENT]
- ❌ Model merging (Hui et al.) [ABSENT]

**1XxNbecjXe / review_2.txt** (human=MIXED, agent challenged 3/4):
- ✅ Bailey et al. (2023): Prior work on prompt injection attacks via images and the 'Behavior Matching' approach for generating image-based attacks on VLMs. [PRESENT] → pool: "Image Hijacks: Adversarial Images can Control Generative Models at Runtime — Luk"

**2NqssmiXLu / review_0.txt** (human=MIXED, agent challenged 0/3):
- ❌ expert iteration (Polu et al., 2022) [ABSENT]

**328vch6tRs / review_2.txt** (human=INSUFFICIENT, agent challenged 2/4):
- ✅ Byte Pair Encoding (BPE): A widely used subword tokenization method that enables models to learn larger vocabularies by combining tokens. [PRESENT] → pool: "Byte Pair Encoding is Suboptimal for Language Model Pretraining — Kaj Bostrom, 2"
- ❌ Rogers et al., 2020: A study analyzing syntactic and semantic composition in transformers, specifically referenced for similar findings about aggregation and disambiguation in network layers. [ABSENT]

**4QWPCTLq20 / review_3.txt** (human=INSUFFICIENT, agent challenged 1/3):
- ❌ H2O [ABSENT]
- ❌ SnapKV [ABSENT]

**5GuhYMgaap / review_3.txt** (human=MIXED, agent challenged 2/3):
- ❌ https://aclanthology.org/2023.findings-acl.67.pdf: Study on deductive reasoning in LLMs [ABSENT] → pool: "Large Language Models are In-Context Semantic Reasoners rather than Symbolic Rea"
- ❌ https://openreview.net/forum?id=KFjCFxiGk4: Study on deductive reasoning in LLMs [ABSENT] → pool: "Large Language Models are In-Context Semantic Reasoners rather than Symbolic Rea"
- ✅ https://arxiv.org/abs/2309.05660: Study on inductive reasoning in LLMs [PRESENT] → pool: "Phenomenal Yet Puzzling: Testing Inductive Reasoning Capabilities of Language Mo"

**5bUy4F59mk / review_2.txt** (human=INSUFFICIENT, agent challenged 3/3):
- ❌ Domino: focuses on grammar and token alignment in general constrained text generation tasks [ABSENT] → pool: "Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning"
- ❌ TOOLDEC: eliminates syntax errors by constraining token choices using finite state machines to maintain tool syntax [ABSENT] → pool: "Don't Fine-Tune, Decode: Syntax Error-Free Tool Use via Constrained Decoding"

**8zxGruuzr9 / review_3.txt** (human=INSUFFICIENT, agent challenged 0/4):
- ❌ Social Chemistry 101 (Forbes et al. 2020): Study of values and social norms in language models. [ABSENT]
- ❌ Argyle et al. (2022): Work on simulating human samples and values in language models. [ABSENT]
- ✅ Durmus et al. (2023): Research on world opinions and values in language models. [PRESENT] → pool: "Towards Measuring the Representation of Subjective Global Opinions in Language M"
- ❌ Ma et al. (2024): Survey summarizing research on evaluating attitudes, opinions, and values in LLMs. [ABSENT]

**BUpdp5gETF / review_1.txt** (human=INSUFFICIENT, agent challenged 1/3):
- ❌ muP: Recent works on the 'muP' framework, which involve tuning learning rates and other hyperparameters per component/layer in neural networks. [ABSENT] → pool: "Scaling Exponents Across Parameterizations and Optimizers"

**BVCGTsgpOS / review_1.txt** (human=INSUFFICIENT, agent challenged 2/4):
- ❌ Vovk et al., 2012: PAC-style conformal prediction; foundational work on conformal prediction with statistical guarantees. [ABSENT]
- ❌ Conformal language modeling (https://arxiv.org/abs/2306.10193): Extension of conformal prediction to language modeling tasks, including hallucination detection. [ABSENT]
- ❌ https://arxiv.org/abs/2106.09848: Prior work introducing rejection sampling for covariate shift in statistical prediction. [ABSENT]

**CvGqMD5OtX / review_0.txt** (human=INSUFFICIENT, agent challenged 0/3):
- ✅ DIN-SQL: Prior work on few-shot example generation for NL2SQL tasks. [PRESENT] → pool: "DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction — M."
- ✅ CodeS: Prior work on few-shot example generation for NL2SQL tasks. [PRESENT] → pool: "CodeS: Towards Building Open-source Language Models for Text-to-SQL — Haoyang Li"

> Situations: **B** = my overlap paradigm structurally cannot address the objection (and staying honest ≠ over-claiming); **A1** = fix retrieval recall; **A2** = fix the agent's overlap-degree / can_refute threshold. Pipeline pool = ranked_papers.json (+ agent_retrieved if any).

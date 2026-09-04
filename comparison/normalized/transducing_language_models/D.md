# Assessment D

> This is one system's assessment of the paper's novelty. Several systems assessed the
> same paper; they are presented in a common wrapper so that presentation does not decide
> the comparison. The text below is each system's own, unedited and complete: it was not
> shortened, reordered or rewritten, so the systems differ in length and structure.
>
> Where a system marks verbatim quotations, they appear in quotation marks; unmarked text
> is that system's own prose.

---

## Novelty Verification & Related-Work Matrix
### (9A) Contribution Novelty Verdict Board
| Claim ID | Author Contribution Claim | Key Evidence Papers [n] | Novelty Verdict Tag | Why | Confidence | Required Repositioning |
|----------|--------------------------|------------------------|---------------------|-----|------------|----------------------|
| C1 | Formalizes a general framework for transforming LMs via deterministic string-to-string mappings using FSTs | [2], [3], [4], [5] | supported | No prior work formalizes FST-based LM transformation as yielding new, fully functional LMs; prior work is limited to special cases or non-probabilistic settings | High | None |
| C2 | Develops exact and approximate algorithms for marginalizing over source strings and conditioning on transformed outputs | [2], [3], [4], [5], [6] | supported | No previous method provides both exact and efficient approximate algorithms for general FST-based LM adaptation; prior work is either heuristic or limited in scope | High | None |
| C3 | Demonstrates practical adaptation to diverse output units (bytes, words, amino acids) without retraining | [2], [7], [8] | supported | No prior work shows inference-time adaptation of pretrained LMs to such a broad range of output units using FSTs | High | None |

### (9B) Related-Work Taxonomy Matrix
| Taxonomy Layer | Branch/Leaf | Representative Papers [n] | Common Assumptions | Difference vs This Paper | Novelty Risk Signal |
|----------------|------------|--------------------------|--------------------|-------------------------|---------------------|
| Root           | FST-based LM adaptation | [2], [3], [4], [5], [6], [7], [8] | FSTs for string-to-string mapping; often limited to specific tasks | This paper generalizes to arbitrary deterministic mappings and provides full LM interface | Low |
|                |  ├─ Tokenization marginalization | [6], [7], [8] | Marginalize over tokenizations for string probability | This paper supports arbitrary FSTs, not just tokenization | Low |
|                |  ├─ Weighted FSTs for tagging/normalization | [4], [5] | Weighted FSTs for POS tagging, normalization | Prior work does not yield new LMs or support full marginalization | Low |
|                |  └─ End-to-end learned tokenization | [9], [10] | Learn tokenization via neural models | This paper uses deterministic FSTs, not learned mappings | Low |

### (9C) Head-to-Head Comparison Matrix
| Ref [n] | Problem/Setting | Method Core | Strongest Overlap Point | Clear Difference | Impact on Final Judgment |
|---------|----------------|------------|------------------------|------------------|-------------------------|
| [6] | Marginalizing over tokenizations in LMs | Importance-sampling-based marginalization | Both marginalize over multiple tokenizations | This paper supports arbitrary FSTs, not just tokenization; provides full LM interface | This paper is more general and algorithmically novel |
| [7] | Hierarchical/learned tokenization | End-to-end learned tokenization | Both seek robust output units | This paper uses deterministic FSTs, not neural tokenization | This paper is more interpretable and modular |
| [4] | Weighted FSTs for POS tagging | Weighted FSTs for sequence labeling | Both use FSTs for string transformation | Prior work does not yield new LMs or support full marginalization | This paper is more general and probabilistically grounded |

### Contribution-level Novelty Conclusion
All three core claims (C1–C3) are supported by the literature review and retrieval. No prior work formalizes FST-based LM transformation as yielding new, fully functional LMs with a full autoregressive interface, nor provides both exact and efficient approximate algorithms for general FST-based adaptation. The empirical demonstration of adaptation to bytes, words, and amino acids without retraining is also novel. The work is a clear generalization and unification of prior approaches, with no substantial overlap risk.

### ASCII Diagram — Related-Work Taxonomy Tree (Layered)
```text
Related Work Taxonomy (Root)
├── FST-based LM adaptation
│   ├── Tokenization marginalization [6]
│   ├── Weighted FSTs for tagging/normalization [4], [5]
│   └── End-to-end learned tokenization [7], [8]
```

## References
[2] Modular Descriptions of Regular Functions 1908.01137

[3] Use of Weighted Finite State Transducers in Part of Speech Tagging cmp-lg/9710001

[4] A Flexible Rule Compiler for Speech Synthesis cs/0403039

[5] Aperiodic String Transducers 1506.04059

[6] Should you marginalize over possible tokenizations? 2306.17757

[7] From Characters to Words: Hierarchical Pre-trained Language Model for Open-vocabulary Language Understanding 2305.14571

[8] Learn Your Tokens: Word-Pooled Tokenization for Language Modeling 2310.11628

[9] Adapters for Altering LLM Vocabularies: What Languages Benefit the Most? 2410.09644

[10] Benchmarking Compositionality with Formal Languages 2208.08195

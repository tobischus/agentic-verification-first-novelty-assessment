## Novelty Verification & Related-Work Matrix
### Contribution Novelty Verdict Board

| Claim ID | Author Contribution Claim | Key Evidence Papers [n] | Novelty Verdict Tag | Why | Confidence | Required Repositioning |
|----------|---------------------------|------------------------|---------------------|-----|------------|-----------------------|
| C1 | Proposal of GraphRAG-Bench, a comprehensive benchmark with diverse corpora and tasks of increasing complexity for evaluating GraphRAG models | [1] Xiang et al. (2025) | supported | No existing benchmark comprehensively covers hierarchical knowledge retrieval and deep reasoning with multi-domain corpora and stage-specific metrics | High | None |
| C2 | Extensive empirical evaluation of GraphRAG vs vanilla RAG revealing nuanced trade-offs across tasks and datasets | [1], [2], [3] | partially_overlapping | Prior studies compare GraphRAG and RAG but lack comprehensive task diversity and stage-specific evaluation | Medium | Clarify scope and emphasize unique evaluation aspects |
| C3 | Practical design guidelines for effective GraphRAG systems emphasizing precise retrieval, quality graph construction, and context management | [1], [4] | partially_overlapping | Some prior works discuss design principles but lack systematic empirical validation and integration with benchmark findings | Medium | Explicitly position guidelines as derived from benchmark insights |

### Related-Work Taxonomy Matrix

| Taxonomy Layer | Branch/Leaf | Representative Papers [n] | Common Assumptions | Difference vs This Paper | Novelty Risk Signal |
|----------------|------------|--------------------------|--------------------|-------------------------|--------------------|
| Root | Graph Retrieval-Augmented Generation (GraphRAG) | [1], [2], [3], [4], [5] | Use of graph structures for knowledge retrieval and reasoning | This paper focuses on comprehensive benchmarking and systematic evaluation | Low |
| Branch 1 | Benchmarking and Evaluation | [1], [5] | Evaluation of GraphRAG models on various tasks | This paper introduces multi-domain corpora and stage-specific metrics | Medium |
| Leaf 1.1 | Existing RAG Benchmarks | [5] | Focus on fact retrieval and limited reasoning complexity | Lacks hierarchical and diverse task coverage | High |
| Leaf 1.2 | GraphRAG-specific Benchmarks and Analysis | [1], [2] | Limited task diversity and homogeneous datasets | This paper offers broader task spectrum and hybrid corpora | Medium |
| Branch 2 | GraphRAG Methods | [3], [4] | Graph construction, retrieval, and generation techniques | This paper focuses less on methods, more on evaluation | Low |
| Branch 3 | Design Principles and Efficiency | [1], [4] | Emphasis on retrieval precision, graph quality, and efficiency | This paper provides empirical guidelines based on benchmark results | Medium |

### Head-to-Head Comparison Matrix

| Ref [n] | Problem/Setting | Method Core | Strongest Overlap Point | Clear Difference | Impact on Final Judgment |
|---------|-----------------|-------------|------------------------|------------------|--------------------------|
| [1] Xiang et al. (2025) | Evaluation of GraphRAG models on hierarchical knowledge retrieval and deep reasoning | Comprehensive benchmark with multi-domain corpora and stage-specific metrics | Similar task complexity focus but broader corpus diversity | Provides more systematic evaluation and practical guidelines | Supports novelty claim |
| [2] Han et al. (2025) | Architectural comparison of GraphRAG models on homogeneous datasets | Focus on model architecture and performance | Lacks task diversity and stage-specific evaluation | Highlights need for comprehensive benchmarks |
| [3] Zhou et al. (2025) | Analysis of GraphRAG retrieval and reasoning performance | Empirical evaluation on limited datasets | Limited task scope and evaluation depth | Reinforces benchmark necessity |
| [4] Guo et al. (2024) | Design principles for scalable GraphRAG | Emphasis on retrieval precision and efficiency | No integrated empirical benchmark | Provides partial overlap with design guidelines |
| [5] Qian et al. (2024) | Existing RAG benchmarks (UltraDomain) | Focus on fact retrieval and limited reasoning | Lacks hierarchical knowledge and task diversity | Motivates new benchmark |

### Contribution-level Novelty Conclusion

The paper's primary novelty lies in proposing GraphRAG-Bench, a comprehensive benchmark that fills critical gaps in existing evaluations by integrating diverse domain-specific corpora and a taxonomy of tasks with increasing complexity. While prior works have addressed aspects of GraphRAG evaluation and design, they lack the systematic, multi-stage, and multi-domain evaluation framework presented here. The empirical design guidelines further differentiate this work by grounding recommendations in extensive benchmark results.

No substantial novelty conflicts were found, but claims related to design principles should be explicitly positioned as derived from benchmark insights to avoid overclaiming.

References:
[1] When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation 2506.05690
[2] Rag vs. GraphRAG: A Systematic Evaluation and Key Insights 2502.11371
[3] Graph Retrieval-Augmented Generation: A Survey 2408.08921
[4] Empowering GraphRAG with Knowledge Filtering and Integration 2503.13804
[5] UltraDomain: A Domain-Specific Benchmark for Retrieval-Augmented Generation 2409.05591

## References

[1] When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation 2506.05690

[2] Rag vs. GraphRAG: A Systematic Evaluation and Key Insights 2502.11371

[3] Graph Retrieval-Augmented Generation: A Survey 2408.08921

[4] Empowering GraphRAG with Knowledge Filtering and Integration 2503.13804

[5] UltraDomain: A Domain-Specific Benchmark for Retrieval-Augmented Generation 2409.05591

# Novelty Assessment

**WHEN TO USE GRAPHS IN RAG: A COMPREHENSIVE ANALYSIS FOR GRAPH RETRIEVAL-AUGMENTED GEN-ERATION**

Authors: Zhishang Xiang, Chuanjie Wu, Qinggang Zhang, Shengyuan Chen, Zijin Hong, Xiao Huang, Jinsong Su
Publication date: 2025-06-06

## Extracted claims

### Extracted Claim 1

We propose GraphRAG-Bench, a comprehensive benchmark designed to evaluate GraphRAG models on deep reasoning, featuring comprehensive corpora with different information density, tasks of increasing difficulty, and systematic evaluation across the entire pipeline.

Evidence in paper:

“To bridge this gap, we propose GraphRAG-Bench, a comprehensive benchmark designed to evaluate GraphRAG models on deep reasoning. GraphRAG-Bench features ❶ comprehensive corpora with different information density, including tightly structured domain knowledge and loosely organized texts, and ❷ tasks of increasing difficulty, covering fact retrieval, multi-hop reasoning, Contextual Summarize, and creative generation, and ❸ systematic evaluation across the entire pipeline, from graph construction and knowledge retrieval to final generation.”

✓ verbatim in paper

### Extracted Claim 2

Leveraging GraphRAG-Bench, we systematically investigate the conditions when GraphRAG surpasses traditional RAG systems and the underlying reasons for its success, offering guidelines for its practical application.

Evidence in paper:

“Leveraging this novel benchmark, we systematically investigate the conditions when GraphRAG surpasses traditional RAG systems and the underlying reasons for its success, offering guidelines for its practical application.”

✓ verbatim in paper

## Related work examined

16 papers were compared against the claims above.

| Paper | Claim 1 | Claim 2 |
|---|---|---|
| In-depth Analysis of Graph-based RAG in a Unified Framework — Zhou et al. · 2025 | partial overlap · material evidence | substantial overlap · material evidence |
| RAG vs. GraphRAG: A Systematic Evaluation and Key Insights — Han et al. · 2025 | superficial · material evidence | substantial overlap · material evidence |
| CG-RAG: Research Question Answering by Citation Graph Retrieval-Augmented LLMs — Hu et al. · 2025 | superficial · nonmaterial | partial overlap · material evidence |
| Enhancing Structured-Data Retrieval with GraphRAG: Soccer Data Case Study — 2024 | superficial · nonmaterial | partial overlap · material evidence |
| Graph Retrieval-Augmented Generation: A Survey — Peng et al. · 2024 | superficial · nonmaterial | partial overlap · material evidence |
| HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models — Gutierrez et al. · 2024 | superficial · nonmaterial | partial overlap · material evidence |
| KET-RAG: A Cost-Efficient Multi-Granular Indexing Framework for Graph-RAG — Huang et al. · 2025 | superficial · insufficient evidence | partial overlap · material evidence |
| Medical Graph RAG: Towards Safe Medical Large Language Model via Graph Retrieval-Augmented Generation — 2024 | superficial · nonmaterial | partial overlap · material evidence |
| MedRAG: Enhancing Retrieval-augmented Generation with Knowledge Graph-Elicited Reasoning for Healthcare Copilot — Zhao et al. · 2025 | superficial · material evidence | partial overlap · material evidence |
| MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries — Tang et al. · 2024 | partial overlap · material evidence | superficial · nonmaterial |
| PIKE-RAG: sPecIalized KnowledgE and Rationale Augmented Generation — Wang et al. · 2025 | superficial · material evidence | partial overlap · material evidence |
| StructRAG: Boosting Knowledge Intensive Reasoning of LLMs via Inference-time Hybrid Information Structurization — Li et al. · 2024 | superficial · nonmaterial | partial overlap · material evidence |
| A Survey of Graph Retrieval-Augmented Generation for Customized Large Language Models — Zhang et al. · 2025 | superficial · insufficient evidence | superficial · no evidence check |
| How to Mitigate Information Loss in Knowledge Graphs for GraphRAG: Leveraging Triple Context Restoration and Query-Driven Feedback — 2025 | superficial · insufficient evidence | superficial · nonmaterial |
| Retrieval-Augmented Generation with Graphs (GraphRAG) — Han et al. · 2024 | superficial · no evidence check | superficial · no evidence check |
| Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph — Sun et al. · 2023 | superficial · nonmaterial | superficial · material evidence |
Legend: Cells show overlap degree and evidence status: material = meaningful shared contribution supported; nonmaterial = examined correspondences do not support meaningful contribution overlap; insufficient = inconclusive evidence; no evidence check = no check recorded. Missing support is not proof of no overlap. Conflicting assessments are identified under Evidence limits.

## Review

---

### First extracted claim

We propose GraphRAG-Bench, a comprehensive benchmark designed to evaluate GraphRAG models on deep reasoning, featuring comprehensive corpora with different information density, tasks of increasing difficulty, and systematic evaluation across the entire pipeline.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries (Both papers contribute evaluation benchmarks for retrieval-augmented generation that include curated corpora, questions requiring multiple pieces of evidence, ground-truth evidence or answers, and systematic evaluation of retrieval and generation performance.) [partial overlap · material]; In-depth Analysis of Graph-based RAG in a Unified Framework (Both works provide a systematic evaluation infrastructure for GraphRAG rather than evaluating only final answer quality.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries:** GraphRAG-Bench is specifically designed for GraphRAG rather than general RAG and adds corpora with contrasting information density, including medical guidelines and ambiguous novels; ontology-based logic mining and evidence extraction; a hierarchy of retrieval, reasoning, summarization, and creative-generation tasks; difficulty calibrated by graph properties; and evaluation spanning graph construction, retrieval, and generation with graph-specific metrics.
- **In-depth Analysis of Graph-based RAG in a Unified Framework:** The submission's distinct contribution is a purpose-built benchmark: it constructs complementary medical and novel-literature corpora with different information densities, formalizes their latent logic into ontologies, creates tasks with controlled increases in reasoning difficulty, and introduces stage-specific metrics for graph quality, retrieval, and generation.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 3 of 16 comparisons have insufficient evidence, and 1 has no recorded evidence check. One comparison shows a conflict between the overlap assessment and evidence check: RAG vs. GraphRAG: A Systematic Evaluation and Key Insights was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: PIKE-RAG: sPecIalized KnowledgE and Rationale Augmented Generation was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: MedRAG: Enhancing Retrieval-augmented Generation with Knowledge Graph-Elicited Reasoning for Healthcare Copilot was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 16 comparisons processed, 15 with an evidence check: 5 material, 7 nonmaterial, 3 insufficient.

#### What the submission does for this claim

The submission delivers a text-based benchmark organized around complementary corpora, progressively harder tasks, and evaluation of the full GraphRAG workflow. Its corpus combines structured medical guidelines with ambiguous narrative fiction, while its ontology-based construction makes relationships and difficulty explicit.

“GraphRAG-Bench consists a comprehensive dataset with (i) tasks of increasing difficulty, covering fact retrieval, multi-hop reasoning, Contextual Summarize, and creative generation, and (ii) real-world corpora with different information density, and (iii) a systematic evaluation across the entire pipeline, from graph construction and knowledge retrieval to final generation. Traditional benchmarks focus on tasks with simple fact retrieval or linear multi-hop reasoning, where answers depend on linking concepts or facts across a limited set of documents.”

The benchmark evaluates retrieval, reasoning, summarization, and creative generation using evidence grounded in graph structure, with metrics covering graph quality, retrieval quality, answer accuracy, faithfulness, and evidence coverage. In the reported comparison, its studied conditions show that basic RAG remains competitive for simple fact retrieval, whereas GraphRAG has an advantage on complex reasoning, contextual summarization, and creative generation; on the novel dataset, RAPTOR reaches 70.9% faithfulness while RAG covers 40.0% of the evidence.

“RAPTOR scores highest in faithfulness (70.9%) on the novel dataset, though RAG covers more evidence (40.0%), likely because GraphRAG's fragmented knowledge retrieval and complicates broad scope generation.”

#### Overlapping prior work

##### MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries
partial overlap · Tang et al. · 2024

How this paper realizes the claim

MultiHop-RAG delivers a benchmark dataset for multi-hop RAG, including a knowledge base, multi-hop queries, ground-truth answers, and supporting evidence.

“In this paper, we develop a novel dataset, MultiHop-RAG, which consists of a knowledge base, a large collection of multihop queries, their ground-truth answers, and the associated supporting evidence. We detail the procedure of building the dataset, utilizing an English news article dataset as the underlying RAG knowledge base.”

It constructs the dataset from news articles, extracts and validates evidence, and generates several query types with varying numbers of supporting evidence pieces.

“MultiHopRAG contains four types of multi-hop queries and the distribution of these queries is shown in Table 3. In total, about 88% of queries in the dataset are non-null queries where answers can be retrieved and reasoned from the knowledge base.”

It evaluates both retrieval and answer generation, using retrieval metrics against ground-truth evidence and response accuracy against ground-truth answers.

“An RAG system handling multi-hop queries can be assessed from two key aspects: retrieval evaluation and generation evaluation. Retrieval Evaluation: Evidently, the quality of the retrieval set Rq determines the final generation quality.”

Grounded evidence for the assessed overlap

Evidence check: material
5 of 8 grounded candidates support the overlap

The valid pairs establish substantive overlap in meaningful components of the current benchmark contribution. Pair 1 supports shared benchmark/task design involving multi-hop retrieval-and-reasoning queries, although MultiHop-RAG is narrower. Pairs 4 and 5 support shared empirical evaluation of retrieval and answer/reasoning performance, while pairs 7 and 8 directly support overlap in retrieval evaluation against supporting evidence and answer evaluation against ground-truth answers. These components are more than a shared topic or generic research activity and justify the proposed partial degree, but they do not establish equivalence with the full GraphRAG-Bench scope.

Pair 2 is not independently relied upon because the quoted submission span concerns evaluation across the entire pipeline, whereas the prior-paper span primarily describes dataset contents; their contribution roles are not fully aligned. Pair 3 does not establish shared ontology- or graph-based difficulty control: varying evidence counts are not equivalent to the submission's ontology-based logic map. Pair 6 similarly supports multi-evidence query construction at most, not the claimed ontology transformation or logical synthesis, so it is not needed for the decision.

The delta's statements that MultiHop-RAG does not provide GraphRAG-specific benchmarking, varying-density corpora, ontology/graph-structural difficulty control, or full graph-construction-to-generation evaluation are not established merely by the absence of corresponding pairs. They should remain qualified as limitations of the demonstrated overlap, rather than certified residual novelty. This does not block the partial-overlap decision because the positive evidence independently establishes a meaningful shared benchmark, retrieval-evaluation, and answer-evaluation component.

Submission contribution span
“GraphRAG-Bench consists a comprehensive dataset with (i) tasks of increasing difficulty, covering fact retrieval, multi-hop reasoning, Contextual Summarize, and creative generation, and (ii) real-world corpora with different information density”

Pair 1: Both papers contribute a benchmark dataset containing diverse retrieval-and-reasoning query tasks rather than a single evaluation question type; MultiHop-RAG provides a narrower multi-hop query benchmark than the submission's broader hierarchy.

The prior work states:
“Approximately 27% of interrogative queries start with "does," around 15% initiate with "what," a similar proportion start "which," and 14% begin with "who," with the remainder incorporating a small percentage of other interrogative words such as "when." Moreover, the number of evidence required to answer a multi-hop query varies.”

Submission contribution span
“To address Q1, we evaluate seven representative GraphRAG frameworks on our benchmark, using tailored metrics for different question types.”

Pair 4: Both papers contribute empirical benchmark evaluations of retrieval systems or models on their constructed multi-hop-oriented datasets; MultiHop-RAG's evaluation is narrower and focused on embedding-model retrieval.

The prior work states:
“The first experiment compares different embedding models for retrieving evidence for multi-hop queries.”

Pair 5: Both papers evaluate generation or reasoning performance on evidence-supported multi-hop questions using multiple language models; MultiHop-RAG evaluates answer reasoning given evidence but does not evaluate the submission's full GraphRAG task suite.

The prior work states:
“Llama2-70B, in reasoning and answering multi-hop queries given the evidence.”

Submission contribution span
“2) EVIDENCE RECALL measures retrieval completeness by assessing whether all critical components required to correctly answer the question are captured.”

Pair 7: Both papers evaluate retrieval by comparing retrieved material with answer-supporting ground-truth evidence, with MultiHop-RAG using retrieval metrics such as MAP, MRR, and Hit Rate.

The prior work states:
“Assuming the topK chunks are retrieved, i.e., |Rq| = K, we use retrieval evaluation metrics including Mean Average Precision at K (MAP@K), Mean Reciprocal Rank at K (MRR@K), and Hit Rate at K (Hit@K).”

Submission contribution span
“2) ANSWER ACCURACY: Assesses both semantic similarity and factual consistency with the reference answer. 3) FAITHFULNESS: Evaluates whether the relevant knowledge points in a long-form answer are faithful to the given context.”

Pair 8: Both papers evaluate answer quality by comparing generated responses with ground-truth answers for evidence-based multi-hop questions.

The prior work states:
“Since the multi-hop query requires reasoning over multiple pieces of retrieved chunks, we can also evaluate the reasoning capability of the LLM by comparing the LLM response with the ground truth answer of the query.”

Comparison with the submission

The prior paper substantially overlaps with the benchmark-design aspect of the claim: it provides a multi-hop dataset, multiple query forms, supporting evidence, and retrieval and generation evaluation. However, it does not itself provide a GraphRAG benchmark, varying-density corpora, explicit ontological or graph-structural difficulty control, or evaluation of the full graph construction-to-generation pipeline, so the submission retains a distinct central contribution.

##### In-depth Analysis of Graph-based RAG in a Unified Framework
partial overlap · Zhou et al. · 2025

How this paper realizes the claim

The paper does not propose a benchmark specifically designed around GraphRAG reasoning difficulty, information density, or newly constructed corpora. Instead, it contributes a unified framework and an open-source evaluation testbed for comparing existing graph-based RAG methods across datasets, question types, metrics, and retrieval-stage configurations.

“In this paper, we first summarize a unified framework to incorporate all graph-based RAG methods from a high-level perspective. We then extensively compare representative graph-based RAG methods over a range of questing-answering (QA) datasets – from specific questions to abstract questions – and examine the effectiveness of all methods, providing a thorough analysis of graph-based RAG approaches. As a byproduct of our experimental analysis, we are also able to identify new variants of the graph-based RAG methods over specific QA and abstract QA tasks respectively, by combining existing techniques, which outperform the state-of-the-art methods.”

“In this section, we develop a novel unified framework, consisting of four stages: ❶Graph building, ❷Index construction, ❸Operator configuration, and ❹Retrieval & generation, which can cover all existing graph-based RAG methods, as shown in Algorithm 1. Algorithm 1: A unified framework for graph-based RAG input :Corpus D, and user question 𝑄 output:The answers for user question 𝑄 1 C ←split D into multiple chunks; // (1) Graph building.”

“We present the first open-source testbed for graph-based RAG methods, which (1) collects and reimplements 12 representative methods within a unified framework (as depicted in Section 3). (2) supports a fine-grained comparison over the building blocks of the retrieval stage with up to 100+ variants, and (3) provides a comprehensive evaluation over 11 datasets with various metrics in different scenarios, we summarize the workflow of our empirical study in Figure 3, and make our unified system available in: https://github.com/JayLZhou/GraphRAG/tree/master. Benchmark Dataset.”

Its evaluation covers simple and complex specific questions as well as abstract questions, and it uses different metrics for these settings. However, the paper uses existing datasets and generated abstract questions rather than constructing a benchmark with purpose-built corpora of different information densities or a controlled hierarchy of increasingly difficult tasks.

Grounded evidence for the assessed overlap

Evidence check: material
3 of 3 grounded candidates support the overlap

Pairs 1 and 3 establish substantive overlap in the claimed systematic evaluation contribution: both works evaluate GraphRAG across multiple pipeline stages and through a broad empirical testbed rather than only a single final-answer setting. Pair 2 independently supports overlap in metric-based empirical evaluation, although the prior paper's quoted metrics are narrower and primarily answer-level rather than stage-specific. These pairs justify a meaningful partial overlap, but not substantial or same overlap: the evidence does not establish equivalence in benchmark scope, reasoning-oriented task design, corpus construction, ontology grounding, or stage-specific metrics. The submission delta's claims that the prior paper does not provide those benchmark-design elements are not established by the absence of corresponding pairs and should remain qualified; they do not block the partial-overlap determination because the shared evaluation component is independently supported.

Submission contribution span
“(iii) a systematic evaluation across the entire pipeline, from graph construction and knowledge retrieval to final generation.”

Pair 1: Both works contribute an evaluation setup spanning multiple GraphRAG stages from graph or index construction through retrieval, with generation at the end; the prior paper provides the corresponding end-to-end pipeline directly.

The prior work states:
“We then sequentially execute operations in the following four stages (lines 2-5): (1) Build the graph G for input chunks C (Section 4); (2) Construct the index based on the graph G from the previous stage; (3) Configure the retriever operators for subsequent retrieving stages, and (4) For the input user question 𝑄, retrieve relevant information from G”

Submission contribution span
“To address this, we design stage-specific metrics that evaluate the entire workflow from graph construction and retrieval to final generation.”

Pair 2: Both works contribute systematic metric-based evaluation of GraphRAG or graph-based RAG outputs across an empirical testbed; the prior paper's metrics are narrower and primarily assess answer-level performance rather than each pipeline stage.

The prior work states:
“For specific QA tasks, we use Accuracy and Recall to evaluate performance on the first five datasets based on whether gold answers are included in the generations instead of strictly requiring exact matching, following [53, 69].”

Submission contribution span
“As shown in Table 1 , these four tasks ensure more comprehensive evaluation: lower-level tasks validate retrieval capability, while higher levels assess reasoning depth, ensuring models balance precise fact extraction with clear contextual comprehension.”

Pair 3: Both works contribute a broad empirical evaluation testbed covering multiple methods, datasets or tasks, and evaluation dimensions rather than assessing only a single final-answer setting.

The prior work states:
“(3) provides a comprehensive evaluation over 11 datasets with various metrics in different scenarios, we summarize the workflow of our empirical study in Figure 3, and make our unified system available in: https://github.com/JayLZhou/GraphRAG/tree/master.”

Comparison with the submission

The prior paper delivers a meaningful evaluation framework and broad empirical testbed that overlaps with the submission's systematic, multi-stage GraphRAG evaluation. Nevertheless, it does not itself contribute the submission's central benchmark-design elements: new corpora spanning information densities, ontology-grounded evidence and difficulty control, or a purpose-built task hierarchy for deep reasoning. The overlap is therefore partial rather than substantial: an important evaluation component is already present, while the submission retains a distinct central contribution in benchmark construction and reasoning-oriented task design.

---

### Second extracted claim

Leveraging GraphRAG-Bench, we systematically investigate the conditions when GraphRAG surpasses traditional RAG systems and the underlying reasons for its success, offering guidelines for its practical application.

#### Claim-level conclusion

**Assessment:** challenged by prior work. At least one comparison in the examined candidate set is assessed to substantially or equivalently overlap this claim under material evidence. This does not by itself determine whether the claim should be rejected.

**Main overlap:** RAG vs. GraphRAG: A Systematic Evaluation and Key Insights (Both papers make a systematic empirical comparison of traditional RAG and GraphRAG, investigate the task or query conditions under which one outperforms the other, and derive explanations or practical insights from the observed trade-offs.) [substantial overlap · material]; In-depth Analysis of Graph-based RAG in a Unified Framework (Both works make a systematic empirical contribution comparing GraphRAG or graph-based RAG with traditional RAG across varied task conditions, and both seek to explain when graph-based methods outperform, underperform, or incur additional costs.) [substantial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **RAG vs. GraphRAG: A Systematic Evaluation and Key Insights:** The submission extends the evaluation with GraphRAG-Bench, a broader benchmark organized around generation accuracy, retrieval performance, graph complexity, and efficiency.
- **In-depth Analysis of Graph-based RAG in a Unified Framework:** The submission contributes the specifically named GraphRAG-Bench benchmark, its question taxonomy and generation/retrieval metrics, and a new evaluation scope spanning generation accuracy, retrieval performance, graph complexity, efficiency, scalability, model size, and open-source backbones.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 2 have no recorded evidence check. One comparison shows a conflict between the overlap assessment and evidence check: Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved.

**Coverage:** 16 comparisons processed, 14 with an evidence check: 12 material, 2 nonmaterial.

#### What the submission does for this claim

The submission delivers GraphRAG-Bench as a benchmark and a comparative empirical study of seven representative GraphRAG frameworks against standard RAG across retrieval, reasoning, summarization, and creative-generation tasks. It finds that standard RAG is comparable to or better than GraphRAG for simple fact retrieval, whereas GraphRAG has a clear advantage on complex reasoning, contextual summarization, and creative generation because those tasks require connecting multiple concepts; for creative tasks, the study also reports a precision–breadth trade-off.

“Basic RAG Matches GraphRAG in simple fact retrieval task: basic RAG is comparable to or outperforms GraphRAG in simple fact retrieval tasks that does not require com- Obs.2 . GraphRAG excels in complex tasks: GraphRAG models show a clear advantage in complex reasoning, Contextual Summarize, and creative generation. This is intuitive, as these tasks require bridging the complex relations among multiple concepts, which is naturally a graph structure.”

The retrieval results specify the conditions more concretely: RAG performs best for simple questions whose evidence is usually in a single passage, while GraphRAG's benefits emerge for Level 2–3 and multi-hop questions that require connecting distant text segments. The submission also identifies practical costs and guidance: graph retrieval increases prompt length and can add redundant or noisy context, with efficiency varying substantially across systems; HippoRAG2 is comparatively compact. The reported conclusions are limited to the evaluated text-only datasets and systems, and the study further finds that GraphRAG benefits more from larger language models, with a reported practical threshold at 7B parameters.

“RAG excels at retrieving discrete facts for simple questions that do not require complex logics, achieving 83.2% Evidence Recall on the novel dataset (vs. HippoRAG2's best Context Relevance). Medical dataset results confirm this pattern, suggesting relevant evidence for Level 1 questions typically resides in single passages. It is because the graph used in GraphRAG introduces several logically relevant but redundant information in these scenarios.”

“GraphRAG's advantages emerge clearly as questions grow more complex. For Level 2-3 questions on the novel dataset, HippoRAG achieves remarkable Evidence Recall (87.9-90.9%), while HippoRAG2 leads in Context Relevance (85.8-87.8%). Medical dataset results reinforce this trend, demonstrating GraphRAG's unique ability to connect information across distant text segments, crucial for multi-hop reasoning and comprehensive summarization.”

#### Overlapping prior work

##### RAG vs. GraphRAG: A Systematic Evaluation and Key Insights
substantial overlap · Han et al. · 2025

How this paper realizes the claim

The paper itself systematically compares RAG and GraphRAG across general text-based question answering and query-based summarization tasks, using multiple datasets, task types, and representative GraphRAG methods.

“we systematically evaluate the performance of RAG and GraphRAG on general text-based tasks using widely adopted datasets, including Question Answering and Query-based Summarization. Specifically, we assess two representative GraphRAG methods: (1) Knowledge Graph-based GraphRAG (Liu, 2022), which extracts a Knowledge Graph (KG) from text and performs retrieval solely based on the KG and (2) Community-based GraphRAG (Edge et al., 2024), which retrieves information not only from the constructed KG but also from hierarchical communities within the graph.”

It analyzes when each paradigm performs better and identifies task-dependent conditions: RAG is stronger for detailed single-hop questions and fine-grained information, whereas GraphRAG is stronger for multi-hop questions and more diverse, multi-faceted summaries.

“Our findings reveal that RAG and GraphRAG are complementary, each excelling in different aspects. For the Question Answering task, we observe that RAG performs better on singlehop questions and those requiring detailed information, while GraphRAG is more effective for multi-hop questions.”

“For the Question Answering task, we observe that RAG performs better on singlehop questions and those requiring detailed information, while GraphRAG is more effective for multi-hop questions. In the Query-based Summarization task, RAG captures fine-grained details, whereas GraphRAG generates more diverse and multi-faceted summaries.”

“In the Query-based Summarization task, RAG captures fine-grained details, whereas GraphRAG generates more diverse and multi-faceted summaries. Building on these insights, we investigate two strategies from different perspectives to integrate their unique strengths and enhance the overall performance.”

The paper also proposes selection and integration strategies based on these findings, and discusses limitations and future directions, but its central contribution is the systematic comparative evaluation and task-specific explanation of the relative strengths of RAG and GraphRAG.

“Based on our comprehensive evaluation, we conduct an in-depth analysis of the strengths and weaknesses of RAG and GraphRAG across different tasks. Our findings reveal that RAG and GraphRAG are complementary, each excelling in different aspects.”

Grounded evidence for the assessed overlap

Evidence check: material
3 of 4 grounded candidates support the overlap

Pair 1 directly establishes the shared central activity of systematic empirical comparison of traditional RAG and GraphRAG across multiple task settings. Pair 2 supports a shared condition-dependent comparative finding: RAG is stronger for simpler/single-hop or detail-focused questions, while GraphRAG is stronger for multi-hop questions. Pair 3 supports a shared explanatory trade-off concerning GraphRAG's broader or more diverse information access versus RAG's preservation of fine-grained detail, although the submission's wording additionally mentions noisy context and prompt inflation, which are not fully established by the prior span. Pair 4 does not validly establish the asserted shared derivation of practical recommendations: the submission span mentions recommendations, but the prior span only states a systematic evaluation contribution and does not show recommendations or hybrid-integration guidance. This rejected pair does not block the decision because pairs 1–3 independently establish substantive overlap in the claim's central comparative-evaluation, condition-dependent findings, and explanatory components. Those pairs support substantial overlap: the prior paper reaches the central contribution of determining comparative performance across conditions, while the submission adds benchmark design, broader coverage, diagnostics, and efficiency/structural analyses. The delta's claims about what the prior paper does not cover, and about the precise novelty of the added benchmark dimensions, are not established merely by these pairs and should remain qualified; they do not change the supported substantial-overlap conclusion.

Submission contribution span
“This section evaluates GraphRAG against RAG through comprehensive experiments on our new benchmarks.”

Pair 1: Both papers contribute a systematic empirical evaluation directly comparing traditional RAG with GraphRAG across multiple task settings.

The prior work states:
“To bridge this gap, we systematically evaluate the performance of RAG and GraphRAG on general text-based tasks using widely adopted datasets, including Question Answering and Query-based Summarization.”

Submission contribution span
“RAG excels at retrieving discrete facts for simple questions that do not require complex logics, achieving 83.2% Evidence Recall on the novel dataset (vs. HippoRAG2's best Context Relevance).”

Pair 2: Both papers find that RAG has an advantage for simpler or more focused information needs rather than universally outperforming GraphRAG.

The prior work states:
“For the Question Answering task, we observe that RAG performs better on singlehop questions and those requiring detailed information, while GraphRAG is more effective for multi-hop questions.”

Submission contribution span
“These findings underscore a critical trade-off: while GraphRAG improves retrieval breadth, it may also introduce noisy context due to prompt inflation, especially in complex tasks.”

Pair 3: Both papers explain comparative performance through a trade-off between GraphRAG's broader or more diverse information access and RAG's more focused detail preservation.

The prior work states:
“In the Query-based Summarization task, RAG captures fine-grained details, whereas GraphRAG generates more diverse and multi-faceted summaries.”

Comparison with the submission

The overlap is substantial because the prior paper already delivers the central contribution of systematically comparing RAG with GraphRAG and identifying the conditions and task characteristics associated with each method's success. The submission retains meaningful novelty through its new benchmark, larger framework coverage, generation and retrieval diagnostics, graph-complexity and efficiency analyses, and broader investigation of underlying causes, but these are extensions and refinements of an already established central comparative-evaluation contribution rather than a wholly distinct core idea.

##### In-depth Analysis of Graph-based RAG in a Unified Framework
substantial overlap · Zhou et al. · 2025

How this paper realizes the claim

The paper itself provides a unified framework and a broad empirical comparison of graph-based RAG methods against baselines across datasets and question types, using multiple evaluation metrics.

“We then extensively compare representative graph-based RAG methods over a range of questing-answering (QA) datasets – from specific questions to abstract questions – and examine the effectiveness of all methods, providing a thorough analysis of graph-based RAG approaches. As a byproduct of our experimental analysis, we are also able to identify new variants of the graph-based RAG methods over specific QA and abstract QA tasks respectively, by combining existing techniques, which outperform the state-of-the-art methods.”

It analyzes when graph-based RAG helps or fails, including differences between simple and complex or abstract questions, retrieval strategies, high-level information, graph structure, and computational cost.

“For complex questions in specific QA, high-level information is typically needed, as they capture the complex relationship among chunks, and the vector search-based retrieval strategy is better than the rule-based (e.g., Entity operator) one. L4.”

The paper also turns these findings into practical recommendations for selecting methods under different task and cost conditions.

“We summarize the lessons (L) for practitioners and propose practical research opportunities (O) based on our observations. Lessons: L1.”

Grounded evidence for the assessed overlap

Evidence check: material
4 of 7 grounded candidates support the overlap

Pairs 1 and 2 establish a substantive overlap in the central empirical activity: systematic comparison of graph-based RAG with conventional RAG and identification of task conditions associated with relative performance. Pair 4 independently supports overlap in comparative efficiency and cost analysis, and pair 6 supports the practical or research guidance component. Together these pairs reach the central type of contribution claimed—an empirical, condition-sensitive investigation with explanatory and guidance-oriented analysis—rather than merely sharing a topic or evaluation activity. The evidence supports the proposed substantial degree, although it does not establish that the benchmark design, taxonomy, metrics, datasets, or full evaluation scope are identical. Pair 5 does not support the specific shared assertion that graph-based RAG imposes additional costs: the prior quotation says some graph-based methods are comparatively cost-efficient and share a retrieval stage with VanillaRAG. Pair 3 shows a related discussion of task characteristics but does not clearly establish a comparison of graph-based RAG against standard RAG, and pair 7 concerns graph sparsity and scaling rather than the submission's implementation-level structural variation; neither is needed for the decision. The delta's claims that the submission uses a distinct unified framework, datasets, method variants, and retains substantive novelty are not fully established by the pairs, but those limitations do not block the independently supported substantial overlap.

Submission contribution span
“This section evaluates GraphRAG against RAG through comprehensive experiments on our new benchmarks.”

Pair 1: Both works contribute a systematic empirical comparison of graph-based RAG methods against conventional RAG across multiple QA conditions, directly supporting the claimed comparative investigation.

The prior work states:
“We then extensively compare representative graph-based RAG methods over a range of questing-answering (QA) datasets – from specific questions to abstract questions – and examine the effectiveness of all methods, providing a thorough analysis of graph-based RAG approaches.”

Submission contribution span
“GraphRAG models show a clear advantage in complex reasoning, Contextual Summarize, and creative generation.”

Pair 2: Both works report comparative performance differences between graph-based RAG and standard RAG, identifying task-dependent cases in which graph-based methods perform better.

The prior work states:
“Generally, the RAG technique significantly enhances LLM performance across all datasets, and the graph-based RAG methods (e.g., HippoRAG and RAPTOR) typically exhibit higher accuracy than VanillaRAG. However, if the retrieved elements are not relevant to the given question, RAG may degrade the LLM’s accuracy.”

Submission contribution span
“To better understand the associated efficiency and cost implications, we conduct a dedicated analysis on prompt statistics across different GraphRAG models.”

Pair 4: Both works contribute an empirical efficiency and cost analysis of graph-based RAG methods, including comparisons with standard RAG.

The prior work states:
“In this experiment, we evaluate the time and token costs for each method in specific QA tasks.”

Submission contribution span
“In this paper, we not only build GraphRAG-Bench to evaluate existing GraphRAG systems, but more importantly, we provide insightful recommendations for future GraphRAG research, as illustrated in Figure 7 .”

Pair 6: Both works derive practitioner- or researcher-oriented guidance from their empirical GraphRAG analyses.

The prior work states:
“We summarize the lessons (L) for practitioners and propose practical research opportunities (O) based on our observations.”

Comparison with the submission

The overlap is substantial because the prior paper already performs the central kind of systematic GraphRAG-versus-RAG investigation, identifies conditions associated with GraphRAG's advantages, analyzes costs and mechanisms, and derives practical lessons. However, the contributions are not essentially identical: the submission's benchmark design, evaluation dimensions, and additional controlled analyses remain substantive extensions and a distinct empirical realization. Thus, after subtracting the prior paper's broad comparative-analysis contribution, the submission retains important novelty, but its claimed high-level contribution is largely anticipated.

##### Enhancing Structured-Data Retrieval with GraphRAG: Soccer Data Case Study
partial overlap · 2024

How this paper realizes the claim

The paper introduces Structured-GraphRAG, a graph-based retrieval framework for structured datasets, and demonstrates it in a soccer-data case study by comparing it with traditional retrieval-augmented generation.

“Our findings show that Structured-GraphRAG significantly improves query processing efficiency and reduces response times. While our case study focuses on soccer data, the framework’s design is broadly applicable, offering a powerful tool for data analysis and enhancing language model applications across various structured domains.”

It evaluates the framework using soccer queries, measuring execution time and answer consistency/accuracy against a prior non-graph method.

“These results highlight the efficiency gains achieved by our framework, demonstrating its ability to process and respond to queries with significantly greater speed, thereby confirming the superior performance of Structured-GraphRAG over the direct data analysis approach employed in [17].”

“Our experimental results demonstrate that the graph-based approach we employed significantly improves accuracy compared to the method used in [17]. This highlights the effectiveness of integrating graph-based techniques to reduce hallucinations and provide more consistent, accurate outputs across multiple iterations.”

The paper also analyzes graph sparsity as an efficiency-related design property, arguing that sparse knowledge graphs reduce traversal overhead and support faster retrieval.

“The sparsity of the Label and Caption KGs ensures that our framework can quickly identify and retrieve the necessary information without being bogged down by an excessive number of irrelevant connections. Therefore, our designed KGs structure significantly enhances the system’s performance, enabling it to handle large-scale data efficiently.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 3 grounded candidates support the overlap

Pairs 1 and 3 establish a substantive partial overlap. Pair 1 supports that both contributions empirically compare graph-based retrieval with a traditional or non-graph approach and evaluate comparative answer accuracy. Pair 3 supports a narrower shared explanatory component: both relate graph organization or sparsity/density to retrieval or processing benefits. Together these support the prior paper as an empirically narrower version of the claim, rather than merely a shared topic or generic use of GraphRAG. Pair 2 is not independently material evidence of the same finding: it shows that both papers evaluate efficiency, but they report different efficiency outcomes (reduced response time versus increased prompt length), so it supports shared evaluation activity more than a shared conclusion. The quoted pairs do not establish the submission's broader cross-system, cross-dataset, multi-complexity benchmark or its full set of conditions, trade-offs, and guidelines. The delta's specific claims that the prior paper is limited to one dataset, framework, query set, and metrics are not established by these pairs and should remain qualified; however, those limitations are not necessary to establish the supported partial overlap or to distinguish it from substantial overlap.

Submission contribution span
“Basic RAG is comparable to or outperforms GraphRAG in simple fact retrieval tasks that does not require complex logics”

Pair 1: Both papers empirically compare graph-based retrieval with a traditional or non-graph approach and report comparative answer-accuracy performance, although the prior paper uses a narrower evaluation.

The prior work states:
“Our experimental results demonstrate that the graph-based approach we employed significantly improves accuracy compared to the method used in [17].”

Submission contribution span
“This enhanced graph density improves both information connectivity and coverage, ultimately contributing to superior retrieval and generation capabilities.”

Pair 3: Both papers attribute retrieval or processing benefits to the structural organization of the graph, linking graph complexity or sparsity to system efficiency and effectiveness.

The prior work states:
“Such sparsity is crucial for efficiency because it reduces the computational overhead required to traverse the graph and locate relevant nodes and edges.”

Comparison with the submission

The prior paper delivers a meaningful but narrower version of the claimed contribution: it empirically compares a GraphRAG system with a traditional approach and attributes gains partly to graph organization and sparsity. However, it does not provide the submission's systematic cross-system benchmark or broad analysis of the conditions and underlying reasons for GraphRAG's success across task complexity, datasets, retrieval/generation behavior, and efficiency trade-offs. Thus, important central novelty remains beyond the prior paper, warranting partial rather than substantial overlap.

##### Graph Retrieval-Augmented Generation: A Survey
partial overlap · Peng et al. · 2024

How this paper realizes the claim

The paper is a survey rather than an empirical benchmark study. It organizes existing GraphRAG methodologies and formalizes the common workflow, but does not itself systematically compare when GraphRAG outperforms traditional RAG or explain the underlying causes of such performance differences.

“This paper provides the first comprehensive overview of GraphRAG methodologies. We formalize the GraphRAG workflow, encompassing Graph-Based Indexing, Graph-Guided Retrieval, and Graph-Enhanced Generation. We then outline the core technologies and training methods at each stage.”

“Additionally, we examine downstream tasks, application domains, evaluation methodologies, and industrial use cases of GraphRAG. Finally, we explore future research directions to inspire further inquiries and advance progress in the field.”

“We provide a comprehensive and systematic review of existing state-of-the-art GraphRAG methodologies. We offer a formal definition of GraphRAG, outlining its universal workflow which includes G-Indexing, G-Retrieval, and G-Generation. • We discuss the core technologies underpinning existing GraphRAG systems, including GIndexing, G-Retrieval, and G-Generation.”

“We delineate the downstream tasks, benchmarks, application domains, evaluation metrics, current challenges, and future research directions pertinent to GraphRAG, discussing both J.”

In its benchmark-and-metrics discussion, the paper catalogs evaluation resources and notes that the field lacks unified standards; it recommends establishing a standard benchmark, but does not build or use one to derive comparative conditions or practical guidelines.

“GraphRAG is a relatively new field that lacks unified and standard benchmarks for evaluating different methods. Establishing a standard benchmark is crucial for this area as it can provide a consistent framework for comparison, facilitate objective assessments of various approaches, and drive progress by identifying strengths and weaknesses. This benchmark should encompass diverse and representative datasets, well-defined evaluation metrics, and comprehensive test scenarios to ensure robust and meaningful evaluations of GraphRAG methods.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 establishes a substantive but limited overlap in evaluation-oriented coverage: both works organize GraphRAG evaluation across multiple tasks, benchmarks, and metrics. The roles differ, however: the submission conducts an evaluation of seven frameworks on a benchmark, while the prior paper delineates and surveys evaluation dimensions. Thus, the pair supports a meaningful shared evaluation-framing component, but not the same empirical question, comparative findings, or explanations of when GraphRAG surpasses traditional RAG. The proposed partial degree is therefore supported. The delta's stronger claims that the prior paper lacks the submission's benchmark construction, experiments, causal analysis, and recommendations should remain qualified: the pair does not exhaustively establish the absence of all such components, although that limitation does not block the partial-overlap decision.

Submission contribution span
“To address Q1, we evaluate seven representative GraphRAG frameworks on our benchmark, using tailored metrics for different question types.”

Pair 1: Both contribute systematic coverage of GraphRAG evaluation across multiple tasks, benchmarks, and metrics, but the prior paper surveys these dimensions rather than experimentally comparing systems.

The prior work states:
“We delineate the downstream tasks, benchmarks, application domains, evaluation metrics, current challenges, and future research directions pertinent to GraphRAG, discussing both J.”

Comparison with the submission

The prior paper contributes meaningful evaluation infrastructure at the conceptual and survey level, including a taxonomy of benchmarks and metrics and a call for standardized evaluation. However, it does not itself deliver the central empirical contribution claimed by the submission: a benchmark-based, systematic investigation of when GraphRAG surpasses traditional RAG and why. The overlap is therefore partial, with the submission retaining a distinct central contribution in benchmark construction, comparative experimentation, causal analysis, and recommendations.

##### Medical Graph RAG: Towards Safe Medical Large Language Model via Graph Retrieval-Augmented Generation
partial overlap · 2024

How this paper realizes the claim

The paper proposes MedGraphRAG, a medical-domain GraphRAG framework, rather than a general benchmark for characterizing when GraphRAG outperforms RAG.

“We introduce a novel graph-based RetrievalAugmented Generation (RAG) framework specifically designed for the medical domain, called MedGraphRAG, aimed at enhancing Large Language Model (LLM) capabilities for generating evidence-based medical responses, thereby improving safety and reliability when handling private medical data. Graph-based RAG (GraphRAG) leverages LLMs to organize RAG data into graphs, showing strong potential for gaining holistic insights from longform documents.”

“Our approach is validated on 9 medical Q&A benchmarks, 2 health fact-checking benchmarks, and one collected dataset testing long-form generation. The results show that MedGraphRAG consistently outperforms stateof-the-art models across all benchmarks, while also ensuring that responses include credible source documentation and definitions.”

It does directly compare standard RAG, GraphRAG, and MedGraphRAG across medical tasks, providing empirical evidence about relative performance in that domain.

“The results show that MedGraphRAG significantly enhances LLM performance on both health fact-checking and medical Q&A benchmarks. Compared to baselines without retrieval, MedGraphRAG achieves an average improvement of nearly 10% in factchecking and 8% in medical Q&A.”

“When compared to baselines using GraphRAG, it demonstrates an average improvement of around 8% in fact-checking and 5% in medical Q&A. Notably, MedGraphRAG yields more pronounced improvements in smaller LLMs, such as Llama213B and Llama28B.”

The paper also offers a mechanistic explanation for its gains: separating user data, sources, and definitions into linked graph tiers and replacing summary-based retrieval with hierarchical top-down retrieval plus bottom-up response refinement.

“In contrast, MedGraphRAG provided a more comprehensive answer by recommending cardioselective betablockers—such as bisoprolol or metoprolol—that safely manage both conditions without adverse effects. As we can see form the graph abstracted, this superiority stems from MedGraphRAG’s architecture, where entities are directly linked to key information in references, allowing retrieval of specific evidence.”

“As we can see form the graph abstracted, this superiority stems from MedGraphRAG’s architecture, where entities are directly linked to key information in references, allowing retrieval of specific evidence. Conversely, GraphRAG struggles to retrieve specific information since its reference and user data are intertwined within the same layer of the graph, which leads to missing key information under the same number of nearest neighbors.”

“The results show a gradual performance improvement as more of our modules are added, with significant gains observed when replacing GraphRAG graph construction with our Triple Graph Construction. Additionally, by replacing the summary-based retrieval(Edge et al., 2024b) in GraphRAG with our U-Retrieval method, we achieved further improvements, setting new stateof-the-art results across all three benchmarks.”

“Additionally, by replacing the summary-based retrieval(Edge et al., 2024b) in GraphRAG with our U-Retrieval method, we achieved further improvements, setting new stateof-the-art results across all three benchmarks. 3.4.2 Which is important?”

Its conclusions are therefore primarily about the superiority and safety of a specialized medical GraphRAG design, not a systematic cross-task study of the conditions under which GraphRAG as a family surpasses traditional RAG or general practical guidelines.

Grounded evidence for the assessed overlap

Evidence check: material
2 of 4 grounded candidates support the overlap

Pair 1 establishes a substantive empirical overlap: both works report performance benefits for graph-based retrieval in medical or demanding information-seeking settings. It supports the shared claim that graph-based retrieval is empirically compared with conventional RAG and can provide advantages, although it does not establish identical tasks, conditions, or a systematic finding about increasing question complexity. Pair 4 establishes a further meaningful overlap in deriving practical guidance about when graph-based retrieval benefits from particular data organization and retrieval choices. These overlaps support a partial degree, but not equivalence with the submission's broader benchmark-level investigation. Pair 2 supports a related methodological rationale about graph organization enabling comprehensive information synthesis, but its quoted spans do not directly establish the submission's broader empirical investigation of when GraphRAG surpasses RAG. Pair 3 establishes comparative evaluation activity across model configurations, but not the same scientific findings or a comparable multi-framework investigation; it is therefore not independently sufficient for substantive overlap. The delta's claims about broader coverage, failure modes, efficiency, scalability, and multiple implementations are not established by the correspondence pairs, but those limitations do not block the independently supported partial overlap. They should not be treated as proven residual novelty solely from missing correspondences.

Submission contribution span
“For Level 2-3 questions on the novel dataset, HippoRAG achieves remarkable Evidence Recall (87.9-90.9%), while HippoRAG2 leads in Context Relevance (85.8-87.8%).”

Pair 1: Both papers report empirical performance gains for graph-based retrieval on medical or more demanding information-seeking tasks, although the prior paper does not systematically attribute the gain to increasing question complexity.

The prior work states:
“The results show that MedGraphRAG significantly enhances LLM performance on both health fact-checking and medical Q&A benchmarks.”

Submission contribution span
“In this paper, we not only build GraphRAG-Bench to evaluate existing GraphRAG systems, but more importantly, we provide insightful recommendations for future GraphRAG research, as illustrated in Figure”

Pair 4: Both papers derive practical guidance about the conditions or design choices needed for graph-based retrieval to realize its benefits, although the prior paper's guidance is limited to matching data organization with retrieval method.

The prior work states:
“The results show that both the data and the right retrieval method must work together to unlock the full potential. When retrieving data by standard RAG, Med-Paper data individually improves performance by less than 2%, and Med-Dictionary data by less than 1%.”

Comparison with the submission

The prior paper delivers a meaningful part of the claimed contribution by directly comparing RAG and GraphRAG in a substantial medical evaluation and by analyzing architectural reasons for its observed gains. However, its central contribution is a specialized medical GraphRAG method and its validation, not a general systematic investigation of when GraphRAG surpasses traditional RAG across conditions and implementations. Important novelty remains in the submission's benchmark-level, multi-dimensional analysis of success conditions, failure modes, efficiency, and general guidelines, so the overlap is partial.

##### PIKE-RAG: sPecIalized KnowledgE and Rationale Augmented Generation
partial overlap · Wang et al. · 2025

How this paper realizes the claim

The paper evaluates GraphRAG against several RAG and reasoning baselines on multi-hop open-domain and legal benchmarks, organizing the analysis around task difficulty and retrieval/reasoning capability.

“Additionally, we propose a new paradigm that classifies tasks based on their complexity in knowledge extraction and application, allowing for a systematic evaluation of RAG systems’ problem-solving capabilities.”

“Regarding GraphRAG, originally designed for the query-focused summarization (QFS) task as outlined by [21], we observe its suboptimal performance in both local and global modes compared to our method.”

It also provides a limited explanation of comparative outcomes: naive retrieval works for simpler multi-hop questions, while decomposition and knowledge-aware retrieval help on more complex questions. However, the paper does not itself introduce GraphRAG-Bench or systematically study the conditions under which GraphRAG surpasses traditional RAG across retrieval, generation, graph structure, efficiency, and model or corpus factors.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 3 grounded candidates support the overlap

Pair 2 establishes a substantive shared empirical component: both works relate the relative effectiveness of graph-based versus ordinary/naive retrieval to task complexity. The submission reports a GraphRAG advantage on complex reasoning, while PIKE-RAG reports that naive RAG can be effective on simpler multi-hop benchmarks. This supports partial overlap in investigating conditions under which retrieval approaches differ, although it does not establish the same findings, benchmark scope, or comprehensive multi-factor diagnosis. Pair 1 is weaker and does not clearly show that PIKE-RAG compares GraphRAG with traditional RAG in the quoted span; it mainly discusses naive RAG variants and knowledge-base structure, so it is not included as a supporting material pair. Pair 3 does not establish shared comparative empirical investigation or the same practical-guideline contribution: the submission span concerns benchmark design, whereas the PIKE-RAG span concerns staged capability development. The delta's claims that PIKE-RAG lacks the benchmark-centered multi-factor analysis and corresponding systematic guidelines are not established by absence of correspondence pairs and should remain qualified, but this limitation does not block the independently supported partial overlap.

Submission contribution span
“GraphRAG models show a clear advantage in complex reasoning, Contextual Summarize, and creative generation.”

Pair 2: Both works contribute empirical conclusions relating the relative effectiveness of graph-based or ordinary retrieval to task complexity, with PIKE-RAG providing the narrower finding that naive RAG is effective on simpler multi-hop benchmarks.

The prior work states:
“This indicates that for simpler benchmarks, RAG equipped with naive knowledge retrieval could address simple multihop questions, leading to a significant accuracy boost.”

Comparison with the submission

The overlap is partial: PIKE-RAG itself performs comparative GraphRAG/RAG evaluation and connects outcomes to task complexity and reasoning demands, rather than merely mentioning GraphRAG as related work. Nevertheless, its primary contribution is a specialized RAG framework and decomposition method, while the submission’s distinct central contribution is a dedicated benchmark and systematic explanation of when GraphRAG outperforms traditional RAG across multiple operating conditions.

##### MedRAG: Enhancing Retrieval-augmented Generation with Knowledge Graph-Elicited Reasoning for Healthcare Copilot
partial overlap · Zhao et al. · 2025

How this paper realizes the claim

The paper develops and evaluates MedRAG, a healthcare-specific RAG system that integrates a diagnostic knowledge graph with retrieved EHRs to elicit reasoning. It compares MedRAG with several RAG baselines on two medical datasets using accuracy, diagnostic specificity, and text-generation metrics.

“MedRAG is evaluated on both a public dataset DDXPlus and a private chronic pain diagnostic dataset (CPDD) collected from Tan Tock Seng Hospital, and its performance is compared against various existing RAG methods. Experimental results show that, leveraging the information integration and relational abilities of the KG, our MedRAG provides more specific diagnostic insights and outperforms state-of-the-art models in reducing misdiagnosis rates.”

The paper also investigates why its graph-elicited reasoning helps through component ablations, showing that combining retrieval with correctly selected diagnostic-graph knowledge improves performance, especially for granular diagnosis.

“As shown in Figure 3, both the retriever and KG-elicited reasoning module significantly enhance performance across all specificity levels. the best outcomes are achieved when RAG and KG components are combined and aligned, especially for granular diagnosis tasks that demand high specificity.”

“Once correct KG-augmented knowledge was added, this noise effect was mitigated, leading to accuracy improvements across all metrics: an average accuracy increase of 18.88% for 𝐿1, 26.92% for 𝐿2, and 18.89% for 𝐿3, compared to the baseline with random or without KG-elicited reasoning module. The ablation study of KG components is shown in the Appendix.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 2 establishes a substantive shared component: both works attribute improved RAG performance to graph-derived or KG-augmented information and report performance gains associated with that mechanism. The conditions and outcomes are narrower and not identical—MedRAG concerns correct KG augmentation in medical diagnosis, whereas the submission discusses graph density, connectivity, retrieval, and generation—so this supports partial rather than substantial overlap. Pair 1 supports that MedRAG performs an empirical comparison against alternative RAG systems, but its quoted span only establishes comparative evaluation, not that MedRAG reaches the same finding about when graph-based RAG surpasses traditional RAG; shared evaluation activity alone is insufficient for material overlap. The delta's claims that MedRAG lacks general cross-framework conditions and practical guidelines are not established by the pairs, since missing correspondences do not prove those absences. That limitation does not block the partial-overlap decision, which is independently supported by pair 2.

Submission contribution span
“This enhanced graph density improves both information connectivity and coverage, ultimately contributing to superior retrieval and generation capabilities.”

Pair 2: Both papers analyze how graph-derived structure or knowledge produces performance gains over less informative retrieval configurations, with MedRAG offering a narrower component-level causal analysis in medical diagnosis.

The prior work states:
“Once correct KG-augmented knowledge was added, this noise effect was mitigated, leading to accuracy improvements across all metrics: an average accuracy increase of 18.88% for 𝐿1, 26.92% for 𝐿2”

Comparison with the submission

The overlap is substantive but limited: MedRAG itself compares graph-enhanced and non-graph RAG behavior and uses ablations to explain the benefit of graph-elicited knowledge. However, it does not deliver the submission's central benchmark-level, cross-system analysis of when GraphRAG surpasses traditional RAG or the resulting general guidelines. Important novelty therefore remains in the submission, warranting partial rather than substantial overlap.

##### HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models
partial overlap · Gutierrez et al. · 2024

How this paper realizes the claim

The paper introduces HippoRAG, a graph-based retrieval framework inspired by hippocampal memory indexing. It constructs a schemaless knowledge graph from passages and uses query concepts as seeds for Personalized PageRank, enabling single-step multi-hop retrieval across passages.

“In this work, we propose HippoRAG, a RAG framework that serves as a long-term memory for LLMs by mimicking this model of human memory. Our novel design first models the neocortex’s ability to process perceptual input by using an LLM to transform a corpus into a schemaless knowledge graph (KG) as our artificial hippocampal index.”

The paper evaluates its method against existing retrieval approaches on multi-hop QA benchmarks and reports stronger retrieval and QA performance, along with lower online retrieval cost and latency.

“This capacity for single-step multi-hop retrieval yields strong performance improvements of around 3 and 20 points over current RAG methods [10, 35, 53, 70, 71] on two popular multi-hop QA benchmarks, MuSiQue [77] and 2WikiMultiHopQA [33]. Additionally, HippoRAG’s online retrieval process is 10 to 30 times cheaper and 6 to 13 times faster than current iterative retrieval methods like IRCoT [78], while still achieving comparable performance. Furthermore, our approach can be combined with IRCoT to provide complementary gains of up to 4% and 20% on the same datasets and even obtain improvements on HotpotQA, a less challenging multi-hop QA dataset.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 1 validly establishes substantive overlap in the current claim’s core empirical contribution: both use graph-based retrieval/association structures to connect information across passages for knowledge integration and multi-hop reasoning. This is more than a shared topic or generic evaluation activity, so it supports a meaningful partial overlap. It does not establish the submission’s broader systematic benchmark, cross-system comparison, or full analysis of conditions and trade-offs; those differences support the proposed partial rather than substantial degree. Pair 2 is not a valid match for the asserted efficiency contribution as stated: it compares different baselines and measures different consequences—HippoRAG’s cost and speed against iterative retrieval versus the submission’s prompt-token overhead against vanilla RAG. It therefore does not independently establish shared efficiency findings, though it does not undermine the overlap supported by pair 1. The delta’s claims about the submission’s broader metrics, systems, datasets, and practical trade-offs are not established by these pairs and should remain qualified; their absence from the pairs does not itself prove novelty, but resolving them is not necessary to establish the meaningful shared graph-based multi-hop component or the partial degree.

Submission contribution span
“Medical dataset results reinforce this trend, demonstrating GraphRAG's unique ability to connect information across distant text segments, crucial for multi-hop reasoning and comprehensive summarization.”

Pair 1: Both contribute a graph-based retrieval mechanism that connects information across passages to support knowledge integration and multi-hop reasoning.

The prior work states:
“HippoRAG allows LLMs to build and leverage a similar graph of associations to tackle knowledge integration tasks. standard multi-hop question answering (QA) also requires integrating information between passages in a retrieval corpus.”

Comparison with the submission

HippoRAG delivers a meaningful substantive part of the claim: it demonstrates that a graph-based RAG system can outperform traditional and iterative retrieval in knowledge-integration and multi-hop settings, while also analyzing efficiency. However, it does not provide the submission's systematic cross-system benchmark or its broader investigation of the conditions, mechanisms, and practical trade-offs governing GraphRAG versus RAG. The overlap is therefore partial rather than substantial.

##### CG-RAG: Research Question Answering by Citation Graph Retrieval-Augmented LLMs
partial overlap · Hu et al. · 2025

How this paper realizes the claim

The paper itself presents CG-RAG as a citation-graph RAG framework for research-question answering. It contributes a graph-contextualized retrieval method that combines sparse and dense relevance signals, propagates them through citation-graph neighborhoods, retrieves contextual subgraphs, and uses those subgraphs for generation.

“This forms the basis of an entangled representation, integrating both sparse-dense fusion and graph contextual information. Algorithm 1 Lexical-Semantic Graph Retrieval.”

“When relevant graph contexts are present, the entangled framework dynamically propagates and aggregates sparse and dense signals through structural relationships among neighboring chunks. This enables the model to capture relational dependencies and multi-hop connections in graphs, enhancing retrieval accuracy and effectively utilizing sparse and dense signals from neighbors.”

Quoted from the source but NOT confirmed verbatim:
These retrieved chunks, together with their contextual subgraph, are then used to generate the answer, as illustrated in Figure 2.

“Extensive experiments on research question answering benchmarks across multiple domains demonstrate that our CG-RAG framework significantly outperforms RAG methods combined with various state-of-the-art retrieval approaches, delivering superior retrieval accuracy and generation quality. Permission to make digital or hard copies of all or part of this work for personal or classroom use is granted without fee provided that copies are not made or distributed for profit or commercial advantage and that copies bear this notice and the full citation on the first page.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 5 grounded candidates support the overlap

Pair 1 validly establishes a meaningful shared empirical component: both works evaluate graph-based retrieval against conventional sparse, dense, or hybrid alternatives. The submission span specifies comparative retrieval evaluation, while the prior-paper span reports an improvement over those baselines. This supports partial overlap in the claim’s investigation of GraphRAG versus traditional retrieval, although it does not establish that the works share the submission’s broader systematic analysis of conditions, mechanisms, or practical guidelines. Pair 4 also supports a narrower shared component concerning graph-contextualized retrieval for connecting relationally separated information and supporting multi-hop reasoning. Pair 2 supports shared evaluation of graph-augmented RAG on question-answering tasks, but the prior-paper quotation does not clearly establish the specific downstream generation-quality comparison asserted, so it is not needed as a material pair. Pair 3 is not sufficiently grounded: the prior-paper span is fragmentary and does not itself establish improved generation quality relative to conventional retrieval. Pair 5 should not be treated as direct support for a shared efficiency finding because the quoted spans concern different aspects—prompt-token overhead and task-complexity trade-offs versus latency and memory efficiency. The submission’s claims that CG-RAG lacks the broader conditions-and-reasons study, evaluation framework, and recommendations are not established by absence of correspondence pairs and should remain qualified, but those limitations do not block the independently supported partial-overlap judgment.

Submission contribution span
“To quantitatively compare the retrieval effectiveness of the two paradigms, we adopt two complementary metrics: Evidence Recall, which measures how completely the retrieved context covers the gold evidence”

Pair 1: Both works contribute an empirical comparison of graph-based retrieval against sparse, dense, and hybrid retrieval alternatives, directly supporting the claim’s investigation of when GraphRAG surpasses traditional retrieval systems.

The prior work states:
“Table 3 demonstrates that LeSeGR significantly outperforms all baselines in the retrieval phase, including sparse, dense, and hybrid approaches.”

Submission contribution span
“Medical dataset results reinforce this trend, demonstrating GraphRAG's unique ability to connect information across distant text segments, crucial for multi-hop reasoning and comprehensive summarization.”

Pair 4: Both works contribute graph-contextualized retrieval that connects relationally separated information to support multi-hop question answering or reasoning; CG-RAG delivers this as a particular citation-graph retrieval mechanism rather than as a systematic study of the conditions under which it succeeds.

The prior work states:
“This enables the model to capture relational dependencies and multi-hop connections in graphs, enhancing retrieval accuracy and effectively utilizing sparse and dense signals from neighbors.”

Comparison with the submission

CG-RAG delivers meaningful overlap by building and evaluating a graph-based RAG system whose graph-contextualized retrieval improves downstream generation relative to conventional retrieval approaches. However, its central contribution is a particular citation-graph retrieval and generation method for research-question answering, whereas the submission's central contribution is a benchmark-driven systematic investigation of the conditions, mechanisms, and costs under which GraphRAG outperforms traditional RAG. Important novelty therefore remains in the submission, making the overlap partial rather than substantial.

##### KET-RAG: A Cost-Efficient Multi-Granular Indexing Framework for Graph-RAG
partial overlap · Huang et al. · 2025

How this paper realizes the claim

KET-RAG proposes a specific cost-efficient Graph-RAG indexing and retrieval framework, combining a knowledge-graph skeleton with a text-keyword bipartite graph; it is not a benchmark or systematic study of the conditions under which GraphRAG outperforms RAG.

“To ensure a good result accuracy while reducing the indexing cost, we propose KET-RAG, a multi-granular indexing framework. KET-RAG first identifies a small set of key text chunks and leverages an LLM to construct a knowledge graph skeleton.”

“We evaluate eight solutions on two real-world datasets, demonstrating that KET-RAG outperforms all competitors in indexing cost, retrieval effectiveness, and generation quality. Notably, it achieves comparable or superior retrieval quality to Microsoft’s Graph-RAG while reducing indexing costs by over an order of magnitude.”

The paper does provide comparative evidence relevant to the claim: it evaluates KET-RAG against Text-RAG and other retrieval methods, measuring retrieval and generation quality under different cost configurations.

“In the first set of experiments, we evaluate the performance of KET-RAG against existing competitors (Text-RAG, KNNG-RAG, KG-RAG, and Hybrid-RAG) under two configurations: a low-cost version with reduced accuracy and a high-accuracy version with increased cost. Following previous works [8], we achieve the lowcost setting by using an input chunk size of ℓ= 1, 200 and the highaccuracy setting by fixing ℓ= 150 for all solutions.”

“Most notably, we observe that KETRAG in low-cost mode achieves comparable or even superior coverage to KG-RAG and Hybrid-RAG in high-accuracy mode while reducing indexing costs by over an order of magnitude. For example, on HotpotQA, the coverage scores of KET-RAG-P, Hybrid-RAG, and KG-RAG are 81.6%, 80.2%, and 74.6%, respectively, yet KET-RAG-P incurs only 8.7% of their indexing cost.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 2 grounded candidates support the overlap

Pair 1 validly establishes a shared empirical comparison activity: the submission evaluates multiple GraphRAG frameworks against alternatives, while KET-RAG evaluates its framework against Text-RAG and other competitors. This supports overlap in comparative Graph-RAG evaluation, though it does not establish that the works answer the same broad diagnostic question or provide equivalent benchmark scope. Pair 2 establishes a shared quality-resource-cost trade-off analysis: both relate GraphRAG quality to costs, even though the specific cost dimensions differ (prompt-token overhead versus indexing cost). Together these are substantive shared components of the current claim and support partial overlap. They do not establish substantial or same overlap because the cited evidence does not show that KET-RAG provides the submission's multi-system, task-regime diagnosis of when GraphRAG succeeds, its underlying-cause analysis, or practical guidelines. The delta's characterization of KET-RAG as a single-framework evaluation is supported by Pair 1, but any stronger assertion that KET-RAG lacks every form of broader diagnosis or guidance should remain qualified because the pairs are not exhaustive; that limitation does not block the partial-overlap decision.

Submission contribution span
“To address Q1, we evaluate seven representative GraphRAG frameworks on our benchmark, using tailored metrics for different question types.”

Pair 1: Both works experimentally compare graph-based retrieval systems with traditional or alternative RAG systems using quality-oriented evaluation, although KET-RAG evaluates one proposed framework against baselines rather than providing a broad multi-system benchmark.

The prior work states:
“In the first set of experiments, we evaluate the performance of KET-RAG against existing competitors (Text-RAG, KNNG-RAG, KG-RAG”

Submission contribution span
“These findings underscore a critical trade-off: while GraphRAG improves retrieval breadth, it may also introduce noisy context due to prompt inflation, especially in complex tasks.”

Pair 2: Both works contribute empirical analysis of the trade-off between GraphRAG quality and its resource cost, though the submission emphasizes prompt-token overhead while KET-RAG emphasizes indexing cost.

The prior work states:
“As reported in Table 2, our proposed KET-RAG (-U/-P) achieves superior quality-cost trade-offs compared to existing methods on both MuSiQue and HotpotQA. In terms of retrieval quality, KETRAG significantly outperforms all baselines, achieving the coverage score of 77.0%/80.2% and 81.6%/82.6% on MuSiQue and HotpotQA, respectively.”

Comparison with the submission

The overlap is partial: KET-RAG itself delivers meaningful comparative evidence about Graph-RAG versus Text-RAG and other baselines, including quality and cost trade-offs. However, it does not deliver the central benchmark contribution of systematically characterizing the conditions, underlying reasons, and practical guidance for GraphRAG's superiority across systems and task regimes; its remaining contribution is a distinct algorithmic framework and its evaluation.

##### StructRAG: Boosting Knowledge Intensive Reasoning of LLMs via Inference-time Hybrid Information Structurization
partial overlap · Li et al. · 2024

How this paper realizes the claim

StructRAG proposes an inference-time framework that selects a task-appropriate information structure, reconstructs documents into that structure, and uses the structured representation for reasoning.

“In this paper, motivated by the cognitive theories that humans convert raw information into various structured knowledge when tackling knowledge-intensive reasoning, we proposes a new framework, StructRAG, which can identify the optimal structure type for the task at hand, reconstruct original documents into this structured format, and infer answers based on the resulting structure. Extensive experiments across various knowledge-intensive tasks show that StructRAG achieves state-of-the-art performance, particularly excelling in challenging scenarios, demonstrating its potential as an effective solution for enhancing LLMs in complex real-world applications.”

The paper evaluates StructRAG against RAG and GraphRAG baselines on knowledge-intensive tasks, reporting that its gains become larger as documents become longer and information becomes more dispersed.

“these results indicate that StructRAG shows more significant improvements over the baselines with longer documents and more scattered information, demonstrating that abilities of our framework to construct and use the optimal type of structured knowledge is especially effective for complex tasks.”

It also analyzes the relative implementation cost of GraphRAG and StructRAG, finding that StructRAG is much faster in its reported setting.

“StructRAG has slightly higher latency compared to RQ-RAG but is obviously faster than GraphRAG. Therefore, StructRAG is a kind of high-performance framework with available implementing speed.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 establishes a substantive shared component: both papers compare GraphRAG-related approaches with non-graph or alternative retrieval approaches and report an efficiency disadvantage or cost for GraphRAG. The submission measures increased prompt-token length, while StructRAG reports implementation latency relative to RQ-RAG and GraphRAG; these are different efficiency metrics and do not establish the same quantitative finding or identical conditions, but they support a narrower shared efficiency-trade-off contribution. This is meaningful overlap within the claim and supports a partial degree. The pair does not establish the broader shared claims about when GraphRAG surpasses traditional RAG, retrieval or generation quality, graph complexity, scalability, model size, underlying causal explanations, or practical guidelines. The delta's assertions that StructRAG primarily contributes its own hybrid framework and lacks the submission's dedicated benchmark and systematic diagnostic scope are not established by this pair; they should remain qualified, but resolving them is not necessary to support the independently evidenced partial efficiency overlap.

Submission contribution span
“Compared to vanilla RAG, GraphRAG significantly increases prompt length due to the additional steps involved in knowledge retrieval and graph-based aggregation.”

Pair 1: Both papers contribute comparative evidence about the practical efficiency costs of GraphRAG relative to non-graph retrieval approaches, although the submission measures prompt-token overhead while the prior paper measures implementation latency.

The prior work states:
“StructRAG has slightly higher latency compared to RQ-RAG but is obviously faster than GraphRAG. Therefore, StructRAG is a kind of high-performance framework with available implementing speed.”

Comparison with the submission

The overlap is partial: StructRAG supplies meaningful comparative evidence about GraphRAG's behavior on increasingly complex or dispersed knowledge-intensive tasks and reports an efficiency comparison. However, it does not itself deliver the submission's dedicated GraphRAG-Bench or its broad systematic analysis of retrieval, generation, graph structure, scalability, and causal explanations for when GraphRAG succeeds. After subtracting the comparative baseline findings, the submission retains a distinct central benchmark and diagnostic contribution.

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

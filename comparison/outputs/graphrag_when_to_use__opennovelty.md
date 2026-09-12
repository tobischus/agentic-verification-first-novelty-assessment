# Novelty Assessment Report

Paper: When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation

### PDF URL: https://openreview.net/pdf?id=i9q9xDMjG7

### Venue: ICLR 2026 Conference Submission

### Year: 2026

### Report Generated: 2026-01-04

# Abstract

Graph retrieval-augmented generation (GraphRAG) has emerged as a powerful paradigm for enhancing large language models (LLMs) with external knowledge. It leverages graphs to model the hierarchical structure between specific concepts, enabling more coherent and effective knowledge retrieval for accurate reasoning. Despite its conceptual promise, recent studies report that GraphRAG frequently underperforms vanilla RAG on many real-world tasks. This raises a critical question: Is GraphRAG really effective, and in which scenarios do graph structures provide measurable benefits for RAG systems? To address this, we propose GraphRAG-Bench, a comprehensive benchmark designed to evaluate GraphRAG models on both hierarchical knowledge retrieval and deep contextual reasoning. GraphRAG- Bench  features  a  comprehensive  dataset  with  tasks  of  increasing  difficulty,  covering  fact  retrieval,  complex  reasoning,  contextual summarize, and creative generation, and a systematic evaluation across the entire pipeline, from graph construction and knowledge retrieval to final generation. Leveraging this novel benchmark, we systematically investigate the conditions when GraphRAG surpasses traditional RAG and the underlying reasons for its success, offering guidelines for its practical application. All related resources and analysis are collected for the community at https://anonymous.4open.science/r/GraphRAG-Benchmark-CE8D/.

### Disclaimer

This report is AI-GENERATED using Large Language Models and WisPaper (a scholar search engine). It analyzes academic papers' tasks and contributions against retrieved prior work. While this system identifies POTENTIAL overlaps and novel directions, ITS COVERAGE IS NOT EXHAUSTIVE AND JUDGMENTS ARE APPROXIMATE. These results are intended to assist human reviewers and SHOULD NOT be relied upon as a definitive verdict on novelty.
Note that some papers exist in multiple, slightly different versions (e.g., with different titles or URLs). The system may retrieve several versions of the same underlying work. The current automated pipeline does not reliably align or distinguish these cases, so human reviewers will need to disambiguate them manually.
If you have any questions, please contact: mingzhang23@m.fudan.edu.cn

# Core Task Landscape

This paper addresses: Evaluating Graph Retrieval-Augmented Generation Effectiveness Across Task Complexity Levels

### A total of 26 papers were analyzed and organized into a taxonomy with 12 categories.

### Taxonomy Overview

The research landscape has been organized into the following main categories:

### Benchmark Design and Evaluation Frameworks

### Graph Construction and Knowledge Representation

### Retrieval Strategies and Optimization

### Reasoning and Generation Architectures

### Domain-Specific Applications

### Complete Taxonomy Tree

Evaluating Graph Retrieval-Augmented Generation Effectiveness Across Task Complexity Levels Survey Taxonomy Benchmark Design and Evaluation Frameworks Comprehensive Multi-Dimensional Benchmarks ★ (3 papers) [0] When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation (Anon et al., 2026) View paper [2] In-depth Analysis of Graph-based RAG in a Unified Framework (Zhou Yingli, 2025) View paper [7] Graphrag-bench: Challenging domain-specific reasoning for evaluating graph retrieval-augmented generation (Xiao Yi-Lin, 2025) Domain-Specific Evaluation Studies (3 papers) [1] Document GraphRAG: Knowledge Graph Enhanced Retrieval Augmented Generation for Document Question Answering Within the Manufacturing Domain (Simon Knollmeyer, 2025) View paper [15] Beyond Vector Retrieval: Evaluating Graph-Enhanced RAG performance in aSystem Architecture Environment (A Filipson, 2025) View paper [16] Benchmarking Vector, Graph and Hybrid Retrieval Augmented Generation (RAG) Pipelines for Open Radio Access Networks (ORAN) (Sarat Ahmad, 2025) View paper Question Generation and Difficulty Calibration (2 papers) [4] KAQG: A Knowledge-Graph-Enhanced RAG for Difficulty-Controlled Question Generation (Changan Chen, 2025) View paper [22] GRADE: Generating multi-hop QA and fine-gRAined Difficulty matrix for RAG Evaluation (Jeongsoo Lee, 2025) View paper Graph Construction and Knowledge Representation Document-Based Graph Construction (2 papers) [10] Hierarchical lexical graph for enhanced multi-hop retrieval (Abdellah Ghassel, 2025) View paper [18]  Guiding  Graph-Based  Retrieval  Augment  Generation:Guided  Strategies  for  Enhancing  Graph  Structure  Retrievaland Generation (Yu-Hsiu Chiu, 2025) View paper Domain-Specific Knowledge Graph Engineering (2 papers) [13] Reducing Hallucinations in Medical AI: A Knowledge Graph-Augmented Retrieval System for Evidence-Based Age-Related Macular Degeneration Information (Alexandru Lecu, 2025) View paper [24] Approaches to automatic discovery and modeling of Industrial Assets for IT/OT Integration * (Anand Todkar, 2025) View paper Retrieval Strategies and Optimization Adaptive and Complexity-Aware Retrieval (3 papers) • • • • • • • ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ • ◦ ◦ ◦ ◦ ◦ ◦ • ◦ [3] Frag: A flexible modular framework for retrieval-augmented generation based on knowledge graphs (Yukun Cao, 2025) View paper [8] Curriculum Engineering: Structured Learning for Large Language Models (LLMs) Through Curriculum Based Retrieval (Ke-xin Sun, 2025) View paper [14] AdaGCRAG: Adaptive Graph-Chunk Retrieval for Lightweight RAG (Yanqiu Zhang, 2025) View paper Multi-Hop and Iterative Retrieval (3 papers) [5] Optimizing open-domain question answering with graph-based retrieval augmented generation (Joyce Cahoon, 2025) View paper [21] NeuroPath: Neurobiology-Inspired Path Tracking and Reflection for Semantically Coherent Retrieval (Junchen Li, 2025) View paper [23] Beyond Static Retrieval: Opportunities and Pitfalls of Iterative Retrieval in GraphRAG (Guo Kai, 2025) View paper Query Processing and Retrieval Enhancement (2 papers) [6] Adaptive Schema-aware Event Extraction with Retrieval-Augmented Generation (Sheng Liang, 2025) View paper [17] Enhancing Retrieval-Augmented Generation for Electric Power Industry Customer Support (Hei Yu Chan, 2025) View paper Reasoning and Generation Architectures Collaborative and Hierarchical Reasoning Systems (3 papers) [12] Collab-RAG: Boosting Retrieval-Augmented Generation for Complex Question Answering via White-Box and Black-Box LLM Collaboration (Xu Ran, 2025) View paper [20] Hierarchical Planning for Complex Tasks with Knowledge Graph-RAG and Symbolic Verification (Cornelio, 2025) View paper [25] Human Cognition Inspired RAG with Knowledge Graph for Complex Problem Solving (Cheng Yao, 2025) View paper Integrated Graph-RAG Generation Systems (2 papers) [9] Hyper-RAG: Combating LLM Hallucinations using Hypergraph-Driven Retrieval-Augmented Generation (Feng Yi-fan, 2025) View paper [19] EchoRAG: a framework for enhancing language models with graph-RAG and in-context learning (William Jones Beckhauser, 2025) View paper Domain-Specific Applications Educational and Training Applications (1 papers) [11] Retrieval-augmented generation for exam question creation in power industry education (xiaojian liu, 2025) View paper Technical Optimization and Code Generation (1 papers) [26] From Large to Small: Transferring CUDA Optimization Expertise via Reasoning Graph (Gong Jun-feng, 2025) View paper

### Narrative

Core task: Evaluating graph retrieval-augmented generation effectiveness across task complexity levels. The field has organized itself around five main branches that reflect the lifecycle of graph-based RAG systems. Benchmark Design and Evaluation Frameworks establish standardized testbeds for measuring performance, with works like When to use Graphs[0], In-depth Analysis[2], and Graphrag- bench[7] providing comprehensive multi-dimensional assessments. Graph Construction and Knowledge Representation addresses how structured knowledge is extracted and organized, while Retrieval Strategies and Optimization explores methods for efficiently navigating these structures, including approaches like Hyper-RAG[9] and Hierarchical Lexical Graph[10]. Reasoning and Generation Architectures focuses on how retrieved graph information is integrated into language model outputs, and Domain-Specific Applications demonstrates practical  deployments  in  areas  such  as  medical  question  answering  (Medical  Hallucinations[13]),  education  (Exam  Question Creation[11]), and industrial settings (Electric Power Support[17]).
A particularly active tension exists between general-purpose benchmarking efforts and specialized retrieval techniques. Works like Benchmarking RAG Pipelines[16] and Beyond Vector Retrieval[15] examine fundamental trade-offs in retrieval paradigms, while adaptive methods such as AdaGCRAG[14] and Adaptive Schema[6] explore dynamic graph construction strategies. The original paper When to use Graphs[0] sits squarely within the comprehensive benchmarking cluster alongside In-depth Analysis[2] and Graphrag-bench[7], but distinguishes itself by systematically investigating when graph-based approaches outperform simpler alternatives across varying task complexity.  Where  Graphrag-bench[7]  emphasizes  breadth  of  evaluation  scenarios  and  In-depth  Analysis[2]  provides  detailed performance  breakdowns,  When  to  use  Graphs[0]  focuses  on  the  decision  boundary  itself—helping  practitioners  understand  the conditions under which the added complexity of graph structures yields measurable benefits over traditional retrieval methods.

# Related Works in Same Category

### The following 2 sibling papers share the same taxonomy leaf node with the original paper:

### 1. In-depth Analysis of Graph-based RAG in a Unified Framework

Authors: Zhou Yingli, Su Yaodong, Yingli Zhou, Sun Youran, Yaodong Su, et al. (26 authors total) | Year/Venue: 2025 | URL: View paper

### Abstract

Graph-based Retrieval-Augmented Generation (RAG) has proven effective in integrating external knowledge into large language models (LLMs), improving their factual accuracy, adaptability, interpretability, and trustworthiness. A number of graph-based RAG methods have been proposed in the literature. However, these methods have not been systematically and comprehensively compared under the same experimental settings. In this paper, we first summarize a unified framework to incorporate all graph-ba...

### Relationship Analysis

Both papers belong to the Comprehensive Multi-Dimensional Benchmarks category, evaluating GraphRAG systems across multiple dimensions including task complexity, retrieval quality, and generation accuracy. They overlap in their focus on systematically assessing GraphRAG effectiveness through structured benchmarks with varying difficulty levels and comprehensive evaluation metrics covering the entire RAG pipeline. The key difference is that the original paper (GraphRAG-Bench) emphasizes benchmark design with novel corpus construction (domain-specific medical guidelines and literary texts) and task categorization by reasoning complexity, while the candidate paper focuses on unifying existing GraphRAG methods into a common framework with modular operator decomposition and comparative analysis of 12 representative methods across 11 datasets.

### 2. Graphrag-bench: Challenging domain-specific reasoning for evaluating graph retrieval-augmented

### generation

Authors: Xiao Yi-Lin, Yilin Xiao, Zhou Chuang, Junnan Dong, Dong Su, et al. (17 authors total) | Year/Venue: 2025 | URL: View paper

### Abstract

Graph Retrieval Augmented Generation (GraphRAG) has garnered increasing recognition for its potential to enhance large language models (LLMs) by structurally organizing domain-specific corpora and facilitating complex reasoning. However, current evaluations of GraphRAG models predominantly rely on traditional question-answering datasets. Their limited scope in questions and evaluation metrics fails to comprehensively assess the reasoning capacity improvements enabled by GraphRAG models. To addre...
◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ ◦ • ◦ ◦ ◦ ◦ ◦ ◦ ◦ • ◦ ◦ ◦ ◦

### ⚠ Similarity Notice

These  papers  share  nearly  identical  titles,  core  contributions,  and  technical  approaches.  Both  propose  'GraphRAG-Bench'  as  a comprehensive benchmark for evaluating GraphRAG systems across multiple task complexity levels (fact retrieval, complex reasoning, contextual  summarization,  creative  generation)  with  systematic  evaluation  of  the  entire  pipeline  (graph  construction,  retrieval, generation). The abstracts, methodology descriptions, and evaluation frameworks are substantively the same, strongly suggesting these are variants or near-duplicates of the same work.

# Contributions Analysis

Overall  novelty  summary. The  paper  proposes  GraphRAG-Bench,  a  comprehensive  benchmark  for  evaluating  graph  retrieval- augmented generation across multiple task types and difficulty levels. It sits within the 'Comprehensive Multi-Dimensional Benchmarks' leaf, which contains only three papers total. This is a relatively sparse research direction within the broader taxonomy of 26 papers across the field, suggesting that systematic, multi-dimensional benchmarking of GraphRAG remains an emerging area. The sibling papers in this leaf include works examining when to use graphs and providing in-depth analysis of GraphRAG performance, indicating a shared focus on understanding GraphRAG effectiveness rather than proposing new architectures.
The taxonomy reveals neighboring research directions in domain-specific evaluation, question generation for difficulty calibration, and various retrieval optimization strategies. The paper's position in benchmark design distinguishes it from adjacent branches focused on graph construction methods, adaptive retrieval techniques, and reasoning architectures. While the field shows substantial activity in retrieval  strategies  (with  adaptive,  multi-hop,  and  query  processing  subcategories)  and  domain  applications,  the  comprehensive benchmarking  cluster  remains  small.  This  positioning  suggests  the  work  addresses  a  recognized  gap:  the  need  for  standardized evaluation frameworks that can systematically compare GraphRAG against traditional RAG across varying task complexities.
Among 28 candidates examined through semantic search and citation expansion, none were found to clearly refute any of the three main contributions. For the GraphRAG-Bench benchmark itself, 10 candidates were examined with no refutable prior work identified. Similarly, the systematic investigation of when GraphRAG outperforms traditional RAG examined 9 candidates without finding overlapping work, and the multi-stage evaluation framework examined 9 candidates with the same result. These statistics suggest that within the limited search scope, the specific combination of comprehensive benchmarking, task complexity analysis, and pipeline-level evaluation appears relatively novel, though the search scale of 28 papers means substantial prior work outside this scope cannot be ruled out.
Based on the limited literature search of 28 candidates, the work appears to occupy a relatively underexplored niche within GraphRAG evaluation. The sparse population of its taxonomy leaf and absence of clearly overlapping work among examined candidates suggest potential novelty, though this assessment is constrained by the top-K semantic search methodology. A more exhaustive review of the broader RAG benchmarking literature would be needed to definitively assess originality.

### This paper presents 3 main contributions, each analyzed against relevant prior work:

### Contribution 1: GraphRAG-Bench benchmark for evaluating graph retrieval-augmented generation

Description: The authors introduce GraphRAG-Bench, a novel benchmark that systematically evaluates GraphRAG systems through tasks of increasing difficulty (fact retrieval, complex reasoning, contextual summarization, creative generation), comprehensive corpora with varying information density, and systematic evaluation across the entire pipeline from graph construction to generation.
This contribution was assessed against 10 related papers from the literature. Papers with potential prior art are analyzed in detail with textual evidence; others receive brief assessments.

### 1. Graph retrieval-augmented generation: A survey

### URL: View paper

### Brief Assessment

Graph RAG Survey[38] is a survey paper that reviews existing GraphRAG methodologies and evaluation approaches but does not introduce a new benchmark. The original paper's GraphRAG-Bench with its specific task hierarchy and systematic evaluation framework remains novel.

### 2.  Graphrag-bench:  Challenging  domain-specific  reasoning  for  evaluating  graph  retrieval-augmented

### generation

### URL: View paper

### Brief Assessment

Graphrag-bench[7]  focuses  on  domain-specific  reasoning  with  college-level  questions  requiring  multi-hop  reasoning,  mathematical computation, and programming tasks across 16 CS disciplines. The original paper's GraphRAG-Bench emphasizes hierarchical knowledge retrieval  with  tasks  of  increasing  difficulty  (fact  retrieval  to  creative  generation)  and  systematic  pipeline  evaluation.  These  are complementary benchmarks with different design philosophies and evaluation focuses, not evidence of prior work.

### 3. Ragbench: Explainable benchmark for retrieval-augmented generation systems

### URL: View paper

### Brief Assessment

Ragbench[44] focuses on evaluating general RAG systems (not specifically graph-based RAG) across retrieval and generation quality metrics  like  utilization,  relevance,  adherence,  and  completeness.  It  does  not  address  graph-structured  knowledge  retrieval  or hierarchical reasoning tasks that are central to GraphRAG-Bench's novelty.

### 4. Crud-rag: A comprehensive chinese benchmark for retrieval-augmented generation of large language models

### URL: View paper

### Brief Assessment

Crud-rag[43] focuses on evaluating traditional RAG systems across CRUD application scenarios (create, read, update, delete), not graph- based RAG systems. The benchmark does not address graph structures or GraphRAG evaluation.

### 5. Neural-Symbolic Dual-Indexing Architectures for Scalable Retrieval-Augmented Generation

### URL: View paper

### Brief Assessment

Neural-Symbolic  Dual-Indexing[39]  focuses  on  dual-indexing  architectures  for  scalable  RAG,  not  on  benchmark  development  for evaluating GraphRAG systems. The provided context contains only fragmentary mentions of benchmarks without substantive detail about benchmark construction or evaluation frameworks.

### 6. G-retriever: Retrieval-augmented generation for textual graph understanding and question answering

### URL: View paper

### Brief Assessment

G-retriever[42] introduces a GraphQA benchmark focused on textual graph understanding and question answering across scene graphs, knowledge graphs, and common sense reasoning. This differs from GraphRAG-Bench's focus on evaluating the entire GraphRAG pipeline (graph construction, retrieval, generation) with tasks of varying complexity and systematic corpus design with different information densities.

### 7. Weak-to-Strong GraphRAG: Aligning Weak Retrievers with Large Language Models for Graph-based Retrieval

### Augmented Generation

### URL: View paper

### Brief Assessment

Weak-to-Strong GraphRAG[40] focuses on aligning weak retrievers with LLMs through refined supervision signals and structure-aware reorganization, rather than proposing a comprehensive benchmark for evaluating GraphRAG systems across multiple dimensions of task complexity and pipeline stages.

### 8. Multihop-rag: Benchmarking retrieval-augmented generation for multi-hop queries

### URL: View paper

### Brief Assessment

Multihop-rag[37] focuses on multi-hop query benchmarking for RAG systems using news articles, not specifically on evaluating graph- based RAG systems with hierarchical knowledge structures and systematic pipeline evaluation as in GraphRAG-Bench.

### 9. Medical graph RAG: evidence-based medical large language model via graph retrieval-augmented generation

### URL: View paper

### Brief Assessment

Medical Graph RAG[41] focuses on developing a medical-domain GraphRAG framework with triple graph construction and U-retrieval methods, not on creating evaluation benchmarks for GraphRAG systems. The papers address fundamentally different problems.

### 10. Optimizing open-domain question answering with graph-based retrieval augmented generation

### URL: View paper

### Brief Assessment

Open-domain QA[5] focuses on benchmarking graph-based RAG systems for open-domain question answering with OLTP/OLAP query types, while the original paper introduces a comprehensive benchmark evaluating GraphRAG across hierarchical knowledge retrieval tasks with varying complexity levels (fact retrieval, complex reasoning, contextual summarization, creative generation). The candidate does not demonstrate prior work that challenges the novelty of GraphRAG-Bench's systematic evaluation framework.

### Contribution 2: Systematic investigation of when GraphRAG outperforms traditional RAG

Description: Using the GraphRAG-Bench benchmark, the authors conduct a comprehensive analysis to identify specific scenarios and conditions under which GraphRAG provides measurable benefits over vanilla RAG systems, providing practical guidelines for applying GraphRAG effectively.
This contribution was assessed against 9 related papers from the literature. Papers with potential prior art are analyzed in detail with textual evidence; others receive brief assessments.

### 1. Lightrag: Simple and fast retrieval-augmented generation

### URL: View paper

### Brief Assessment

Lightrag[45] focuses on proposing a new GraphRAG architecture with dual-level retrieval and incremental updates, not on systematically investigating when GraphRAG outperforms traditional RAG across different scenarios and conditions.

### 2. Graph retrieval-augmented generation: A survey

### URL: View paper

### Brief Assessment

Graph RAG Survey[38] provides a comprehensive overview of GraphRAG technologies but does not conduct empirical investigations comparing GraphRAG versus traditional RAG performance across different scenarios. The original paper's systematic analysis using GraphRAG-Bench to identify specific conditions remains a distinct contribution.

### 3. Knowledge graph retrieval-augmented generation for llm-based recommendation

### URL: View paper

### Brief Assessment

Knowledge  Graph  Recommendation[49]  focuses  on  knowledge  graph  retrieval  for  LLM-based  recommendation  systems,  not  on systematic comparative analysis of GraphRAG versus traditional RAG across diverse task types and scenarios.

### 4. Align-GRAG: Reasoning-Guided Dual Alignment for Graph Retrieval-Augmented Generation

### URL: View paper

### Brief Assessment

Align-GRAG[46] focuses on post-retrieval alignment techniques for graph RAG systems, specifically addressing irrelevant knowledge filtering and representation gaps between graph and language embeddings. It does not conduct systematic comparative analysis of when GraphRAG outperforms traditional RAG across varying task complexities and corpus types, which is the core contribution of the original paper.

### 5. Neural-Symbolic Dual-Indexing Architectures for Scalable Retrieval-Augmented Generation

### URL: View paper

### Brief Assessment

The candidate paper appears to focus on neural-symbolic dual-indexing architectures rather than comparative analysis of GraphRAG versus traditional RAG performance across different scenarios. No evidence in the provided context suggests systematic investigation of GraphRAG performance conditions.

### 6. From Local to Global: A Graph RAG Approach to Query-Focused Summarization

### URL: View paper

### Brief Assessment

Local  to  Global[47]  focuses  on  a  specific  GraphRAG  implementation  for  query-focused  summarization  tasks,  not  a  systematic investigation of when GraphRAG outperforms traditional RAG across diverse scenarios and conditions.

### 7. G-retriever: Retrieval-augmented generation for textual graph understanding and question answering

### URL: View paper

### Brief Assessment

G-retriever[42] primarily presents a new architecture for graph question answering rather than conducting a systematic comparative analysis  of  GraphRAG  versus  traditional  RAG  performance  across  different  scenarios  and  conditions  as  described  in  the  original contribution.

### 8. A survey of graph retrieval-augmented generation for customized large language models

### URL: View paper

### Brief Assessment

Survey Graph Retrieval[51] is a survey paper that reviews existing GraphRAG methods and their advantages over traditional RAG, but does  not  present  original  empirical  investigations  or  benchmarks  comparing  performance  conditions.  The  original  paper  conducts systematic experiments using GraphRAG-Bench to identify specific scenarios where GraphRAG provides benefits.

### 9. Simple is Effective: The Roles of Graphs and Large Language Models in Knowledge-Graph-Based Retrieval-

### Augmented Generation

### URL: View paper

### Brief Assessment

Simple is Effective[50] focuses on optimizing subgraph retrieval mechanisms for KG-based RAG rather than systematically investigating conditions under which GraphRAG outperforms traditional RAG across diverse task complexities and corpus types.

### Contribution 3: Multi-stage evaluation framework for GraphRAG pipeline

Description: The authors develop a holistic evaluation methodology that assesses GraphRAG systems at each stage of the pipeline, including graph quality metrics, retrieval performance measures, and generation accuracy, rather than treating the system as a black box focused only on final outputs.
This contribution was assessed against 9 related papers from the literature. Papers with potential prior art are analyzed in detail with textual evidence; others receive brief assessments.

### 1.  â ¦  Performance  Analysis  of  Locally  Deployed  Large  Language  Models  Through  a  Retrieval-Augmented

### Generation Educational Assistant Application for â ¦

### URL: View paper

### Brief Assessment

Educational Assistant Performance[36] focuses on evaluating locally deployed LLMs in an educational RAG application context, not on developing comprehensive multi-stage evaluation frameworks for GraphRAG systems with graph quality metrics and pipeline-specific assessments.

### 2.  Cofe-rag:  A  comprehensive  full-chain  evaluation  framework  for  retrieval-augmented  generation  with

### enhanced data diversity

### URL: View paper

### Brief Assessment

Cofe-rag[29] focuses on evaluating RAG systems (not specifically GraphRAG) across chunking, retrieval, reranking, and generation stages. The original paper's contribution is specifically about evaluating GraphRAG systems with graph-specific metrics (graph quality, graph-based retrieval), which differs from Cofe-rag[29]'s general RAG evaluation approach.

### 3. A survey on retrieval-augmented text generation for large language models

### URL: View paper

### Brief Assessment

Survey Text Generation[33] discusses evaluation frameworks for RAG systems broadly but does not present a multi-stage evaluation framework specifically designed for GraphRAG pipelines that assesses graph quality, retrieval performance, and generation accuracy at each stage as described in the original paper.

### 4. Are We on the Right Way for Assessing Document Retrieval-Augmented Generation?

### URL: View paper

### Brief Assessment

Assessing Document RAG[30] focuses on document retrieval-augmented generation with multimodal documents (PDFs, slides, HTML), not  graph-based  RAG  systems.  The  evaluation  targets  embedding  models,  MLLMs,  and  document  RAG  frameworks  rather  than GraphRAG pipeline stages (graph construction, retrieval, generation).

### 5. Adaptive-rag: Learning to adapt retrieval-augmented large language models through question complexity

### URL: View paper

### Brief Assessment

Adaptive-rag[34] focuses on adapting retrieval strategies based on query complexity for general QA tasks, not on multi-stage evaluation of GraphRAG pipelines. The paper does not address graph construction quality metrics or stage-specific evaluation of graph-based retrieval systems.

### 6. Fact, fetch, and reason: A unified evaluation of retrieval-augmented generation

### URL: View paper

### Brief Assessment

Fact  Fetch  Reason[28]  focuses  on  evaluating  retrieval-augmented  generation  systems  through  factuality,  retrieval,  and  reasoning dimensions in an end-to-end manner, but does not specifically address graph-based RAG systems or multi-stage pipeline evaluation (graph construction, retrieval, generation) as proposed in the original paper.

### 7. Evaluating retrieval quality in retrieval-augmented generation

### URL: View paper

### Brief Assessment

Evaluating  Retrieval  Quality[27]  focuses  on  evaluating  retrieval  models  within  RAG  systems  through  document-level  downstream performance metrics, not on multi-stage pipeline evaluation of GraphRAG systems that includes graph construction quality, retrieval performance, and generation accuracy assessments.

### 8. Think-then-Act: A Dual-Angle Evaluated Retrieval-Augmented Generation

### URL: View paper

### Brief Assessment

Think-then-Act[35] focuses on query assessment and model capability evaluation for retrieval-augmented generation, not on multi-stage evaluation of GraphRAG pipelines. The candidate does not address graph construction quality, retrieval performance measures specific to graph structures, or generation accuracy assessment across GraphRAG pipeline stages.

### 9. Automating systematic literature reviews with retrieval-augmented generation: a comprehensive overview

### URL: View paper

### Brief Assessment

Automating  Literature  Reviews[31]  focuses  on  RAG  applications  for  systematic  literature  reviews,  not  on  multi-stage  evaluation frameworks for GraphRAG pipelines. The paper does not address graph-based RAG evaluation methodologies.

# Appendix: Text Similarity Detection

Textual similarity detection checked 28 papers and found 5 similarity segment(s) across 2 paper(s).
The following 2 paper(s) were detected to have high textual similarity with the original paper. These may represent different versions of the same work, duplicate submissions, or papers with substantial textual overlap. Readers are advised to verify these relationships independently.

### 1. A survey of graph retrieval-augmented generation for customized large language models

### Detected in: Contribution: contribution_2

⚠ Note: This paper shows substantial textual similarity with the original paper. It may be a different version, a duplicate submission, or contain significant overlapping content. Please review carefully to determine the nature of the relationship.

### 2. In-depth Analysis of Graph-based RAG in a Unified Framework

### Detected in: Core Task (sibling)

⚠ Note: This paper shows substantial textual similarity with the original paper. It may be a different version, a duplicate submission, or contain significant overlapping content. Please review carefully to determine the nature of the relationship.

# References

[0] When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation View paper [1] Document GraphRAG: Knowledge Graph Enhanced Retrieval Augmented Generation for Document Question Answering Within the Manufacturing Domain View paper [2] In-depth Analysis of Graph-based RAG in a Unified Framework View paper [3] Frag: A flexible modular framework for retrieval-augmented generation based on knowledge graphs View paper [4] KAQG: A Knowledge-Graph-Enhanced RAG for Difficulty-Controlled Question Generation View paper [5] Optimizing open-domain question answering with graph-based retrieval augmented generation View paper [6] Adaptive Schema-aware Event Extraction with Retrieval-Augmented Generation View paper [7] Graphrag-bench: Challenging domain-specific reasoning for evaluating graph retrieval-augmented generation View paper [8] Curriculum Engineering: Structured Learning for Large Language Models (LLMs) Through Curriculum Based Retrieval View paper [9] Hyper-RAG: Combating LLM Hallucinations using Hypergraph-Driven Retrieval-Augmented Generation View paper [10] Hierarchical lexical graph for enhanced multi-hop retrieval View paper [11] Retrieval-augmented generation for exam question creation in power industry education View paper [12]  Collab-RAG:  Boosting  Retrieval-Augmented  Generation  for  Complex  Question  Answering  via  White-Box  and  Black-Box  LLM Collaboration View paper [13]  Reducing  Hallucinations  in  Medical  AI:  A  Knowledge  Graph-Augmented  Retrieval  System  for  Evidence-Based  Age-Related Macular Degeneration Information View paper [14] AdaGCRAG: Adaptive Graph-Chunk Retrieval for Lightweight RAG View paper [15] Beyond Vector Retrieval: Evaluating Graph-Enhanced RAG performance in aSystem Architecture Environment View paper [16] Benchmarking Vector, Graph and Hybrid Retrieval Augmented Generation (RAG) Pipelines for Open Radio Access Networks (ORAN) View paper [17] Enhancing Retrieval-Augmented Generation for Electric Power Industry Customer Support View paper [18] Guiding Graph-Based Retrieval Augment Generation:Guided Strategies for Enhancing Graph Structure Retrievaland Generation V iew paper [19] EchoRAG: a framework for enhancing language models with graph-RAG and in-context learning View paper [20] Hierarchical Planning for Complex Tasks with Knowledge Graph-RAG and Symbolic Verification View paper [21] NeuroPath: Neurobiology-Inspired Path Tracking and Reflection for Semantically Coherent Retrieval View paper [22] GRADE: Generating multi-hop QA and fine-gRAined Difficulty matrix for RAG Evaluation View paper [23] Beyond Static Retrieval: Opportunities and Pitfalls of Iterative Retrieval in GraphRAG View paper [24] Approaches to automatic discovery and modeling of Industrial Assets for IT/OT Integration * View paper [25] Human Cognition Inspired RAG with Knowledge Graph for Complex Problem Solving View paper [26] From Large to Small: Transferring CUDA Optimization Expertise via Reasoning Graph View paper [27] Evaluating retrieval quality in retrieval-augmented generation View paper [28] Fact, fetch, and reason: A unified evaluation of retrieval-augmented generation View paper [29] Cofe-rag: A comprehensive full-chain evaluation framework for retrieval-augmented generation with enhanced data diversity View paper [30] Are We on the Right Way for Assessing Document Retrieval-Augmented Generation? View paper [31] Automating systematic literature reviews with retrieval-augmented generation: a comprehensive overview View paper [32] Research on the online update method for retrieval-augmented generation (rag) model with incremental learning View paper • • • • • • • • • • • • • • • • • • • • • • • • • • • • • • • • • [33] A survey on retrieval-augmented text generation for large language models View paper [34] Adaptive-rag: Learning to adapt retrieval-augmented large language models through question complexity View paper [35] Think-then-Act: A Dual-Angle Evaluated Retrieval-Augmented Generation View paper [36] â ¦ Performance Analysis of Locally Deployed Large Language Models Through a Retrieval-Augmented Generation Educational Assistant Application for â ¦ View paper [37] Multihop-rag: Benchmarking retrieval-augmented generation for multi-hop queries View paper [38] Graph retrieval-augmented generation: A survey View paper [39] Neural-Symbolic Dual-Indexing Architectures for Scalable Retrieval-Augmented Generation View paper [40]  Weak-to-Strong  GraphRAG:  Aligning  Weak  Retrievers  with  Large  Language  Models  for  Graph-based  Retrieval  Augmented Generation View paper [41] Medical graph RAG: evidence-based medical large language model via graph retrieval-augmented generation View paper [42] G-retriever: Retrieval-augmented generation for textual graph understanding and question answering View paper [43] Crud-rag: A comprehensive chinese benchmark for retrieval-augmented generation of large language models View paper [44] Ragbench: Explainable benchmark for retrieval-augmented generation systems View paper [45] Lightrag: Simple and fast retrieval-augmented generation View paper [46] Align-GRAG: Reasoning-Guided Dual Alignment for Graph Retrieval-Augmented Generation View paper [47] From Local to Global: A Graph RAG Approach to Query-Focused Summarization View paper [48] E^ 2GraphRAG: Streamlining Graph-based RAG for High Efficiency and Effectiveness View paper [49] Knowledge graph retrieval-augmented generation for llm-based recommendation View paper [50] Simple is Effective: The Roles of Graphs and Large Language Models in Knowledge-Graph-Based Retrieval-Augmented Generation [51] A survey of graph retrieval-augmented generation for customized large language models View paper • • • • • • • • • • • • • • • • • • •

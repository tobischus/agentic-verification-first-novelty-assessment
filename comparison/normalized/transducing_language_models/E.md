# Assessment E

> This is one system's assessment of the paper's novelty. Several systems assessed the
> same paper; they are presented in a common wrapper so that presentation does not decide
> the comparison. The text below is each system's own, unedited and complete: it was not
> shortened, reordered or rewritten, so the systems differ in length and structure.
>
> Where a system marks verbatim quotations, they appear in quotation marks; unmarked text
> is that system's own prose.

---

**TRANSDUCING LANGUAGE MODELS**

Authors: Vésteinn Snaebjarnarson, Samuel Kiegeland, Tianyu Liu, Reda Boumasmoud, Ryan Cotterell, Tim Vieira, Eth Zürich
Publication date: 2026-03-05

## Extracted claims

### Extracted Claim 1

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

Evidence in paper:

“We formalize this perspective and introduce a general framework for language models derived from deterministic string-to-string transformations. We focus on transformations representable as finite-state transducers-a commonly used state-machine abstraction for efficient string-to-string mappings. We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs.”

✓ verbatim in paper

### Extracted Claim 2

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

Evidence in paper:

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

✓ verbatim in paper

### Extracted Claim 3

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

Evidence in paper:

“Lemma 6.1 gives sufficient conditions on a transducer that guarantee a finite decomposition for every target string, even when the underlying function is not prefix monotone. The key notion is safety: a state is safe if it is IP-universal, has finite closure (i.e., | f [s] | < ∞), or all its successors are safe.”

✓ verbatim in paper

### Extracted Claim 4

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

Evidence in paper:

“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining. Our theoretical analysis characterizes the conditions under which such mappings can be performed exactly.”

✓ verbatim in paper

## Related work examined

24 papers were compared against the claims above.

- Automata-based constraints for language model decoding — Koo et al. · 2024 — partial overlap
- Differentiable Weighted Finite-State Transducers — 2020 — partial overlap
- Efficient Guided Generation for Large Language Models — Willard et al. · 2023 — partial overlap
- From Language Models over Tokens to Language Models over Characters — Vieira et al. · 2024 — substantial overlap
- How to Compute the Probability of a Word — Pimentel et al. · 2024 — partial overlap
- Language Models over Canonical Byte-Pair Encodings — Vieira et al. · 2025 — substantial overlap
- Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Oh et al. · 2024 — partial overlap
- Neural Finite-State Transducers: Beyond Rational Relations — Lin et al. · 2019 — partial overlap
- Neural Grammatical Error Correction with Finite State Transducers — Stahlberg et al. · 2019 — partial overlap
- Sampling from Your Language Model One Byte at a Time — Hayase et al. · 2025 — substantial overlap
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Lew et al. · 2023 — partial overlap
- Understanding and Mitigating Tokenization Bias in Language Models — Phan et al. · 2024 — substantial overlap
- Weighting Finite-State Transductions With Neural Context — Rastogi et al. · 2016 — partial overlap
- Where is the signal in tokenization space? — Geh et al. · 2024 — partial overlap
- Analyzing Cognitive Plausibility of Subword Tokenization — Beinborn et al. · 2023
- Effect of tokenization on transformers for biological sequences — Dotan et al. · 2023
- Effective Large Language Model Adaptation for Improved Grounding and Citation Generation — 2023
- Formalizing BPE Tokenization — Berglund et al. · 2023
- Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — 2019
- Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA — Qiao et al. · 2024
- Neural Machine Translation of Rare Words with Subword Units — Sennrich et al. · 2015
- Speech Recognition using Weighted Finite-State Transducers — 2022
- SQL-PaLM: Improved Large Language Model Adaptation for Text-to-SQL (extended) — 2023
- Syntactic Control of Language Models by Posterior Inference — Xefteri et al. · 2025

## Review

### Overall assessment

Within the examined literature, the submission presents a mix of genuinely novel and challenged contributions. The general framework for transduced language models (Claim 1) and the theoretical results on sufficient transducer-level conditions for finite prefix decompositions (Claim 3) are not challenged by any prior work, with the closest related papers only partially overlapping and lacking the submission's generality and theoretical depth. However, the core algorithmic contributions for composing language models with FSTs and marginalizing over source strings (Claim 2) are substantially present in prior works such as "Language Models over Canonical Byte-Pair Encodings," "From Language Models over Tokens to Language Models over Characters," and "Understanding and Mitigating Tokenization Bias in Language Models." The submission does extend these ideas to arbitrary FSTs and introduces new algorithmic techniques, but the main idea is not novel. Similarly, the demonstration of inference-time adaptation to new output units (Claim 4) is substantially covered for character/byte adaptation by "From Language Models over Tokens to Language Models over Characters," though the submission generalizes to additional domains like words and amino acids. Overall, the submission's primary novelty lies in its generalization to arbitrary FST-based transformations and the associated theoretical guarantees, while its core algorithmic and adaptation mechanisms are challenged by prior work in the context of tokenization and character-level adaptation.

---

### First extracted claim

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

**Verdict:** not challenged in the examined literature

The claim is not challenged by any examined prior work. The closest examined prior works, such as "Automata-based constraints for language model decoding," "Neural Finite-State Transducers: Beyond Rational Relations," and "From Language Models over Tokens to Language Models over Characters," all share partial overlap with the submission in their use of finite-state transducers (FSTs) and composition with language models. However, each is limited in scope: for example, they focus on specific applications like detokenization, canonicalization, or neural scoring, and do not present a general framework for arbitrary deterministic string-to-string transformations or the associated algorithms for marginalization and autoregressive modeling as claimed by the submission. The evidence is strong, as it is based on full-text comparisons and detailed, verified overlap analysis. Therefore, the novelty of this general framework holds within the examined literature.

#### Overlapping prior work

##### Automata-based constraints for language model decoding
partial overlap · Koo et al. · 2024

How this paper realizes the claim

The paper presents a framework for constraining language model (LM) decoding to formal languages using automata theory, specifically finite-state automata (FSAs), finite-state transducers (FSTs), and push-down automata (PDAs).

“Our main contributions are primarily conceptual rather than empirical: 1. Identify an as-yet unnoticed connection between detokenization and transduction. 2. Solve the tokenization issues using this connection and operations on automata. 3. Define extensions that address practical problems of efficiency and convenience. ∗Equal contribution, alphabetical.”

The paper introduces the use of FSTs to model detokenization as a string-to-string transformation, and composes these FSTs with FSAs or PDAs representing formal language constraints, enabling the LM to generate only valid outputs according to the constraints.

Quoted from the source but NOT confirmed verbatim:
Our first contribution is a reformulation of detokenization (i.e., the process of converting token sequences back into text) as an FST, using the following construction: ... For compactness, common prefixes of the chains can be merged to form a trie-like structure, as in Figure 4; see Appendix B.1 for a proof of correctness.

The framework is general in that it allows any regular or deterministic context-free language constraint to be composed with the LM via FSTs, and the FSTs are used to bridge between token sequences and character-level constraints.

“This clean decomposition is only possible because FST-FSA composition provides a fast, automatic, and general method for joining the two halves. For example, alternative detokenization automata (see Section 4.3) can be slotted into TV without changing the rest of the system. Similarly, alternative constraint automata (see Section 3.1) can be substituted for AR and FST composition still works. 2.5 ## Extensions Our last contribution in this section is a set of regular expression extensions, written as specially-named capturing groups, that greatly increase the efficiency and expressiveness of the system.”

However, the paper does not introduce a general framework for transforming arbitrary language models with arbitrary deterministic string-to-string transformations represented by FSTs. Rather, it focuses on using FSTs for detokenization and for adapting formal language constraints to the LM's tokenization.

Comparison with the submission

This paper introduces the use of FSTs to model detokenization and to adapt formal language constraints to the tokenization of language models, composing these with FSAs or PDAs to constrain LM outputs. While it shares the use of FSTs and composition with LMs, its scope is limited to detokenization and constraint adaptation, not to arbitrary deterministic string-to-string transformations of language models as a general framework. The submission's contribution is broader and more general, including algorithms for marginalization and autoregressive modeling, which are not present here. Thus, the overlap is partial, and the prior paper cannot refute the submission's claim.

##### Neural Finite-State Transducers: Beyond Rational Relations
partial overlap · Lin et al. · 2019

How this paper realizes the claim

The paper introduces neural finite state transducers (NFSTs), which are models that define joint and conditional probability distributions over pairs of strings using a finite-state transducer structure. The probability of a string pair is computed by marginalizing over all accepting paths in the FST, with each path scored by a neural network rather than fixed weights. The paper presents algorithms for training and inference for these models and demonstrates their effectiveness on transduction tasks.

“We introduce neural finite state transducers (NFSTs), a family of string transduction models defining joint and conditional probability distributions over pairs of strings. The probability of a string pair is obtained by marginalizing over all its accepting paths in a finite state transducer. In contrast to ordinary weighted FSTs, however, each path is scored using an arbitrary function such as a recurrent neural network, which breaks the usual conditional independence assumption (Markov property).”

Comparison with the submission

The prior paper and the submission both use finite-state transducers to define probabilistic models over string pairs, and both involve marginalization over possible paths or source strings. However, the prior paper's main contribution is the introduction of neural finite-state transducers, where each path is scored by a neural network, and the focus is on joint and conditional modeling of string pairs. The submission, in contrast, introduces a general framework for transforming language models using deterministic FSTs, with a focus on composing a language model with a deterministic transformation and developing algorithms for efficient marginalization and autoregressive prediction. Thus, the overlap is partial: the prior paper covers some of the same ground in using FSTs for probabilistic modeling, but does not present the same framework or algorithms as the submission.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper addresses the problem of converting token-level language models (LMs) into character-level LMs, motivated by practical issues such as the prompt boundary problem. It formalizes the process of generating character strings from a token-level LM using a decoding function (often deterministic) and provides algorithms for computing the probability of character strings and their prefixes under the induced character-level distribution.

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms. In the empirical portion of the paper, we benchmark the practical runtime and approximation quality.”

The core technical contribution is the development of efficient algorithms to compute the probability of a character string (or prefix) under the induced character-level model, by summing over all token strings that decode to the given character string (or have it as a prefix). The paper introduces the notion of a 'covering' to efficiently enumerate these token strings and provides both exact and approximate methods for this computation.

“Our method finds a set of token strings that form a covering, a key technical concept we introduce in this paper. We will provide the precise definition in due course; for now, we will illustrate the covering of Hello,␣worl: 5The misspelling is a testament to the extent to which the tokenized prompt is out-of-distribution.”

The algorithms are developed for the case where the decoding function is strict-prefix monotone (e.g., BPE or WordPiece), which allows the infinite sum over token strings to be reduced to a finite computation. The paper does not generalize to arbitrary string-to-string transformations, but focuses on the specific case of tokenization/decoding functions used in language modeling.

Comparison with the submission

This prior paper presents a specific instance of the claimed framework: composing a token-level language model with a deterministic decoding function to obtain a character-level model, and provides efficient algorithms for this case. However, it does not introduce a general framework for arbitrary deterministic string-to-string transformations via FSTs, nor does it provide algorithms for the general case. The submission extends the idea to a much broader class of transformations and formalizes the general framework, representing a significant delta beyond this prior work. The overlap is partial: the prior paper covers a special case, but not the general contribution claimed by the submission.

##### Neural Grammatical Error Correction with Finite State Transducers
partial overlap · Stahlberg et al. · 2019

How this paper realizes the claim

This paper presents a method for grammatical error correction (GEC) that uses finite-state transducers (FSTs) to construct and constrain the hypothesis space of possible corrections. The FSTs are used to represent possible edits (confusion sets, edit operations) and to compose these with input sentences or SMT lattices, creating a structured search space for corrections.

“In this paper, we propose to construct a hypothesis space using standard FST operations like composition, and then constrain the output of a neural GEC system to that space. We study two different scenarios: In the ﬁrst scenario, we do not have access to annotated training data, and only use a small development set for tuning.”

The paper further composes this FST-based hypothesis space with language models (both count-based and neural LMs), and uses the composed structure to rescore and constrain the outputs of neural models. The FSTs are used to encode possible string-to-string transformations (edits), but these are not arbitrary deterministic functions; rather, they are based on confusion sets and edit operations relevant to GEC.

“We make extensive use of the FST operations available in OpenFST (Allauzen et al., 2007) like composition (denoted with the ◦-operator) and projection (denoted with Πinput(·) and Πoutput(·)) to build H. The process starts with an input lattice I.”

The language model is composed with the FST to score hypotheses, but the framework is not presented as a general method for transforming arbitrary language models with arbitrary deterministic string-to-string FSTs. Instead, the FSTs are used to encode specific edit operations for GEC, and the language model is used to rescore the resulting hypotheses.

Quoted from the source but NOT confirmed verbatim:
To incorporate word-level language model scores we train a 5-gram count-based LM ... and convert it to an FST L using the OpenGrm NGram Library ... Our combined word-level scores can be expressed with the following transducer: Hword = B ◦P ◦L.

The paper does not introduce a general framework for transduced language models as a composition of a language model with an arbitrary deterministic FST, nor does it provide algorithms for marginalizing over all source strings mapping to a given target prefix in the general sense. Its use of FSTs is specific to the GEC task and the structure of the edits/confusion sets.

Comparison with the submission

This prior paper uses FSTs to encode edit operations and confusion sets for grammatical error correction, and composes these with language models to constrain and rescore hypotheses. However, its use of FSTs is specific to the GEC task and does not constitute a general framework for transforming language models with arbitrary deterministic FSTs. The submission's contribution is broader and more general, providing a framework and algorithms for composing any language model with any deterministic FST. Thus, the overlap is partial: the prior paper shares the idea of composing FSTs with LMs, but not the generality or the full framework of the submission.

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper addresses the problem of language models assigning probability mass to noncanonical token strings under deterministic tokenization schemes such as byte-pair encoding (BPE). It proposes methods to ensure that only canonical token strings (those produced by the tokenizer) are assigned positive probability.

“We present two approaches: (1) canonicality by conditioning, leveraging test-time inference strategies without additional training, and (2) canonicality by construction, a model parameterization that guarantees canonical outputs but requires training. We demonstrate that fixing canonicality mistakes improves the likelihood of held-out data for several models and corpora.”

The paper formalizes the tokenization process as a pair of deterministic functions (encoding and decoding), and defines the tokenized language model as the marginalization of a token-level model over all token strings that decode to a given character string.

“A tokenized language model is a language model pΣ over character strings Σ∗that is parameterized by a tokenlevel language model p∆over ∆∗and a decoding function κ: ∆∗→Σ∗. The tokenized language model defines the following probability distribution over Σ∗: pΣ(σ) def= X δ∈∆∗ 1{σ = κ(δ)} p∆(δ) (2) Notice that τ is conspicuously absent from this expression, as it is only part of the estimation process, which we characterize below.”

The paper develops algorithms for enforcing canonicality, including exact and approximate inference methods for sampling only canonical token strings, and analyzes their theoretical properties.

“We describe two families of methods for doing so • Canonicality by conditioning: We explore efficient testtime inference methods for conditionally generating text that satisfies the canonicality constraint without retraining. • Canonicality by construction: We explore methods that impose canonicality constraints directly in the language model’s parameterized architecture and give a method to fine-tune its parameters. In addition to these novel methods, this paper presents the following contributions: • We prove that our methods can only improve the fit to the true distribution over tokens.”

The paper discusses the use of finite-state automata for efficient membership tests in the set of canonical token strings and their prefixes, but does not generalize to arbitrary string-to-string transductions beyond tokenization.

Comparison with the submission

This prior paper presents a framework for composing language models with deterministic tokenization functions (such as BPE), and develops algorithms for enforcing canonicality by conditioning or construction. However, its scope is limited to tokenization and canonicalization, and does not introduce a general framework for arbitrary deterministic string-to-string transformations via finite-state transducers. The submission extends the idea to a broader class of transformations and provides a more general theoretical and algorithmic treatment. Thus, the overlap is partial: the prior paper covers a special case of the submission's framework, but not the general case.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper studies the bias introduced by tokenization in language models and proposes algorithms to correct this bias, allowing a tokenized language model to simulate token-free behavior. The main technical contribution is the Maximum Prefix Correction (MPC) algorithm, which marginalizes over possible tokenizations to recover character-level probabilities from a model trained on tokenized data.

“we propose a novel algorithm to obtain unbiased estimates from any language model trained on tokenized data. Our methods do not require finetuning the model, and the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE. As a result, we show that one can simulate token-free behavior from a tokenized language model. We empirically verify the correctness of our method through a Markov-chain setup, where it accurately recovers the transition probabilities, as opposed to the conventional method of directly prompting tokens into the language model.”

“We present two novel algorithms to correct this bias for MPE and Byte-Pair-Encoding (BPE) respectively. Due to space limit, the analysis and algorithm for BPE are presented in Appendix H.”

“We present the MPC algorithm in Algorithm 1, that allows us to compute the probabilities P(xN nk+1|tk 1) and P(xn nk+1|tk 1) in Equation (1). Note that this algorithm does not require tk∈V∗. Details on the algorithmic correctness are shown in Appendix E. 3Many current language models begins with a start token <start> in V∗, e.g.”

“The idea is to marginalize out P(xN nk+1|tk 1) by considering two complementary events: when the next token tk+1 has a prefix xN nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN nk+1 (pval in the Pass Step). Formally, MPC computes the following probabilities: bval = P(xN nk+1, tk+1 ∈B(xN nk+1)) tk 1), (2) pval = P(xN nk+1, tk+1 /∈B(xN nk+1)) tk 1), (3) where B(xN nk+1)={t∈V|xN nk+1∈prefix(decode(t))} and we immediately see that P(xN nk+1|tk 1)=bval+pval.”

Comparison with the submission

The prior paper and the claim both address the problem of transforming language models via deterministic string-to-string mappings and marginalizing over possible source strings. However, the prior paper is focused specifically on tokenization schemes (MPE/BPE) and provides algorithms tailored to those cases, whereas the submission claims a general framework for arbitrary deterministic FST-based transformations. Thus, the overlap is partial: the prior paper covers a special case of the submission's general framework but does not subsume it. The submission's generality and formalization of transduced language models as FST compositions is not present in the prior work.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, a method for converting any autoregressive language model with a BPE tokenizer into a character-level or byte-level language model at inference time. The core mechanism is the Valid Covering Tree (VCT), which represents all valid token sequences that cover a given byte prefix. This enables the computation of prefix probabilities, sampling completions, and next-byte distributions, all while preserving the original model's output distribution (up to invalid token sequences). The VCT is constructed and updated efficiently, allowing for practical byte-level sampling and solving the prompt boundary problem.

Quoted from the source but NOT confirmed verbatim:
In this paper, we propose ByteSampler, a system that can condition LMs on arbitrary byte-prefixes. This can be used to solve the PBP and can also be applied to convert the (tokenized) LM into a byte-level LM.

“The VCT T for a given a byte-string S can be used to efficiently perform various byte-level language modeling tasks. We use “ByteSampler” to refer to this collection of routines. prefix: h y p o t ?”

“To compute the probability of S (as a prefix) under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of T. ## 2.”

“To sample a completion of S while avoiding the PBP, we compute the probability (as above) of every leaf in T and sample one of them accordingly. We are then free to continue sampling a continuation from that leaf using normal token-level sampling because sampled tokens induce token boundaries selected by the model. This one-time operation can be used to solve the PBP without paying the cost of byte-level sampling.”

“To compute the next byte distribution following S, we group the leaves of T by their corresponding next byte and sum the probabilities of the leaves in each group, as illustrated in Fig. 3. By repeatedly sampling from this distribution, we can generate text one byte at a time. Naturally, this will generate text more slowly than sampling at the token level.”

Comparison with the submission

This prior paper introduces a method (ByteSampler) that transforms a token-level language model into a byte-level model by marginalizing over valid tokenizations using the Valid Covering Tree, which is a deterministic structure akin to a finite-state machine. However, the scope is limited to the specific case of BPE tokenization and byte-level outputs, and the framework is not presented as a general composition with arbitrary deterministic string-to-string functions or general FSTs. The submission's contribution is broader, providing a general and formal framework for composing language models with any deterministic FST, not just for tokenization. Thus, the overlap is partial: the prior paper covers a special case of the submission's general framework, but does not subsume it.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

This paper addresses the problem of computing the probability of a word given a context using language models that operate over subwords, particularly focusing on the technicalities introduced by different tokenization schemes (end-of-word and beginning-of-word markers).

“This paper derives the correct methods for computing word probabilities, highlighting issues when relying on language models that use beginning-of-word (bow)-marking tokenisers, e.g., the GPT family. Empirically, we show that correcting the widespread bug in probability computations affects measured outcomes in sentence comprehension and lexical optimisation analyses.”

The paper formalizes the mapping between words and subwords, and shows how to marginalize over subword sequences to recover word-level probabilities, providing explicit formulas and theorems for both eow and bow tokenizers.

“We can compute our desired conditional distribution as the quotient of two evaluations of PW: p(w | w<t) = PW(w<t ◦w ◦W∗) / PW(w<t ◦W∗)”

“Eq. (7) suggests a way to extract probabilities over words from a language model; we can simply use the equivalence: p(w) = p(s), for s = S_{W^*→S^*}(w)”

The paper does not introduce a general framework for transforming language models with arbitrary deterministic string-to-string transformations represented by finite-state transducers. Rather, it focuses on the specific case of mapping between subword and word representations as determined by tokenizers, and how to correctly marginalize probabilities in this context.

Comparison with the submission

The prior paper provides a rigorous treatment of how to compute word probabilities from subword-based language models, including marginalization over subword sequences and handling of different tokenization schemes. However, it is limited to the specific transformation induced by tokenization/detokenization, and does not propose a general framework for arbitrary FST-based transformations of language models. The submission extends this idea to a much broader class of deterministic string-to-string functions, providing a general and flexible framework. Thus, the overlap is partial: the prior paper covers a special case, but not the general contribution claimed by the submission.

---

### Second extracted claim

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

**Verdict:** challenged by prior work

This claim is challenged by several prior works, most notably "Language Models over Canonical Byte-Pair Encodings," "From Language Models over Tokens to Language Models over Characters," and "Understanding and Mitigating Tokenization Bias in Language Models." These papers, as verified by both-sides quotes, present algorithms for composing language models with finite-state transducers (typically tokenizers or decoders), marginalizing over source strings to compute probabilities for target outputs, enabling conditioning on transformed outputs, and supporting exact or approximate inference without changing model parameters. The overlap is substantial, as the core technical content of the claim is present in these prior works. However, the submission appears to generalize these algorithms to arbitrary FST-defined string transformations (not just tokenization), and introduces new algorithmic techniques such as the precover decomposition and breadth-first search for efficient computation, which are not present in the challenging papers. Thus, while the main idea is not novel, the submission's generalization and algorithmic refinements represent a delta beyond the prior work.

#### Overlapping prior work

##### Neural Finite-State Transducers: Beyond Rational Relations
partial overlap · Lin et al. · 2019

How this paper realizes the claim

The paper introduces neural finite state transducers (NFSTs), which are models that define joint and conditional probability distributions over string pairs by marginalizing over all accepting paths in a finite-state transducer. The scoring of each path can use an arbitrary function, such as a recurrent neural network, rather than being limited to Markovian weights. The paper presents training and inference algorithms for these models, including both locally and globally normalized variants.

“We introduce neural finite state transducers (NFSTs), a family of string transduction models defining joint and conditional probability distributions over pairs of strings. The probability of a string pair is obtained by marginalizing over all its accepting paths in a finite state transducer. In contrast to ordinary weighted FSTs, however, each path is scored using an arbitrary function such as a recurrent neural network, which breaks the usual conditional independence assumption (Markov property).”

“We present training and inference algorithms for locally and globally normalized variants of NFSTs. In experiments on different transduction tasks, they compete favorably against seq2seq models while offering interpretable paths that correspond to hard monotonic alignments.”

Comparison with the submission

The prior paper and the submission both address string transduction with finite-state transducers and marginalization over possible paths or string pairs. However, the prior paper's main contribution is the introduction of neural finite-state transducers as a new model class, with neural scoring of paths, and does not focus on composing with a fixed pretrained language model or on the specific algorithms for marginalizing source-string probabilities into target outputs as in the submission. Thus, there is partial overlap in the general area and some methods, but the submission's contribution is distinct and not refuted by this prior work.

##### Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs
partial overlap · Lew et al. · 2023

How this paper realizes the claim

The paper proposes Sequential Monte Carlo (SMC) steering as an inference-time method for enforcing constraints on large language models (LLMs) by framing generation as posterior inference in probabilistic programs. It introduces Feynman-Kac Transformer models, which allow the composition of LLMs with various constraints and transformations, and describes how to specify these as probabilistic programs using the LLaMPPL library.

“The key idea is to specify language generation tasks as posterior inference problems in a class of discrete probabilistic sequence models, and replace standard decoding with sequential Monte Carlo inference. For a computational cost similar to that of beam search, SMC can steer LLMs to solve diverse tasks, including infilling, generation under syntactic constraints, and prompt intersection.”

“We make three key contributions: 1. The class of Feynman-Kac Transformer models (§2), probabilistic models over Transformer token sequences that are amenable to SMC and can encode a variety of language generation tasks. 2. SMC Transformer steering (§3), a variant of SMC specialized for Feynman-Kac Transformer models. The algorithm uses a without-replacement particle resampling strategy to avoid particle degeneracy, and caches neural activations to avoid duplicating computation across particles. 3. The LLaMPPL library for building Feynman-Kac Transformer models as probabilistic programs that invoke LLaMA Transformers [Touvron et al., 2023], and automating SMC steering.”

The paper gives several examples of constraints and transformations, such as hard constraints, infilling, and prompt intersection, all implemented as probabilistic programs that define a posterior over output strings. The SMC algorithm is used to sample from these posteriors, approximating the desired conditional distributions.

“Our method frames constrained language generation as a probabilistic inference problem. This perspective is commonly adopted in the literature [see, e.g., Kumar et al., 2022, Poesia et al., 2022, Miao et al., 2019, Qin et al., 2022], and has several distinctive features compared to popular heuristic and optimization-based approaches to inference-time constrained generation: • Global vs.”

Quoted from the source but NOT confirmed verbatim:
A Feynman-Kac Transformer model is a tuple (s0, {Mt}t≥1, {Gt}t≥1), where: ... Mt(st | st−1, fθ) is a Markov kernel (i.e., conditional probability distribution) from st−1 ∈Fc to st ∈S, parameterized by a Transformer network fθ ... Gt(st−1, st, fθ) is a potential function, mapping a pair (st−1, st) ∈Fc × S to a real-valued non-negative score.

The approach does not require changing the parameters of the underlying language model; instead, it composes the model with constraints or transformations at inference time.

Quoted from the source but NOT confirmed verbatim:
This perspective is commonly adopted in the literature ... and has several distinctive features compared to popular heuristic and optimization-based approaches to inference-time constrained generation: • Global vs. local constraint following. ... By contrast, conditioning the LLM on the constraint causes global reallocation of probability mass, yielding a posterior that upweights early tokens which make it easier to satisfy the constraint later. By targeting this posterior, SMC steering avoids greedy dead ends.

The paper does not explicitly describe the use of finite-state transducers (FSTs) as the mechanism for string transformations, nor does it present algorithms for marginalizing source-string probabilities into target outputs via FST composition. Instead, it uses probabilistic programs and potential functions to encode constraints and transformations.

Comparison with the submission

This prior paper and the submission both address inference-time conditioning of language models on constraints or transformations, and both support approximate inference without changing model parameters. However, the prior paper does not use finite-state transducers or develop algorithms for marginalizing source-string probabilities into target outputs via FST composition. Instead, it uses a general probabilistic programming approach with SMC. Thus, the overlap is partial: the high-level goal is similar, but the technical approach and specific algorithms are different, and the submission's FST-based marginalization is not present in the prior work.

##### Differentiable Weighted Finite-State Transducers
partial overlap · 2020

How this paper realizes the claim

The paper introduces a framework for automatic differentiation with weighted finite-state transducers (WFSTs), enabling their use at training time within deep learning models. It provides a set of differentiable operations on WFSTs, including composition, intersection, and forward scoring, and demonstrates how these can be used to construct and optimize sequence-level loss functions such as ASG and CTC.

“We develop a framework for automatic differentiation through operations on WFSTs. We show the utility of this framework by leveraging it to design and experiment with existing and novel learning algorithms. Automata are a more convenient structure than tensors to encode prior knowledge into a learning algorithm.”

The framework allows for the composition of WFSTs representing different components (e.g., emissions, transitions, lexicons) and supports marginalization over latent structures, such as word piece decompositions, by composing a lexicon transducer with a label graph and marginalizing over all decompositions.

Quoted from the source but NOT confirmed verbatim:
The word piece decomposition for a given phrase is not important, serving only as a stepping stone to more accurate models. This assumption can be made explicit by marginalizing over the set of decompositions for a target label while training the task specific model. ... In the differentiable WFST framework this can be implemented in a plug-and-play fashion by incorporating a single lexicon graph. The lexicon transducer L, which maps sequences of sub-word tokens to graphemes, is the closure of the union of the individual sub-word-to-grapheme graphs. A composition with the label graph, L ◦Y, gives the decomposition graph for the label y.

The framework is designed to allow gradients to flow through all WFST operations, so that model parameters can be updated via backpropagation. The paper demonstrates the use of these algorithms in handwriting and speech recognition tasks, including marginalization over latent decompositions and the use of WFSTs as neural network layers.

Comparison with the submission

The prior paper presents a differentiable WFST framework that enables composition and marginalization over latent structures, such as word piece decompositions, and supports learning with these structures in end-to-end models. However, it does not present the specific algorithms for marginalizing source-string probabilities into target outputs via FST composition, nor does it focus on conditioning on transformed outputs or provide the exact/approximate inference algorithms described in the submission. Thus, while there is partial overlap in the use of FST composition and marginalization, the submission provides a distinct and more specialized contribution.

##### Automata-based constraints for language model decoding
partial overlap · Koo et al. · 2024

How this paper realizes the claim

The paper presents a method for constraining language model (LM) decoding to outputs that conform to a formal language, such as those defined by regular expressions or context-free grammars. The core technical contribution is to represent detokenization as a finite-state transducer (FST), and then compose this FST with a finite-state automaton (FSA) or pushdown automaton (PDA) representing the constraint. This composition yields a new automaton that accepts only token sequences whose detokenized forms are in the target language.

“Our main contributions are primarily conceptual rather than empirical: 1. Identify an as-yet unnoticed connection between detokenization and transduction. 2. Solve the tokenization issues using this connection and operations on automata. 3. Define extensions that address practical problems of efficiency and convenience. ∗Equal contribution, alphabetical.”

“Algorithm 2 Constrains LM L with vocabulary V to generate the language of regex R TV ←BUILDDETOKENIZINGFST(V) ▷token-to-character FST, see Algorithm 1 AR ←BUILDREGEXFSA(R) ▷character-accepting FSA (Thompson, 1968) AR◦V ←DETERMINIZE(AR ◦TV) ▷token-accepting FSA q ←IR◦V ▷start from initial FSA state for t = 1 to T do ▷decoding steps ℓ←COMPUTELOGITS(L) A ←{eσ : e ∈ER◦V ∧es = q} ▷allowed next tokens for i = 1 to |V| do ▷penalize logits as in Deutsch et al. (2019) if vi ̸∈A then ℓi ←−∞ ˆv ←SAMPLENEXTTOKEN(L, ℓ) ˆe ←e s.t. e ∈ER◦V ∧es = q ∧eσ = ˆv ▷find the matching edge q ←ˆet ▷traverse the edge Note that AR◦V is a closed-form solution: it expresses R using all relevant tokens from V and can be executed independently from both.”

“This clean decomposition is only possible because FST-FSA composition provides a fast, automatic, and general method for joining the two halves. For example, alternative detokenization automata (see Section 4.3) can be slotted into TV without changing the rest of the system. Similarly, alternative constraint automata (see Section 3.1) can be substituted for AR and FST composition still works. 2.5 ## Extensions Our last contribution in this section is a set of regular expression extensions, written as specially-named capturing groups, that greatly increase the efficiency and expressiveness of the system.”

The paper does not describe marginalizing source-string probabilities into target outputs, nor does it provide algorithms for computing the probability of a target string by summing over all source strings that map to it under the FST. The focus is on constraining generation to valid outputs, not on marginalization or transformed-output conditioning. The algorithms described operate by masking logits during decoding, not by changing the probability computation or supporting exact/approximate inference over transformed outputs.

Comparison with the submission

This paper and the submission both use FST composition to connect language models with formal constraints or transformations. However, this paper focuses on constraining the output of the LM to a formal language by masking logits, not on marginalizing probabilities or conditioning on transformed outputs. The submission's contribution of marginalizing over source strings and supporting inference over transformed outputs is not present in this paper. Thus, the overlap is partial: the core idea of FST composition is shared, but the submission's probabilistic marginalization and inference algorithms are novel relative to this work.

##### Language Models over Canonical Byte-Pair Encodings
substantial overlap · Vieira et al. · 2025

How this paper realizes the claim

This paper addresses the problem of language models assigning probability mass to noncanonical tokenizations under deterministic tokenizers like BPE. It proposes methods to enforce that only canonical token strings are assigned positive probability, using both test-time conditioning and model parameterization.

“We present two approaches: (1) canonicality by conditioning, leveraging test-time inference strategies without additional training, and (2) canonicality by construction, a model parameterization that guarantees canonical outputs but requires training. We demonstrate that fixing canonicality mistakes improves the likelihood of held-out data for several models and corpora.”

The 'canonicality by conditioning' approach involves conditioning the language model's output on the event that the generated token string is canonical, which is implemented via probabilistic conditioning and does not require changing model parameters.

“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition 1.”

The paper develops both exact (rejection sampling) and approximate (local canonicalization, importance sampling) inference algorithms to sample or compute probabilities under this conditioned model, all without modifying the underlying language model parameters.

Quoted from the source but NOT confirmed verbatim:
The simplest exact conditioning algorithm for sampling from g is rejection sampling: ... if δ ∈D: return δ ... Another correct sampling algorithm is ancestral sampling ... Unfortunately, computing −→g exactly is intractable as it requires summing over infinitely many future strings. Thus, −→g must be approximated. In §3.2.2, we will provide a cheap, local approximation and, in §3.2.3, we will devise a strategy for improving the short-sightedness of the local approximation by using more computation.

The methods are described for the specific case of enforcing canonicality under a deterministic tokenizer (such as BPE), where the transformation from source (character) strings to target (token) strings is deterministic and invertible. The algorithms marginalize over token strings that decode to a given character string, and enable conditioning on canonical outputs.

Comparison with the submission

This prior paper presents algorithms for composing language models with deterministic tokenizers (viewed as FSTs), conditioning on canonical outputs, and performing exact or approximate inference without changing model parameters. The overlap is substantial, as the core idea of marginalizing over source strings that map to a target via an FST and conditioning on transformed outputs is present. However, the submission extends these ideas to arbitrary FST-defined transformations and introduces new algorithmic techniques for efficiently representing and computing the relevant sets, which are not covered in this paper. Thus, while the contributions are closely related, the submission has a clear delta in generality and algorithmic novelty.

##### Where is the signal in tokenization space?
partial overlap · Geh et al. · 2024

How this paper realizes the claim

This paper investigates the problem of non-canonical tokenizations in language models, specifically focusing on the fact that a string can be tokenized in multiple ways, and that the probability of a string under a language model is the sum (marginalization) over all possible tokenizations.

“We prove that, given a string, it is computationally hard to find the most likely tokenization for an autoregressive LLM, as well as to compute the marginal probability over all possible tokenizations. We then show how the marginal is, in most cases, indistinguishable from the canonical probability.”

The paper formalizes the marginalization problem, proves it is #P-hard, and develops an importance sampling estimator to approximate the marginal probability of a string by aggregating over all tokenizations.

“Hence, we implement an importance sampling estimator for the marginal probability. Surprisingly, despite the extremely large number of non-canonical tokenizations, we empirically find that the estimated marginal probability is usually very close to the canonical tokenization’s probability.”

The paper empirically evaluates the difference between canonical and marginal probabilities, and shows that in most cases, the canonical probability is very close to the marginal. It also explores whether aggregating over tokenizations provides additional signal for downstream tasks.

“Specifically, we show that for Gemma-2B (Gemma Team et al., 2024), Llama2-7B (Touvron et al., 2023) and Mamba-130M (Gu and Dao, 2024), by employing ensemble strategies for weighting different tokenizations at inference time, we achieve significant performance improvements on challenging LLM evaluation benchmarks. Contributions.”

The algorithms developed operate over the space of tokenizations (as defined by the vocabulary and merge rules), and use data structures like Multi-valued Decision Diagrams (MDDs) to represent all tokenizations of a string. The focus is on marginalizing over tokenizations for a fixed string, not on arbitrary FST-defined string transformations.

Comparison with the submission

This prior paper addresses the problem of marginalizing language model probabilities over all possible tokenizations of a string, which is a special case of composing a language model with a finite-state transducer (the tokenizer). It develops both theoretical results and practical algorithms for this marginalization, but only for the case where the FST represents tokenization ambiguity. The submission claims a more general framework for arbitrary FST-defined transformations, enabling conditioning on transformed outputs and supporting both exact and approximate inference. Thus, the overlap is partial: the prior paper covers a special case, but not the full generality or algorithmic contributions of the submission.

##### Weighting Finite-State Transductions With Neural Context
partial overlap · Rastogi et al. · 2016

How this paper realizes the claim

The paper proposes a hybrid model that combines finite-state transducers (FSTs) with neural network-based context features for sequence-to-sequence tasks such as morphological reinflection and lemmatization. The approach begins with a hand-specified FST that defines possible edits from input to output strings. The FST is composed with an input string to produce a lattice (G) representing all possible output strings and their alignments.

“Our novel architecture allows efﬁcient modeling of globally normalized probability distributions over string-valued output spaces, simultaneously with automatic feature extraction. We evaluate on morphological reinﬂection and lemmatization tasks, showing that our approach strongly outperforms a standard WFST baseline as well as neural sequence-tosequence models with attention.”

The model assigns weights to arcs in the composed FST G using features extracted by a stack of bidirectional LSTMs over the input string. The probability of an output string y given input x, p(y|x), is defined as the sum over all paths in G that align x to y, with path weights determined by the neural features and FST structure.

“Recall that p(y∗| x) sums over all alignments. As explained by Eisner (2002), it can be computed as the pathsum of the composition G ◦y∗(Figure 4), divided by the pathsum of G (which gives the normalizing constant for the distribution p(y | x)). The pathsum of a weighted FST is the total weight of all paths from the initial state to a ﬁnal state, and can be computed by the forward algorithm.4 3Our present implementation handles INS edits (for which j = i) a bit differently, using (exi+1, γi:i+1, exi, exi+2) rather than (eε, γi:i, exi, exi+1).”

Inference is performed by constructing the weighted FST G for a given input x, and then either finding the most probable path (Viterbi) or summing over all paths for marginal probabilities. The model supports exact inference via dynamic programming, and the FST structure is not changed during inference; only the arc weights are parameterized by the neural network.

Comparison with the submission

This prior paper presents a hybrid neural-FST model for sequence transduction, where a neural network provides context-sensitive weights for FST arcs, and inference is performed by composing the FST with the input string and summing over all alignments to compute p(y|x). While both works use FST composition and marginalization over paths, this paper does not address the problem of marginalizing source-string probabilities into target outputs or conditioning on transformed outputs. The submission's algorithms for target-side conditioning and efficient marginalization are not present here. Thus, the overlap is partial: the prior paper covers FST composition and marginalization for p(y|x), but not the specific contributions of the submission regarding target-side conditioning and marginalization.

##### From Language Models over Tokens to Language Models over Characters
substantial overlap · Vieira et al. · 2024

How this paper realizes the claim

This paper develops algorithms to convert token-level language models into character-level models by marginalizing over all tokenizations that decode to a given character string. The core technical contribution is to efficiently compute the probability of a character string under a token-level language model, by summing over all token strings that decode to that character string via a finite-state decoder (the tokenizer). The paper presents both exact and approximate algorithms for this marginalization, leveraging properties of the tokenizer as a finite-state transducer (FST).

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms. In the empirical portion of the paper, we benchmark the practical runtime and approximation quality.”

“pΣ(σ) def= P Y ∼p∆ [κ(Y ) = σ] (6) Note that pΣ(σ) accounts for the fact that many token strings may be associated with a given character string through κ.9 To describe that association, we define E(σ) def= {δ ∈∆∗: σ = κ(δ)}, the set of encodings for any character string σ ∈Σ∗.10 ## What about τ?”

“A character-level interface to the token-level language model p∆is available in the following equations, which hold ∀σ, σ′ ∈Σ∗: −→ pΣ(σ) = P Y ∼p∆ [κ(Y ) ⪰σ] (7) −→ pΣ(σ′ | σ) = −→ pΣ(σ·σ′) / −→ pΣ(σ) (8) −→ pΣ(EOS | σ) = pΣ(σ) / −→ pΣ(σ) (9) These equations show that we can have a complete characterlevel language model derived from the tokenized language model if we can compute—or approximate—the necessary summations implied by Eq. (6) and (7); specifically, pΣ(σ) = ∑_{δ∈∆∗} 1{κ(δ) = σ} p∆(δ) (10) −→ pΣ(σ) = ∑_{δ∈∆∗} 1{κ(δ) ⪰σ} p∆(δ) (11) We will develop effective methods for these summations for the family of strict-prefix monotone decoders κ (described in §2.4) where Eq. (10) and Eq. (11) admit a finite summation.”

“This section gives algorithms for computing pΣ(σ), −→ pΣ(σ), −→ pΣ(σ′ | σ), −→ pΣ(EOS | σ), and conditional token generation. We assume throughout that κ is strict-prefix monotone. ## 3.1.”

Comparison with the submission

This prior paper presents algorithms that compose a language model with a finite-state transducer (the tokenizer/decoder) to marginalize over all tokenizations that map to a given character string, enabling exact and approximate inference of character-level probabilities from a token-level model. This matches the core technical content of the claim, including conditioning on transformed outputs and not altering model parameters. However, the submission appears to generalize the approach to arbitrary FSTs and introduces new algorithmic techniques (such as the precover decomposition and BFS quotient/remainder sets) that are not present in this paper. Thus, the overlap is substantial but not identical: the prior paper covers the main idea for the special case of tokenization, while the submission extends and refines it for broader FSTs and with new algorithms.

##### Understanding and Mitigating Tokenization Bias in Language Models
substantial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper identifies and analyzes the sampling bias introduced by tokenization in language models, specifically focusing on maximum prefix encoding (MPE) and byte-pair encoding (BPE). It shows that this bias persists even with more data and proposes algorithms to correct the bias and recover unbiased character-level probabilities from a tokenized language model.

“we propose a novel algorithm to obtain unbiased estimates from any language model trained on tokenized data. Our methods do not require finetuning the model, and the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE. As a result, we show that one can simulate token-free behavior from a tokenized language model. We empirically verify the correctness of our method through a Markov-chain setup, where it accurately recovers the transition probabilities, as opposed to the conventional method of directly prompting tokens into the language model.”

“We present two novel algorithms to correct this bias for MPE and Byte-Pair-Encoding (BPE) respectively. Due to space limit, the analysis and algorithm for BPE are presented in Appendix H.”

“We present the MPC algorithm in Algorithm 1, that allows us to compute the probabilities P(xN nk+1|tk 1) and P(xn nk+1|tk 1) in Equation (1). Note that this algorithm does not require tk∈V∗. Details on the algorithmic correctness are shown in Appendix E. 3Many current language models begins with a start token <start> in V∗, e.g.”

“The idea is to marginalize out P(xN nk+1|tk 1) by considering two complementary events: when the next token tk+1 has a prefix xN nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN nk+1 (pval in the Pass Step). Formally, MPC computes the following probabilities: bval = P(xN nk+1, tk+1 ∈B(xN nk+1)) tk 1), (2) pval = P(xN nk+1, tk+1 /∈B(xN nk+1)) tk 1), (3) where B(xN nk+1)={t∈V|xN nk+1∈prefix(decode(t))} and we immediately see that P(xN nk+1|tk 1)=bval+pval.”

Comparison with the submission

This prior paper presents algorithms that marginalize over possible tokenizations to recover unbiased character-level probabilities from a tokenized language model, without changing model parameters. It provides both theoretical analysis and practical algorithms (including an exact algorithm) for this marginalization, which is highly similar in kind and scope to the claimed contribution. The main difference may be in the generality of the transformation (arbitrary FSTs vs. tokenization) and the specific algorithmic details. Thus, the overlap is substantial, and this paper can refute the claim if the submission does not go beyond tokenization or does not introduce fundamentally new algorithmic ideas.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

This paper addresses the problem of computing the probability of a word (or string) given a language model that operates over subwords, particularly focusing on the complications introduced by different tokenization schemes (end-of-word vs. beginning-of-word markers). It formalizes the mapping between words and subwords, and shows how to marginalize over all subword sequences that correspond to a given word or word sequence.

“This paper derives the correct methods for computing word probabilities, highlighting issues when relying on language models that use beginning-of-word (bow)-marking tokenisers, e.g., the GPT family. Empirically, we show that correcting the widespread bug in probability computations affects measured outcomes in sentence comprehension and lexical optimisation analyses.”

The paper develops efficient algorithms for computing the probability of a word in context by summing over all subword sequences that map to that word, and provides theoretical justification for these methods. It discusses how to perform this marginalization efficiently by leveraging the autoregressive property of language models and the structure of the tokenization.

“This paper is concerned with the proper method for computing the probability of a word in context, i.e., p(wt | w<t), using a pretrained language model. To this end, we first discuss its equivalence to other quantities, which will ultimately reveal a flaw in prior approaches to its computation.”

Quoted from the source but NOT confirmed verbatim:
Eq. (7) suggests a way to extract probabilities over words from a language model; we can simply use the equivalence:8 p(w) = p(s), for s = S W∗→S∗(w) (8) ... The implication of eq. (8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS.

The paper does not use general finite-state transducers (FSTs) for arbitrary string transformations, but rather focuses on the specific transformation defined by the tokenization process (mapping between words and subwords). It does not present algorithms for composing language models with arbitrary FSTs, nor does it discuss conditioning on arbitrary transformed outputs or supporting exact/approximate inference for general FSTs.

Comparison with the submission

The prior paper develops efficient and theoretically justified algorithms for marginalizing language model probabilities over all subword sequences that correspond to a given word, focusing on the complications of different tokenization schemes. However, it does not address the more general problem of composing language models with arbitrary finite-state transducers for general string transformations. The submission extends the marginalization approach to arbitrary FSTs, enabling a broader class of transformations and conditioning scenarios. Thus, the overlap is partial: the prior paper covers a special case (tokenization), while the submission generalizes and extends the approach.

##### Sampling from Your Language Model One Byte at a Time
substantial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, a method for composing a pretrained language model (LM) with a byte-level interface, allowing the LM to be conditioned on arbitrary byte prefixes. This is achieved by constructing a Valid Covering Tree (VCT) that represents all valid token sequences whose decoding covers a given byte prefix. The VCT enables efficient computation of prefix probabilities, sampling completions, and next-byte distributions, all while preserving the original LM's output distribution (up to probability mass on invalid token sequences). The method does not require any changes to the LM's parameters and works at inference time.

Quoted from the source but NOT confirmed verbatim:
In this paper, we propose ByteSampler, a system that can condition LMs on arbitrary byte-prefixes. This can be used to solve the PBP and can also be applied to convert the (tokenized) LM into a byte-level LM. Compared to prior work (Table 1), our method is the first to simultaneously achieve the following objectives: 1. Exact. Our method preserves the model’s output distribution, up to probability mass on invalid token sequences. We empirically show that our method preserves language modeling loss in Section 4.2 and preserves utility in downstream tasks (Sections E.5 and F). 2. Efficient. Our method is faster and uses fewer inference tokens than all methods of comparable quality (Sections 4.1, E.1 and E.2) 3. Compatible. Our method supports BPE tokenizers with future-dependent pretokenization, making it applicable to the vast majority of current open-weight LMs. (Table 1 and Section C.7)

Quoted from the source but NOT confirmed verbatim:
The VCT T for a given a byte-string S can be used to efficiently perform various byte-level language modeling tasks. We use “ByteSampler” to refer to this collection of routines. ... 1. To compute the probability of S (as a prefix) under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of T. 2. To sample a completion of S while avoiding the PBP, we compute the probability (as above) of every leaf in T and sample one of them accordingly. We are then free to continue sampling a continuation from that leaf using normal token-level sampling because sampled tokens induce token boundaries selected by the model. This one-time operation can be used to solve the PBP without paying the cost of byte-level sampling. 3. To compute the next byte distribution following S, we group the leaves of T by their corresponding next byte and sum the probabilities of the leaves in each group, as illustrated in Fig. 3. By repeatedly sampling from this distribution, we can generate text one byte at a time.

“Our method preserves the model’s output distribution, up to probability mass on invalid token sequences.”

“In our experiments, we apply ByteSampler at inference time to off-the-shelf language models. In Section 4.1 we show that our method has less computational overhead compared to other exact methods.”

Comparison with the submission

[downgraded: no both-sides-verified evidence quote pair] This paper presents ByteSampler, which composes a language model with the tokenizer (viewed as a finite-state transducer) to marginalize over token sequences that decode to a given byte string, enabling conditioning on arbitrary byte prefixes and supporting exact inference without modifying the model. This matches the core technical contribution of the claim, as both involve composing an LM with an FST to marginalize source-string probabilities into target outputs and enable transformed-output conditioning. However, the submission may go further by supporting arbitrary FSTs, not just tokenizers, and by providing a more general decomposition and theoretical analysis. Thus, the overlap is substantial but not identical.

##### Neural Grammatical Error Correction with Finite State Transducers
partial overlap · Stahlberg et al. · 2019

How this paper realizes the claim

This paper develops a grammatical error correction (GEC) system that constructs a hypothesis space using finite-state transducers (FSTs) and then constrains the output of neural models to this space. The FSTs are used to represent possible corrections (via confusion sets and edit transducers), and the hypothesis space is scored using a combination of symbolic (n-gram) and neural language models.

“We make extensive use of the FST operations available in OpenFST (Allauzen et al., 2007) like composition (denoted with the ◦-operator) and projection (denoted with Πinput(·) and Πoutput(·)) to build H. The process starts with an input lattice I.”

Quoted from the source but NOT confirmed verbatim:
To incorporate word-level language model scores we train a 5-gram count-based LM ... and convert it to an FST L using the OpenGrm NGram Library ... Our combined word-level scores can be expressed with the following transducer: Hword = B ◦P ◦L.

“Note that exact inference in Hword is possible using FST shortest path search. This is an improvement over the work of Bryant and Briscoe (2018) who selected correction options greedily.”

The paper composes FSTs representing possible edits with FSTs representing language models, and uses the composed FST to constrain and score candidate outputs. The composition is used to efficiently search for the best correction, and exact inference is possible in the composed FST. The neural language model is used for rescoring, but is not itself composed as an FST.

The paper does not describe algorithms for marginalizing source string probabilities into target outputs, nor does it enable conditioning on transformed outputs in the sense of propagating probabilities through the transducer from a pretrained language model without changing its parameters. Instead, it uses FSTs to define a constrained search space and then applies language models (symbolic and neural) for scoring.

Comparison with the submission

This prior paper uses FST composition to build a hypothesis space for grammatical error correction and composes it with an n-gram language model FST for scoring, supporting exact inference in the composed space. However, it does not develop algorithms for marginalizing source string probabilities into target outputs or for conditioning on transformed outputs by propagating probabilities through the FST from a pretrained language model. The submission's contribution is more general and algorithmic, enabling new forms of inference and conditioning not present in this work. Thus, the overlap is partial: the prior paper shares the use of FST-LM composition and exact inference, but not the core marginalization and conditioning algorithms of the submission.

##### Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities
partial overlap · Oh et al. · 2024

How this paper realizes the claim

This paper identifies a confound in how word probabilities are calculated from language models (LMs) that use subword tokenization with leading whitespaces. It proves that the standard method of aggregating subword probabilities can violate probability axioms and proposes a correction called whitespace-trailing (WT) decoding. WT decoding reallocates the probability of the trailing whitespace to the current word, resulting in consistent word probabilities without modifying the LM parameters. The paper provides a mathematical proof of this correction, demonstrates its effect on psycholinguistic modeling, and shows that it can be implemented efficiently as a post-processing step.

“We propose a simple and efficient decoding method that reaccounts the probability of the trailing whitespace into that of the current word, which resolves this confound. Regression results show that this correction reveals significantly lower surprisal-based estimates of garden-path effects in transitive/intransitive sentences and poorer fits of LM surprisal to naturalistic reading times.”

“WT decoding simply involves the factorization of whitespace probabilities by marginalizing over tokens in VB and rearranging them, it requires no modifications to the LM and minimal overhead. Additionally, the joint probability of the entire sequence, and therefore metrics like perplexity, changes minimally by a factor of the probability of the final trailing whitespace with WT decoding.”

“we note that WT decoding does not resolve other issues with subword units that may be addressed by re-training LMs with different tokenization schemes (e.g. Nair and Resnik, 2023), which can nonetheless be expensive. Concurrent work by Pimentel and Meister (2024) points out this same issue and also proposes WT decoding.”

“As WT decoding simply involves the factorization of whitespace probabilities by marginalizing over tokens in VB and rearranging them, it requires no modifications to the LM and minimal overhead. Additionally, the joint probability of the entire sequence, and therefore metrics like perplexity, changes minimally by a factor of the probability of the final trailing whitespace with WT decoding.”

Comparison with the submission

The prior paper addresses a specific case of marginalizing over subword tokenizations to correct word probability calculations in LMs with leading whitespace tokens, using a simple post-processing algorithm (WT decoding). However, it does not develop general algorithms for composing LMs with arbitrary FSTs, nor does it address conditioning on transformed outputs or provide the theoretical and algorithmic generalizations found in the submission. Thus, the overlap is partial: the prior paper shares the high-level idea of marginalizing over latent structures for output probabilities without changing model parameters, but the submission is broader and more general in scope and technical contribution.

---

### Third extracted claim

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

**Verdict:** not challenged in the examined literature

This claim is not challenged by any examined prior work. The closest related works, such as "From Language Models over Tokens to Language Models over Characters" and "Sampling from Your Language Model One Byte at a Time," only address prefix decompositions in the context of strict-prefix monotone transformations or specific cases like BPE tokenizers. They do not provide general transducer-level conditions for finiteness, especially for non-prefix-monotone transformations. The submission extends these results by providing sufficient transducer-level conditions (e.g., absence of ε-output cycles and inductive safety) for finite prefix decompositions in a much broader setting. The evidence is strong, as it is based on full-text comparisons and explicit statements of the submission's broader scope. Therefore, the novelty of this theoretical contribution holds within the examined literature.

#### Overlapping prior work

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper addresses the problem of converting token-level language models to character-level ones, focusing on the computation of prefix probabilities for character strings given a token-level model and a decoding function. It introduces the notion of a 'covering' set of token strings whose decoded outputs cover a given character prefix, and provides algorithms for efficiently computing prefix probabilities by summing over this covering set.

“We will develop effective methods for these summations for the family of strict-prefix monotone decoders κ (described in §2.4) where Eq. (10) and Eq. (11) admit a finite summation. ## 2.4.”

The paper explicitly states that its algorithms and finite covering constructions rely on the decoder κ being strict-prefix monotone (a property stronger than prefix monotonicity). It does not provide constructions or sufficient conditions for finite prefix decompositions in the absence of prefix monotonicity, nor does it address the case of general transducers or non-monotone transformations.

Comparison with the submission

This prior paper develops algorithms for computing prefix probabilities for character strings given a token-level model, but its constructions and guarantees are limited to the case where the decoder is strict-prefix monotone. It does not address the more general case of non-monotone transformations or provide transducer-level conditions for finiteness in that setting. The submission extends this line of work by giving sufficient conditions for finite decompositions even when prefix monotonicity does not hold, thus going beyond the contributions of this paper. The overlap is therefore partial: the prior paper covers the monotone case, but not the general case addressed by the submission.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, a method for sampling from a language model conditioned on arbitrary byte prefixes, addressing the prompt boundary problem caused by tokenization. The core technical object is the Valid Covering Tree (VCT), which represents all valid token sequences whose decoding covers a given byte prefix. The VCT is constructed to be finite and efficiently computable for any prefix, with its size bounded by a constant depending on the tokenizer. The paper provides a formal definition of the VCT, proves its compactness (Proposition 3.2), and describes algorithms for constructing and incrementally updating it as new bytes are generated. The VCT enables efficient computation of prefix probabilities and next-byte distributions, and the paper proves that the VCT is always finite for BPE tokenizers with certain properties (constant lookahead, no merges crossing pretoken boundaries). The paper does not explicitly discuss general transducers or provide transducer-level conditions for finite prefix decompositions beyond the BPE/tokenizer setting.

Comparison with the submission

This prior paper delivers a finite, efficiently computable representation (the Valid Covering Tree) for all token sequences covering a given prefix, enabling prefix probability computation and sampling for BPE tokenizers. However, it does not address arbitrary transducers or provide general transducer-level conditions for finiteness, nor does it handle non-prefix-monotone transformations in the general sense. The submission extends these ideas to a broader class of transformations and provides explicit transducer-level guarantees, representing a significant generalization. Thus, the overlap is partial: the prior paper covers the BPE/tokenizer case, but not the full generality or the transducer-level conditions of the submission.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper addresses the problem of computing the probability of a word given a subword-based language model, focusing on the correct computation of prefix probabilities and the mapping between words and subwords under different tokenization schemes (end-of-word and beginning-of-word marking).

“We are now in a position to define our quantity of interest p(w | w<t) in terms of subword probabilities: it is simply the quotient of PS(·) for two different sets ΨS. Lemma 1. The contextual probability of a word can be computed using probability distributions over subwords as: p(w | w<t) = PS(Ψ′ S) / PS(Ψ′′ S) where Ψ′ S ∆= w<t ◦w ◦W∗ and Ψ′′ S ∆= w<t ◦W∗.”

The paper provides efficient strategies for computing these probabilities by leveraging the autoregressive property of language models and the structure of the tokenization scheme. It gives explicit constructions for the sets of subword prefixes needed to compute prefix probabilities, and shows how these can be used to compute word probabilities for both eow- and bow-marking tokenizers.

“It follows that if we can find a set of subword sequences ΨS = {s(k)}K k=1 for which we have the equivalence w ◦W∗ ∆= ⨆_{s∈ΨS} s ◦S∗, then we can compute prefix probabilities as: PS[⨆_{s∈ΨS} s ◦S∗] = ∑_{s∈ΨS} PS(s ◦S∗)”

The paper's constructions are based on properties of the tokenization function and the language model, not on general transducers. It does not provide general transducer-level sufficient conditions for the finiteness of prefix decompositions for arbitrary string transformations, nor does it address transformations that are not prefix monotone in the general sense.

Comparison with the submission

This prior paper provides a detailed and rigorous treatment of prefix decompositions and probability computations for word and subword mappings in language models, including efficient algorithms for the specific case of tokenization functions. However, it does not address the more general problem of arbitrary transducer-based string transformations, nor does it provide transducer-level sufficient conditions for finite decompositions, especially for non-prefix-monotone cases. Thus, the submission's contribution is only partially overlapped: it generalizes the results to a broader class of transformations and provides new sufficient conditions at the transducer level.

---

### Fourth extracted claim

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

**Verdict:** challenged by prior work

This claim is challenged by the prior work "From Language Models over Tokens to Language Models over Characters," which, as verified by both-sides quotes, presents algorithms for inference-time adaptation of pretrained token-level language models to character/byte-level outputs without retraining, by marginalizing over tokenizations. The overlap is substantial for the case of byte/character adaptation. However, the submission claims to generalize this approach to arbitrary string transformations via finite-state transducers, enabling adaptation not only to bytes/characters but also to words and amino acids, and introduces new algorithms and demonstrations in these additional domains. Thus, while the core idea of inference-time adaptation to new units is not novel, the submission's broader generalization and application to new domains represent a meaningful extension beyond the prior work.

#### Overlapping prior work

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, a method for inference-time adaptation of pretrained language models (LMs) with BPE tokenizers to operate at the byte level, without retraining the model. The method constructs a Valid Covering Tree (VCT) for a given byte prefix, representing all valid token sequences that cover the prefix, and uses this to compute next-byte distributions and sample completions at the byte level. The approach is exact (up to probability mass on invalid token sequences), efficient, and compatible with BPE tokenizers. The paper demonstrates ByteSampler on off-the-shelf LMs, showing applications to byte-level language modeling, ensembling models with different tokenizers, and proxy-tuning. However, the method is specifically designed for byte-level adaptation and does not address adaptation to words or amino acids.

“In this work, we present an inference-time method to convert any autoregressive LM with a BPE tokenizer into a character-level or byte-level LM. Our method efficiently solves the PBP and is also able to unify the vocabularies of language models with different tokenizers, allowing one to ensemble LMs with different tokenizers at inference time or transfer the post-training from one model to another using proxy-tuning.”

Quoted from the source but NOT confirmed verbatim:
Contributions. In this paper, we propose ByteSampler, a system that can condition LMs on arbitrary byte-prefixes. This can be used to solve the PBP and can also be applied to convert the (tokenized) LM into a byte-level LM.

“Our method preserves the model’s output distribution, up to probability mass on invalid token sequences. We empirically show that our method preserves language modeling loss in Section 4.2 and preserves utility in downstream tasks (Sections E.5 and F).”

“Our method supports BPE tokenizers with future-dependent pretokenization, making it applicable to the vast majority of current open-weight LMs. (Table 1 and Section C.7) 2 ## Background In this section we give essential background regarding tokenization as well a prior work addressing the Prompt Boundary Problem.”

“In our experiments, we apply ByteSampler at inference time to off-the-shelf language models. In Section 4.1 we show that our method has less computational overhead compared to other exact methods.”

Comparison with the submission

This paper presents a method for inference-time adaptation of pretrained language models to the byte level, without retraining, using a Valid Covering Tree construction. This overlaps with the submission's claim regarding byte-level adaptation, but the paper does not address adaptation to words or amino acids, nor does it use a general FST framework. The submission's broader scope and generalization to arbitrary string transformations (including words and amino acids) represent a significant delta beyond this paper. Therefore, the overlap is partial: the prior work covers byte-level adaptation, but not the full generality or the additional domains claimed by the submission.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper identifies and analyzes the sampling bias introduced by tokenization in language models, specifically showing that the next-character distribution is not faithfully represented by the next-token distribution due to the structure of tokenization schemes like MPE and BPE.

“we propose a novel algorithm to obtain unbiased estimates from any language model trained on tokenized data. Our methods do not require finetuning the model, and the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE. As a result, we show that one can simulate token-free behavior from a tokenized language model. We empirically verify the correctness of our method through a Markov-chain setup, where it accurately recovers the transition probabilities, as opposed to the conventional method of directly prompting tokens into the language model.”

The core contribution is the Maximum Prefix Correction (MPC) algorithm, which computes the probability of a string (e.g., a character sequence) given a tokenized language model by marginalizing over possible tokenizations, thus recovering unbiased character-level probabilities at inference time without retraining.

“We present two novel algorithms to correct this bias for MPE and Byte-Pair-Encoding (BPE) respectively. Due to space limit, the analysis and algorithm for BPE are presented in Appendix H. • We verify the correctness of our algorithms on learning the transition matrix of a k-th order Markov chain.”

Quoted from the source but NOT confirmed verbatim:
This algorithm recursively computes P(xN_nk+1|tk_1). ... The idea is to marginalize out P(xN_nk+1|tk_1) by considering two complementary events: when the next token tk+1 has a prefix xN_nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN_nk+1 (pval in the Pass Step).

The method is validated on synthetic Markov chain data, showing that the algorithm can recover unbiased character-level transition probabilities from a tokenized LM.

The paper does not demonstrate adaptation to bytes or amino acids, nor does it use finite-state transducers for general string transformations. Its focus is on character-level inference from tokenized LMs, specifically for text (characters/tokens), and does not address adaptation to other modalities or arbitrary string transformations.

Comparison with the submission

This prior paper presents a method for inference-time adaptation of tokenized language models to character-level outputs, correcting for tokenization bias without retraining. However, it is limited to character-level adaptation in text and does not address adaptation to bytes, words, or amino acids, nor does it use finite-state transducers for general string transformations. The submission extends the idea to a broader class of string transformations and modalities, including bytes and amino acids, using FSTs. Thus, the overlap is partial: the prior paper covers part of the claimed contribution (character-level adaptation without retraining), but not the full generality or the specific mechanisms and domains of the submission.

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

This paper addresses the problem of pretrained language models assigning probability mass to noncanonical tokenizations (e.g., noncanonical BPE segmentations) and proposes methods to enforce canonicality at inference time, without retraining the model.

“We present two approaches: (1) canonicality by conditioning, leveraging test-time inference strategies without additional training, and (2) canonicality by construction, a model parameterization that guarantees canonical outputs but requires training. We demonstrate that fixing canonicality mistakes improves the likelihood of held-out data for several models and corpora.”

“Canonicality by conditioning: We explore efficient testtime inference methods for conditionally generating text that satisfies the canonicality constraint without retraining. • Canonicality by construction: We explore methods that impose canonicality constraints directly in the language model’s parameterized architecture and give a method to fine-tune its parameters.”

The main technical contribution is a set of algorithms for conditioning the output of a pretrained token-level language model so that it only generates canonical tokenizations (i.e., those that would be produced by the deterministic tokenizer), using only inference-time modifications. This includes exact and approximate algorithms for sampling and computing probabilities under the constrained model.

Quoted from the source but NOT confirmed verbatim:
We describe two families of methods for doing so • Canonicality by conditioning, leveraging test-time inference strategies without additional training, and (2) canonicality by construction, a model parameterization that guarantees canonical outputs but requires training.

“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition 1.”

“We will discuss the details of how to approximately and exactly generate samples from g. ## Why do we condition?”

“The simplest exact conditioning algorithm for sampling from g is rejection sampling: 1 def rejection_sampling(): 2 while True: 3 δ ∼p∆ 4 ## if δ ∈D: return δ However, the rejection sampling algorithm can be inefficient if Z is small, as its expected running time per sample is O(1/Z).”

Quoted from the source but NOT confirmed verbatim:
Another correct sampling algorithm is ancestral sampling:

“Unfortunately, computing −→g exactly is intractable as it requires summing over infinitely many future strings. Thus, −→g must be approximated. In §3.2.2, we will provide a cheap, local approximation and, in §3.2.3, we will devise a strategy for improving the short-sightedness of the local approximation by using more computation.”

The algorithms are demonstrated on BPE tokenizations, and the focus is on enforcing canonicality for token-level language models over character strings (e.g., bytes or characters).

Comparison with the submission

This paper presents inference-time algorithms for adapting pretrained language models to only generate canonical BPE tokenizations, without retraining. The overlap with the submission is partial: both use inference-time composition to constrain or adapt the output of a fixed language model, but this paper is limited to canonical BPE tokenizations, while the submission generalizes to arbitrary FST-based transformations and demonstrates adaptation to bytes, words, and amino acids. Thus, the submission has a broader scope and a more general mechanism, and is not refuted by this prior work.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

This paper addresses the problem of computing word probabilities from pretrained language models that operate over subwords, specifically focusing on the correct computation of word-level probabilities given subword-level outputs. It derives the correct mathematical methods for marginalizing over subword sequences that correspond to a given word, with special attention to the differences between end-of-word and beginning-of-word tokenization schemes.

“This paper derives the correct methods for computing word probabilities, highlighting issues when relying on language models that use beginning-of-word (bow)-marking tokenisers, e.g., the GPT family. Empirically, we show that correcting the widespread bug in probability computations affects measured outcomes in sentence comprehension and lexical optimisation analyses.”

“We derive methods for these tokenisation schemes, which we present in Fig. 1.”

“Empirically, we evaluate how correcting this computation affects the results of two prior empirical analyses: one on sentence comprehension and another on the lexicon’s communicative efficiency. While these studies’ conclusions do not change, we do observe statistically significant differences between the measured quantities when using the correct vs.”

The paper provides theoretical derivations and practical algorithms for computing the probability of a word in context from a subword-based language model, including how to sum over all subword segmentations that map to a word. It does not propose or demonstrate inference-time adaptation to new unit types (such as bytes or amino acids) beyond words, nor does it use finite-state transducers for general string transformations.

Comparison with the submission

The prior paper provides a rigorous treatment of how to compute word probabilities from subword-based language models, including the necessary marginalization over subword segmentations and the handling of different tokenization schemes. However, it is limited to the word/subword setting and does not address adaptation to other unit types (such as bytes or amino acids), nor does it use finite-state transducers for general string transformations. The submission extends the idea to a much broader class of transformations and unit types, making its contribution more general and technically distinct. Thus, the overlap is partial: the prior paper covers part of the claim (word-level inference-time adaptation), but not the full generality or mechanism of the submission.

##### Automata-based constraints for language model decoding
partial overlap · Koo et al. · 2024

How this paper realizes the claim

The paper presents a method for constraining the output of a pretrained language model (LM) to conform to a regular or context-free language, using automata theory. The core technique is to compose a finite-state transducer (FST) that maps tokens to characters (detokenization) with a finite-state automaton (FSA) or pushdown automaton (PDA) that encodes the desired output constraint (e.g., a regular expression or grammar). This composition yields a new automaton that operates over the LM's tokens and can be used to mask the LM's logits at each decoding step, ensuring only valid outputs are generated.

“Our main contributions are primarily conceptual rather than empirical: 1. Identify an as-yet unnoticed connection between detokenization and transduction. 2. Solve the tokenization issues using this connection and operations on automata. 3. Define extensions that address practical problems of efficiency and convenience. ∗Equal contribution, alphabetical.”

Quoted from the source but NOT confirmed verbatim:
Our first contribution is a reformulation of detokenization (i.e., the process of converting token sequences back into text) as an FST, using the following construction: ... For compactness, common prefixes of the chains can be merged to form a trie-like structure, as in Figure 4; see Appendix B.1 for a proof of correctness.

“Our next contribution is a generic method for adapting any FSA from characters to tokens. Specifically, given a token vocabulary V and an FSA A that accepts character sequences, A′ = A ◦TV accepts essentially the same language as A, but in token form. More precisely, for each token sequence w ∈LA′, the detokenization of w is in LA.”

“We now present our method for constraining an LM to a regular language: Algorithm 2 Constrains LM L with vocabulary V to generate the language of regex R TV ←BUILDDETOKENIZINGFST(V) ▷token-to-character FST, see Algorithm 1 AR ←BUILDREGEXFSA(R) ▷character-accepting FSA (Thompson, 1968) AR◦V ←DETERMINIZE(AR ◦TV) ▷token-accepting FSA ... for t = 1 to T do ▷decoding steps ℓ←COMPUTELOGITS(L) A ←{eσ : e ∈ER◦V ∧es = q} ▷allowed next tokens for i = 1 to |V| do ▷penalize logits as in Deutsch et al. (2019) if vi ̸∈A then ℓi ←−∞ ˆv ←SAMPLENEXTTOKEN(L, ℓ) ˆe ←e s.t. e ∈ER◦V ∧es = q ∧eσ = ˆv ▷find the matching edge q ←ˆet ▷traverse the edge”

The method is inference-time only: the LM is not retrained or fine-tuned, but is instead constrained at decoding time by masking logits according to the automaton state. The paper discusses the generality of this approach for regular and context-free languages, and the ability to adapt constraints to the LM's tokenization via FST composition.

However, the paper does not demonstrate adaptation to bytes, words, or amino acids specifically, nor does it present experiments or algorithms for marginalizing over source strings whose transducer outputs cover a target prefix, as in the claim. The focus is on constraining output to formal languages, not on adapting the LM to new output units or alphabets (such as bytes or amino acids) at inference time.

Comparison with the submission

This prior paper presents a general method for constraining the output of a pretrained LM at inference time using automata, specifically by composing a detokenization FST with a constraint FSA or PDA. While this is conceptually related to the claim, the paper does not address adaptation to new output units (such as bytes or amino acids), nor does it provide algorithms for marginalizing over source strings for next-symbol prediction in a transformed space. The overlap is partial: both use FST composition at inference time, but the submission's focus on adaptation to new alphabets and marginalization for next-symbol prediction is not covered here.

##### Efficient Guided Generation for Large Language Models
partial overlap · Willard et al. · 2023

How this paper realizes the claim

The paper presents a method for efficiently guiding the generation of sequences from a pretrained language model so that the outputs conform to regular expressions or context-free grammars, using finite-state machines (FSMs) and pushdown automata (PDAs) to represent constraints.

“This framework leads to an efficient approach to guiding text generation with regular expressions and context-free grammars by allowing the construction of an index over a language model’s vocabulary. The approach is model agnostic, allows one to enforce domain-specific knowledge and constraints, and enables the construction of reliable interfaces by guaranteeing the structure of the generated text. It adds little overhead to the token sequence generation process and significantly outperforms existing solutions.”

The approach is inference-time only: it does not require retraining or modifying the parameters of the pretrained language model. Instead, it constructs an index mapping FSM (or parser) states to valid next tokens in the vocabulary, enabling efficient masking of invalid tokens during generation.

“Our approach does not require the complete transducer abstraction and can be used to more easily extend existing, efficient regular expression libraries without modifying the underlying automatons and their implementations. More importantly, our indexing approach can also be extended to CFGs and LALR(1) parsers to allow for efficient guided generation according to popular data formats and programming languages (e.g.”

The method is demonstrated for regular expressions and context-free grammars, including examples such as generating valid Python identifiers or IP addresses, but all demonstrations are at the token level (i.e., the model's native vocabulary).

The paper does not demonstrate adaptation to different unit granularities (such as bytes or amino acids), nor does it describe marginalizing over source strings via FST composition to expose next-symbol probabilities in a transformed space.

Comparison with the submission

This prior paper presents an efficient inference-time method for guiding language model generation using FSMs and PDAs, enforcing constraints such as regular expressions or grammars, but only at the model's native token level. It does not address adaptation to different unit granularities (e.g., bytes, words, amino acids) or the use of FST composition to marginalize over source strings for transformed outputs. Thus, while both works share the idea of inference-time composition with finite-state machinery, the submission's contribution is broader and more general, enabling adaptation to arbitrary output units and transformations, which is not realized in this prior work. The overlap is partial, as the prior paper covers only a subset (token-level constraints) of the submission's broader mechanism.

##### Neural Grammatical Error Correction with Finite State Transducers
partial overlap · Stahlberg et al. · 2019

How this paper realizes the claim

This paper focuses on grammatical error correction (GEC) using a combination of finite-state transducers (FSTs) and neural language models (NLMs). The main contribution is to construct a hypothesis space of possible corrections using FSTs, and then rescore these hypotheses with neural models, including neural LMs and neural machine translation (NMT) models.

“we propose to construct a hypothesis space using standard FST operations like composition, and then constrain the output of a neural GEC system to that space. We study two different scenarios: In the ﬁrst scenario, we do not have access to annotated training data, and only use a small development set for tuning.”

“We report further gains by rescoring with neural language models. We show that our methods developed for LM-GEC can also be used with SMT systems if annotated training data is available.”

The neural language models used are pretrained and are applied at inference time to rescore the hypotheses generated by the FSTs. The paper describes the use of a Transformer-based neural LM trained on a large corpus, and the composition with FSTs is used to constrain the search space for decoding.

“Our ultimate goal, however, is to rescore Hword with neural models such as an NLM and – if annotated training data is available – an NMT model. Since our neural models use subword units (Sennrich et al., 2016, BPEs), we compose Hword with a transducer T which maps word sequences to BPE sequences. Our final transducer HBPE which we use to constrain the neural beam decoder can be written as: HBPE = Πoutput(Hword ◦T) = Πoutput(I ◦E ◦P ◦L ◦T).”

The approach does not retrain the neural language model; it uses the pretrained model as-is for rescoring. The FSTs are used to define the set of possible outputs, and the neural LM provides probabilities for these outputs during inference.

Comparison with the submission

This prior paper demonstrates inference-time composition of FSTs with a pretrained neural language model for grammatical error correction, without retraining the LM. However, its use of FSTs is to constrain the output space for GEC, and the neural LM is used for rescoring, not for adapting the model to new units or arbitrary string transformations. The submission's contribution is broader and more general, providing algorithms for exact and approximate inference over arbitrary FSTs and demonstrating adaptation to bytes, words, and amino acids. Thus, the overlap is partial: the prior paper shares the idea of inference-time FST composition with a fixed LM, but not the generality, algorithms, or breadth of demonstrations of the submission.

##### Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs
partial overlap · Lew et al. · 2023

How this paper realizes the claim

The paper proposes an inference-time method for steering large language models (LLMs) using sequential Monte Carlo (SMC) applied to probabilistic programs. The approach allows the imposition of syntactic and semantic constraints, infilling, and prompt intersection by specifying these tasks as posterior inference in a class of discrete probabilistic sequence models (Feynman-Kac Transformer models). The LLM itself is kept fixed, and the constraints or transformations are imposed at inference time via the probabilistic program and SMC algorithm.

“We propose a new inference-time approach to enforcing syntactic and semantic constraints on the outputs of LLMs, called sequential Monte Carlo (SMC) steering. The key idea is to specify language generation tasks as posterior inference problems in a class of discrete probabilistic sequence models, and replace standard decoding with sequential Monte Carlo inference. For a computational cost similar to that of beam search, SMC can steer LLMs to solve diverse tasks, including infilling, generation under syntactic constraints, and prompt intersection.”

“To facilitate experimentation with SMC steering, we present a probabilistic programming library, LLaMPPL, for concisely specifying new generation tasks as language model probabilistic programs, and automating steering of LLaMA-family Transformers. 1 ## Introduction Despite significant advances in recent years, it remains unclear if and how large language models (LLMs) can be made reliable and controllable enough to meet the functional requirements of many applications.”

“Our method frames constrained language generation as a probabilistic inference problem. This perspective is commonly adopted in the literature [see, e.g., Kumar et al., 2022, Poesia et al., 2022, Miao et al., 2019, Qin et al., 2022], and has several distinctive features compared to popular heuristic and optimization-based approaches to inference-time constrained generation: • Global vs.”

“this workshop abstract proposes sequential Monte Carlo (SMC) steering, an alternative to standard decoding procedures that works by approximating the posteriors of language model probabilistic programs [Lew et al., 2020, Dohan et al., 2022, Zhi-Xuan, 2022]: models that mix LLMs, probabilistic conditioning, and symbolic programming to encode semantic and syntactic constraints. By varying the probabilistic program, SMC can steer LLMs to solve diverse tasks, including infilling [Qian and Levy, 2022, Donahue et al., 2020, Bavarian et al., 2022], constrained generation [Zhang et al., 2023a, Pascual et al., 2020, Roush et al., 2022], and prompt intersection (Figure 1), all at a cost similar to that of beam search.”

The paper demonstrates this approach on tasks such as infilling, hard constraints (e.g., word length), and prompt intersection, but does not specifically demonstrate adaptation to bytes, words, or amino acids as output units, nor does it describe the use of finite-state transducers (FSTs) for string transformations.

Comparison with the submission

The prior paper and the submission both address inference-time adaptation of pretrained language models by composing them with external mechanisms, without retraining. However, the prior paper focuses on steering generation with constraints and probabilistic programs, not on adapting the model to new output units or using FSTs for string transformations. The submission's contribution of adapting to bytes, words, and amino acids via FST composition is not present in the prior work. Thus, the overlap is partial: the general idea of inference-time adaptation is shared, but the specific mechanism and demonstrations in the submission are new.

##### Where is the signal in tokenization space?
partial overlap · Geh et al. · 2024

How this paper realizes the claim

This paper investigates the effect of non-canonical tokenizations in pretrained language models (LLMs) at inference time, focusing on the marginalization over all possible tokenizations of a string (i.e., summing probabilities over all token sequences that yield the same string). It proves that finding the most likely tokenization and computing the marginal probability are computationally hard, and proposes approximate algorithms (e.g., importance sampling) to estimate the marginal probability. The paper empirically evaluates whether using marginal probabilities or aggregating over non-canonical tokenizations can improve downstream tasks, such as question answering, without retraining the model.

“by simply aggregating the probabilities of noncanonical tokenizations, we achieve improvements across a range of LLM evaluation benchmarks for a variety of architectures, including transformers and state space models. 1 ## Introduction Autoregressive large language models (LLMs) generate text by predicting the next word sequentially.”

“we analyze modern LLMs and consider multiple strategies for extracting information from tokenization space; finding that, contrary to prior belief, the signal is present not in the most-likely tokenization or (approximated) marginals, but rather in a mixture of canonical and non-canonical tokenizations. 3 ## Tokenizations Let x = (x1, x2, .”

“we implement an importance sampling estimator for the marginal probability. Surprisingly, despite the extremely large number of non-canonical tokenizations, we empirically find that the estimated marginal probability is usually very close to the canonical tokenization’s probability. This raises our last question: does the complete tokenization space add any meaningful signal at all, in addition to the canonical tokenization alone?”

Comparison with the submission

This paper partially overlaps with the claimed contribution by demonstrating inference-time adaptation of pretrained language models to alternative tokenizations (words/subwords) without retraining, via marginalization over tokenization space. However, it is limited to tokenization variants within the same language and does not address adaptation to fundamentally different representations (such as bytes or amino acids) or arbitrary FST-based transformations. The submission extends the idea to a much broader class of string transformations, provides new algorithms for efficient inference in this setting, and demonstrates applications in multiple domains. Thus, the overlap is partial, and the submission presents a significant delta in generality and scope.

##### From Language Models over Tokens to Language Models over Characters
substantial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper presents algorithms for converting token-level language models to character-level ones, enabling inference-time adaptation of pretrained token-based language models to operate over character strings without retraining. The core contribution is an exact and approximate algorithm for computing the conditional distribution over characters (bytes) given a character prefix, by summing over all token strings whose decoded output covers the character prefix. This allows the computation of next-character probabilities and enables character-level generation and scoring from a fixed, pretrained token-level model.

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms. In the empirical portion of the paper, we benchmark the practical runtime and approximation quality.”

Quoted from the source but NOT confirmed verbatim:
Our method finds a set of token strings that form a covering, a key technical concept we introduce in this paper. ... The computation of this conditional probability is simply the total probability of the covering of Hello,␣world divided by the total probability of the covering of Hello,␣worl. These quantities are derived from our concept of covering, which directly leads to an algorithm for determining the distribution over possible next characters.

“We provide an algorithm for correctly conditioning a token-level model on a character string in §3.4. Character-level model.”

“In the experimental portion of our paper (§4), we report the empirical runtime of our algorithm for converting token-level language models to character-level ones and quantify its accuracy in estimating the conditional distribution over characters. We find that even with a limited computational budget, our method provides an accurate estimate of the conditional distribution over the next character under four publicly available language models.6 We also find that the compression rate (bits/byte) is significantly improved by estimating the probability of the corpus as a character string rather than a canonical token string.”

Comparison with the submission

This prior paper presents a substantial overlap with the claimed contribution in the domain of adapting pretrained token-level language models to character/byte-level inference without retraining, using exact and approximate algorithms for marginalizing over tokenizations. However, it does not address adaptation to words or amino acids, nor does it generalize the approach to arbitrary FST-based string transformations. The submission's main delta is the generalization to broader classes of string transformations and additional domains beyond characters/bytes. Thus, the overlap is substantial but not identical.

##### Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities
partial overlap · Oh et al. · 2024

How this paper realizes the claim

This paper identifies a confound in how word probabilities are computed from subword-tokenized language models, specifically due to leading whitespaces in the token vocabulary. It proves that the standard method of aggregating subword probabilities can violate probability axioms and proposes a new decoding method, whitespace-trailing (WT) decoding, to correct this. WT decoding reallocates the probability of the trailing whitespace to the current word, resulting in consistent word probabilities without modifying the language model parameters or retraining. The paper demonstrates this method on English text and evaluates its impact on psycholinguistic measures, such as garden-path effects and reading time predictions.

“we propose whitespace-trailing (WT) decoding. Given a word wt+1 that consists of subword tokens xnt+1..nt+1, where nt is the total number of subword tokens in the word sequence w1..t, and xnt+1∈VB, and xnt+2..nt+1∈VI, WT decoding reallocates the probability of the leading whitespace of each word to its previous word:3 P(w′ t+1 | w′ 1..t) = P(wt+1 | w1..t) · P(xnt+1+1∈VB | w1..t+1) P(xnt+1∈VB | w1..t) . (5) 3See Appendix A for the proof that WT decoding results in consistent word probabilities.”

“As WT decoding simply involves the factorization of whitespace probabilities by marginalizing over tokens in VB and rearranging them, it requires no modifications to the LM and minimal overhead. Additionally, the joint probability of the entire sequence, and therefore metrics like perplexity, changes minimally by a factor of the probability of the final trailing whitespace with WT decoding.”

“WT decoding does not resolve other issues with subword units that may be addressed by re-training LMs with different tokenization schemes (e.g. Nair and Resnik, 2023), which can nonetheless be expensive. Concurrent work by Pimentel and Meister (2024) points out this same issue and also proposes WT decoding.”

Comparison with the submission

This paper presents a method for inference-time adaptation of language models to word-level probabilities from subword tokenizations, without retraining, by introducing whitespace-trailing decoding. This overlaps with the submission's claim in the specific case of word-level adaptation, but does not address adaptation to bytes or amino acids, nor does it provide a general FST-based framework. The submission is broader in scope, offering a general mechanism for arbitrary string transformations and supporting multiple domains. Therefore, the overlap is partial: the prior paper covers one instance of the general problem addressed by the submission, but not its full generality or algorithmic contributions.

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

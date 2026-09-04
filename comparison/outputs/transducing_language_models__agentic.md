# Novelty Assessment

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

- Efficient Guided Generation for Large Language Models — Willard et al. · 2023 — partial overlap
- From Language Models over Tokens to Language Models over Characters — Vieira et al. · 2024 — substantial overlap
- How to Compute the Probability of a Word — Pimentel et al. · 2024 — partial overlap
- Language Models over Canonical Byte-Pair Encodings — Vieira et al. · 2025 — substantial overlap
- Sampling from Your Language Model One Byte at a Time — Hayase et al. · 2025 — substantial overlap
- Understanding and Mitigating Tokenization Bias in Language Models — Phan et al. · 2024 — substantial overlap
- Where is the signal in tokenization space? — Geh et al. · 2024 — partial overlap
- Analyzing Cognitive Plausibility of Subword Tokenization — Beinborn et al. · 2023
- Automata-based constraints for language model decoding — Koo et al. · 2024
- Differentiable Weighted Finite-State Transducers — 2020
- Effect of tokenization on transformers for biological sequences — Dotan et al. · 2023
- Effective Large Language Model Adaptation for Improved Grounding and Citation Generation — 2023
- Formalizing BPE Tokenization — Berglund et al. · 2023
- Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — 2019
- Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Oh et al. · 2024
- Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA — Qiao et al. · 2024
- Neural Finite-State Transducers: Beyond Rational Relations — Lin et al. · 2019
- Neural Grammatical Error Correction with Finite State Transducers — Stahlberg et al. · 2019
- Neural Machine Translation of Rare Words with Subword Units — Sennrich et al. · 2015
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Lew et al. · 2023
- Speech Recognition using Weighted Finite-State Transducers — 2022
- SQL-PaLM: Improved Large Language Model Adaptation for Text-to-SQL (extended) — 2023
- Syntactic Control of Language Models by Posterior Inference — Xefteri et al. · 2025
- Weighting Finite-State Transductions With Neural Context — Rastogi et al. · 2016

## Review

### Overall assessment

Across the four claims, the evidence shows that the submission's core contributions—introducing a general framework for transduced language models and developing algorithms for composing language models with finite-state transducers—are substantially challenged by prior works such as "Language Models over Canonical Byte-Pair Encodings," "From Language Models over Tokens to Language Models over Characters," and "Understanding and Mitigating Tokenization Bias in Language Models." These prior works, examined at the full-text level, already present the main ideas of composing language models with deterministic string-to-string transformations and algorithms for marginalization and inference. However, the submission differentiates itself by generalizing these frameworks and algorithms to arbitrary FST-defined transformations (not just tokenization), introducing new decomposition techniques, and providing broader theoretical analyses. The claim regarding sufficient transducer-level conditions for finite prefix decompositions is not challenged by any examined prior work and appears genuinely novel within the examined literature. The demonstration of inference-time adaptation is also challenged by prior work, but the submission's extension to arbitrary FSTs and new modalities (such as words and amino acids) is not fully covered. Overall, while the foundational ideas are not novel within the examined literature, the submission advances the state of the art through generalization and new theoretical contributions.

---

### First extracted claim

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

**Verdict:** challenged by prior work

This claim is challenged by both "Language Models over Canonical Byte-Pair Encodings" and "From Language Models over Tokens to Language Models over Characters," both of which were compared against the full text and show substantial overlap. Both prior works introduce a framework for composing a language model with a deterministic string-to-string transformation represented by a finite-state transducer, resulting in a new language model over the transformed outputs, and provide algorithms for marginalization and inference. However, the submission differentiates itself by generalizing the framework beyond tokenization to arbitrary deterministic string-to-string transformations and introducing new algorithms and theoretical analyses for efficient marginalization and prefix probability computation. Thus, while the core framework is not novel within the examined literature, the submission extends it in meaningful ways.

#### What the submission does for this claim

The paper defines the framework by composing a source language model over X with a deterministic string-to-string function f whose structure is encoded as a finite-state transducer, producing a model over target strings Y.

“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X . Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y.”

The target model is not limited to sampling: it marginalizes source strings that can produce a target prefix, then uses those prefix probabilities to recover the usual autoregressive interface.

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis.”

To make this computation finite or tractable, the paper represents each target prefix's precover—the source strings whose transformed outputs begin with that prefix—as a maximal cylindrical part plus a remainder.

“Instead, we decompose it into two disjoint parts: a maximal cylindrical subset and its complement in the precover. The quotient collects the shortest element of each cylinder; the complement is the remainder. The final step (5c) illustrates a computational shortcut; for any y we can decompose -→ p Y (y): The precover can also be represented as an FSA, as shown below for P(ba).”

The decomposition algorithm explores candidate source prefixes breadth-first, classifying each one as a quotient element when all of its extensions cover the target, as a remainder element when only the prefix covers it, or as live when some extension may still cover it.

“Fig. 2 gives the decomposition algorithm (decompose), which maintains a queue of candidate source strings and explores them by breadth-first search (BFS), optionally pruning low-probability candidates at each step (described below). 10 Each dequeued string x undergoes three checks, defined in terms of the precover P(y): 1.”

The FST supplies the checks needed by this search: the target-conditioned input projection is converted to a deterministic, trimmed automaton, while the efficient implementation replaces explicit construction with lazy frontiers that track reachable transducer states and emitted output buffers.

“Given a target prefix y, proj X (f • yY * ) is an NFA that accepts exactly P(y). To enable the efficient state-based checks below, we determinize and trim this NFA to obtain a DFA: P y def = trim(determinize(proj X (f • yY * ))) Let S y , I y , F y , and T y denote the components of P y .”

“Instead, we track frontiers: sets of transducer states reachable after scanning a source prefix, paired with the output emitted so far. Frontiers lazily perform the subset construction (the standard NFA-to-DFA conversion; Rabin & Scott, 1959 ) and the composition with yY * simultaneously, avoiding both eager determinization and eager composition.”

This yields both exact and approximate transformed language models: exact decomposition is used when finite, while probability-mass pruning retains high-probability decomposition elements when enumeration is too large. The framework is instantiated with FSTs for several target units.

“We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

“we construct FSTs for the three use cases above: (i) converting tokens to bytes, (ii) inserting orthographic boundaries following the Penn Treebank tokenizer, and (iii) converting DNA sequences to sequences over amino acids. We then employ commonly used pretrained language models over the input units of the FSTs, and compose them with the FSTs to obtain language models over the output tokens.”

#### Overlapping prior work

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, an algorithm for converting any BPE tokenizer-based language model into a byte-level model, preserving the generative distribution at the text level. The core mechanism is the Valid Covering Tree (VCT), which represents all token sequences that cover a given byte-string prompt. The VCT is used to compute prefix probabilities, sample completions, and compute next-byte distributions efficiently. The method is exact in the sense that it samples according to the original model's distribution, modulo probability mass on invalid sequences. The paper discusses how ByteSampler can be used for model composition, ensembles, and knowledge distillation across models with different tokenizers. The method is compatible with various tokenization schemes and supports arbitrary pretokenizers.

“In this work, we introduced ByteSampler, an algorithm that eliminates the Prompt Boundary Problem by converting any BPE tokenizer-based language model into a byte-level model while preserving its generative distribution at the text level. Interesting extensions of this method include 11This is necessary because, for byte-level BPE, a token might be a partial character.”

“In this section, we describe the core mechanism behind ByteSampler. In Section 3.1 we define the Valid Covering Tree (VCT), an object containing all of the token sequences that cover a prompt. In Section 3.2, we show how the VCT can then be used to perform standard language modeling tasks: computing prefix probabilities, sampling completions while avoiding the prompt boundary problem, and computing next-byte distributions. In Section 3.3, we show that the VCT has bounded size, leading to low inference costs.”

“Beyond correcting sampling artifacts at the promptboundary—which is useful in its own right in many situations—the ability to unify vocabularies at inference time enables many forms of model composition, including ensembles of (and post-training transfer between) models with different tokenizers. Other applications of this technology include (i) byte-level knowledge distillation to transfer skills more effectively between models with different tokenizers, (ii) rapid post-training research leveraging the fact that a post-training recipe (represented by a pair of proxy-tuning experts) can be applied to any number of models without additional training, (iii) routing dynamically between models (Zheng et al., 2025) during generation without requiring matching tokenizers, and potentially (iv) more convenient LM-powered compression of byte streams. In general, whenever (mismatching) tokenizers represent an obstacle or inconvenience, our method has the potential to completely bypass it at the cost of (minimally) increased inference compute.”

Comparison with the submission

The ByteSampler paper presents a method for converting BPE-tokenized language models to byte-level models, supporting efficient and exact sampling and enabling model composition across different tokenizations. While this shares the high-level goal of transforming language models via deterministic mappings, ByteSampler is specifically designed for tokenization-related transformations and does not present a general framework for arbitrary FST-based string-to-string transformations. The submission's contribution is broader and more general, encompassing any deterministic FST, not just those arising from tokenization. Thus, the overlap is partial: the prior work covers a special case of the submission's framework but does not subsume it.

##### Language Models over Canonical Byte-Pair Encodings
substantial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper presents a framework for language modeling over canonical byte-pair encodings (BPE), where a language model over character strings is defined via a token-level language model and a decoding function. The encoding and decoding functions (τ and κ) are deterministic string-to-string mappings, and τ can be implemented as a finite-state transducer. The paper defines the probability of a character string as the sum over token strings that decode to it, and discusses conditioning the model to generate only canonical token strings (those that are valid BPE encodings of character strings). Algorithms for exact and approximate sampling from the canonicalized model are provided, including rejection sampling and importance sampling.

“6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs. 7More precisely, as a function of a length limit N, the fraction of canonical strings in the universal of token strings |{δ∈D : |δ|≤N}| |{δ∈∆∗: |δ|≤N}| decreases exponentially quickly.”

“The globally canonicalized language models gΣ and g are defined as the following probability distributions over Σ∗and ∆∗, respectively: gΣ(σ) def= g(τ(σ)) (6a) g(δ) def= Pr Y ∼p∆[Y = δ | Y ∈D] (6b) = PrY ∼p∆[Y = δ, Y ∈D] PrY ∼p∆[Y ∈D] (6c) = 1 Z p∆(δ)1{δ ∈D} (6d) where Z is the canonicality rate: Z def= Pr Y ∈p∆[Y ∈D] (6e) 6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs.”

“6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs. 7More precisely, as a function of a length limit N, the fraction of canonical strings in the universal of token strings |{δ∈D : |δ|≤N}| |{δ∈∆∗: |δ|≤N}| decreases exponentially quickly.”

Comparison with the submission

The prior paper presents a substantial overlap with the claimed contribution, as it defines language models composed with deterministic string-to-string functions (tokenization/decoding) implemented as finite-state transducers, and develops algorithms for exact and approximate inference. However, the prior work is focused specifically on tokenization (BPE) and canonicalization, whereas the submission claims a more general framework for arbitrary deterministic FST-based transformations and introduces new algorithms for tractable marginalization and autoregressive modeling. Thus, while the core idea is present in the prior work, the submission extends the scope and generality, and introduces new technical contributions.

##### From Language Models over Tokens to Language Models over Characters
substantial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper defines a framework for tokenized language models, where a language model over tokens (from an alphabet ∆) is composed with a deterministic decoding function κ: ∆* → Σ* to yield a language model over character strings. The probability of a character string σ is given by marginalizing over all token strings δ such that κ(δ) = σ. The paper provides algorithms for computing probabilities and conditional probabilities over character strings by summing over token sequences, leveraging properties of κ such as strict-prefix monotonicity. The framework is instantiated for common tokenization schemes like BPE and WordPiece, where κ is deterministic and can be represented as a finite-state transducer.

“A tokenized language model pΣ is a language model over Σ∗that is parameterized by a language model p∆over ∆∗and a decoding function κ: ∆∗→Σ∗. This tokenized language model generates character strings via the following process: (i) δ ∼p∆, (ii) σ ←κ(δ). Thus, the character strings σ generated have the distribution: pΣ(σ) def= P Y ∼p∆ [κ(Y ) = σ] (6) Note that pΣ(σ) accounts for the fact that many token strings may be associated with a given character string through κ.9 To describe that association, we define E(σ) def= {δ ∈∆∗: σ = κ(δ)}, the set of encodings for any character string σ ∈Σ∗.10 ## What about τ?”

“Thus, the character strings σ generated have the distribution: pΣ(σ) def= P Y ∼p∆ [κ(Y ) = σ] (6) Note that pΣ(σ) accounts for the fact that many token strings may be associated with a given character string through κ.9 To describe that association, we define E(σ) def= {δ ∈∆∗: σ = κ(δ)}, the set of encodings for any character string σ ∈Σ∗.10 ## What about τ?”

“This section gives algorithms for computing pΣ(σ), −→ pΣ(σ), −→ pΣ(σ′ | σ), −→ pΣ(EOS | σ), and conditional token generation. We assume throughout that κ is strict-prefix monotone. ## 3.1.”

Comparison with the submission

This prior paper presents a highly similar framework to the claimed contribution: it defines language models over outputs of deterministic string-to-string functions (decoders) applied to token sequences, and provides algorithms for marginalizing over tokenizations to compute probabilities over character strings. The main difference is that the prior work is framed specifically in terms of tokenization and decoding functions, while the submission may generalize to arbitrary deterministic FSTs and introduce new algorithmic techniques. The overlap is substantial, as the core idea of composing a language model with a deterministic transducer and marginalizing over preimages is present in both. However, unless the submission's framework or algorithms go significantly beyond tokenization or introduce fundamentally new techniques, the contribution is not entirely novel.

---

### Second extracted claim

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

**Verdict:** challenged by prior work

This claim is challenged by four prior works: "Language Models over Canonical Byte-Pair Encodings," "Understanding and Mitigating Tokenization Bias in Language Models," "From Language Models over Tokens to Language Models over Characters," and "Sampling from Your Language Model One Byte at a Time." All were compared against the full text and show substantial overlap, as each develops algorithms for composing a language model with a finite-state transducer to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters. The submission distinguishes itself by generalizing these algorithms to arbitrary FST-defined transformations (not just tokenization), introducing new decomposition techniques (precover, quotient, remainder), and providing a broader theoretical and algorithmic framework. The overlap is substantial for the core idea, but the submission's generalization and new algorithms are not fully covered by prior work.

#### What the submission does for this claim

The paper composes a source language model with an FST-defined string transformation and computes probabilities for target strings by aggregating source strings whose transformed outputs match the target. This composition is explicitly designed to preserve the pretrained model while exposing transformed-output conditioning.

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis.”

For a target prefix, the method represents the relevant source strings as a precover, then decomposes that set into source prefixes whose every continuation still covers the target and exceptional source strings that cover it only temporarily. A breadth-first search constructs this decomposition: it classifies each candidate as a quotient element, remainder element, or live prefix whose extensions must still be explored.

“Each dequeued string x undergoes three checks, defined in terms of the precover P(y): 1. Cylinder: is_cylinder(x, y) ⇐⇒ ⟨x⟩ ⊆ P(y), i.e., every extension of x covers y. x is added to the quotient set Q and not explored further (line 12). 2. Member: is_member(x, y) ⇐⇒ x ∈ P(y), i.e., x itself covers y. When is_cylinder is false but is_member is true, x is added to the remainder set R; its extensions are still explored (line 15). 3. Live: is_live(x, y) ⇐⇒ ∃x ′′ ∈ X * : xx ′′ ∈ P(y), i.e., some extension of x belongs to the precover. Only live extensions are enqueued (line 18). Because strings are processed shortest-first, if any prefix of the current string had already entered the quotient, the current string would never have been enqueued.”

The FST supplies the state structure for these checks. The paper first constructs a target-specific precover automaton by projecting away output labels, then determinizing and trimming it; the resulting state properties identify cylinders, members, and live prefixes. For efficiency, the implementation avoids materializing this automaton by maintaining frontiers of transducer states paired with output buffers compatible with the target.

“Given a target prefix y, proj X (f • yY * ) is an NFA that accepts exactly P(y). To enable the efficient state-based checks below, we determinize and trim this NFA to obtain a DFA: P y def = trim(determinize(proj X (f • yY * ))) Let S y , I y , F y , and T y denote the components of P y .”

“The frontier F = run y (x) collects this information: it is the set of (s, b) pairs-where s ∈ S is a transducer state and b ∈ Y * is the output produced so far-reachable by reading x from the initial states, filtered to buffers b compatible with y. 23 The frontier encodes all information needed for the three checks: is_cylinder, is_member, and is_live can each be evaluated from F alone, without retaining the full path history ( §C.2; Fig.”

Summing source prefix probabilities over the resulting decomposition yields target prefix probabilities, from which the paper derives next-symbol distributions, string probabilities, and conditional generation. When the decomposition is finite and the checks are unpruned, this procedure is exact; when it is too large, probability-mass pruning retains high-probability candidates to produce a terminating approximation and a lower bound.

“The primitive operation above is prefix_prob, which requires a single call to decompose. Both next_dist and prob are derived from it: next_dist computes |Y| additional prefix probabilities and obtains -→ p Y (EOS | y) by complement; prob is a one-line product. In an implementation, -→ p X and p X should be memoized so that extending -→ p X (x) to -→ p X (xx) requires only a single conditional evaluation rather than replaying the entire history (see §C.7).”

“As τ → 0 and n max → ∞, the algorithm converges to the exact decomposition. Even when the decomposition is finite, its size can be enormous.”

#### Overlapping prior work

##### Efficient Guided Generation for Large Language Models
partial overlap · Willard et al. · 2023

How this paper realizes the claim

The paper presents algorithms for guiding the generation of large language models (LLMs) by constraining their outputs to match regular expressions or context-free grammars, using finite-state machines (FSMs) and pushdown automata (PDAs).

“We frame the case of regular expression guided generation in terms of state machines. This framing allows us to specify exactly how regular expression matching can be arbitrarily started and stopped, so that it can be easily and efficiently continued between samples of ˜si+1, as well as how the masks can be computed without run-time evaluations over V. To be precise, we consider regular expressions in 5-tuple finite automaton form [Sipser, 1996, Definition 1.5]: Definition 1 (Finite Automaton).”

The approach involves tracking the state of an FSM during token sampling, masking out invalid next tokens, and efficiently updating the FSM state as new tokens are generated. The paper also describes preprocessing the vocabulary with the FSM to build an index for efficient masking.

“These FSM states can then be tracked during the LLM token sampling process in Algorithm 2 and used to efficiently continue the state machine without reading from the beginning of the growing sample sequence each time. 5 Example 1.”

The method is extended to context-free grammars by using PDAs, allowing for parser-guided generation. The algorithms focus on efficiently determining valid next tokens at each generation step, given the current FSM/PDA state and the generated prefix.

Comparison with the submission

This prior paper presents algorithms for guiding LLM generation using FSMs and PDAs, focusing on constraining outputs to match regular expressions or grammars by masking invalid tokens and efficiently updating automaton states. While both works use automata to guide or constrain language model outputs, the prior paper does not address the marginalization of source-string probabilities into target outputs via FSTs, nor does it enable conditioning on transformed outputs in the probabilistic sense described in the claim. The overlap is partial: the prior work covers efficient automaton-guided generation, but not the probabilistic marginalization or output conditioning central to the submission.

##### Where is the signal in tokenization space?
partial overlap · Geh et al. · 2024

How this paper realizes the claim

The paper studies the problem of marginalizing over all possible tokenizations of a string under a language model, i.e., computing the total probability of a string by summing over all token sequences that yield it. It formalizes this as the 'marginal string probability' problem and proves it is #P-hard. The paper then proposes and empirically evaluates approximate algorithms for estimating this marginal probability using sequential importance sampling, with a proposal distribution that prunes inconsistent tokenizations via a multi-valued decision diagram (MDD). The focus is on the tokenization ambiguity induced by subword tokenizers (like BPE) and how to aggregate probabilities over all tokenizations for a given string.

“Evaluating the probability of a string requires marginalizing over all its possible tokenizations. We now formally define this task and show it to be computationally hard. Problem 5.1 (Marginal String Probability). Let v denote a token sequence. Given a string x and an autoregressive LLM p, the marginal string probability problem is to compute p(x) = X v p (v, x) . Theorem 5.2.”

“In light of the above hardness results, we now shift our attention to approximating the marginal string probability. In particular, we will focus on estimators based on sequential importance sampling (Kloek and van Dijk, 1978; Geweke, 1989). In this instance of importance sampling, we sample tokenizations v given a string x according to some proposal distribution q(v|x). Given a set of samples v(1), . . . , v(N) from this distribution, an estimate of the marginal string probability p(x) is p(x)=Ev∼q(v|x) [p(x, v)/q(v|x)] ≈1/N ∑_{i=1}^N p(x, v(i))/q(v(i)|x) .”

“This can be done efficiently by simply traversing the MDD compiled from the string and masking out all tokens that are not compatible with the labels of the outgoing edges at the current node. Formally, the proposal distribution is qLA(v|x) := |v| Y j=1 qLA(vj|v1:j−1, x), where qLA(vj|v1:j−1, x) ∝p(vj|v1:j−1)vv1:j |= x1:w.”

Comparison with the submission

This prior paper addresses the marginalization of language model probabilities over all tokenizations of a string, using MDDs to represent the set of tokenizations and proposing approximate inference algorithms. However, it is limited to the special case where the FST is the tokenization process, and does not address arbitrary FST-defined transformations, conditioning on transformed outputs, or provide exact algorithms. The submission is broader in scope, supporting general FSTs and enabling new forms of conditioning and inference. Thus, the overlap is partial: the prior paper covers a special case of the submission's contribution, but not its full generality or algorithmic advances.

##### Language Models over Canonical Byte-Pair Encodings
substantial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper addresses the problem of language modeling over tokenized strings, specifically focusing on canonical and noncanonical encodings (e.g., BPE tokenizations). It considers the probability distribution over character strings induced by a language model over token strings, where the mapping from characters to tokens is many-to-one and can be implemented as a finite-state transducer (FST).

“6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs. 7More precisely, as a function of a length limit N, the fraction of canonical strings in the universal of token strings |{δ∈D : |δ|≤N}| |{δ∈∆∗: |δ|≤N}| decreases exponentially quickly.”

The paper develops algorithms for conditioning a language model to generate only canonical token strings, which involves renormalizing the probability distribution over the set of canonical outputs. It presents both exact (rejection sampling) and approximate (local canonicalization, importance sampling) algorithms for sampling from this conditioned distribution, and discusses how to estimate probabilities and sample efficiently.

“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition 1.”

“We will discuss the details of how to approximately and exactly generate samples from g. ## Why do we condition?”

The algorithms do not require changing the parameters of the underlying language model, but instead modify the sampling or probability computation process to enforce canonicality constraints. The FST is used to define the set of canonical outputs, and the algorithms marginalize over token strings that map to a given character string via the FST.

“Note that gΣ(σ) = 1/Z p∆(τ(σ)), meaning that we may interpret the globally canonicalized model as renormalizing p′Σ. We note that the effect of conditioning the language model to generate only canonical token strings may dramatically change the conditional prefix distributions of the distribution.”

The paper also describes how to use importance sampling and resampling to estimate probabilities and generate samples from the conditioned distribution, again without modifying model parameters.

Comparison with the submission

This prior paper presents algorithms for composing a language model with a finite-state transducer (specifically, a tokenization FST) to marginalize over source strings and compute probabilities for target outputs, using both exact and approximate inference methods, all without changing model parameters. This matches the core of the claimed contribution, though the prior paper is focused on canonicalization (e.g., BPE) as the transformation. The submission's delta lies in generalizing the approach to arbitrary FSTs and introducing new algorithmic techniques for efficient marginalization and conditioning. Thus, the overlap is substantial, but the submission still adds new generality and algorithmic contributions.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper studies how to compute the probability of a word (or word sequence) given a language model defined over subwords, where the mapping from words to subwords is defined by a tokenization function. It formalizes the relationship between word and subword probabilities, showing how to marginalize over subword sequences that correspond to a given word sequence.

“The implication of eq. (8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. Formally, we define the set equivalence ∆= between two sets of sequences as: ΨW ∆= ΨS =⇒  w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS  (9) Now let PS be a probability function defined analogously to PW (in Defn.”

The paper provides algorithms and lemmas for efficiently computing these probabilities, leveraging the autoregressive property of language models. It discusses how to construct the relevant sets of subword sequences and how to sum their probabilities to obtain the probability of a word or word prefix.

“We must thus find a more efficient strategy to compute these probabilities than summing over the (also infinite) sets Ψ′ S and Ψ′′ S. they will thus not be exact in this sense.”

The paper does not use general finite-state transducers (FSTs) for arbitrary string transformations, but rather focuses on the specific case of tokenization/detokenization mappings between words and subwords. The algorithms are tailored to this setting and do not address conditioning on arbitrary transformed outputs or supporting general FST-defined transformations.

Comparison with the submission

This prior paper addresses the marginalization of language model probabilities over subword sequences that map to a given word sequence, specifically in the context of tokenization. While it develops efficient algorithms for this special case, it does not generalize to arbitrary FST-defined transformations or support conditioning on arbitrary transformed outputs. The submission extends these ideas to the more general and challenging setting of arbitrary FSTs, providing new algorithms and theoretical analysis. Thus, the overlap is partial: the prior paper covers a special case, but the submission's contribution is broader and more general.

##### Understanding and Mitigating Tokenization Bias in Language Models
substantial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper proposes algorithms (Maximum Prefix Correction, MPC, and Byte-Pair Correction, BPC) to compute the probability of a string in the original character space using a language model trained on tokenized text. The algorithms marginalize over all possible tokenizations (encodings) of a given string, aggregating the probabilities assigned by the language model to each valid encoding. This is done without modifying the language model parameters, but by algorithmically summing over the possible token sequences that decode to the target string.

“Our method consists of two stages. In the first stage, the idea is to identify the condition when P(xN n+1|ti 1) = P(xN n+1|xn 1) where ti 1 = encode(xn 1). Once identified, we can refactor the conditional probability to match the conditioning events. In the second stage, we compute P(xN n+1|ti 1) using the LM output probability, i.e. P(ti+1|ti 1), through the novel Maximum Prefix Correction (MPC) Algorithm. ## 3.1.”

“We present the MPC algorithm in Algorithm 1, that allows us to compute the probabilities P(xN nk+1|tk 1) and P(xn nk+1|tk 1) in Equation (1). Note that this algorithm does not require tk∈V∗. Details on the algorithmic correctness are shown in Appendix E. 3Many current language models begins with a start token <start> in V∗, e.g.”

“The idea is to marginalize out P(xN nk+1|tk 1) by considering two complementary events: when the next token tk+1 has a prefix xN nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN nk+1 (pval in the Pass Step). Formally, MPC computes the following probabilities: bval = P(xN nk+1, tk+1 ∈B(xN nk+1)) tk 1), (2) pval = P(xN nk+1, tk+1 /∈B(xN nk+1)) tk 1), (3) where B(xN nk+1)={t∈V|xN nk+1∈prefix(decode(t))} and we immediately see that P(xN nk+1|tk 1)=bval+pval.”

“The BPC algorithm can also be applied for the case of MPE. In fact, it is more general than the original MPC algorithm as it only relies on the property of invalid encodings. 15 Understanding and Mitigating Tokenization Bias in Language Models Algorithm 2 Byte-Pair Correction Algorithm.”

Comparison with the submission

This prior paper presents algorithms (MPC and BPC) that marginalize over all tokenizations of a string to compute its probability under a token-based language model, which is a special case of composing a language model with a finite-state transducer (the tokenizer). The core idea of marginalizing source-string probabilities into target outputs without changing model parameters is present and algorithmically realized. However, the submission extends this idea to arbitrary FST-defined transformations, not just tokenization, and introduces new algorithmic techniques for efficient decomposition and inference. Thus, the overlap is substantial, but the submission has a clear delta in generality and algorithmic approach.

##### From Language Models over Tokens to Language Models over Characters
substantial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper develops algorithms for composing a language model (over tokens) with a deterministic mapping (kappa) to another string space (e.g., characters), and computes probabilities for target strings by marginalizing over all source token strings that map to the target. This is achieved via the concept of 'covering' and efficient enumeration algorithms (enum_cover) that sum over all token strings whose decoded output covers the target string.

“Eq. (11) shows that we can, in principle, compute the prefix probability −→ pΣ(σ) by summing over prefix-encodings of σ, P(σ) def= {δ ∈∆∗: κ(δ) ⪰σ}. Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

“Our algorithm enum_cover performs recursive enumeration of the members of the covering C(σ) along with some metadata. Specifically, the algorithm returns a collection of triples where each triple (p′, σ′, δ′) satisfies δ′ ∈C(σ), p′ = −→ p∆(δ′), and σ′ = κ(δ′).”

The paper provides both exact and approximate (beam search) algorithms for this marginalization, and discusses their computational complexity and implementation details.

“We propose a heuristic based on beam search. This heuristic is very effective: it gives us a linear running time as a function of the character string’s length. It has a parameter K that controls the approximation quality. Larger K makes the approximation more accurate, and the approximation becomes exact as K approaches the size of the (largest intermediate) covering. We take K to be a global variable in the pseudocode.”

The algorithms allow for conditioning on transformed outputs (e.g., generating token strings that map to a given character prefix), and do so without changing the underlying language model parameters.

“This section gives a simple algorithm for correctly generating a token string Y that has a given character-level prompt σ as its prefix. This algorithm is equivalent to the algorithm in the introduction but significantly faster. The algorithm works by enumerating the covering C(σ), drawing a token string from it in proportion to its prefix probability, and finishing the token string by sampling a completion, which can be done from the token-level model. 43 def conditional_token_generation(σ): 44 δ′ ∼Categorical({δ′ : p′/−→ pΣ(σ) 45 for (p′, _, δ′) in enum_cover(σ)}) 46 return sample_completion(δ′) 47 def sample_completion(δ′): 48 δ′′ ←ε 49 while True: 50 δ ∼−→ p∆(· | δ′·δ′′) 51 if δ = EOS: break 52 δ′′ ←δ′′·δ 53 return δ′·δ′′ 7 From Language Models over Tokens to Language Models over Characters (a) Error (JSD/byte) vs.”

Comparison with the submission

This prior paper presents algorithms that compose a language model with a deterministic string transducer (kappa), marginalizing over source strings to compute probabilities for target outputs, and enabling conditioning on transformed outputs, all without modifying model parameters. It provides both exact and approximate (beam search) algorithms for this purpose. The overlap with the claimed contribution is substantial, as the core algorithmic ideas and goals are the same. However, if the submission extends to more general FSTs, introduces new decomposition techniques, or provides additional theoretical insights, it may still have a meaningful delta. Otherwise, the core contribution is already substantially addressed by this prior work.

##### Sampling from Your Language Model One Byte at a Time
substantial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces ByteSampler, a method for sampling from language models at the byte level, particularly to address the prompt boundary problem when using BPE tokenizers. The core mechanism is the Valid Covering Tree (VCT), which represents all valid token sequences whose decodings cover a given byte-string prefix. The VCT is constructed to efficiently enumerate and score all tokenizations that match a given byte prefix, allowing for exact computation of probabilities and sampling of next bytes or completions.

“The Valid Covering Tree of P, denoted VCT(P), is the tree of all finite token sequences T = [t1, . . . , tn] such that: 1. P is a prefix of decode(T), 2. decode(t1, . . . , tn−1) is a prefix of P, and 3. T is a valid token sequence. Condition 1 ensures that the token sequence covers the prompt, Condition 2 ensures that it minimally covers the prompt (i.e., only the final token straddles the end of the prompt), and Condition 3 enforces token sequence validity (i.e., that it is in the output space of encode).”

The VCT is used to aggregate probabilities over all tokenizations that match a given byte prefix, enabling exact computation of next-byte distributions and prefix probabilities. The method preserves the language model's output distribution (modulo invalid token sequences) and does not require changing model parameters.

“The VCT T for a given a byte-string S can be used to efficiently perform various byte-level language modeling tasks. We use “ByteSampler” to refer to this collection of routines. prefix: h y p o t ?”

The method supports exact inference (and some approximate variants), and is compatible with standard pretrained language models and tokenizers. The approach is described as a composition of the language model with the tokenizer's decoding function, but is not framed in terms of general finite-state transducers (FSTs) beyond the tokenizer.

Comparison with the submission

This prior paper (ByteSampler) presents a substantial overlap with the claimed contribution: it develops algorithms that compose a language model with the tokenizer's decode function (a finite-state process) to marginalize over all tokenizations matching a given byte prefix, enabling conditioning on transformed outputs and supporting exact inference. However, the scope of ByteSampler is limited to tokenization, whereas the submission claims a more general framework for arbitrary FST-defined transformations. Thus, while the core idea and algorithmic structure are similar, the submission extends the approach to a broader class of transformations and provides a more general theoretical treatment.

---

### Third extracted claim

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

**Verdict:** not challenged in the examined literature

This claim is not challenged by any examined prior work. The closest examined papers, such as "Automata-based constraints for language model decoding" and "Efficient Guided Generation for Large Language Models," were compared against the full text but only superficially overlap, as they focus on applications of automata theory or guided generation rather than providing theoretical conditions for finite prefix decompositions in transducers. No prior work addresses the specific theoretical contribution of sufficient transducer-level conditions for finite prefix decompositions, so the novelty of this claim holds within the examined literature.

#### What the submission does for this claim

The paper represents each target prefix with a quotient of source prefixes whose entire cylinders cover the target, plus a remainder for source strings that cover the target without all their extensions doing so.

“We call the pair (Q(y), R(y)) the optimal prefix decomposition of P(y), characterized by three conditions: (i) Q(y) is prefix-free, (ii) P(y) = ⟨Q(y)⟩ ⊔ R(y) (validity), and (iii) ⟨Q(y)⟩ = C(y) (maximality)-Q(y) identifies the largest cylinder in P(y). This decomposition (indeed, any valid one) lets us compute prefix probabilities using the shortcut: §5 provides an algorithm for computing the prefix decomposition; §6 identifies when it is finite.”

This construction does not require prefix monotonicity: the remainder explicitly handles the cases where coverage is lost after extending a source string.

“Second, by introducing the remainder, we can handle functions that are not prefix monotone, meaning that there can be source strings that cover the target, but not all of their extensions do (e.g., Example 2). Lemma 6.1 gives sufficient conditions on a transducer that guarantee a finite decomposition for every target string, even when the underlying function is not prefix monotone.”

The transducer-level guarantee is Lemma 6.1: for every target, the decomposition is finite when the transducer has no cycles made entirely of ε-output arcs and every state satisfies the inductive safety condition.

“Lemma 6.1. Let f : X * → Y * be a function realized by a transducer f. The decomposition (Q(y), R(y)) is finite for every y ∈ Y * if: (i) No ε-output cycles: f contains no cycle in which every arc outputs ε. (ii) Safety: Every state of f is safe, defined inductively as the smallest set such that s is safe if: (a) s is IP-universal; (b) | f [s] | < ∞ (finite closure); or (c) for all transitions s x:y --→ s ′ , s ′ is safe. Proof: See §D.3.”

Here IP-universality supplies unrestricted continuations, while finite closure supplies a finite set of possible remaining outputs.

“We say that a state s is IP-universal (input-projection universal) if proj X (f [s] ) = X * , i.e., no matter what input follows, the transducer can still produce output. Let U ⊆ S denote the set of IP-universal states; this set can be precomputed for each transducer ( §C.6).”

The proof makes the two finiteness arguments explicit: the absence of ε-output cycles bounds paths that emit a fixed target, and safety prevents the subsequent extension tree from continuing indefinitely; finite-closure states then contribute only finitely many remainder strings.

“By condition (i), the ε-output subgraph of f is acyclic, so any sub-path that emits no output has length at most |S|. Since the total output is y, each path has bounded length, and Π y is finite. Let Π ⪰y be the set of all valid paths formed by extending the roots in Π y until they reach a state satisfying a safety base case.”

“By condition (ii), every state of f is safe-in particular, the end states of paths in Π y . This implies that no extension path can continue indefinitely without satisfying a base case (IP-universality or finite closure). Since a finite-state transducer has finite branching and no infinite valid extension paths, Kőnig's Lemma implies that the tree of extensions is finite. 27 Thus, Π ⪰y is a finite set.”

#### Overlapping prior work

None found among the 24 papers compared.

---

### Fourth extracted claim

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

**Verdict:** challenged by prior work

This claim is challenged by "Understanding and Mitigating Tokenization Bias in Language Models," which was compared against the full text and shows substantial overlap. Both the submission and this prior work present algorithms for inference-time adaptation of pretrained language models to operate over bytes or characters by marginalizing over possible tokenizations, without retraining. However, the submission claims to generalize this approach to arbitrary string transformations via finite-state transducers, enabling adaptation not just to bytes but also to words and amino acids, and provides a general algorithm for composing a language model with an FST. The prior work does not explicitly address adaptation to words and amino acids or arbitrary FST-based transformations, so the submission's broader generalization remains a differentiator.

#### What the submission does for this claim

The paper keeps the pretrained source language model fixed and composes it at inference time with a finite-state transducer (FST) describing the desired string transformation. It computes target-prefix probabilities by summing the probabilities of source strings whose transducer outputs cover the target prefix, thereby exposing next-symbol probabilities and conditioning over the transformed units.

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis.”

The implementation decomposes each target precover into a maximal cylindrical quotient and a remainder, using breadth-first search with cylinder, membership, and liveness checks. It supports exact computation when the decomposition is finite, and an inference-time approximation that prunes low-probability candidates; frontiers, lazy determinization, cached decompositions, and joint next-symbol decomposition make repeated autoregressive queries practical.

“We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

The three demonstrations instantiate this same mechanism with separate FSTs: a token-to-byte machine, a contextual Penn Treebank word-boundary machine, and a DNA-to-amino-acid machine, while using pretrained models over the corresponding source alphabets.

“we construct FSTs for the three use cases above: (i) converting tokens to bytes, (ii) inserting orthographic boundaries following the Penn Treebank tokenizer, and (iii) converting DNA sequences to sequences over amino acids. We then employ commonly used pretrained language models over the input units of the FSTs, and compose them with the FSTs to obtain language models over the output tokens.”

For bytes, the transducer has a chain for each source token; for words, tokenizer rules insert separators at punctuation and clitic boundaries and collapse whitespace; for proteins, the transducer maps the four DNA nucleotides through codon-level paths to amino-acid outputs. The resulting models are therefore obtained by inference-time composition rather than parameter updates.

“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining. Our theoretical analysis characterizes the conditions under which such mappings can be performed exactly.”

#### Overlapping prior work

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

This paper addresses the problem of evaluating and sampling from language models over canonicalized string representations, specifically focusing on canonical byte-pair encodings (BPE). It proposes methods to condition a pretrained language model to generate only canonical token strings, both exactly (via rejection sampling) and approximately (via local approximations and importance sampling), without retraining the model.

“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition 1.”

“We will discuss the details of how to approximately and exactly generate samples from g. ## Why do we condition?”

“The simplest exact conditioning algorithm for sampling from g is rejection sampling: 1 def rejection_sampling(): 2 while True: 3 δ ∼p∆ 4 ## if δ ∈D: return δ However, the rejection sampling algorithm can be inefficient if Z is small, as its expected running time per sample is O(1/Z).”

“Our locally canonicalized model ℓis a distribution over ∆∗that approximates ancestral_sampling for sampling from g by using the following local approximation −→ℓto the global prefix probability −→g . ## Definition 2.”

“These methods use the local distributions as a proposal distribution to produce candidates that will be properly weighted and resampled in a manner so that they maintain a principled approximation to the global distribution g. Therefore, in expectation and in the limit, these methods produce exact samples; thus, they do not warp the distribution. The warping in the locally canonicalized method can occur because the sampling algorithm approximated the conditional prefix probability canonicality, meaning that we may sample a string of tokens that looks good initially, but we end up stuck with a bad string prefix because we overestimated the conditional prefix probability.”

Comparison with the submission

This prior paper presents methods for conditioning pretrained language models to generate only canonical token strings, specifically focusing on canonical BPE, using rejection sampling, local approximations, and importance sampling. While it shares the high-level goal of inference-time adaptation without retraining, its scope is limited to canonicalization and does not generalize to arbitrary FST-based transformations or multiple domains (bytes, words, amino acids) as in the submission. The submission's contribution is broader and more general, providing new algorithms and practical inference-time mechanisms for a wider range of transformations. Thus, the overlap is partial, and the prior paper cannot refute the submission's claim.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper presents ByteSampler, a method for converting off-the-shelf, pretrained language models (LMs) into character- or byte-level language models at inference time, without retraining or modifying the model parameters. The core mechanism is the Valid Covering Tree (VCT), which efficiently enumerates all token sequences that cover a given byte-string prefix, allowing the computation of next-byte or next-character distributions by summing over the probabilities of all tokenizations that yield the desired prefix.

“In this section, we describe the core mechanism behind ByteSampler. In Section 3.1 we define the Valid Covering Tree (VCT), an object containing all of the token sequences that cover a prompt. In Section 3.2, we show how the VCT can then be used to perform standard language modeling tasks: computing prefix probabilities, sampling completions while avoiding the prompt boundary problem, and computing next-byte distributions. In Section 3.3, we show that the VCT has bounded size, leading to low inference costs.”

“Character-Level Language Modeling In this section, we will focus on converting off-the-shelf language models into character-level language models.10 We then evaluate the character-level prediction performance using the standard cross-entropy loss as well as next-character prediction accuracy in two languages: English in Section 4.2.1 and Chinese in Section 4.2.2. 4.2.1 OLMO2 FOR ENGLISH TEXT In this setting, we sample a document randomly from the OLMO2 pretraining corpus (OLMo et al., 2024) and choose a random prefix of length at most 1000 characters.”

The method is demonstrated for byte-level and character-level adaptation, including for English and Chinese text. The approach is exact (preserves the model's output distribution modulo invalid token sequences), efficient, and compatible with BPE tokenizers. However, the paper does not demonstrate adaptation to word-level outputs or to non-text domains such as amino acids.

Comparison with the submission

This paper (ByteSampler) presents a method for inference-time adaptation of pretrained LMs to bytes and characters, closely matching part of the submission's claim. However, it does not address adaptation to words or amino acids, nor does it present a general FST-based framework for arbitrary string transformations. The overlap is therefore partial: the core idea of inference-time adaptation to bytes/characters is shared, but the submission's broader scope and generalization to other domains and transformations represent a significant delta.

##### Understanding and Mitigating Tokenization Bias in Language Models
substantial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper proposes algorithms (Maximum Prefix Correction, MPC, and Byte-Pair Correction, BPC) to correct for tokenization bias in language models by enabling the computation of probabilities over character (or byte) sequences using a pretrained, fixed token-based language model. The algorithms marginalize over all possible tokenizations (encodings) that could produce a given character sequence, allowing the model to output probabilities for arbitrary strings at the character or byte level, without retraining the model.

“We propose a method to remove the described bias and recover the original token-free autoregressive model, i.e. expressing the implicitly learned P(xN n+1|xn 1) using the tokenized LM that outputs the conditional probability P(ti+1|ti 1). For N=n+1, this captures the behavior of a token-free model, i.e.”

“We present the MPC algorithm in Algorithm 1, that allows us to compute the probabilities P(xN nk+1|tk 1) and P(xn nk+1|tk 1) in Equation (1). Note that this algorithm does not require tk∈V∗. Details on the algorithmic correctness are shown in Appendix E.”

“The idea is to marginalize out P(xN nk+1|tk 1) by considering two complementary events: when the next token tk+1 has a prefix xN nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN nk+1 (pval in the Pass Step). Formally, MPC computes the following probabilities: bval = P(xN nk+1, tk+1 ∈B(xN nk+1)) tk 1), (2) pval = P(xN nk+1, tk+1 /∈B(xN nk+1)) tk 1), (3) where B(xN nk+1)={t∈V|xN nk+1∈prefix(decode(t))} and we immediately see that P(xN nk+1|tk 1)=bval+pval.”

“We begin by introducing the Byte-Pair Correction (BPC) Algorithm for bias correction in Byte-Pair Encoding, which is more general than the MPC algorithm and also works for case of MPE. We then follow with a detail analysis to show the correctness of the algorithm.”

“The BPC algorithm can also be applied for the case of MPE. In fact, it is more general than the original MPC algorithm as it only relies on the property of invalid encodings. 15 Understanding and Mitigating Tokenization Bias in Language Models Algorithm 2 Byte-Pair Correction Algorithm.”

Comparison with the submission

This prior paper presents a substantial overlap with the claimed contribution: it demonstrates inference-time adaptation of pretrained language models to bytes (and, by extension, characters) without retraining, using algorithms that marginalize over tokenizations. However, the submission appears to generalize this idea to arbitrary FST-based transformations, including adaptation to words and amino acids, which is not covered in the prior paper. Thus, while the core idea of inference-time adaptation to bytes/characters is present here, the submission's broader generalization and application to other domains (words, amino acids) via FSTs is a meaningful delta.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper presents algorithms for adapting pretrained language models (LMs) over tokens to operate over characters at inference time, without retraining the LM. It describes how to compute character-level prefix probabilities by summing over token-level encodings that cover the character prefix, and provides both exact and approximate (beam search) algorithms for this computation.

“This section gives algorithms for computing pΣ(σ), −→ pΣ(σ), −→ pΣ(σ′ | σ), −→ pΣ(EOS | σ), and conditional token generation. We assume throughout that κ is strict-prefix monotone.”

“Eq. (11) shows that we can, in principle, compute the prefix probability −→ pΣ(σ) by summing over prefix-encodings of σ, P(σ) def= {δ ∈∆∗: κ(δ) ⪰σ}. Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

“Our algorithm enum_cover performs recursive enumeration of the members of the covering C(σ) along with some metadata. Specifically, the algorithm returns a collection of triples where each triple (p′, σ′, δ′) satisfies δ′ ∈C(σ), p′ = −→ p∆(δ′), and σ′ = κ(δ′).”

“We propose a heuristic based on beam search. This heuristic is very effective: it gives us a linear running time as a function of the character string’s length. It has a parameter K that controls the approximation quality. Larger K makes the approximation more accurate, and the approximation becomes exact as K approaches the size of the (largest intermediate) covering. We take K to be a global variable in the pseudocode.”

“This section gives algorithms for computing the characterlevel conditional prefix probability. Recall the definition of the character-level conditional prefix probability, that is, Eq. (8) and (9), can be computed from a certain ratio of calls to −→ pΣ (and pΣ in the case of EOS). From here, Eq.”

“This section gives a simple algorithm for correctly generating a token string Y that has a given character-level prompt σ as its prefix. This algorithm is equivalent to the algorithm in the introduction but significantly faster. The algorithm works by enumerating the covering C(σ), drawing a token string from it in proportion to its prefix probability, and finishing the token string by sampling a completion, which can be done from the token-level model. 43 def conditional_token_generation(σ): 44 δ′ ∼Categorical({δ′ : p′/−→ pΣ(σ) 45 for (p′, _, δ′) in enum_cover(σ)}) 46 return sample_completion(δ′) 47 def sample_completion(δ′): 48 δ′′ ←ε 49 while True: 50 δ ∼−→ p∆(· | δ′·δ′′) 51 if δ = EOS: break 52 δ′′ ←δ′′·δ 53 return δ′·δ′′ 7 From Language Models over Tokens to Language Models over Characters (a) Error (JSD/byte) vs.”

Comparison with the submission

This prior paper presents inference-time adaptation of token-level language models to characters/bytes, using algorithms that marginalize over tokenizations, and provides both exact and approximate solutions. However, it is limited to monotonic token-to-character/byte mappings and does not address more general string transformations or other domains such as word segmentation or DNA-to-amino-acid translation. The submission extends the idea to arbitrary FST-based transformations, enabling adaptation to a wider range of output units and tasks. Thus, the overlap is partial: the prior paper covers only a subset (token-to-character/byte) of the submission's broader contribution.

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

# Assessment B

> This is one system's assessment of the paper's novelty. Several systems assessed the
> same paper; they are presented in a common wrapper so that presentation does not decide
> the comparison. The text below is each system's own, unedited and complete: it was not
> shortened, reordered or rewritten, so the systems differ in length and structure.
>
> Where a system marks verbatim quotations, they appear in quotation marks; unmarked text
> is that system's own prose.

---

**TRANSDUCING LANGUAGE MODELS**

Publication date: 2026-03-05

## Extracted claims

### Extracted Claim 1

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

Evidence in paper:

“We formalize this perspective and introduce a general framework for language models derived from deterministic string-to-string transformations. We focus on transformations representable as finite-state transducers-a commonly used state-machine abstraction for efficient string-to-string mappings. We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs.”

### Extracted Claim 2

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

Evidence in paper:

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

### Extracted Claim 3

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

Evidence in paper:

“Lemma 6.1 gives sufficient conditions on a transducer that guarantee a finite decomposition for every target string, even when the underlying function is not prefix monotone. The key notion is safety: a state is safe if it is IP-universal, has finite closure (i.e., | f [s] | < ∞), or all its successors are safe.”

### Extracted Claim 4

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

Evidence in paper:

“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining. Our theoretical analysis characterizes the conditions under which such mappings can be performed exactly.”

## Related work examined

10 papers were read in full and compared against the claims above; the rest of the retrieved pool ranked below the level at which a paper could still challenge a claim.

- Automata-based constraints for language model decoding — no overlap of contribution
- Differentiable Weighted Finite-State Transducers — partial overlap
- Efficient Guided Generation for Large Language Models — no overlap of contribution
- From Language Models over Tokens to Language Models over Characters — substantial overlap
- Language Models over Canonical Byte-Pair Encodings — no overlap of contribution
- Neural Finite-State Transducers: Beyond Rational Relations — no overlap of contribution
- Sampling from Your Language Model One Byte at a Time — partial overlap
- Understanding and Mitigating Tokenization Bias in Language Models — substantial overlap
- Weighting Finite-State Transductions With Neural Context — no overlap of contribution
- Where is the signal in tokenization space? — unrelated to the claim

## Overall assessment

Claims 1 and 2 are substantially challenged by prior work: "From Language Models over Tokens to Language Models over Characters" already defines a target-string distribution by composing a source LM with a deterministic string-to-string mapping and gives marginalization algorithms, and "Sampling from Your Language Model One Byte at a Time" similarly marginalizes token-sequence probabilities to obtain character/byte output distributions while preserving the pretrained LM; the submission’s novelty over these is primarily in generalizing the mapping to arbitrary finite-state transducers and in proposing a broader theoretical decomposition (maximal cylindrical subsets and remainders) together with a claimed exact algorithm and a BFS-based precover decomposition (quotient/remainder/live classifications), but the evidence that these generalizations and algorithmic variants materially advance beyond the prior exact/approximate marginalization approaches is thin. Claim 3 (the paper’s sufficient transducer-level conditions that guarantee finite prefix decompositions, including non-prefix-monotone transformations) stands — it was not challenged. Claim 4 (inference-time adaptation of pretrained LMs to bytes, words, and amino acids without retraining) is challenged by "Understanding and Mitigating Tokenization Bias in Language Models" and "Language Models over Canonical Byte‑Pair Encodings", which already compute target‑prefix/next‑symbol probabilities and perform inference‑time conditioning; the submission still adds an explicit FST framing, an FST-based decomposition (maximal cylindrical quotient + remainder), and an explicit composition algorithm to compute target‑prefix probabilities, but the empirical novelty for adaptation without retraining is limited given the overlapping prior demonstrations.

## Review

---

### First extracted claim

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

**Verdict:** challenged by prior work

1 of the 7 papers examined for this claim challenge it. Examination stopped because: remaining candidates below threshold.

#### From Language Models over Tokens to Language Models over Characters

**Substantial overlap.** gives exact and approximate algorithms to convert token-level LMs to character-level ones, effectively transforming LM distributions across string representations

The prior paper presents the same kind of construction for turning a token-level LM into a character-level LM via a deterministic decoding κ and gives explicit algorithms to enumerate minimal token prefixes (the covering), sum probabilities, and compute next-character distributions, including pruning heuristics. This substantially overlaps the submission’s goal of marginalizing source strings that map to target prefixes, but the submission generalizes to arbitrary finite-state transducers and introduces a different theoretical decomposition and additional algorithmic/analytical results. Because the core computational idea and algorithms for marginalizing over source encodings are already present in the prior paper, the overlap is substantial though not identical in scope or generality.

The submission states:

“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X . Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y. Unfortunately, evaluating p Y (y) exactly using Eq.”

The prior work states:

“Eq. (11) shows that we can, in principle, compute the prefix probability −→ pΣ(σ) by summing over prefix-encodings of σ, P(σ) def= {δ ∈∆∗: κ(δ) ⪰σ}. Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set. Let δ ∈∆∗, δ1 ··· δM = δ, and σ ∈Σ∗. We say that δ covers σ if and only if κ(δ) ⪰σ. Monotonicity ensures that for all δ ∈P(σ), we have that ∀δ′ ∈∆∗: κ(δ·δ′) ⪰σ. In other words, any δ that decodes to an extension of σ (i.e., κ(δ) ⪰σ) will continue to do so if we append tokens to it. Thus, we may additionally qualify the relationship as δ minimally covers σ if additionally κ(δ1 ··· δM−1) ≺σ. With that in mind, we define ϕσ(δ) as the shortest prefix δ′ ⪯δ such that κ(δ′) ⪰σ, i.e., ϕσ maps any δ that covers σ to a (possibly equal) token string that minimally covers σ. Next, we define the set of minimal prefix encodings of σ, which we call the covering of σ, C(σ) def= {ϕσ(δ) | δ ∈P(σ)}. A more convenient expression for the covering C(σ) of a 5 From Language Models over Tokens to Language Models over Characters string σ ∈Σ∗is equal to the following subset of ∆∗: C(σ) =      {ε} if σ = ε {δ1 ··· δM ∈∆+ : ## otherwise κ(δ1 ··· δM−1) ≺σ ⪯κ(δ1 ··· δM)} (12) Example 2.”

Both passages state the same core construction: marginalizing a target-prefix probability by summing over (potentially infinite) source encodings and reducing that sum to a finite enumeration of minimal source prefixes (the covering) to compute prefix and next-symbol probabilities.

What the submission adds beyond it: The submission frames the mapping as a general finite-state transducer and develops a broader theoretical decomposition (maximal cylindrical subsets and remainders), claims an exact algorithm plus an efficient approximation and analysis for arbitrary FSTs, whereas the prior paper focuses specifically on token→character decoding via a tokenizer function κ and gives concrete enumeration and pruning algorithms for that setting.

#### Examined, partial overlap only

Each of these delivers a piece of what the claim promises without challenging it:

- Sampling from Your Language Model One Byte at a Time — Both works compute prefix/next-token probabilities and sample outputs by marginalizing over multiple tokenizations/source sequences that map to the same target byte-prefix The submission adds: The claimed paper formalizes a general framework of composing a source LM with an arbitrary deterministic string-to-string finite-state transducer (FST) to obtain a transduced
- Differentiable Weighted Finite-State Transducers — Both works use finite-state transducers and composition to map between input and output string spaces, compute forward (marginalized) scores over transducer paths, and support marginalization over alternative decompositions via WFST composition. The submission adds: The submission explicitly defines 'transduced language models' as composing a source probabilistic language model with a deterministic string-to-string FST to yield a target

#### Examined and found not to overlap

- Efficient Guided Generation for Large Language Models — The prior paper provides efficient guided generation via FSMs, incremental state tracking, and vocabulary indexing to compute masks for sampling, which overlaps with the submission only at the level of using automata to constrain generation. It does not presen
- Automata-based constraints for language model decoding — The prior paper provides closely related automata machinery—detokenizing FSTs, composition with FSAs/PDA, and algorithms to constrain decoding—so it shares the conceptual use of FSTs to link token vocabularies and formal languages. However, it does not present
- Neural Finite-State Transducers: Beyond Rational Relations — The NFST paper and the claimed submission share the high-level idea of using finite-state transducers and marginalization to assign probabilities over string pairs or mappings. However, NFSTs are a generative transduction model that scores FST paths with neura
- Weighting Finite-State Transductions With Neural Context — The prior paper shares the core idea of using FSTs to map between strings and of weighting transducer arcs with neural context features, so it overlaps conceptually. However, it conditions on a concrete input string x and builds a neural-weighted transducer G 

#### Examined no further

These ranked below the level at which a paper could still challenge this claim, and were not read in full:

- Formalizing BPE Tokenization — formalizes BPE tokenization and shows incremental/left-to-right tokenization using a finite-state string-to-string transducer
- Language Models over Canonical Byte-Pair Encodings — proposes methods to enforce canonical BPE encodings in token-level LMs by conditioning or reparameterization
- Neural Grammatical Error Correction with Finite State Transducers — applies finite-state transducer techniques to improve language-model-based grammatical error correction, an application of FSTs to LM tasks rather than a general transduced LM framework
- Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — uses finite-state transducers as intermediate morphological representations to improve neural models in low-resource settings
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — introduces sequential Monte Carlo steering to enforce syntactic/semantic constraints on LLM outputs via probabilistic programs
- Understanding and Mitigating Tokenization Bias in Language Models — proposes algorithms to obtain unbiased estimates from tokenized LMs and simulate token-free behavior, addressing tokenization-to-string mapping but not a general FST transform framework
- Where is the signal in tokenization space? — analyzes non-canonical tokenizations and marginal probabilities over tokenizations, related to string-to-token issues but not presenting deterministic string-to-string transducer transformations of
- Syntactic Control of Language Models by Posterior Inference — controls syntax of LM outputs by posterior inference and SMC with a tagger to align tokens to constituents, relating to constrained generation but not FST-based deterministic string transductions
- Speech Recognition using Weighted Finite-State Transducers — describes weighted finite-state transducers for speech recognition broadly but not transforming pretrained language models with deterministic string-to-string transducers
- Effect of tokenization on transformers for biological sequences — studies tokenization effects for biological sequences and alternative tokenizers, not proposing deterministic FST transformations of language models
- How to Compute the Probability of a Word — derives correct methods for computing word probabilities from subword LMs and highlights tokenization issues, but does not present FST-based LM transformation techniques
- Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — identifies a confound from leading whitespaces in subword vocabularies and offers a decoding correction, relevant to tokenization but not FST-based LM transforms
- … and 5 more

---

### Second extracted claim

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

**Verdict:** challenged by prior work

2 of the 8 papers examined for this claim challenge it. Examination stopped because: budget exhausted.

#### From Language Models over Tokens to Language Models over Characters

**Substantial overlap.** Gives exact and approximate algorithms to convert token-level LMs into character-level distributions, directly computing marginals/approximations over tokenizations to get string-level probabilities

The prior paper already gives algorithms to marginalize a token-level LM into character-level probabilities by summing over token strings whose decoded characters match the target, plus an exact enumeration and an efficient beam-pruned approximation, and it provides conditional token-generation that samples from the induced distribution — all without altering the underlying model. This is the same kind of contribution as the submission but specialized to the deterministic token→character mapping κ; the submission extends these ideas to arbitrary FST-defined transformations and introduces a different decomposition/search procedure (precover and BFS classification). Because the prior paper provides the core marginalization, conditioning, exact/approximate algorithmic structure, and complexity/pruning analysis, the overlap is substantial though the submission has a meaningful generalization and distinct algorithmic design.

The submission states:

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

The prior work states:

“we can, in principle, compute the prefix probability −→ pΣ(σ) by summing over prefix-encodings of σ, P(σ) def= {δ ∈∆∗: κ(δ) ⪰σ}. Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

The paper explicitly formulates marginalization over all token strings that decode to a given character prefix, which matches the claim's marginalization objective.

The submission states:

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis. We conduct experiments in three domains: converting language models from tokens to bytes, from tokens to words, and from DNA to amino acids.”

The prior work states:

“The enumeration algorithm will enumerate elements of the covering along with their prefix probability (for convenience). It filters prefixes of token strings that cannot eventually cover the target string σ. The strict-prefix monotonicity property is essential for this filtering.”

The paper presents an exact enumeration (enum_cover) and an efficient pruning/beam approximation (prune_top_K_buckets) to compute probabilities and to enable conditional generation without changing the token model.

What the submission adds beyond it: The submission generalizes from the specific deterministic token→character decoding κ to arbitrary finite-state transducer (FST) string transformations, and introduces a BFS-based precover decomposition (quotient/remainder/live classification and explicit checks) and associated algorithms tailored to FST composition; it also emphasizes propagating probabilities through the transducer and supports conditioning on transformed outputs in that broader setting.

#### Sampling from Your Language Model One Byte at a Time

**Substantial overlap.** Presents an inference-time method to convert BPE-tokenized autoregressive LMs into character/byte-level samplers, enabling token-free sampling and addressing prompt-boundary issues without retraining.

ByteSampler directly implements marginalization of token-sequence probabilities to byte-level outputs via the Valid Covering Tree, preserves the original LM distribution, and computes next-byte distributions by summing leaf probabilities — closely matching the high-level goals of the claimed contribution. However, ByteSampler is specialized to the tokenizer/byte decoding setting and presents the VCT construction and tokenizer-dependent compactness results, whereas the submission claims a general FST-composition framework and a distinct precover decomposition algorithm (quotient/remainder/live classification and BFS construction). Thus the overlap is substantial but the submission still contributes a different, more general algorithmic framing and decomposition.

The prior work states:

“Our method preserves the model’s output dis- tribution, up to probability mass on invalid token sequences. We empirically show that our method preserves language modeling loss in Section 4.2 and preserves utility in downstream tasks (Sections E.5 and F). 2.”

“Definition 3.1 (Valid Covering Tree). Let P be a byte string and let decode be the tokenizer’s decoding function. The Valid Covering Tree of P, denoted VCT(P), is the tree of all finite token sequences T = [t1, . . . , tn] such that: 1. P is a prefix of decode(T), 2. decode(t1, . . . , tn−1) is a prefix of P, and 3. T is a valid token sequence.”

What the submission adds beyond it: The submission frames the mapping as composition with a general finite-state transducer and introduces a precover decomposition algorithm with quotient/remainder/live classifications and a BFS-based construction to enable exact and approximate inference for arbitrary FST transformations; ByteSampler is specialised to byte/BPE tokenizer decoding and the Valid Covering Tree data structure, not an explicit general FST composition or the precover decomposition.

#### Examined, partial overlap only

Each of these delivers a piece of what the claim promises without challenging it:

- Automata-based constraints for language model decoding — Both the submission and this paper compose FSTs (detokenizers) with automata representing constraints to enable conditioning the LM's outputs on transformed representations, and both apply this composition at decoding time without modifying LM parameters. The submission adds: The submission presents algorithms to marginalize source-string probabilities into target outputs (exact and approximate inference)
- Weighting Finite-State Transductions With Neural Context — Both works compose a representation of the source (x) with an FST/transducer to obtain a composed transducer G and compute p(y|x) by summing path probabilities (pathsum) over all alignments/paths that yield y. The submission adds: The submission composes a pretrained language model (not just a hand-specified FST) with an FST-defined string transformation to marginalize source strings to target outputs while

#### Examined and found not to overlap

- Neural Finite-State Transducers: Beyond Rational Relations — The NFST paper and the claim share the high-level idea of combining finite-state transducer structure with learned scoring functions and using marginalization over internal FST structures to obtain string-pair probabilities, so there is partial overlap. Howeve
- Efficient Guided Generation for Large Language Models — The prior paper focuses on guided generation by masking LLM logits using FSMs and building indices/algorithms to efficiently compute allowed next tokens (including extensions to CFGs and parsing). It does not present algorithms that compose an LLM with an FST 
- Language Models over Canonical Byte-Pair Encodings — The prior paper addresses conditioning a token-level LM on transformed outputs (canonical token sequences) and presents exact and approximate inference techniques (rejection sampling, a local approximation, and importance-sampling corrections). However, it doe
- Where is the signal in tokenization space? — The prior paper focuses on marginalizing over tokenizations of a fixed input string (representing the combinatorial space with an MDD, hardness proofs, and importance-sampling approximations). It does not develop algorithms that compose language models with fi

#### Examined no further

These ranked below the level at which a paper could still challenge this claim, and were not read in full:

- Understanding and Mitigating Tokenization Bias in Language Models — Proposes test-time algorithms to obtain unbiased (token-free) estimates from tokenized LMs without finetuning
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Uses sequential Monte Carlo to perform posterior inference over discrete sequence models to steer frozen LLMs, matching the inference/conditioning aspect though not via FST composition.
- Syntactic Control of Language Models by Posterior Inference — Uses sequential Monte Carlo posterior inference to enforce syntactic structures during generation from frozen LMs, providing conditioning/steering capabilities but not via FST composition.
- How to Compute the Probability of a Word — Derives correct methods for computing word probabilities from subword LMs, addressing marginalization over subword encodings and common pitfalls in probability computation at inference.
- Differentiable Weighted Finite-State Transducers — Provides differentiable WFST operations and uses WFSTs inside neural networks for training and structured losses
- Formalizing BPE Tokenization — Formalizes BPE tokenizers and shows how tokenization can be implemented as finite-state transducers, providing groundwork for transducer-based token handling but not full LM+FST inference algorithms.
- Neural Grammatical Error Correction with Finite State Transducers — Applies FST techniques to language-model-based grammatical error correction and rescoring with neural LMs
- Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Identifies and corrects a decoding confound in aggregating subword probabilities to words, providing a decoding fix that reassigns whitespace probability and affects word-level surprisal computations.
- Speech Recognition using Weighted Finite-State Transducers — Surveys/apply WFSTs to speech recognition mapping inputs to outputs probabilistically, using WFST inference but in an ASR-specific modeling/training context rather than composing a pretrained LM at
- Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — Uses FSTs to provide intermediate morphological forms to improve neural morphology learners, applying FSTs in training/data modeling rather than composing with frozen LMs for inference-time
- Neural Machine Translation of Rare Words with Subword Units — Uses subword units to enable open-vocabulary NMT and discusses segmentation choices, which is related to tokenization but not to composing pretrained LMs with FSTs for marginals.
- Effect of tokenization on transformers for biological sequences — Studies tokenization choices for biological sequences and their effect on downstream tasks, which is tangential to composing LMs with FSTs for marginalization or conditioning.
- … and 4 more

---

### Third extracted claim

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

**Verdict:** not challenged in the examined literature

0 of the 1 papers examined for this claim challenge it. Examination stopped because: remaining candidates below threshold.

#### Examined and found not to overlap

- Neural Finite-State Transducers: Beyond Rational Relations — The prior paper introduces Neural Finite-State Transducers and algorithms for training/inference with neural path scoring; it does not present definitions, constructions, or lemmas about prefix decompositions or transducer-level conditions that guarantee finit

#### Examined no further

These ranked below the level at which a paper could still challenge this claim, and were not read in full:

- Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — Shows using FSTs' intermediate representations to improve morphology learning with two-step mappings, touching on decompositions via FSTs but focused on practical morphology pipelines rather than
- Formalizing BPE Tokenization — Formalizes BPE tokenization and notes left-to-right tokenization using a finite-state string-to-string transducer
- Differentiable Weighted Finite-State Transducers — Provides a differentiable WFST framework and learning uses (including latent decompositions) but centers on autodiff and neural layers rather than proving transducer-level sufficiency for finite
- Weighting Finite-State Transductions With Neural Context — Combines learned context features with transducers to define weighted distributions over aligned outputs
- Automata-based constraints for language model decoding — Focuses on compiling automata for constrained LM decoding and performance, not on theoretical transducer-level conditions for finite prefix decompositions
- Efficient Guided Generation for Large Language Models — Reformulates guided generation as FSM transitions to enforce grammars, but does not state transducer-level sufficient conditions for finite prefix decompositions
- Speech Recognition using Weighted Finite-State Transducers — Survey/application of WFSTs to speech recognition with emphasis on weights and algorithms, not on theoretical prefix-decomposition guarantees for all target strings
- Neural Grammatical Error Correction with Finite State Transducers — Applies FST techniques to grammatical error correction and LM-GEC improvements, an application paper rather than one giving general transducer-level decomposition theorems
- From Language Models over Tokens to Language Models over Characters — Converts token-level LMs to character-level ones with exact/approximate algorithms, but addresses LM conversion and runtime/approximation rather than transducer-level decomposition guarantees
- Analyzing Cognitive Plausibility of Subword Tokenization — Evaluates cognitive plausibility of subword tokenization algorithms empirically, not providing transducer-theoretic sufficient conditions for finite prefix decompositions
- Language Models over Canonical Byte-Pair Encodings — Addresses canonicality of token encodings in token-level language models and fixes for modelling, unrelated to proving transducer-level conditions for prefix decompositions
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Proposes SMC steering for constrained generation via probabilistic programs, an inference-time control method rather than providing transducer-level sufficiency theorems
- … and 11 more

---

### Fourth extracted claim

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

**Verdict:** challenged by prior work

2 of the 4 papers examined for this claim challenge it. Examination stopped because: remaining candidates below threshold.

#### Understanding and Mitigating Tokenization Bias in Language Models

**Substantial overlap.** Proposes algorithms to obtain unbiased, token-free estimates from a tokenized LM without finetuning, enabling simulation of token-free behavior at inference

The prior paper already demonstrates inference-time marginalization over tokenizations to recover character/byte/word-level probabilities without retraining, via MPC and BPC algorithms, which substantially overlaps the submission's core goal. However, the submission contributes a more general FST-composition formalism, decomposition-based exactness conditions, approximation/pruning strategies, and additional domain instantiations (e.g., amino-acids) and engineering optimizations. Thus the overlap is substantial but the submission still adds generalization, new algorithms, and practical systems work beyond the prior paper.

The prior work states:

“We propose a method to remove the described bias and recover the original token-free autoregressive model, i.e. expressing the implicitly learned P(xN n+1|xn 1) using the tokenized LM that outputs the conditional probability P(ti+1|ti 1). For N=n+1, this captures the behavior of a token-free model, i.e.”

“Our method consists of two stages. In the first stage, the idea is to identify the condition when P(xN n+1|ti 1) = P(xN n+1|xn 1) where ti 1 = encode(xn 1). Once identified, we can refactor the conditional probability to match the conditioning events. In the second stage, we compute P(xN n+1|ti 1) using the LM output probability, i.e. P(ti+1|ti 1), through the novel Maximum Prefix Correction (MPC) Algorithm. ## 3.1.”

What the submission adds beyond it: The submission frames the transformation as composing the LM with an arbitrary finite-state transducer (FST), gives an FST-based decomposition (maximal cylindrical quotient + remainder), provides an exact algorithm plus an inference-time approximation with pruning, lazy determinization, caching, and other optimizations to make repeated autoregressive queries practical, and demonstrates additional domains (e.g., DNA→amino-acids) and broader FST transformations beyond tokenization-specific corrections.

#### Language Models over Canonical Byte-Pair Encodings

**Substantial overlap.** Offers test-time inference strategies (canonicality by conditioning) to enforce canonical token outputs without additional training

The prior paper already supplies the same high-level idea of test-time conditioning to enforce canonical token outputs and gives exact and approximate inference procedures, and it explicitly links tokenizers to finite-state transducers for prefix reasoning. However, the submission adds a more general and algorithmically different composition/marginalization mechanism tailored to computing next-symbol probabilities for arbitrary target alphabets and practical optimizations for efficient repeated autoregressive queries and demonstrations on bytes, words, and amino acids, so the overlap is substantial but not complete.

The submission states:

“We develop algorithms that compose a language model with an FST to marginalize over source strings mapping to a given target, propagating probabilities through the transducer without altering model parameters and enabling conditioning on transformed outputs. We present an exact algorithm, an efficient approximation, and a theoretical analysis.”

The prior work states:

“We present two approaches: (1) canonicality by conditioning, leveraging test-time inference strategies without additional training, and (2) canonicality by construction, a model parameterization that guarantees canonical outputs but requires training. We demonstrate that fixing canonicality mistakes improves the likelihood of held-out data for several models and corpora.”

Both statements describe performing test-time conditioning/inference to restrict or reweight the LM's outputs (conditioning on a transducer-defined set of outputs) without changing model parameters, i.e., composing or conditioning a pretrained LM at inference time to enforce constraints.

What the submission adds beyond it: The submission develops an explicit composition algorithm that marginalizes a fixed pretrained LM with an arbitrary FST to compute target-prefix probabilities (not just renormalization/sampling), gives an exact marginalization algorithm plus an efficient approximation with decomposition/pruning, and demonstrates practical, efficient autoregressive next-symbol queries across bytes, words, and amino-acids with engineering optimizations (cylindrical quotient decomposition, BFS membership/liveness checks, lazy determinization, cached decompositions, joint next-symbol decomposition).

#### Examined, partial overlap only

Each of these delivers a piece of what the claim promises without challenging it:

- Sampling from Your Language Model One Byte at a Time — Both the paper and the claim describe inference-time adaptation of a pretrained language model to a finer-grained character/byte representation without retraining The submission adds: The submission uses a general finite-state transducer composition framework (token->target-unit FSTs) with theoretical decomposition (maximal cylindrical quotient + remainder)
- From Language Models over Tokens to Language Models over Characters — Both works perform inference-time conversion of pretrained token-level language models to operate over bytes/characters, providing exact and approximate algorithms (including beam-pruning approximations) to compute next-character probabilities without The submission adds: The submission generalizes the mechanism to compose the fixed pretrained model with arbitrary finite-state transducers (FSTs)

#### Examined no further

These ranked below the level at which a paper could still challenge this claim, and were not read in full:

- Where is the signal in tokenization space? — Analyzes non-canonical tokenizations and shows aggregating tokenization-space probabilities improves performance
- Automata-based constraints for language model decoding — Provides automata-based decoding constraints and handles tokenization ambiguity at inference to enforce formal languages, but not general byte/aa conversion without retraining
- Efficient Guided Generation for Large Language Models — Reformulates guided generation via FSM indices over a model's vocabulary to enforce constraints at inference, yet does not convert token-level LMs to byte/aa-level ones without retraining
- Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Proposes SMC steering as an inference-time method to enforce constraints on LM outputs, but focuses on steering/guidance rather than converting token granularity to bytes/amino acids
- Effective Large Language Model Adaptation for Improved Grounding and Citation Generation — Proposes tuning-based framework for grounding and test-time retrieval, but adaptation relies on fine-tuning or retrieval, not tokenizer-free inference conversion
- How to Compute the Probability of a Word — Derives correct methods to compute word probabilities from subword models (probability bookkeeping), not methods to convert models to bytes/amino acids at inference
- Syntactic Control of Language Models by Posterior Inference — Uses posterior-inference sampling (SMC) to enforce syntactic structure at inference, which controls outputs but does not provide general byte/aa-level conversion without retraining
- Formalizing BPE Tokenization — Formalizes BPE tokenization and incremental algorithms (theory/implementation), but does not itself provide inference-time conversion to bytes/amino acids without retraining
- Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Identifies and corrects a decoding confound with leading whitespace in subword vocabularies to fix word-probability estimates, not a tokenizer-free conversion method
- Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA — Learns DNA tokenization via gradient descent during pretraining (requires training), not inference-time adaptation without retraining
- Effect of tokenization on transformers for biological sequences — Studies tokenization effects for biological sequences and trains tokenizers on large data, not inference-time conversion without retraining
- Differentiable Weighted Finite-State Transducers — Introduces differentiable WFSTs for use during training and network layers rather than inference-time tokenizer-free adaptation
- … and 8 more

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

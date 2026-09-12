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

| Paper | Claim 1 | Claim 2 | Claim 3 | Claim 4 |
|---|---|---|---|---|
| Automata-based constraints for language model decoding — Koo et al. · 2024 | partial overlap · material evidence | superficial · material evidence | superficial · insufficient evidence | superficial · nonmaterial |
| From Language Models over Tokens to Language Models over Characters — Vieira et al. · 2024 | partial overlap · material evidence | partial overlap · material evidence | partial overlap · material evidence | partial overlap · material evidence |
| How to Compute the Probability of a Word — Pimentel et al. · 2024 | partial overlap · material evidence | partial overlap · material evidence | none · insufficient evidence | partial overlap · material evidence |
| Language Models over Canonical Byte-Pair Encodings — Vieira et al. · 2025 | partial overlap · material evidence | superficial · material evidence | none · insufficient evidence | superficial · material evidence |
| Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Oh et al. · 2024 | superficial · material evidence | superficial · insufficient evidence | none · insufficient evidence | partial overlap · insufficient evidence |
| Sampling from Your Language Model One Byte at a Time — Hayase et al. · 2025 | partial overlap · material evidence | partial overlap · material evidence | partial overlap · material evidence | partial overlap · material evidence |
| Syntactic Control of Language Models by Posterior Inference — Xefteri et al. · 2025 | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence | partial overlap · material evidence |
| Understanding and Mitigating Tokenization Bias in Language Models — Phan et al. · 2024 | superficial · material evidence | partial overlap · material evidence | superficial · insufficient evidence | partial overlap · material evidence |
| Where is the signal in tokenization space? — Geh et al. · 2024 | superficial · nonmaterial | partial overlap · insufficient evidence | none · insufficient evidence | none · insufficient evidence |
| Analyzing Cognitive Plausibility of Subword Tokenization — Beinborn et al. · 2023 | superficial · insufficient evidence | superficial · insufficient evidence | none · insufficient evidence | none · insufficient evidence |
| Differentiable Weighted Finite-State Transducers — 2020 | superficial · insufficient evidence | superficial · material evidence | none · insufficient evidence | none · insufficient evidence |
| Effect of tokenization on transformers for biological sequences — Dotan et al. · 2023 | superficial · insufficient evidence | none · insufficient evidence | none · insufficient evidence | superficial · nonmaterial |
| Effective Large Language Model Adaptation for Improved Grounding and Citation Generation — 2023 | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence | superficial · nonmaterial |
| Efficient Guided Generation for Large Language Models — Willard et al. · 2023 | superficial · nonmaterial | superficial · nonmaterial | superficial · insufficient evidence | none · insufficient evidence |
| Formalizing BPE Tokenization — Berglund et al. · 2023 | superficial · insufficient evidence | superficial · nonmaterial | superficial · material evidence | superficial · insufficient evidence |
| Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — 2019 | superficial · material evidence | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence |
| Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA — Qiao et al. · 2024 | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence | superficial · material evidence |
| Neural Finite-State Transducers: Beyond Rational Relations — Lin et al. · 2019 | superficial · nonmaterial | superficial · material evidence | superficial · insufficient evidence | superficial · insufficient evidence |
| Neural Grammatical Error Correction with Finite State Transducers — Stahlberg et al. · 2019 | superficial · nonmaterial | superficial · nonmaterial | superficial · insufficient evidence | superficial · nonmaterial |
| Neural Machine Translation of Rare Words with Subword Units — Sennrich et al. · 2015 | superficial · nonmaterial | none · insufficient evidence | none · insufficient evidence | superficial · nonmaterial |
| Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Lew et al. · 2023 | none · insufficient evidence | superficial · nonmaterial | none · insufficient evidence | superficial · material evidence |
| Speech Recognition using Weighted Finite-State Transducers — 2022 | superficial · insufficient evidence | superficial · insufficient evidence | none · insufficient evidence | superficial · insufficient evidence |
| Weighting Finite-State Transductions With Neural Context — Rastogi et al. · 2016 | superficial · material evidence | superficial · material evidence | superficial · insufficient evidence | superficial · nonmaterial |
| SQL-PaLM: Improved Large Language Model Adaptation for Text-to-SQL (extended) — 2023 | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence |
Legend: Cells show overlap degree and evidence status: material = meaningful shared contribution supported; nonmaterial = examined correspondences do not support meaningful contribution overlap; insufficient = inconclusive evidence; no evidence check = no check recorded. Missing support is not proof of no overlap. Conflicting assessments are identified under Evidence limits.

## Review

---

### First extracted claim

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** Automata-based constraints for language model decoding (Both works use deterministic string-to-string finite-state transductions as a general computational mechanism around language models: the prior paper's detokenizing FST transforms token sequences into character strings and supports composition-based decoding.) [partial overlap · material]; From Language Models over Tokens to Language Models over Characters (Both papers construct a language model over transformed strings by applying a deterministic string-to-string mapping to a source language model, and both derive an autoregressive interface by decomposing or enumerating source prefixes that cover a target prefix.) [partial overlap · material]; Language Models over Canonical Byte-Pair Encodings (Both works transform a source language model using a deterministic finite-state representation of a string transformation or constraint, producing a new model over transformed or restricted strings.) [partial overlap · material]; Sampling from Your Language Model One Byte at a Time (Both works transform the interface of a language model through a deterministic string-to-string mapping and compute probabilities or next-symbol distributions conditioned on an output-string prefix by aggregating over compatible source/token strings.) [partial overlap · material]; How to Compute the Probability of a Word (Both works use deterministic string-to-string mappings to transform language-model probabilities and reason about the preimages or sets of source strings corresponding to a target word or sequence.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **Automata-based constraints for language model decoding:** The submission introduces transduced language models as a probabilistic framework in which an arbitrary deterministic FST transformation is applied to a source language model, together with prefix and conditional-prefix probability semantics, finite precover decompositions, algorithms for computing them, and conditions for finite computation.
- **From Language Models over Tokens to Language Models over Characters:** The submission generalizes beyond token decoders and strict-prefix-monotone mappings to transformations represented by finite-state transducers, including non-prefix-monotone mappings, ε-transitions, remainders, quotient/remainder decompositions, finite-decomposition conditions, and general transducer-based algorithms.
- **Language Models over Canonical Byte-Pair Encodings:** The submission generalizes beyond canonical BPE tokenization to arbitrary deterministic string-to-string finite-state transducers and develops the transduced-model probability, prefix-probability, precover decomposition, finite-decomposition conditions, and algorithms for autoregressive computation and generation.
- **Sampling from Your Language Model One Byte at a Time:** The submission contributes a general transduced-language-model framework for arbitrary deterministic transformations represented by finite-state transducers, with formal prefix/precover probabilities, prefix decompositions into quotient and remainder, algorithms for computing them, correctness results, and conditions for finite computation.
- **How to Compute the Probability of a Word:** The submission introduces the general transduced-language-model framework for arbitrary deterministic mappings represented by finite-state transducers.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 10 of 24 comparisons have insufficient evidence. One comparison shows a conflict between the overlap assessment and evidence check: Weighting Finite-State Transductions With Neural Context was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Understanding and Mitigating Tokenization Bias in Language Models was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 24 with an evidence check: 9 material, 5 nonmaterial, 10 insufficient.

#### What the submission does for this claim

The submission defines a transduced language model by applying a deterministic string-to-string function represented by a finite-state transducer to a source language model. It provides the resulting probability and prefix-probability formulation, and explains that exact target probabilities require summing source strings in the target’s precover, while sampling remains efficient.

“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X . Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y.”

It further supplies a general computational framework: decompose each precover into a finite prefix-free quotient and remainder when possible, then use this decomposition to compute prefix probabilities and enable left-to-right autoregressive generation. The result is exact under the stated finite-decomposition and exact-check conditions; sufficient transducer conditions include no ε-output cycles and safety of every state, while finite-state transducers remain limited to rational relations.

“The conditions in Lemma 6.1 guarantee exact computation. In particular, these are satisfied by the transducers introduced in the experiments section ( §7): the token-to-byte transducer f α and the DNA-to-amino-acid transducer f dna2aa , whose quotients are finite and remainders empty, but not by the PTB transducer f ptb , whose quotients are infinite. The finiteness of decomposition is a property of the function f , not of any particular transducer encoding it.”

#### Overlapping prior work

##### Automata-based constraints for language model decoding
partial overlap · Koo et al. · 2024

How this paper realizes the claim

The paper constructs a deterministic finite-state transducer that maps token sequences to their detokenized character strings, and uses it to compose character-level constraints into token-level automata for constrained language-model decoding.

“Our first contribution is a reformulation of detokenization (i.e., the process of converting token sequences back into text) as an FST, using the following construction:”

“Our next contribution is a generic method for adapting any FSA from characters to tokens. Specifically, given a token vocabulary V and an FSA A that accepts character sequences, A′ = A ◦TV accepts essentially the same language as A, but in token form.”

“Our key contribution is a reformulation of detokenization as an FST, which enables our other contributions by bringing the entire task of constrained decoding into the domain of automata. Although the problems raised by ambiguous and misaligned tokenizations are quite thorny, we derive simple, elegant, and highly-performant solutions by leveraging the considerable toolkit of automata theory.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes substantive overlap in the current claim’s methodological contribution: both works apply a finite-state string-to-string transformation to language-model representations. The roles are compatible: the submission defines transformation of strings drawn from a source language model, while the prior paper formulates detokenization as an FST transformation of token sequences into text. This is a concrete shared mechanism, not merely a common topic or generic evaluation activity, and supports partial overlap. The pair does not establish equivalence of the broader contributions: it does not show that the prior paper defines the submission’s probabilistic transduced-language-model distribution, prefix or conditional-prefix semantics, finite precover theory, or corresponding probability-computation algorithms. Those distinctions qualify the proposed delta, but their absence from the pair is not a decision-blocking issue for the proposed partial degree. The pair is marked weaker, but it still directly supports the asserted narrower shared mechanism.

Submission contribution span
“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X .”

Pair 1: Both works contribute applying a finite-state string-to-string transformation to language-model representations, with the prior paper providing the narrower detokenization instance rather than a general transformed language-model framework.

The prior work states:
“Our first contribution is a reformulation of detokenization (i.e., the process of converting token sequences back into text) as an FST, using the following construction:”

Comparison with the submission

The prior paper makes a meaningful concrete contribution involving deterministic FST-based transformation of language-model representations, so the relationship is more than topical or merely infrastructural. However, it does not introduce the submission's central probabilistic notion of a transduced language model or its methods for computing the transformed model's probabilities; those remain substantial distinct contributions.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper develops a character-level language-model interface obtained by applying a token decoder κ to a token language model, with tokenization treated as a deterministic string transformation.

“Strict-prefix monotonicity is the key structural property required by §3’s algorithms, as it allows us to replace an infinite sum with a finite sum in Proposition 1. We briefly mention an important special case.”

It defines a finite-style covering of a target character prefix and uses that covering to compute character-prefix probabilities and conditional generation.

“Next, we define the set of minimal prefix encodings of σ, which we call the covering of σ, C(σ) def= {ϕσ(δ) | δ ∈P(σ)}. A more convenient expression for the covering C(σ) of a 5 From Language Models over Tokens to Language Models over Characters string σ ∈Σ∗is equal to the following subset of ∆∗: C(σ) =      {ε} if σ = ε {δ1 ··· δM ∈∆+ :”

The paper then provides an enumeration algorithm, exact computation without pruning, and a beam-pruned approximation with stated complexity bounds. It does not itself present the broader finite-state-transducer framework for arbitrary deterministic string-to-string transformations; its transformation is a token decoder with stronger monotonicity assumptions.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 2 validly establishes a substantive shared component: both papers provide algorithms for computing transformed-model prefix probabilities and supporting autoregressive/conditional generation. This is more than a shared topic or generic activity and supports a partial overlap. It does not establish equivalence of the full frameworks or the submission’s general FST scope. Pair 1 is weaker and does not independently establish that the prior paper constructs a transformed language model: its prior-paper span only states that strict-prefix monotonicity is needed by its algorithms. Thus the specific assertion that both quoted spans directly establish the full source-model-plus-deterministic-mapping construction is not fully demonstrated by Pair 1, but that limitation does not block a partial-overlap determination based on Pair 2. The stated differences concerning non-prefix-monotone mappings, ε-transitions, remainders, and finite-decomposition conditions are not established by correspondence pairs and should remain qualified; they are not needed to support the partial degree.

Submission contribution span
“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences).”

Pair 2: Both papers contribute algorithms for computing transformed-model prefix probabilities and thereby supporting an autoregressive interface, with the prior paper providing this computation specifically by enumerating token prefixes that cover a character prefix.

The prior work states:
“This section gives algorithms for computing pΣ(σ), −→ pΣ(σ), −→ pΣ(σ′ | σ), −→ pΣ(EOS | σ), and conditional token generation.”

Comparison with the submission

The prior paper makes a meaningful contribution overlapping with the submission: it already realizes transformed language modeling for token-to-character decoding and supplies algorithms for computing the resulting prefix probabilities. The overlap is partial rather than substantial because its decoder-specific, strict-prefix-monotone setting does not provide the submission's general FST framework or its treatment of non-monotone transformations and remainders. The submission retains a distinct central contribution by extending the construction to a substantially broader class of deterministic string-to-string transformations.

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper constructs canonicalized language models for byte-pair-encoded tokenizations, using the tokenizer's canonicality constraint to transform a base token language model into a distribution supported only on canonical token strings.

“The globally canonicalized language models gΣ and g are defined as the following probability distributions over Σ∗and ∆∗, respectively: gΣ(σ) def= g(τ(σ)) (6a) g(δ) def= Pr Y ∼p∆[Y = δ | Y ∈D] (6b) = PrY ∼p∆[Y = δ, Y ∈D] PrY ∼p∆[Y ∈D] (6c) = 1 Z p∆(δ)1{δ ∈D} (6d) where Z is the canonicality rate: Z def= Pr Y ∈p∆[Y ∈D] (6e) 6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs.”

It also gives a locally constrained construction that modifies each next-token distribution according to whether the resulting prefix remains canonically tokenizable.

“Our canonicalized architecture is a parametric family of language models {ℓθ}θ∈RD that is built on top of a base architecture {pθ}θ∈RD.”

“We define each ℓθ in terms of pθ in the following manner: ℓθ(δ) def= −→ ℓθ(EOS | δ) |δ| Y t=1 −→ ℓθ(δt | δ<t) (15a) where each −→ ℓθ(· | δ<t) is defined as one of the following distributions over ∆∪{EOS}: −→ ℓθ(δ′ | δ) def= −→ pθ(δ′ | δ) 1{δ·δ′ ∈−→ D} −→ ℓθ(δ) (15b) −→ ℓθ(EOS | δ) def= −→ pθ(EOS | δ) 1{δ ∈D} −→ ℓθ(δ) (15c) and −→ ℓθ(δ) ensures normalization: −→ ℓθ(δ) def= −→ pθ(EOS | δ) 1{δ ∈D} (15d) + X δ′′ −→ pθ(δ′′ | δ) 1{δ·δ′′ ∈−→ D} Much like the locally canonicalized model (Def.”

The paper represents canonical tokenizations with a finite-state automaton and discusses efficient canonicality checking, but it does not present a general framework for applying arbitrary deterministic string-to-string finite-state transformations to language models.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 establishes substantive overlap in the current claim: both works construct a new language-model distribution by applying a string-level transformation or restriction to outputs of a source model. The submission explicitly uses deterministic finite-state string-to-string transformations, while the prior paper defines globally canonicalized distributions based on a canonical-tokenization mapping and finite-state canonicality machinery. These are compatible roles and show that the prior work supplies a meaningful, narrower instance of the claimed transformed-model construction, rather than merely sharing a topic or evaluation activity. The pair does not establish that the prior paper contains the submission's general transduced-language-model framework, preimage/prefix-decomposition algorithms, or broader transformation examples. Those submission-delta assertions are not independently evidenced here and should remain qualified, but their absence does not block the independently supported partial-overlap judgment.

Submission contribution span
“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X .”

Pair 1: Both works define a new language model by transforming or restricting the outputs of a source language model through a string-level mapping; the prior paper provides a narrower canonical-tokenization instance rather than the submission’s general deterministic finite-state transducer framework.

The prior work states:
“The globally canonicalized language models gΣ and g are defined as the following probability distributions over Σ∗and ∆∗, respectively: gΣ(σ) def= g(τ(σ)) (6a) g(δ) def= Pr Y ∼p∆[Y = δ | Y ∈D] (6b) = PrY ∼p∆[Y = δ, Y ∈D] PrY ∼p∆[Y ∈D] (6c) = 1 Z p∆(δ)1{δ ∈D} (6d) where Z is the canonicality rate: Z def= Pr Y ∈p∆[Y ∈D] (6e) 6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs.”

Comparison with the submission

The prior paper makes a meaningful instance-level contribution related to transformed language models: it defines globally conditioned and locally constrained models for canonical BPE encodings and uses finite-state canonicality tests. However, it does not itself introduce the general transduced-language-model framework or the associated general preimage and prefix-decomposition algorithms. Thus the overlap is partial, with the submission retaining a distinct central contribution in generality and computational treatment.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper addresses a specific deterministic string transformation induced by BPE tokenization: it conditions a token-level language model on an arbitrary byte prefix and represents the compatible token sequences with a finite, compact covering tree.

“We introduce an efficient procedure to condition a BPE tokenizer-based model on an arbitrary byte-prefix given only access to the tokenizer and log-probability queries to the model (Section 3). We demonstrate in experiments that this represents an exact solution to the Prompt Boundary Problem presented above (Section 4.2).”

“We show that our method can be used to convert the model into a byte-level language model and that this ability can be used to unify the vocabularies of different models. This enables exact byte-level ensembles of language models with different tokenizers (Section 4.3) and allows one to transfer the post-training of one model onto another model at inference time using proxy-tuning [33] (Section 4.4).”

Its method uses pairwise BPE validation and streaming updates to maintain the tree, then sums language-model probabilities over compatible token-sequence leaves to compute prefix probabilities and byte-level next-symbol distributions.

“The fundamental structure of the algorithm is based on what we call the Valid Covering Tree, which is the tree of all possible valid token sequences that share a specific byte prefix and do not extend past the end of the prefix by more than one full token. We show the construction of the Valid Covering Tree in Fig.”

“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group. This can be combined with a sampling rule to generate text one byte at a time.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 3 grounded candidates support the overlap

Pairs 2 and 3 establish a substantive shared contribution within the current claim: both compute output-prefix or next-symbol probabilities by aggregating probabilities over source/token sequences compatible with an output prefix, and both support autoregressive generation from those conditioned distributions. This is more than a shared topic or generic evaluation activity and supports meaningful partial overlap. The evidence does not establish equivalence of the full contributions: the submission span presents a general transduced-language-model formulation, whereas the prior-paper spans describe the concrete tree/leaf-based byte-generation procedure. Pair 1 is weaker and does not, from the quoted prior-paper span alone, fully establish the deterministic BPE/FST relation; it is therefore not needed for the decision. The delta's assertions that the prior work is restricted to BPE and lacks the general FST framework are not fully established by the quoted spans, although pair 3 does support the byte-level/BPE-specific aspect. Those limitations do not block the partial-overlap decision, because the valid pairs independently establish a meaningful shared component. The unverified generality distinction should remain qualified rather than being treated as fully proven residual novelty.

Submission contribution span
“Like all language models, a transduced language model p Y has prefix and conditional prefix probability functions; its prefix probability is where P(y) is the precover of y, with respect to f , defined as P(y) def = {x ∈ X * : y ⪯ f (x)}. foot_0 Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 2: Both works contribute output-prefix probability computation by aggregating source/token-sequence probabilities over representations compatible with the requested output prefix, with the prior paper specializing this to BPE covering trees.

The prior work states:
“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree.”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 3: Both works support autoregressive output generation from prefix-conditioned probabilities by aggregating probabilities over compatible source sequences; the prior paper implements this specifically for byte-level generation from BPE tokens.

The prior work states:
“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group.”

Comparison with the submission

The prior paper delivers a meaningful substantive instance of the claimed idea: it transforms a token-level language model through a deterministic tokenizer/decoder relation and supports exact conditioning and generation over output bytes. However, it does not itself introduce a general finite-state-transducer framework; its tree construction and validation algorithms are specialized to BPE. The submission therefore retains a distinct central contribution in generality, formalization, and algorithms for arbitrary transductions, so the overlap is partial rather than substantial or same.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper defines tokenisation and detokenisation mappings between subword sequences and character or word sequences, focusing on deterministic tokenisers and the fact that multiple subword sequences may represent the same character sequence.

“Notably, multiple subword sequences may map to the same character sequence. However, most tokenisers specify one of 6We are not concerned with most aspects of individual tokenisers, and will focus on general considerations here.”

It then uses these mappings to derive word probabilities from a language model over subwords, including summation over ambiguous subword sequences when necessary.

“The contextual probability of a word can be computed using probability distributions over subwords as: p(w | w<t) = PS(Ψ′ S) (11) PS(Ψ′′ S) ∆= w<t ◦w ◦W∗and Ψ′′ ∆= w<t ◦W∗.”

The paper further develops tokeniser-dependent prefix-set constructions and practical corrections for computing these probabilities under different word-boundary conventions.

“We are left with the task of finding a set of subword prefixes which will allow us to compute the probabilities of Ψ′ and Ψ′′.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 2 grounded candidates support the overlap

Both pairs establish a substantive methodological overlap within the current claim: computing target-level language-model probabilities by aggregating probabilities over source strings or structured source sets induced by a deterministic mapping. Pair 1 directly aligns the submission’s precover-based prefix probabilities with the prior paper’s equivalent subword-set construction and summation. Pair 2 similarly supports structured computation of target probabilities, while also showing the prior method is tokenization-specific. This is more than a shared topic or generic evaluation activity and supports a meaningful special-case overlap, hence the proposed partial degree. The pairs do not establish that the prior paper introduced the submission’s general FST framework, arbitrary-mapping scope, precover/decomposition machinery, or finiteness theory; those delta assertions remain qualified rather than independently certified. The prior paper’s tokenization limitation is supported by the pair descriptions, but no absence of additional prior contributions should be inferred from the limited correspondences.

Submission contribution span
“Like all language models, a transduced language model p Y has prefix and conditional prefix probability functions; its prefix probability is where P(y) is the precover of y, with respect to f , defined as P(y) def = {x ∈ X * : y ⪯ f (x)}. foot_0 Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 1: Both papers contribute probability computation for a target-level sequence by identifying the source sequences or source-set representation corresponding to that target and aggregating source language-model probabilities; the prior paper does so only for word-to-subword tokenization.

The prior work states:
“(8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. ∆= between Formally, we define the set equivalence two sets of sequences as:   ∆= ΨS =⇒ w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS ΨW (9) Now let PS be a probability function defined analogously to PW (in Defn.”

Submission contribution span
“The following two examples illustrate how we can often compute this infinite sum by exploiting structural properties of the transducer.”

Pair 2: Both papers contribute a method for computing target-language probabilities from source subword or string probabilities through structured sets induced by a deterministic mapping, but the prior paper’s method is limited to tokenization-specific sets.

The prior work states:
“We are now in a position to define our quantity of interest p(w | w<t) in terms of subword probabilities: it is simply the quotient of PS(·) for two different sets ΨS. Lemma”

Comparison with the submission

The prior paper delivers a meaningful special case of transforming a language model through a deterministic tokenization mapping, so the relationship is substantive rather than merely topical. However, it does not itself introduce the general FST-based framework, the general precover/decomposition machinery, or the associated algorithms and finiteness theory; those remain central contributions of the submission. Therefore the overlap is partial.

---

### Second extracted claim

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** Where is the signal in tokenization space? (Both works marginalize probabilities assigned by an autoregressive language model over multiple source sequences that correspond to one target string, while leaving the model parameters unchanged.) [partial overlap · insufficient]; From Language Models over Tokens to Language Models over Characters (The prior paper itself contributes exact marginalization of source token probabilities over a transformed target prefix and exact conditional generation given that transformed prefix.) [partial overlap · material]; Understanding and Mitigating Tokenization Bias in Language Models (Both papers develop algorithms that aggregate probabilities from a token-level language model over multiple source tokenizations or source strings consistent with a target character-level prefix.) [partial overlap · material]; How to Compute the Probability of a Word (Both works marginalize probabilities from a source language-model representation over sequences that realize a target linguistic output, and both support conditional probabilities by taking ratios of marginalized prefix or context probabilities.) [partial overlap · material]; Sampling from Your Language Model One Byte at a Time (Both papers compute autoregressive distributions after a deterministic finite-state-like transformation by aggregating source token-sequence probabilities consistent with a target prefix, and both support transformed next-symbol prediction and sampling without changing the underlying language-model parameters.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **From Language Models over Tokens to Language Models over Characters:** The submission develops a general transducer-based framework: prefix decompositions with both quotient and remainder sets, BFS algorithms and transducer-state checks, exact computation beyond strict-prefix-monotone mappings, sufficient conditions for finite decompositions, joint and optimized inference, and probability-mass pruning for approximate inference.
- **Understanding and Mitigating Tokenization Bias in Language Models:** The submission generalizes beyond tokenization correction to arbitrary string-to-string transformations represented by finite-state transducers.
- **How to Compute the Probability of a Word:** The submission generalizes the operation to arbitrary string-to-string functions represented by finite-state transducers.
- **Sampling from Your Language Model One Byte at a Time:** The submission develops a general composition framework for language models with arbitrary string-to-string finite-state transducers.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 11 of 24 comparisons have insufficient evidence. One comparison shows a conflict between the overlap assessment and evidence check: Neural Finite-State Transducers: Beyond Rational Relations was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Differentiable Weighted Finite-State Transducers was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Language Models over Canonical Byte-Pair Encodings was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Automata-based constraints for language model decoding was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Weighting Finite-State Transductions With Neural Context was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 24 with an evidence check: 9 material, 4 nonmaterial, 11 insufficient.

#### What the submission does for this claim

The submission provides a transducer-based representation and exact BFS algorithm for decomposing each target prefix’s precover into a maximal cylindrical quotient and remainder, thereby summing source-model prefix probabilities and exposing an autoregressive interface. With exact checks and a finite decomposition, it guarantees termination and the optimal valid decomposition; the construction applies to general mappings represented by transducers, including transformations such as normalization, boundary insertion, and DNA-to-amino-acid conversion.

“If P(y) admits a finite decomposition and the three checks exactly implement the conditions above with no pruning, then decompose(y) terminates and its output (Q, R) is the optimal prefix decomposition (Eq. ( 7 )). Proof.”

The same framework supports conditioning on transformed prefixes through prefix probabilities, from which next-symbol distributions and string probabilities are derived, without altering the source language model. Exact computation requires finite decompositions (for example, no ε-output cycles plus the stated safety condition); when exhaustive enumeration is too large, probability-mass pruning gives an approximation that is a lower bound rather than a generally valid decomposition.

“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation. We develop a method in §4 that allows us to compute the sum in Eq.”

“Since pruning only removes candidates from the queue, every element found is correct-⟨Q⟩ ⊔ R ⊆ P(y)-but the decomposition is no longer valid in general (coverage may be incomplete), so the computed prefix probability is a lower bound on the true value. Our strategy is detailed in §C.3.”

#### Overlapping prior work

##### Where is the signal in tokenization space?
partial overlap · Geh et al. · 2024

How this paper realizes the claim

The paper models a string as having many possible tokenizations and defines the string probability by summing the language model probabilities of all token sequences that produce that string.

“Thus, an LLM induces a distribution over tokenizations of a given string. Definition 3.1 (Induced Tokenization Distribution).”

“Evaluating the probability of a string requires marginalizing over all its possible tokenizations. We now formally define this task and show it to be 5 computationally hard.”

It represents the compatible tokenizations with an MDD and estimates the resulting marginal using sequential importance sampling with a look-ahead proposal, rather than composing the language model with a general finite-state transducer or providing exact transducer-based inference.

“To address this issue, we use a modified proposal distribution: the 1-step look-ahead proposal distribution, first proposed in Chirkova et al. (2023). This distribution adjusts the LLM’s next-token distribution at each step by checking whether the 80 −6 −8 40 −10 −12 0 −14 20 26 211 20 26 211 Number of samples (b) Log probability difference between approximate marginal and canonical probability (a) String probability estimates Figure 6: Convergence of approximate marginal.”

Comparison with the submission

The prior paper delivers a meaningful instance of the claimed marginalization contribution: it sums or estimates language-model probability across tokenizations yielding the same string. However, its MDD and importance-sampling methods are specialized to tokenization and do not themselves provide the submission's general transducer-composition framework, exact decomposition algorithm, or transformed-output conditioning interface. The overlap is therefore partial rather than substantial.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper restricts the transformation κ to be strict-prefix monotone and uses this structure to replace the infinite set of source strings covering a target prefix with a finite set of minimal prefix encodings.

“Monotonicity ensures that for all δ ∈P(σ), we have that ∀δ′ ∈∆∗: κ(δ·δ′) ⪰σ. In other words, any δ that decodes to an extension of σ (i.e., κ(δ) ⪰σ) will continue to do so if we append tokens to it. Thus, we may additionally qualify the relationship as δ minimally covers σ if additionally κ(δ1 ··· δM−1) ≺σ.”

“Next, we define the set of minimal prefix encodings of σ, which we call the covering of σ, C(σ) def= {ϕσ(δ) | δ ∈P(σ)}. A more convenient expression for the covering C(σ) of a 5 From Language Models over Tokens to Language Models over Characters string σ ∈Σ∗is equal to the following subset of ∆∗: C(σ) =      {ε} if σ = ε {δ1 ··· δM ∈∆+ :”

It then uses the covering to perform exact marginalization of prefix probability and to condition token generation on a character-level prefix, without changing the underlying token model.

“The algorithm works by enumerating the covering C(σ), drawing a token string from it in proportion to its prefix probability, and finishing the token string by sampling a completion, which can be done from the token-level model. 43 def conditional_token_generation(σ): 44 δ′ ∼Categorical({δ′ : p′/−→ pΣ(σ) 45 for (p′, _, δ′) in enum_cover(σ)}) 46 return sample_completion(δ′) 47 def sample_completion(δ′): 48 δ′′ ←ε 49 while True: 50 δ ∼−→ p∆(· | δ′·δ′′) 51 if δ = EOS: break 52 δ′′ ←δ′′·δ 53 return δ′·δ′′ 7 From Language Models over Tokens to Language Models over Characters (a) Error (JSD/byte) vs.”

“Proposition 2. conditional_token_generation(σ) generates samples according to p∆|Σ(· | σ) for all σ ∈Σ∗. Proof.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 2 grounded candidates support the overlap

Pair 1 establishes a substantive shared methodological contribution: both works sum or marginalize source-language probability mass over strings associated with a transformed target string. The quoted submission span explicitly describes transduction-based marginalization, while the prior-paper span describes exploiting its prefix-monotone structure to perform the summation over a finite set. Pair 2 establishes a second shared contribution: conditional left-to-right generation from prefix probabilities in the submission and correct token generation conditioned on a character-level prompt in the prior paper. These are compatible instances of transformed-output conditioning, although the prior paper's quoted method is narrower. Together, the pairs support meaningful partial overlap in the current claim, not merely a shared topic or generic evaluation activity. They do not establish equivalence of the full claimed contribution or independently substantiate all listed delta details, such as quotient/remainder decompositions, BFS and transducer-state checks, finite-decomposition conditions, joint or optimized inference, or probability-mass pruning. Those limitations do not block a partial-overlap decision, but the submission delta should not present each unpaired distinction as established solely from the absence of correspondence pairs.

Submission contribution span
“A core property of transduced language models is the marginalization: the transduction sums source-string probabilities to compute target-string probabilities, aggregating mass across all source strings that map to the same target.”

Pair 1: Both papers contribute exact marginalization of source-language probability mass into probabilities for transformed target strings, although the prior paper restricts this to strict-prefix-monotone token-to-character mappings.

The prior work states:
“Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 2: Both papers contribute conditional generation under a transformed-output prefix, with the prior paper providing the narrower token-generation procedure for a character-level prompt.

The prior work states:
“This section gives a simple algorithm for correctly generating a token string Y that has a given character-level prompt σ as its prefix.”

Comparison with the submission

The prior paper delivers a meaningful special case of the claimed contribution: exact transformed-prefix marginalization and conditional generation under a strict-prefix-monotone token-to-character transformation. The submission retains a distinct central contribution by generalizing the algorithms to finite-state transducers, handling non-monotone mappings through remainders, and supporting exact or approximate inference with explicit transducer-based decomposition procedures. The overlap is therefore partial rather than substantial or same.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper corrects tokenization bias by recovering character-level probabilities from a tokenized language model, without changing the language model parameters. It does this by recursively enumerating token continuations that cover a queried character string and summing their probabilities.

“Our method consists of two stages. In the first stage, the idea is to identify the condition when P(xN n+1|ti 1) = P(xN n+1|xn 1) where ti 1 = encode(xn 1). Once identified, we can refactor the conditional probability to match the conditioning events.”

Its MPC algorithm provides exact marginalization over tokenizations that cover a character prefix, including recursive branching and passing cases.

“The idea is to marginalize out P(xN nk+1|tk 1) by considering two complementary events: when the next token tk+1 has a prefix xN nk+1 (bval in the Branch Step) versus when the next token tk+1 is contained within xN nk+1 (pval in the Pass Step). Formally, MPC computes the following probabilities: bval = P(xN nk+1, tk+1 ∈B(xN nk+1)) tk 1), (2) pval = P(xN nk+1, tk+1 /∈B(xN nk+1)) tk 1), (3) where B(xN nk+1)={t∈V|xN nk+1∈prefix(decode(t))} and we immediately see that P(xN nk+1|tk 1)=bval+pval.”

For BPE and MPE, the appendix generalizes this into BPC, which searches valid cover encodings and aggregates their token-language-model probabilities.

“Having established these two definitions, we will later show that for BPE (and MPE), the probability P(xn 1) can be represented using a tokenized LM P(ti+1|ti 1) as follows: P(xn 1) = X ⃗t∈cover(xn 1 ) P(⃗t), (49), and the main goal of the BPC algorithm is to search through all cover encodings of xn”

“The Byte-Pair Correction (BPC) algorithm, shown in Algorithm 2 and visualized in Figure 5 (right), which is an efficient algorithm that can search all valid encodings covering xn 1. The idea is that, for each cover encoding ⃗t, once the starting position of the last token is determined (say xi+1), we are guaranteed the prior tokens is unique and must be encode(xi 1).”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 3 grounded candidates support the overlap

Pairs 1 and 2 establish a substantive shared component of the current claim: both use an autoregressive language model and algorithms that aggregate probability across multiple source encodings or strings yielding the same target character/string outcome. Pair 1 directly supports exact marginalization, while pair 2 supports the corresponding algorithmic search or decomposition over alternative encodings. This is more than a shared topic or generic evaluation activity and constitutes a meaningful part of the claimed contribution, so the proposed partial degree is supported. Pair 3 is weaker and does not independently establish the same conditioning contribution: the prior span conditions on a source token history, whereas the submission span only states that prefix and string probabilities are sought. It is therefore not counted as a supporting pair for conditioning on transformed outputs. The delta's assertions that the prior lacks arbitrary FST transformations, remainder handling, finiteness analysis, or approximate inference are not established merely by these pairs; they should remain qualified. Those limitations do not block the partial-overlap determination because the independently supported exact marginalization and alternative-encoding component is sufficient.

Submission contribution span
“A core property of transduced language models is the marginalization: the transduction sums source-string probabilities to compute target-string probabilities, aggregating mass across all source strings that map to the same target.”

Pair 1: Both papers contribute exact probability marginalization by summing language-model probabilities over multiple source token encodings or strings that cover the same target character string; the prior paper delivers the narrower tokenization case.

The prior work states:
“Having established these two definitions, we will later show that for BPE (and MPE), the probability P(xn 1) can be represented using a tokenized LM P(ti+1|ti 1) as follows: P(xn 1) = X ⃗t∈cover(xn 1 ) P(⃗t), (49), and the main goal of the BPC algorithm is to search through all cover encodings of xn”

Submission contribution span
“The following two examples illustrate how we can often compute this infinite sum by exploiting structural properties of the transducer.”

Pair 2: Both papers contribute an algorithm for efficiently searching or decomposing alternative source encodings so their probabilities can be aggregated, although the prior paper restricts this to valid BPE/MPE token encodings rather than general transducer precovers.

The prior work states:
“The Byte-Pair Correction (BPC) algorithm, shown in Algorithm 2 and visualized in Figure 5 (right), which is an efficient algorithm that can search all valid encodings covering xn 1.”

Comparison with the submission

The prior paper delivers a meaningful substantive part of the claimed contribution: exact probability marginalization over alternative token encodings, together with algorithms that operate through the existing language model probabilities. The overlap is nevertheless partial because the submission's central contribution is a general finite-state-transducer composition and inference framework, including non-tokenization transformations, remainder handling, transducer-level correctness and finiteness analysis, and approximate inference; these capabilities remain beyond the prior paper.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper derives word probabilities from a subword language model by representing the set of subword sequences corresponding to a word or word context and summing their probabilities.

“The implication of eq. (8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. ∆= between Formally, we define the set equivalence two sets of sequences as:   ∆= ΨS =⇒ w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS ΨW (9) Now let PS be a probability function defined analogously to PW (in Defn.”

“The contextual probability of a word can be computed using probability distributions over subwords as: p(w | w<t) = PS(Ψ′ S) (11) PS(Ψ′′ S) ∆= w<t ◦w ◦W∗and Ψ′′ ∆= w<t ◦W∗.”

It then develops tokeniser-dependent strategies for constructing the relevant subword prefix sets, including corrections for boundary cases. The paper notes that exact computation can require handling infinite sets, and discusses marginalising finite sets of ambiguous subword sequences, but it does not present a general finite-state-transducer composition algorithm or an approximate inference procedure of the submission's kind.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 1 establishes a substantive shared methodological contribution: both works marginalize probabilities over multiple source sequences induced by a mapping to compute the probability of a target output. The prior work is a narrower tokenisation/subword-to-word special case, while the submission applies the construction to general finite-state transductions. This is more than a shared topic or generic evaluation activity and supports partial overlap.

Pair 2 does not independently establish the full asserted correspondence concerning conditional probabilities obtained as ratios of marginalized prefix or context probabilities. The submission span states that prefix probabilities enable conditional factorization, but does not itself state the ratio construction or explicitly connect those prefixes to marginalized probabilities; the prior span does state such a ratio. Thus, the conditioning component of the proposed rationale should remain qualified. This limitation does not block the partial-overlap decision because Pair 1 independently establishes a meaningful shared component. The submission's broader FST generality, decomposition machinery, finiteness analysis, exact interfaces, and pruning-based inference are not established by these pairs; nor should their absence from the pairs be treated as proven residual novelty.

Submission contribution span
“A core property of transduced language models is the marginalization: the transduction sums source-string probabilities to compute target-string probabilities, aggregating mass across all source strings that map to the same target.”

Pair 1: Both papers contribute marginalizing a source language-model distribution over multiple source sequences induced by a mapping so as to obtain the probability of a target linguistic output.

The prior work states:
“(8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. ∆= between Formally, we define the set equivalence two sets of sequences as:   ∆= ΨS =⇒ w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS ΨW (9) Now let PS be a probability function defined analogously to PW (in Defn.”

Comparison with the submission

The prior paper delivers a meaningful special case of the claimed marginalization and conditioning contribution: computing word probabilities by summing subword probabilities for tokeniser-induced mappings. However, it does not itself provide the submission's general FST-based algorithms, decomposition machinery, finiteness analysis, or pruning-based approximate inference. The overlap is therefore partial rather than substantial or same.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The prior paper constructs a Valid Covering Tree over token sequences consistent with a byte prefix, using pairwise validation and bounded-depth streaming updates. It then sums the language model probabilities of tree leaves to compute prefix and next-byte distributions, and samples bytewise while preserving the original token-level distribution.

“The tree is composed of a “trunk” of tokens that are fully determined (starting at the root, every node has only one child) plus a finite number of “branching” nodes at the end of the trunk. (The number is bounded by a constant which depends only on the tokenizer, see Section 3.2.)”

“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree. To sample a continuation of a prefix, we compute the probability (as above) of every leaf and sample one of them accordingly.”

“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group. This can be combined with a sampling rule to generate text one byte at a time.”

“To sample a continuation of a prefix, we compute the probability (as above) of every leaf and sample one of them accordingly. We are then free to continue sampling a continuation from that leaf using normal token-level sampling.”

Grounded evidence for the assessed overlap

Evidence check: material
3 of 4 grounded candidates support the overlap

Pairs 1, 3, and 4 establish substantive overlap within the current claim: both papers aggregate language-model probability over source sequences compatible with a transformed output prefix, use prefix probabilities for autoregressive transformed-space generation, and employ finite structured enumeration of compatible source sequences. These are meaningful components of the submission's transformed autoregressive inference, not merely a shared topic or generic evaluation activity. Pair 2 supports that both papers produce transformed next-symbol distributions, but its submission span only states that next-symbol distributions are computed; it does not itself establish the asserted grouping of compatible source sequences, so it is not counted as support for the full stated relation. The evidence supports partial overlap, while the cited pairs do not establish equivalence with the submission's broader general finite-state-transducer framework. The delta's specific claims about quotient/remainder sets, exact guarantees, pruning-based approximation, non-prefix-monotone mappings, and the precise scope of the prior paper are not all independently established by these pairs. Those limitations should remain qualified and do not block the partial-overlap decision, because the meaningful shared transformed-inference component is directly supported.

Submission contribution span
“In §3, we saw that if we can sum over the precover of y, we can calculate -→ p Y (y) (Eq. ( 3 )), unlocking an autoregressive interface to the transduced language model.”

Pair 1: Both papers contribute computation of a transformed or constrained output-prefix probability by aggregating language-model probabilities over compatible source token sequences; the prior paper delivers this as a narrower byte-prefix covering-tree construction.

The prior work states:
“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree.”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 3: Both papers contribute autoregressive generation in the transformed output space using probabilities conditioned on the already generated target prefix; the prior paper provides the narrower bytewise version.

The prior work states:
“This can be combined with a sampling rule to generate text one byte at a time.”

Submission contribution span
“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences).”

Pair 4: Both papers contribute a finite structured enumeration of source sequences compatible with a target prefix for transformed inference, but the prior paper's enumeration is limited to BPE token sequences covering a byte prefix.

The prior work states:
“The fundamental structure of the algorithm is based on what we call the Valid Covering Tree, which is the tree of all possible valid token sequences that share a specific byte prefix and do not extend past the end of the prefix by more than one full token.”

Comparison with the submission

The prior paper makes a meaningful substantive contribution overlapping the submission's transformed autoregressive inference: it aggregates language-model mass over token sequences compatible with a byte prefix and derives exact next-byte distributions and sampling. However, its method is specialized to BPE tokenization and bytewise sampling, whereas the submission contributes a broader finite-state-transducer composition algorithm, including general marginalization, conditioning, exact/approximate prefix inference, and handling of remainders and non-prefix-monotone functions. Thus important central novelty remains, so the overlap is partial rather than substantial or same.

---

### Third extracted claim

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** From Language Models over Tokens to Language Models over Characters (Both works guarantee a finite prefix-based decomposition or summation for every target string under structural conditions on the transformation.) [partial overlap · material]; Sampling from Your Language Model One Byte at a Time (The prior paper itself provides a finite, bounded representation of all source tokenizations compatible with every target byte prefix, using tokenizer-specific bounded lookahead.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **From Language Models over Tokens to Language Models over Characters:** The submission contributes transducer-level sufficient conditions—no ε-output cycles and inductive state safety—that guarantee finite decompositions even when the realized function is not prefix monotone. It also introduces the remainder needed for non-prefix-monotone transformations and distinguishes sufficient conditions from necessary ones.
- **Sampling from Your Language Model One Byte at a Time:** The submission gives general transducer-level sufficient conditions—absence of ε-output cycles and inductive state safety—that guarantee finite quotient and remainder for every target string.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 21 of 24 comparisons have insufficient evidence. One comparison shows a conflict between the overlap assessment and evidence check: Formalizing BPE Tokenization was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 24 with an evidence check: 3 material, 21 insufficient.

#### What the submission does for this claim

The submission gives a sufficient, transducer-level termination criterion for finite prefix decompositions for every target string, and explicitly covers functions that are not prefix monotone. The criterion has two parts: no cycle whose transitions all emit ε, and inductive safety of every state, where safety arises from input-projection universality, finite closure, or safety of all successor states.

“Lemma 6.1. Let f : X * → Y * be a function realized by a transducer f. The decomposition (Q(y), R(y)) is finite for every y ∈ Y * if: (i) No ε-output cycles: f contains no cycle in which every arc outputs ε.”

The stated scope is sufficient rather than necessary: the conditions guarantee exact computation, but some decompositions may still be finite when individual states fail the safety test. The submission also reports their application to specific transducers: token-to-byte and DNA-to-amino-acid have finite quotients and empty remainders, whereas the PTB transducer has infinite quotients.

“The conditions in Lemma 6.1 guarantee exact computation. In particular, these are satisfied by the transducers introduced in the experiments section ( §7): the token-to-byte transducer f α and the DNA-to-amino-acid transducer f dna2aa , whose quotients are finite and remainders empty, but not by the PTB transducer f ptb , whose quotients are infinite. The lemma's conditions are sufficient but not necessary”

#### Overlapping prior work

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper gives a decoder-level sufficient condition: strict-prefix monotonicity of κ. Under this condition, its covering construction yields a finite set of minimal token prefixes for every target string and replaces the corresponding infinite sum with a finite sum.

“Strict-prefix monotonicity is the key structural property required by §3’s algorithms, as it allows us to replace an infinite sum with a finite sum in Proposition 1. We briefly mention an important special case.”

“Proposition 1. Suppose (Σ, ∆, τ, κ) is a tokenization model where κ is strict-prefix monotone and p∆is a token-level language model. Then, the prefix probability −→ pΣ(σ) for the character-level model Eq. (6) is given by −→ pΣ(σ) = X δ∈C(σ) −→ p∆(δ), ∀σ ∈Σ∗ (13) Proof.”

“Specifically, we now have a finite sum, as |C(σ)| is finite for all σ ∈Σ∗. Bear in mind that the covering’s size is likely too large to be practical, as there may still be a large number of summands; however, the set of high-prefix-probability elements of the covering tends to be reasonably small, an observation that we verify in §4, and leverage to develop practical algorithms in §3.”

The paper does not provide transducer-level conditions, and it does not handle transformations that are not prefix monotone; its guarantee is limited to strict-prefix-monotone decoders.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a shared substantive empirical/methodological contribution: both works provide a finite prefix-based decomposition or summation for every target string. The quoted submission span specifies transducer-level sufficient conditions and explicitly includes non-prefix-monotone functions; the prior-paper span establishes finiteness of the covering/sum for every target, supporting the narrower special case described in the comparison. This is more than a shared topic or generic activity, so the overlap is material and supports a partial degree. The pair does not establish that the prior paper itself has transducer-level conditions, handles non-prefix-monotone transformations, or introduces a remainder; those are appropriately presented as submission-specific differences. The decoder-level versus transducer-level characterization and exclusion of non-prefix-monotone cases are asserted in the comparison but are not fully established by the quoted prior span, so those delta details should remain qualified; they do not block the independently supported partial-overlap determination.

Submission contribution span
“Lemma 6.1 gives sufficient conditions on a transducer that guarantee a finite decomposition for every target string, even when the underlying function is not prefix monotone.”

Pair 1: Both works provide a finite prefix-based decomposition or summation for every target string; the prior paper supplies the narrower strict-prefix-monotone covering case, while the submission generalizes the guarantee to transducer-level conditions and non-prefix-monotone functions.

The prior work states:
“Specifically, we now have a finite sum, as |C(σ)| is finite for all σ ∈Σ∗.”

Comparison with the submission

The prior paper delivers a meaningful special case of the claimed contribution: strict-prefix monotonicity guarantees a finite covering for every target. The overlap is partial rather than substantial because the prior guarantee is decoder-level and excludes non-prefix-monotone transformations, whereas the submission’s central novelty is a transducer-level guarantee covering those cases through safety and a finite remainder.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper constructs a Valid Covering Tree for each byte prefix: a finite representation of all valid token sequences compatible with that prefix, with branches limited to a bounded amount of lookahead.

“The fundamental structure of the algorithm is based on what we call the Valid Covering Tree, which is the tree of all possible valid token sequences that share a specific byte prefix and do not extend past the end of the prefix by more than one full token. We show the construction of the Valid Covering Tree in Fig.”

“Compactness: The tree is composed of a “trunk” of tokens that are fully determined (starting at the root, every node has only one child) plus a finite number of “branching” nodes at the end of the trunk. (The number is bounded by a constant which depends only on the tokenizer, see Section 3.2.)”

It then establishes that bounded lookahead makes the tree constant-sized and supports constant-time updates as bytes arrive, yielding a finite, efficiently maintainable cover for the specific BPE-tokenization setting.

“This implies that the branching tree T will have bounded depth, since any token that is fully determined will be removed from the tree and written to the output stream. The branching factor of the tree is also bounded by a constant depending on the tokenizer. Thus, the number of edges of T is bounded by a constant, which also means the pruning described in Fig.”

“Thus, the number of edges of T is bounded by a constant, which also means the pruning described in Fig. 2 can be carried out in constant time. For more concrete performance numbers see Section 4.1, where we show that the tree has only 0.72 extra non-leaf nodes on average.”

Grounded evidence for the assessed overlap

Evidence check: material
2 of 2 grounded candidates support the overlap

Pair 1 establishes a substantive shared component: both works represent the source-side decompositions compatible with a target prefix using a finite structure, although the submission expresses this as quotient-and-remainder finiteness under transducer conditions and the prior paper as a tokenizer-specific Valid Covering Tree. Pair 2 independently supports that the prior representation is bounded and finite, rather than merely sharing a generic topic or evaluation activity. Together, these pairs support meaningful partial overlap with the finite prefix-covering/decomposition aspect of the claim. They do not establish that the prior paper supplies general transducer-level sufficient conditions, handles non-prefix-monotone transformations, permits nonempty remainders, or distinguishes sufficient from necessary conditions. Those submission-delta assertions must therefore remain qualified and cannot be certified as novelty solely from the quoted pairs, but proving all such residual differences is not necessary to support the proposed partial-overlap degree.

Submission contribution span
“The decomposition (Q(y), R(y)) is finite for every y ∈ Y * if: (i) No ε-output cycles: f contains no cycle in which every arc outputs ε.”

Pair 1: Both papers contribute a finite prefix-covering representation for every target prefix: the submission guarantees finite quotient-and-remainder decompositions under transducer conditions, while the prior paper constructs a tokenizer-specific tree of tokenizations covering a byte prefix.

The prior work states:
“The fundamental structure of the algorithm is based on what we call the Valid Covering Tree, which is the tree of all possible valid token sequences that share a specific byte prefix and do not extend past the end of the prefix by more than one full token.”

Submission contribution span
“In particular, these are satisfied by the transducers introduced in the experiments section (§7): the token-to-byte transducer f α and the DNA-to-amino-acid transducer f dna2aa, whose quotients are finite and remainders empty”

Pair 2: Both papers provide a bounded finite representation of the source decompositions compatible with a target prefix: the submission proves finite quotients and remainders for qualifying transducers, whereas the prior paper bounds the Valid Covering Tree to a determined trunk plus finitely many branching nodes.

The prior work states:
“Compactness: The tree is composed of a “trunk” of tokens that are fully determined (starting at the root, every node has only one child) plus a finite number of “branching” nodes at the end of the trunk.”

Comparison with the submission

The contributions partially overlap because the prior paper already delivers a finite prefix-covering structure for every byte prefix in the BPE setting, with bounded lookahead and constant-size maintenance. However, its result is a tokenizer-specific construction and does not provide general transducer-level guarantees or address non-prefix-monotone transformations and nonempty remainders. The submission therefore retains a distinct central contribution: a broader sufficient-condition theorem for finite decompositions of arbitrary transducer-realized functions.

---

### Fourth extracted claim

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** Sampling from Your Language Model One Byte at a Time (Both papers use an existing tokenizer-based language model at inference time to obtain predictions over a finer-grained unit—bytes or characters—without retraining the model.) [partial overlap · material]; Understanding and Mitigating Tokenization Bias in Language Models (Both works perform inference-time transformation of an existing token-level language model into a model over a finer-grained sequence representation, computing probabilities by marginalizing or correcting over alternative tokenizations/encodings rather than retraining the model.) [partial overlap · material]; How to Compute the Probability of a Word (Both papers adapt an existing pretrained language model at inference time to produce probabilities over orthographic words rather than the model's native subword units, without retraining.) [partial overlap · material]; Syntactic Control of Language Models by Posterior Inference (Both papers contribute an inference-time framework that repurposes an existing pretrained language model without retraining it, using probabilistic inference to obtain a model or generation process adapted to a desired output representation or constraint.) [partial overlap · material]; From Language Models over Tokens to Language Models over Characters (Both works substantively adapt pretrained token-level language models to produce distributions over bytes without retraining the underlying language model.) [partial overlap · material]; Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities (Both works adapt the output unit of an existing pretrained language model at inference time without retraining.) [partial overlap · insufficient].

**Remaining contribution relative to the strongest supported comparison(s):**

- **Sampling from Your Language Model One Byte at a Time:** The submission generalizes inference-time transduction through finite-state transducers and demonstrates it across bytes, orthographic words, and amino acids, including transformations not addressed by the prior paper.
- **Understanding and Mitigating Tokenization Bias in Language Models:** The submission contributes a general transducer-based framework and algorithms for composing pretrained language models with arbitrary string-to-string transformations, including token-to-byte, token-to-orthographic-word, and DNA-to-amino-acid mappings.
- **How to Compute the Probability of a Word:** The submission presents a broader transducer-based framework and inference algorithms for arbitrary string-to-string mappings, together with an efficient approximation and experiments covering token-to-byte, token-to-orthographic-word, and DNA-to-amino-acid transformations.
- **Syntactic Control of Language Models by Posterior Inference:** The submission's distinct central contribution is a general transducer-based framework for composing pretrained language models with string-to-string transformations and computing or approximating the resulting distributions.
- **From Language Models over Tokens to Language Models over Characters:** The submission contributes a general transducer-based framework that supports arbitrary finite-state transformations and extends beyond bytes to orthographic word boundaries and amino-acid sequences.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 10 of 24 comparisons have insufficient evidence. One comparison shows a conflict between the overlap assessment and evidence check: Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Language Models over Canonical Byte-Pair Encodings was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. One comparison shows a conflict between the overlap assessment and evidence check: Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs was assessed as superficial while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 24 with an evidence check: 8 material, 6 nonmaterial, 10 insufficient.

#### What the submission does for this claim

The submission delivers a general transducer-based framework for inference-time transformation of pretrained language models, with an autoregressive interface that computes target-unit probabilities without retraining. It applies this framework to bytes, orthographic words, and amino acids, using token-to-byte conversion, an FST encoding the PTB tokenizer, and a DNA-to-amino-acid transducer.

“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining. Our theoretical analysis characterizes the conditions under which such mappings can be performed exactly.”

The empirical scope is specific: token-to-byte experiments use GPT-2 Large, LLaMA 3.2-1B, LLaMA 3.1-8B, and Phi-4 on the first ten paragraphs of WikiText-2; word-boundary experiments use the PTB tokenizer on the same dataset; and amino-acid experiments evaluate a DNA model on 65 human proteins. Accuracy-throughput behavior is measured with JSD and cross-entropy under probability-mass pruning, with lower thresholds generally improving agreement at the cost of throughput; the DNA case additionally requires candidate-set caps because its decomposition grows exponentially.

“Across all three settings-token-to-byte, PTB tokenization, and DNA-to-amino-acid-JSD decreases as τ decreases, at the cost of throughput (bytes/sec). Tab.”

Quoted from the source but NOT confirmed verbatim:
To evaluate our approach, we sample 65 human proteins.

#### Overlapping prior work

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The prior paper develops ByteSampler, a method for using a tokenizer-based pretrained language model to compute next-byte distributions and sample continuations one byte at a time, without changing or retraining the underlying model.

“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group. This can be combined with a sampling rule to generate text one byte at a time. Naturally, this will generate text more slowly than sampling at the token level.”

It also evaluates the resulting inference-time conversion from off-the-shelf token-level models to character-level prediction, but it does not itself provide adaptation to orthographic words or amino acids.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly supports a substantive overlap in the current claim's byte-level inference-time adaptation: the submission explicitly transduces pretrained token-based language models to bytes without retraining, while the prior paper states that its method can generate text one byte at a time. These spans support compatible conversion/use of an existing token-based model for byte-level prediction or generation, though they do not establish equivalence of methods or the full claimed scope. The pair does not support overlap for word- or amino-acid-level adaptation, nor does it establish that the prior paper lacks those capabilities; those delta assertions must remain qualified unless separately evidenced. It also does not independently substantiate the submission's broader finite-state-transducer, probability-decomposition, or beam-summing framework, but those limitations do not block the proposed partial degree because the byte-level component is a meaningful part of the current claim and the assessment treats the broader framework as residual scope.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time conversion of a pretrained token-based language model into a byte-level predictor by computing distributions over bytes without retraining the underlying model; the prior paper covers the byte case but not the submission’s word- and amino-acid adaptations or general transducer framework.

The prior work states:
“This can be combined with a sampling rule to generate text one byte at a time.”

Comparison with the submission

The overlap is substantive for byte-level inference-time adaptation: the prior paper already demonstrates converting a pretrained token model into a byte/character predictor and sampler without retraining. However, it does not deliver the claimed word- and amino-acid-level adaptations, and the submission's general transducer framework remains a distinct central contribution. Thus the overlap is partial rather than substantial or same.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The prior paper addresses inference-time adaptation only between token and character/string representations: it proposes correcting tokenization bias so a tokenized language model can recover the probabilities of a token-free autoregressive model, without retraining the language model.

“We propose a method to remove the described bias and recover the original token-free autoregressive model, i.e. expressing the implicitly learned P(xN n+1|xn 1) using the tokenized LM that outputs the conditional probability P(ti+1|ti 1). For N=n+1, this captures the behavior of a token-free model, i.e.”

“Our method consists of two stages. In the first stage, the idea is to identify the condition when P(xN n+1|ti 1) = P(xN n+1|xn 1) where ti 1 = encode(xn 1). Once identified, we can refactor the conditional probability to match the conditioning events.”

Its BPC extension similarly computes probabilities of strings by enumerating valid token encodings that cover the queried string, but the paper does not itself provide adaptation of pretrained models to orthographic words or amino-acid sequences.

“The Byte-Pair Correction (BPC) algorithm, shown in Algorithm 2 and visualized in Figure 5 (right), which is an efficient algorithm that can search all valid encodings covering xn 1. The idea is that, for each cover encoding ⃗t, once the starting position of the last token is determined (say xi+1), we are guaranteed the prior tokens is unique and must be encode(xi 1).”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 2 establishes a substantive shared component: the prior paper computes finer-grained string probabilities from a tokenized language model by summing over alternative token encodings, and the submission claims inference-time transduction of a pretrained token-based model into finer-grained units without retraining. This supports overlap in tokenization/probability correction, although it does not establish that the prior paper provides the submission's general transducer framework or all three target domains. Pair 1 is not independently sufficient because the quoted prior span only states that a construction captures token-free-model behavior; it does not itself establish the claimed inference-time transformation or the narrower correction relation. The unsupported assertions that the prior paper lacks word- and amino-acid adaptations or the general framework should remain qualified, since absence cannot be inferred from these pairs. Those limitations do not block a partial-overlap judgment: the valid evidence establishes a meaningful shared byte/string-level component without establishing equivalence of the broader claimed contribution.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 2: Both papers contribute inference-time recovery of finer-grained string or byte-level probabilities from a tokenized language model by aggregating probabilities over alternative token encodings; the prior paper delivers the narrower byte-pair correction component of the submission's broader bytes/words/amino-acids adaptation.

The prior work states:
“Having established these two definitions, we will later show that for BPE (and MPE), the probability P(xn 1) can be represented using a tokenized LM P(ti+1|ti 1) as follows: P(xn 1) = X ⃗t∈cover(xn 1 ) P(⃗t), (49), and the main goal of the BPC algorithm is to search through all cover encodings of xn”

Comparison with the submission

The overlap is substantive but limited to the shared idea of inference-time conversion from token-level models to character/byte-like string units without retraining. The prior paper already provides a meaningful tokenization-correction realization of that part of the claimed contribution, but the submission generalizes the operation to arbitrary transducers and demonstrates distinct word- and amino-acid-level adaptations with a broader computational framework. Therefore, important central novelty remains beyond the prior paper, warranting a partial rather than substantial overlap judgment.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper derives a method for obtaining word-level and contextual word probabilities from a pretrained language model whose outputs are subword sequences, by constructing sets of subword sequences equivalent to word-level events and marginalizing their probabilities.

“The implication of eq. (8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. ∆= between Formally, we define the set equivalence two sets of sequences as:   ∆= ΨS =⇒ w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS ΨW (9) Now let PS be a probability function defined analogously to PW (in Defn.”

It then uses autoregressive conditional probabilities to compute the required prefix probabilities efficiently, and gives separate corrections for end-of-word and beginning-of-word tokenizers.

“In turn, these let us compute p(w | w<t) efficiently through eq. (11). For most tokenisers, finding a set ΨS for which the equivalence w ◦W∗ ∆= s∈ΨS s ◦S∗holds is not actually possible due to S the existence of unmapped sequences in s ◦S∗; unmapped sequences, however, have zero probability and including them in Ψ′ S or Ψ′′ S does not affect the equality in eq.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a substantive overlap in the word-level contribution: both papers perform inference-time conversion from a pretrained model’s native subword probabilities to probabilities over orthographic words by aggregating or summing compatible subword sequences, without retraining. This matches the proposed shared rationale and constitutes a meaningful component of the current claim, while the pair explicitly limits the prior paper to the word case. The evidence does not establish overlap for the submission’s byte or amino-acid adaptations, its broader arbitrary string-to-string transducer framework, or its approximation and unified treatment of mappings; those residual distinctions support a partial rather than substantial or same relation. The delta’s assertion that the prior paper does not deliver those other components is not independently established by the single pair, but that limitation is non-blocking because the pair itself supports partial overlap and does not need to prove every remaining difference absent.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time conversion of subword language-model probabilities into probabilities over orthographic words by aggregating compatible subword sequences, but the prior paper covers only the word case.

The prior work states:
“(8) is that if we can create a subword set ΨS that is “equivalent” to a chosen word set ΨW, we would be able to compute ΨW’s probability by summing over the subwords in ΨS. ∆= between Formally, we define the set equivalence two sets of sequences as:   ∆= ΨS =⇒ w∈ΨW ⇐⇒S W∗→S∗(w)∈ΨS ΨW (9) Now let PS be a probability function defined analogously to PW (in Defn.”

Comparison with the submission

The prior paper delivers a meaningful substantive part of the claimed contribution for the word case: inference-time conversion from subword language-model probabilities to word probabilities without retraining. It does not itself deliver the claimed byte or amino-acid adaptations or the submission's general transducer framework, so important central novelty remains beyond the shared word-level realization. The overlap is therefore partial rather than substantial or same.

##### Syntactic Control of Language Models by Posterior Inference
partial overlap · Xefteri et al. · 2025

How this paper realizes the claim

The prior paper performs inference-time adaptation of pretrained language models to a target syntactic structure by treating the language model as a prior and applying posterior inference during generation. Its method uses importance sampling and sequential Monte Carlo, with a learned autoregressive Tetratagger providing left-to-right shaping guidance; the base language models are not retrained for each target syntax.

“To improve syntactically controlled generation at inference time, we propose a sampling method that approximates the posterior distribution over strings generated by a language model under a target syntactic structure. Our approach is based on sequential Monte Carlo, an algorithm that estimates the posterior by drawing samples from a proposal distribution and weighting them by the likelihood that the given string follows a specific attribute, in our case, a syntax tree.”

“Our approach is based on sequential Monte Carlo, an algorithm that estimates the posterior by drawing samples from a proposal distribution and weighting them by the likelihood that the given string follows a specific attribute, in our case, a syntax tree. In this paper, we use parsers-as-taggers3 to further guide the generation towards samples with higher likelihood.”

“These results demonstrate that controlled generation by posterior inference can make smaller models competitive with larger ones, like GPT4.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 establishes a substantive methodological overlap: both use inference-time probabilistic procedures involving a language model to produce outputs conditioned on a desired target. This supports the shared inference-time adaptation component and is more than merely sharing a topic or conducting the same generic evaluation. The overlap is limited, however: the prior paper applies posterior sampling to syntactic constraints, while the current claim concerns transforming a pretrained model across byte, word, and amino-acid representations. The pair does not establish that the prior paper supports those representations, nor does the quoted prior span explicitly establish the no-retraining property. Those limitations prevent substantial or same overlap but do not block the proposed partial degree. The assertion that the listed transformation capabilities are not delivered by the prior paper should remain qualified, since the single pair does not prove the prior paper lacks other related capabilities; that delta limitation is not necessary to establish the independently supported partial overlap.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time probabilistic procedures that adapt the outputs or generation distribution of a language model to a desired target; the prior paper delivers a narrower syntactic-control version rather than adaptation across byte, word, and amino-acid representations.

The prior work states:
“To improve syntactically controlled generation at inference time, we propose a sampling method that approximates the posterior distribution over strings generated by a language model under a target syntactic structure.”

Comparison with the submission

The prior paper itself meaningfully overlaps with the inference-time, no-retraining adaptation aspect, since it samples from a posterior induced by a pretrained language model and a target constraint. However, its substantive target is syntactic control through posterior sampling, while the submission's central contribution is transducer-based distributional transformation across representations and biological sequences. Thus, the overlap is partial rather than substantial: an important methodological idea is shared, but the submission retains a distinct central contribution and broader transformation framework.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper develops exact and approximate algorithms that convert token-level language models into character-level models, enabling inference over character units rather than only canonical tokenizations.

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms.”

Quoted from the source but NOT confirmed verbatim:
We present both exact and approximate algorithms.

Its experiments evaluate the runtime and approximation quality of these converted models, using bytes as the character alphabet for compatibility with byte-pair encoding.

“We measure the approximation error as the average Jensen–Shannon distance (JSD) to a reference model’s conditional distribution over the next byte (Fig. 1a). We use a large beam K =128 as a reference model.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a substantive methodological overlap within the current claim: both works perform inference-time conversion/adaptation of pretrained token-level language models to lower-level output units without retraining, and the prior paper specifically covers the character-level instance, which includes the byte-level case asserted in the claim. This supports the proposed partial degree because the byte/token-to-byte component is a meaningful part of the current contribution, while the pair also explicitly characterizes the submission as extending beyond that narrower case to words and amino acids. The evidence does not establish overlap in the broader transducer framework, general finite-state transformations, theoretical results, or non-byte adaptations. The delta's assertions that the prior paper lacks those components are not independently proven by the absence of additional pairs and should remain qualified, but resolving them is not necessary to establish the supported partial overlap.】【。ેણalc?}、】【 菲律宾申博 Adhering to schema, no extra.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time conversion of token-level language models into models over lower-level character/byte outputs; the prior paper delivers the narrower character-level (including byte-compatible) instance, while the submission extends this to bytes, words, and amino acids without retraining.

The prior work states:
“This paper presents algorithms for converting token-level language models to character-level ones.”

Comparison with the submission

The prior paper already provides a meaningful substantive part of the claim: adapting pretrained token models to byte-level inference without retraining. However, it is focused on character/byte outputs and does not itself deliver the submission's word-boundary or DNA-to-amino-acid adaptations, nor its general transducer framework. The overlap is therefore partial rather than substantial or same.

##### Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities
partial overlap · Oh et al. · 2024

How this paper realizes the claim

The paper identifies an inconsistency in word probabilities caused by leading-whitespace subword tokenization and proposes an inference-time reallocation of whitespace probability, without modifying or retraining the language model.

“We propose a simple and efficient decoding method that reaccounts the probability of the trailing whitespace into that of the current word, which resolves this confound. Regression results show that this correction reveals significantly lower surprisal-based estimates of garden-path effects in transitive/intransitive sentences and poorer fits of LM surprisal to naturalistic reading times.”

“As WT decoding simply involves the factorization of whitespace probabilities by marginalizing over tokens in VB and rearranging them, it requires no modifications to the LM and minimal overhead. Additionally, the joint probability of the entire sequence, and therefore metrics like perplexity, changes minimally by a factor of the probability of the final trailing whitespace with WT decoding.”

Comparison with the submission

The overlap is substantive for the word-level, no-retraining aspect: the prior paper already proposes an inference-time transformation that produces more consistent word probabilities from a subword LM. However, it does not deliver the submission's central general-purpose transducer framework or its byte- and amino-acid adaptations, so important novelty remains beyond the prior paper.

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

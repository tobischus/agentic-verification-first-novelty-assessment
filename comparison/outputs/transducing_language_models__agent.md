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
| From Language Models over Tokens to Language Models over Characters — Vieira et al. · 2024 | partial overlap · material evidence | substantial overlap · material evidence | partial overlap · material evidence | partial overlap · material evidence |
| Formalizing BPE Tokenization — Berglund et al. · 2023 | partial overlap · material evidence | superficial · nonmaterial | superficial · insufficient evidence | superficial · insufficient evidence |
| How to Compute the Probability of a Word — Pimentel et al. · 2024 | partial overlap · material evidence | superficial · no evidence check | none · insufficient evidence | partial overlap · material evidence |
| Language Models over Canonical Byte-Pair Encodings — Vieira et al. · 2025 | superficial · insufficient evidence | partial overlap · material evidence | superficial · nonmaterial | partial overlap · insufficient evidence |
| Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities — Oh et al. · 2024 | none · material evidence | superficial · no evidence check | superficial · no evidence check | partial overlap · material evidence |
| Sampling from Your Language Model One Byte at a Time — Hayase et al. · 2025 | partial overlap · material evidence | partial overlap · material evidence | superficial · no evidence check | partial overlap · material evidence |
| Understanding and Mitigating Tokenization Bias in Language Models — Phan et al. · 2024 | superficial · nonmaterial | partial overlap · material evidence | none · insufficient evidence | partial overlap · material evidence |
| Analyzing Cognitive Plausibility of Subword Tokenization — Beinborn et al. · 2023 | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check |
| Automata-based constraints for language model decoding — Koo et al. · 2024 | superficial · nonmaterial | superficial · nonmaterial | none · insufficient evidence | superficial · nonmaterial |
| Differentiable Weighted Finite-State Transducers — 2020 | superficial · insufficient evidence | superficial · nonmaterial | none · insufficient evidence | superficial · insufficient evidence |
| Effective Large Language Model Adaptation for Improved Grounding and Citation Generation — 2023 | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check | superficial · nonmaterial |
| Efficient Guided Generation for Large Language Models — Willard et al. · 2023 | superficial · nonmaterial | superficial · no evidence check | superficial · insufficient evidence | superficial · insufficient evidence |
| Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers — 2019 | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check | none · insufficient evidence |
| Model Decides How to Tokenize: Adaptive DNA Sequence Tokenization with MxDNA — Qiao et al. · 2024 | none · insufficient evidence | none · insufficient evidence | superficial · no evidence check | none · insufficient evidence |
| Neural Finite-State Transducers: Beyond Rational Relations — Lin et al. · 2019 | none · nonmaterial | superficial · nonmaterial | none · insufficient evidence | none · insufficient evidence |
| Neural Grammatical Error Correction with Finite State Transducers — Stahlberg et al. · 2019 | superficial · insufficient evidence | superficial · nonmaterial | none · insufficient evidence | superficial · nonmaterial |
| Neural Machine Translation of Rare Words with Subword Units — Sennrich et al. · 2015 | superficial · insufficient evidence | superficial · no evidence check | superficial · no evidence check | none · insufficient evidence |
| Sequential Monte Carlo Steering of Large Language Models using Probabilistic Programs — Lew et al. · 2023 | none · insufficient evidence | superficial · nonmaterial | none · insufficient evidence | superficial · nonmaterial |
| Speech Recognition using Weighted Finite-State Transducers — 2022 | superficial · insufficient evidence | superficial · insufficient evidence | none · insufficient evidence | superficial · insufficient evidence |
| SQL-PaLM: Improved Large Language Model Adaptation for Text-to-SQL (extended) — 2023 | superficial · no evidence check | none · insufficient evidence | superficial · no evidence check | superficial · nonmaterial |
| Syntactic Control of Language Models by Posterior Inference — Xefteri et al. · 2025 | none · insufficient evidence | superficial · no evidence check | none · insufficient evidence | superficial · nonmaterial |
| Weighting Finite-State Transductions With Neural Context — Rastogi et al. · 2016 | superficial · no evidence check | superficial · insufficient evidence | none · insufficient evidence | superficial · no evidence check |
| Where is the signal in tokenization space? — Geh et al. · 2024 | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check | superficial · no evidence check |
| Effect of tokenization on transformers for biological sequences — Dotan et al. · 2023 | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence | none · insufficient evidence |
Legend: Cells show overlap degree and evidence status: material = meaningful shared contribution supported; nonmaterial = examined correspondences do not support meaningful contribution overlap; insufficient = inconclusive evidence; no evidence check = no check recorded. Missing support is not proof of no overlap. Conflicting assessments are identified under Evidence limits.

## Review

---

### First extracted claim

The paper introduces transduced language models as a general framework for transforming language models with deterministic string-to-string transformations represented by finite-state transducers.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** Formalizing BPE Tokenization (Both works treat a deterministic string-to-string transformation as a finite-state transducer; specifically, the prior paper shows how BPE tokenization can be implemented online and represented by such a transducer.) [partial overlap · material]; From Language Models over Tokens to Language Models over Characters (Both papers transform a source language model over one string representation into a distribution over another representation and provide an autoregressive probability interface by summing over source strings that cover a target prefix.) [partial overlap · material]; Sampling from Your Language Model One Byte at a Time (Both works transform an existing autoregressive language model through a deterministic string-to-string mapping and provide an autoregressive interface over the transformed symbols by aggregating probabilities of compatible source token sequences.) [partial overlap · material]; How to Compute the Probability of a Word (Both papers transform or recover probabilities over a target string representation from a language model defined over another representation, using a deterministic mapping from words or characters to subword sequences and summing or factoring probabilities over appropriate source-side prefixes.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **Formalizing BPE Tokenization:** The submission generalizes beyond BPE tokenization to transduced language models: it defines the transformed probability distribution, develops prefix-probability and autoregressive interfaces, gives decomposition and exact or approximate computation algorithms, and analyzes finite-decomposition conditions for general transducers and transformations.
- **From Language Models over Tokens to Language Models over Characters:** The submission generalizes beyond strict-prefix-monotone token decoders and the token-to-character setting to deterministic string-to-string functions represented by finite-state transducers.
- **Sampling from Your Language Model One Byte at a Time:** The submission generalizes beyond BPE tokenization and byte conversion to arbitrary deterministic finite-state string-to-string transducers, including transformations such as lowercasing, orthographic boundary insertion, and DNA-to-amino-acid conversion.
- **How to Compute the Probability of a Word:** The submission generalizes beyond tokenizer mappings to arbitrary deterministic string-to-string functions encoded by finite-state transducers.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 9 of 24 comparisons have insufficient evidence, and 6 have no recorded evidence check. One comparison shows a conflict between the overlap assessment and evidence check: Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities was assessed as none while the evidence check found material overlap. This conflict remains unresolved. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 18 with an evidence check: 5 material, 4 nonmaterial, 9 insufficient.

#### What the submission does for this claim

The submission defines the transformed model by applying a deterministic string-to-string function represented by a finite-state transducer to a source language model, and supplies the probability semantics through the source-string preimage. It delivers an autoregressive interface—prefix probabilities and conditional next-symbol distributions—by decomposing the target’s precover into a maximal cylindrical quotient and a remainder, with exact computation when the decomposition is finite.

“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X . Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y.”

The algorithm searches source prefixes breadth-first and classifies them as cylinders, members of the remainder, or live prefixes; without pruning, it is correct under finite decomposition. The scope is therefore general finite-state mappings, including normalization, orthographic boundaries, and DNA-to-amino-acid conversion, while exact termination is guaranteed by stated transducer conditions such as no ε-output cycles and safety of every state. When decompositions are too large or infinite, the submission instead supports probability-mass pruning as an approximation.

“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences). In §5, we present algorithms to compute these quantities.”

#### Overlapping prior work

##### Formalizing BPE Tokenization
partial overlap · Berglund et al. · 2023

How this paper realizes the claim

The paper formalizes BPE tokenization and proves that, for proper dictionaries, tokenization can be performed left-to-right with a dictionary-dependent finite lookahead and constant memory.

“This has potential to improve tokenization performance by cache locality (where e.g. SentencePiece [4] and HuggingFace [2] access the string contents with random access), but also enables doing streaming tokenization using a constant amount of memory, for when the entire string is not available or impractical to hold in memory. One way to express this finite state tokenization approach is as a deterministic string-to-string transducer.”

“A perhaps more natural presentation of this algorithm would be constructing a string-to-string transducer. This is not very complicated, the transducer would read l(D) symbols and then, in much the same way as the precomputed f in Algorithm 2, output a token accordingly.”

Thus, the paper itself supplies a finite-state string-to-string realization of the BPE tokenization transformation, but it does not introduce language models transformed by such mappings, nor does it develop probabilities, sampling, or autoregressive interfaces for those models.

Grounded evidence for the assessed overlap

Evidence check: material
2 of 3 grounded candidates support the overlap

Pair 1 directly supports a shared transformation-side contribution: both works represent a deterministic string-to-string transformation using a finite-state string-to-string transducer. Pair 2 further supports that the prior paper realizes a narrower tokenization transformation with such a transducer, while the submission embeds the transformation in a language-model framework. This is a substantive shared component, not merely a shared topic or generic activity, so the overlap is material and the proposed partial degree is supported. Pair 3 is weaker and mainly shows a common connection between a transformation algorithm and a transducer; it is not needed because pairs 1 and 2 independently establish the relevant overlap. The delta's claims that the prior paper does not introduce the general language-model framework or address probability computations and autoregressive generation are not established by the correspondence pairs and should remain qualified as limitations of the comparison, rather than certified absences. Those limitations do not block partial-overlap support because the positive evidence already establishes a meaningful shared transformation-side component.

Submission contribution span
“A transducer is a state-machine that encodes string-to-string relations f ⊆ X * × Y *.”

Pair 1: Both papers contribute the representation of a deterministic string-to-string transformation as a finite-state string-to-string transducer.

The prior work states:
“One way to express this finite state tokenization approach is as a deterministic string-to-string transducer.”

Submission contribution span
“The transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X .”

Pair 2: The prior paper provides a narrower instance of the submission's transformation-side component: BPE tokenization is implemented as an online, left-to-right deterministic string-to-string transduction, whereas the submission applies such transformations to a source language model.

The prior work states:
“Beyond this we consider how tokenization can be performed in an incremental fashion, as well as doing it left-to-right using an amount of memory constant in the length of the string, enabling e.g. using a finite state string-to-string transducer.”

Comparison with the submission

The prior paper makes a meaningful contribution to the transformation side of the claim by showing that BPE tokenization can be realized as a finite-state string-to-string transducer with finite lookahead. However, it does not itself introduce the general framework of applying such transformations to language models or address the resulting probability computations and autoregressive generation. The submission therefore retains a distinct central contribution, making the overlap partial rather than substantial.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper develops a token-to-character transformation framework in which a token-level language model is decoded into a character-level model, and derives exact and approximate algorithms for computing character-level probabilities and next-character generation.

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms. In the empirical portion of the paper, we benchmark the practical runtime and approximation quality.”

Its transformation is represented by a decoder κ from token strings to character strings, with strict-prefix monotonicity providing the structural condition that makes the relevant infinite sum finite.

“Strict-prefix monotonicity is the key structural property required by §3’s algorithms, as it allows us to replace an infinite sum with a finite sum in Proposition 1. We briefly mention an important special case.”

The paper therefore delivers a concrete, restricted instance of transformed language modeling—token-to-character conversion—rather than a general framework for arbitrary deterministic string-to-string transformations represented by finite-state transducers.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a substantive shared methodological contribution within the current claim: both papers transform a language model from one string representation to another, and the prior paper explicitly instantiates token-to-character conversion. This is more than a shared topic or generic evaluation activity and supports meaningful partial overlap. The pair does not establish the proposed additional correspondence about an autoregressive probability interface formed by summing over source strings covering a target prefix, nor does it establish that the prior paper has the claimed general finite-state-transducer scope. Those limitations do not block the proposed partial degree because the demonstrated transformation method is itself a meaningful component of the current claim. The submission delta appropriately identifies broader mappings and a general transducer framework, but claims that these capabilities, decompositions, and finiteness conditions are absent from the prior paper are not established by the single pair; they should remain qualified rather than being treated as independently proven novelty. The pair is marked “weaker,” but its quoted spans still support the narrower transformation overlap asserted here.

Submission contribution span
“We have introduced a general framework for transforming language models using transducers.”

Pair 1: Both papers directly contribute a method for transforming a language model from token strings into a different string representation, with the prior paper instantiating this idea only for token-to-character conversion.

The prior work states:
“This paper presents algorithms for converting token-level language models to character-level ones.”

Comparison with the submission

The prior paper makes meaningful contribution-level progress on the claimed idea by showing how to transform a token language model into a character language model and compute the resulting probabilities efficiently. However, it does not itself introduce the general finite-state-transducer framework or support arbitrary deterministic string-to-string transformations; its methods rely on a restricted decoder and strict-prefix monotonicity. The overlap is therefore partial: the submission retains a distinct central contribution in generality of representation, mappings, decomposition, and theoretical conditions.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper introduces an inference-time procedure for converting an autoregressive language model with a deterministic BPE tokenizer into a byte- or character-level model, thereby treating tokenization as a deterministic string transformation.

“In this work, we present an inference-time method to convert any autoregressive LM with a BPE tokenizer into a character-level or byte-level LM. Our method efficiently solves the PBP and is also able to unify the vocabularies of language models with different tokenizers, allowing one to ensemble LMs with different tokenizers at inference time or transfer the post-training from one model to another using proxy-tuning.”

It makes the transformed model operational by constructing a finite Valid Covering Tree of token sequences compatible with a byte prefix, then using that structure to compute prefix probabilities and next-byte distributions for exact sampling.

“The fundamental structure of the algorithm is based on what we call the Valid Covering Tree, which is the tree of all possible valid token sequences that share a specific byte prefix and do not extend past the end of the prefix by more than one full token. We show the construction of the Valid Covering Tree in Fig.”

“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group. This can be combined with a sampling rule to generate text one byte at a time.”

Thus, the paper realizes one important special case of a transduced language model: transforming token-level distributions to byte-level distributions for deterministic BPE tokenization. It does not introduce a general framework for arbitrary deterministic string-to-string transformations represented by finite-state transducers; its construction and guarantees are specialized to BPE validity and bounded tokenization structure.

Grounded evidence for the assessed overlap

Evidence check: material
3 of 3 grounded candidates support the overlap

Pairs 1–3 establish a substantive shared methodological component within the current claim. Pair 1 shows that both works transform an existing autoregressive language model into a model over transformed symbols, with the prior work providing a narrower BPE-to-character/byte instance. Pair 2 supports the shared autoregressive next-symbol interface obtained by aggregating probabilities over compatible source sequences. Pair 3 independently supports shared probability computation for transformed-string prefixes by summing over compatible source sequences. These are compatible methodological roles, not merely a shared topic or evaluation activity, and together establish meaningful partial overlap. The evidence does not establish that the prior paper lacks every general finite-state-transducer idea, nor does it by itself prove all of the submission's listed generalizations, algorithms, or finiteness results. Those delta claims should therefore remain qualified rather than being treated as established solely from the correspondence pairs. That limitation does not block the partial-overlap decision, because the pairs directly establish the narrower shared transformed-language-model construction and interface.

Submission contribution span
“We have introduced a general framework for transforming language models using transducers.”

Pair 1: Both papers contribute a method for transforming an existing autoregressive language model into a model over transformed symbols, although the prior paper is restricted to BPE tokenizers and character or byte outputs.

The prior work states:
“In this work, we present an inference-time method to convert any autoregressive LM with a BPE tokenizer into a character-level or byte-level LM. Our method efficiently solves the PBP and is also able to unify the vocabularies of language models with different tokenizers, allowing one to ensemble LMs with different tokenizers at inference time or transfer the post-training from one model to another using proxy-tuning.”

Submission contribution span
“Combined with the computational shortcut (Eq. ( 6 )), this gives an autoregressive interface to transduced language models.”

Pair 2: Both papers provide an autoregressive next-symbol interface by aggregating source-model probabilities over compatible token or source-sequence alternatives, with the prior paper delivering the narrower next-byte case.

The prior work states:
“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group.”

Submission contribution span
“The following two examples illustrate how we can often compute this infinite sum by exploiting structural properties of the transducer.”

Pair 3: Both papers contribute probability computation for transformed-string prefixes by summing probabilities over compatible source token sequences, with the prior paper implementing this only for its BPE covering tree.

The prior work states:
“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree.”

Comparison with the submission

The prior paper delivers a meaningful substantive instance of the claimed contribution: an exact transformed language model over bytes, with efficient autoregressive sampling, for deterministic BPE tokenization. However, it does not itself provide the claimed general finite-state-transducer framework; its Valid Covering Tree and correctness analysis are specialized to BPE. After subtracting the token-to-byte case, the submission retains a distinct central contribution in generalizing the construction and algorithms to arbitrary deterministic string-to-string transducers, so the overlap is partial.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper does not introduce transduced language models as a general finite-state-transducer framework. It studies the narrower problem of converting subword language-model probabilities into word probabilities under deterministic tokenizers, including the need to marginalize over subword sequences that realize the same string.

“At least superficially, converting from a probability distribution over subwords p(s) into one over characters p(c) or words p(w) appears straightforward. However, some technical details are easy to overlook.”

“However, some technical details are easy to overlook. For example, several sequences of subwords s can map to a single sequence of characters c, implying an accurate computation of p(c) should marginalise over these options (Cao and Rimell, 2021). 2Despite the name, which we use out of convention, a subword need not strictly be a subunit of a word.”

It then derives probability computations for word sequences using prefix sets of subword sequences and gives tokenizer-specific methods for end-of-word and beginning-of-word marking schemes.

“In this work, we discuss how to correctly compute a word’s contextual probability: p(wt | w<t). This value’s computation depends on the choice of tokeniser used to define an LM’s vocabulary.”

“We derive methods for these tokenisation schemes, which we present in Fig.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 establishes a substantive shared component of the current claim: probability transformation between word/string representations via a mapping, specifically using subword distributions to compute word probabilities. This is a meaningful tokenization-based special case of the claimed transformed-language-model probability computation, not merely a shared topic or evaluation activity. The pair does not establish the submission's broader finite-state-transducer framework, arbitrary deterministic string-to-string transformations, prefix interfaces, or exact/approximate algorithms. Those differences support the proposed partial rather than substantial or same degree, although the quoted evidence does not independently prove every stated absence in the prior paper. Claims about the prior paper lacking the broader framework should therefore remain qualified rather than being treated as established solely from this pair.

Submission contribution span
“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X .”

Pair 1: Both papers contribute a method for transforming a language model across string representations using a deterministic mapping, with the prior paper providing a narrower tokenization-based instance of the submission’s general transducer framework.

The prior work states:
“Collectively, the mapping functions we have defined give us the ability to convert between words and subwords, which will be necessary when using subword distributions to compute word probabilities.”

Comparison with the submission

The prior paper makes meaningful contribution to probability transformation for a restricted class of deterministic tokenization mappings, so the relationship is more than topical or merely evaluative. However, it does not itself provide the claimed general transduced-language-model framework or finite-state-transducer algorithms; the submission retains a distinct central contribution in generalizing the setting and enabling efficient exact or approximate autoregressive computation for broad FST-defined transformations.

---

### Second extracted claim

The paper develops algorithms that compose language models with finite-state transducers to marginalize source-string probabilities into target outputs, enable conditioning on transformed outputs, and support exact or approximate inference without changing model parameters.

#### Claim-level conclusion

**Assessment:** challenged by prior work. At least one comparison in the examined candidate set is assessed to substantially or equivalently overlap this claim under material evidence. This does not by itself determine whether the claim should be rejected.

**Main overlap:** From Language Models over Tokens to Language Models over Characters (Both works compose a language model over source strings with a string transformation and compute probabilities over target-string prefixes by summing over source strings or source prefixes that cover the target.) [substantial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **From Language Models over Tokens to Language Models over Characters:** The submission generalizes beyond the prior paper's strict-prefix-monotone token-to-character setting to general string-to-string functions represented by finite-state transducers.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 5 of 24 comparisons have insufficient evidence, and 9 have no recorded evidence check. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 15 with an evidence check: 4 material, 6 nonmaterial, 5 insufficient.

#### What the submission does for this claim

The submission defines a transduced language model by applying a string-to-string transducer to samples from a source model, so target probabilities aggregate all source strings that produce the same target. It computes target prefix probabilities by summing source probabilities over the target’s precover, and uses finite prefix decompositions—maximal cylinders plus a remainder—to expose an autoregressive interface for next-symbol probabilities and conditioning on transformed prefixes, without retraining the source model.

“A transduced language model p Y arises from applying a string-to-string transformation f : X * → Y * , encoded by a transducer f, to a string drawn from a source language model p X . Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y.”

“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation. We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences).”

The exact algorithm is guaranteed to terminate when the precover has a finite decomposition and the checks are exact; the stated transducer-level sufficient conditions are absence of ε-output cycles and safety of every state. When exhaustive decomposition is too large, pruning retains high-probability candidates but can omit mass, making the result a lower bound rather than an exact probability. The submission demonstrates the procedure on lowercasing, token-to-byte conversion, DNA-to-amino-acid translation, and non-prefix-monotone PTB tokenization; in the reported token-to-byte benchmark, lower pruning thresholds produced lower JSD against the reference distribution at the cost of throughput.

Quoted from the source but NOT confirmed verbatim:
The conditions in Lemma 6.1 guarantee exact computation.

“Since pruning only removes candidates from the queue, every element found is correct-⟨Q⟩ ⊔ R ⊆ P(y)-but the decomposition is no longer valid in general (coverage may be incomplete), so the computed prefix probability is a lower bound on the true value. Our strategy is detailed in §C.3.”

#### Overlapping prior work

##### From Language Models over Tokens to Language Models over Characters
substantial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper develops a character-level interface for a token-level language model by exploiting a strict-prefix-monotone token-to-character decoding function. It enumerates minimally covering token prefixes so that probabilities of character prefixes can be obtained by summing the corresponding token-prefix probabilities.

“Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set. Let δ ∈∆∗, δ1 ··· δM = δ, and σ ∈Σ∗.”

“The enumeration algorithm will enumerate elements of the covering along with their prefix probability (for convenience). It filters prefixes of token strings that cannot eventually cover the target string σ. The strict-prefix monotonicity property is essential for this filtering.”

This provides exact marginalization when enumeration is unpruned, and the paper also gives an approximate beam-pruned version with a stated running-time improvement.

“This heuristic is very effective: it gives us a linear running time as a function of the character string’s length. It has a parameter K that controls the approximation quality.”

The paper further supports conditioning on a character-level prefix by sampling a minimally covering token prefix in proportion to its probability and then sampling a completion from the unchanged token model.

“The algorithm works by enumerating the covering C(σ), drawing a token string from it in proportion to its prefix probability, and finishing the token string by sampling a completion, which can be done from the token-level model. 43 def conditional_token_generation(σ): 44 δ′ ∼Categorical({δ′ : p′/−→ pΣ(σ) 45 for (p′, _, δ′) in enum_cover(σ)}) 46 return sample_completion(δ′) 47 def sample_completion(δ′): 48 δ′′ ←ε 49 while True: 50 δ ∼−→ p∆(· | δ′·δ′′) 51 if δ = EOS: break 52 δ′′ ←δ′′·δ 53 return δ′·δ′′ 7 From Language Models over Tokens to Language Models over Characters (a) Error (JSD/byte) vs.”

Grounded evidence for the assessed overlap

Evidence check: material
3 of 3 grounded candidates support the overlap

Pairs 1–3 establish substantive overlap in the current claim: both works marginalize source/token-string probability mass into transformed-output probabilities (pair 1), support conditioning or generation from transformed-output prefixes (pair 2), and provide finite computation of transformed-prefix probability quantities under structural conditions (pair 3). These matches concern the central probability-computation and conditioning paradigm, not merely a shared topic or generic evaluation activity, so they support material overlap and the proposed substantial degree. The pairs do not independently establish every detail in the proposed rationale, especially approximate computation, unchanged parameters, or the full scope of the submission’s general finite-state-transducer and non-prefix-monotone extensions. Those are limitations on the comparison’s completeness, but resolving them is not necessary to determine that the prior paper already covers the central functionality in a meaningful special case. The delta’s claims about capabilities absent from the prior paper should therefore remain qualified: the provided pairs do not prove that the prior paper lacks those features, although they do support the claimed overlap in the functionality that is evidenced.

Submission contribution span
“A core property of transduced language models is the marginalization: the transduction sums source-string probabilities to compute target-string probabilities, aggregating mass across all source strings that map to the same target.”

Pair 1: Both papers contribute algorithms that marginalize probabilities from source/token strings into probabilities for transformed target strings or target prefixes.

The prior work states:
“Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 2: Both papers provide transformed-output prefix conditioning that supports autoregressive generation from the conditioned transformed prefix.

The prior work states:
“This section gives a simple algorithm for correctly generating a token string Y that has a given character-level prompt σ as its prefix.”

Submission contribution span
“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction.”

Pair 3: Both papers contribute finite algorithms for exact transformed-prefix probability computation under structural conditions, although the prior paper restricts the transformation to strict-prefix-monotone token decoding.

The prior work states:
“From the output of the enumeration algorithm, we can compute the other key objects and quantities (i.e., C(σ), −→ pΣ(σ), E(σ), pΣ(σ)) in the character-level interface.”

Comparison with the submission

The prior paper already delivers most of the claimed functionality in a meaningful special case: it marginalizes token probabilities into character outputs, supports transformed-prefix conditioning, and offers exact and approximate algorithms without parameter changes. The overlap is therefore substantial rather than partial, because the central probability-computation and conditioning paradigm is already present, although the submission retains a distinct central contribution by extending it to general finite-state transducers and non-prefix-monotone mappings with remainders.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper develops correction algorithms for recovering character- or string-level probabilities from tokenized language models without fine-tuning. Its MPC and BPC procedures marginalize probability over token encodings that cover a queried string, thereby enabling token-free conditional prediction despite the model operating on tokens.

“To counter this universal problem, for each encoding scheme above, we propose a novel algorithm to obtain unbiased estimates from any language model trained on tokenized data. Our methods do not require finetuning the model, and the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE.”

“Our method consists of two stages. In the first stage, the idea is to identify the condition when P(xN n+1|ti 1) = P(xN n+1|xn 1) where ti 1 = encode(xn 1). Once identified, we can refactor the conditional probability to match the conditioning events.”

“For MPE, the MPC algorithm computes P(xn 1) by searching all possible valid encodings that cover xn 1, where the probability of each encoding are computed using the LMs P(ti+1|ti 1) through greedy search. However, this does not work for the case of BPE.”

Grounded evidence for the assessed overlap

Evidence check: material
3 of 3 grounded candidates support the overlap

The current claim concerns algorithms that compose language models with finite-state transducers to marginalize source-string probability into transformed outputs and obtain conditional/incremental probabilities without changing model parameters. Pair 1 validly establishes a substantive methodological overlap: both aggregate probability mass over multiple source/token strings compatible with the same target string. Pair 2 validly supports overlap in the resulting transformed-representation conditional probabilities and left-to-right conditioning. Pair 3 supports the no-retraining/no-fine-tuning aspect of transformed-output inference. Together these establish a meaningful shared component of the claim, so the overlap is material and the proposed partial degree is supported. The pairs do not establish that the prior paper supplies the submission's general arbitrary-FST composition framework, precover decompositions, finiteness results, caching/structural optimizations, or pruning-based approximate inference; those distinctions support the proposed limitation to partial overlap. The delta's assertion that the prior paper does not provide each of these components is not independently established by the correspondence pairs and should remain qualified as a comparison claim, but resolving it is not necessary to establish the supported partial overlap or distinguish it from substantial overlap given the pairs' explicit tokenization-specific scope.

Submission contribution span
“A core property of transduced language models is the marginalization: the transduction sums source-string probabilities to compute target-string probabilities, aggregating mass across all source strings that map to the same target.”

Pair 1: Both papers contribute exact marginalization of probability mass over multiple source/token encodings that cover or map to a target string; the prior paper provides a narrower tokenization-specific instance of the submission's source-to-target marginalization.

The prior work states:
“As a result, P(xn 1) can be expressed as the marginal probability of all covering tokens of xn 1 P(xn 1) = X ⃗t∈cover(xn 1 ) P(⃗t).”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 2: Both papers contribute recovery of autoregressive, transformed-representation conditional probabilities from a model operating on a different representation, supporting next-symbol or left-to-right conditioning; the prior paper handles token-free probabilities from tokenized models rather than general transducer outputs.

The prior work states:
“We propose a method to remove the described bias and recover the original token-free autoregressive model, i.e. expressing the implicitly learned P(xN n+1|xn 1) using the tokenized LM that outputs the conditional probability P(ti+1|ti 1).”

Submission contribution span
“We show how to equip these transformed models with the familiar autoregressive interfaceincremental next-symbol distributions and prefix probabilitiesmaking them interoperable with any system built for standard autoregressive language models.”

Pair 3: Both papers contribute transformed-output inference without retraining or fine-tuning the underlying language model; the prior paper delivers this only for MPE/BPE tokenization correction rather than arbitrary finite-state-transducer composition.

The prior work states:
“the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE. As a result, we show that one can simulate token-free behavior from a tokenized language model.”

Comparison with the submission

The prior paper delivers a meaningful substantive part of the claim: exact marginalization over token encodings and recovery of transformed, character-level conditional probabilities without fine-tuning. However, it does not itself develop the general finite-state-transducer composition framework, nor the associated decomposition, finiteness, and pruning algorithms. The overlap is therefore partial rather than substantial.

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper addresses conditioning a token-level language model on the event that its token string is canonical, where canonicality is defined by a deterministic tokenizer and can be represented with finite-state machinery.

“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition”

“g(δ) def= Pr Y ∼p∆[Y = δ | Y ∈D] (6b) = PrY ∼p∆[Y = δ, Y ∈D] PrY ∼p∆[Y ∈D] (6c) = 1 Z p∆(δ)1{δ ∈D} (6d) where Z is the canonicality rate: Z def= Pr Y ∈p∆[Y ∈D] (6e) 6When the tokenization function τ is implemented as a finite-state transducer, we may derive an efficient finite-state automaton that describes the prefix language of its outputs.”

It gives an exact global conditional distribution that renormalizes the original model over canonical token strings, without changing the model parameters.

“Note that gΣ(σ) = 1 Z p∆(τ(σ)), meaning that we may interpret the globally canonicalized model as renormalizing p′ Σ. We note that the effect of conditioning the language model to generate only canonical token strings may dramatically change the conditional prefix distributions of the distribution.”

The paper also develops an approximate local conditioning method that masks noncanonical next-token extensions, and sampling-based importance-weighting methods intended to recover the global conditional distribution in expectation.

“The locally canonicalized model ℓis a distribution over ∆∗that approximates ancestral_sampling for sampling from g by using the following local approximation −→ℓto the global prefix probability −→g .”

“It is efficient: The canonicality checks are cheap to compute (App. B), and there is very little additional overhead over sampling from the base conditional distribution. 9We also mention more sophisticated approximations, such as learning (Zhao et al., 2024), adaptive upper bounds (Park et al., 2025), and sequential Monte Carlo steering (Lew et al., 2023; Loula et al., 2025).”

“Therefore, in expectation and in the limit, these methods produce exact samples; thus, they do not warp the distribution. The warping in the locally canonicalized method can occur because the sampling algorithm approximated the conditional prefix probability canonicality, meaning that we may sample a string of tokens that looks good initially, but we end up stuck with a bad string prefix because we overestimated the conditional prefix probability.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 1 establishes a substantive shared component: both works alter or restrict a language-model distribution through a string-level transformation or constraint, with the prior work conditioning on the language of permitted token strings. This supports meaningful partial overlap in conditioning a language model on finite-state/string-structured output constraints, although the quoted spans do not by themselves establish all details of the prior paper’s canonical-output construction or exact inference procedures. Pair 2 is not independently sufficient: the submission span only states that exhaustive scoring may be infeasible, while the prior span describes a sampling-based local approximation. Those spans do not clearly establish compatible approximate inference contributions or the same transformed distribution. The proposed partial degree is nevertheless supported by Pair 1’s meaningful shared conditioning component; the submission’s broader arbitrary-transducer marginalization and inference framework is not shown to be shared. Claims in the delta that the prior paper does not provide general transducer composition, or that its machinery is limited to canonicality testing, are absence/scope assertions not established by these non-exhaustive pairs and should remain qualified, but they are not necessary to establish the partial overlap.

Submission contribution span
“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences).”

Pair 1: Both works contribute inference for a language model whose output distribution is restricted by a string-level transformation or constraint; the prior paper provides the narrower special case of conditioning on canonical token strings.

The prior work states:
“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition”

Comparison with the submission

The prior paper delivers a meaningful specialized conditioning case: it conditions a token model on the canonical language induced by a tokenizer and supplies exact and approximate inference procedures for that event. However, it does not itself provide the submission's general transducer-composition and source-to-target marginalization framework; its finite-state machinery is used for canonicality testing rather than for general transformed-output probability computation. The overlap is therefore partial: the submission retains a distinct central contribution in general exact/approximate inference for arbitrary finite-state transformations.

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper addresses a specialized instance of composing a language model with a finite-state-like tokenizer transformation: it conditions a BPE-tokenized model on arbitrary byte prefixes, thereby resolving token-boundary mismatch without retraining or changing model parameters.

“We introduce an efficient procedure to condition a BPE tokenizer-based model on an arbitrary byte-prefix given only access to the tokenizer and log-probability queries to the model (Section 3). We demonstrate in experiments that this represents an exact solution to the Prompt Boundary Problem presented above (Section 4.2).”

“We show that our method can be used to convert the model into a byte-level language model and that this ability can be used to unify the vocabularies of different models. This enables exact byte-level ensembles of language models with different tokenizers (Section 4.3) and allows one to transfer the post-training of one model onto another model at inference time using proxy-tuning [33] (Section 4.4).”

Its core realization is the Valid Covering Tree, which enumerates valid token sequences compatible with a byte prefix and supports summing their probabilities, sampling continuations, and computing next-byte distributions.

“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree. To sample a continuation of a prefix, we compute the probability (as above) of every leaf and sample one of them accordingly.”

“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group. This can be combined with a sampling rule to generate text one byte at a time.”

The paper provides an exact solution for its prompt-boundary problem, subject to its treatment of invalid token sequences, and also discusses byte-level ensembles and proxy-tuning. It does not develop a general algorithm for arbitrary string-to-string finite-state transducers, general target-output marginalization, or approximate inference via probability pruning.

Grounded evidence for the assessed overlap

Evidence check: material
3 of 4 grounded candidates support the overlap

Pairs 1–3 establish a substantive shared component of the current claim: both works aggregate language-model probability over multiple source sequences compatible with a transformed output or prefix, use this for transformed-output conditioning, and derive autoregressive next-symbol inference. This is a meaningful specialized part of the submission’s contribution, not merely a shared topic or generic evaluation activity. The evidence also supports a narrower scope for the prior work: its transformation and conditioning procedure is tied to BPE tokenization and byte prefixes, whereas the submission describes a general class of mappings and broader transformed-output inference. That supports partial overlap, although the pairs do not by themselves establish every asserted submission-side novelty, such as quotient/remainder decompositions, finite-decomposition conditions, or probability-mass pruning. Those limitations do not block the partial-overlap decision. Pair 4 should not be treated as strong evidence of the same pruning contribution: it shows pruning in both works, but the quoted pruning criteria serve different purposes and do not establish shared probability-mass-based approximate marginalization.

Submission contribution span
“Formally, if X ∼ p X , then f (X) has the following probability mass function: where 2 ), we sum over the strings x such that f (x) = y.”

Pair 1: Both works compute probabilities of transformed or constrained outputs by aggregating language-model probability across multiple compatible source token sequences; the prior paper delivers this for BPE-valid sequences covering a byte prefix.

The prior work states:
“To compute the probability of a prefix under the LM, we sum the cumulative probabilities the LM assigns to the sequences represented by all leaves of the tree.”

Submission contribution span
“We develop a method in §4 that allows us to compute the sum in Eq. ( 3 ) in finite time for a general class of mappings, such as those mentioned in the introduction (i.e., normalizing text, inserting orthographic word boundaries, or converting DNA to amino-acid sequences).”

Pair 2: Both works contribute an exact procedure for conditioning a language model on a transformed-string prefix by summing probabilities over compatible source sequences; the prior paper provides the narrower BPE-to-byte-prefix case.

The prior work states:
“We introduce an efficient procedure to condition a BPE tokenizer-based model on an arbitrary byte-prefix given only access to the tokenizer and log-probability queries to the model (Section 3).”

Submission contribution span
“Prefix probabilities yield a conditional factorization of string probability (see §2), enabling efficient left-to-right autoregressive generation.”

Pair 3: Both works turn transformed-prefix probabilities into autoregressive next-symbol inference; the prior paper specializes this interface to byte-by-byte generation under BPE tokenization.

The prior work states:
“To compute the next byte distribution given a prefix, we group the leaves by the next byte they would entail and sum the probabilities (as above) of the leaves in each group.”

Comparison with the submission

The prior paper delivers a meaningful specialized part of the claimed contribution: exact transformed-output conditioning and probability aggregation for the particular transformation induced by BPE tokenization. However, its Valid Covering Tree is specialized to BPE validity and prompt-boundary sampling, rather than a general finite-state-transducer composition framework with arbitrary output transformations and explicit exact/approximate marginalization. Important central novelty therefore remains in the submission, so the overlap is partial rather than substantial.

---

### Third extracted claim

The paper gives sufficient transducer-level conditions guaranteeing finite prefix decompositions for every target string, including transformations that are not prefix monotone.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** From Language Models over Tokens to Language Models over Characters (Both works provide sufficient conditions under which an otherwise potentially infinite prefix-based decomposition or covering becomes finite for every target string.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **From Language Models over Tokens to Language Models over Characters:** The submission contributes the transducer-level characterization using the absence of ε-output cycles and inductive state safety, including IP-universality and finite-closure cases, and explicitly supports non-prefix-monotone transformations with a remainder.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 13 of 24 comparisons have insufficient evidence, and 9 have no recorded evidence check. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 15 with an evidence check: 1 material, 1 nonmaterial, 13 insufficient.

#### What the submission does for this claim

The submission provides a sufficient, transducer-level criterion ensuring that the quotient and remainder—and hence the prefix decomposition—are finite for every target string, without requiring prefix monotonicity. The criterion applies to a function realized by a transducer when it has no all-ε-output cycles and every state satisfies an inductive safety condition.

“Lemma 6.1. Let f : X * → Y * be a function realized by a transducer f. The decomposition (Q(y), R(y)) is finite for every y ∈ Y * if: (i) No ε-output cycles: f contains no cycle in which every arc outputs ε.”

The stated scope includes non-prefix-monotone transformations because the decomposition retains a remainder for source strings whose extensions do not continue to cover the target. The result guarantees exact finite computation under the conditions, but the conditions are only sufficient, not necessary; the submission also reports that the experimental token-to-byte and DNA-to-amino-acid transducers meet them, whereas the PTB transducer has infinite quotients.

“The conditions in Lemma 6.1 guarantee exact computation. In particular, these are satisfied by the transducers introduced in the experiments section ( §7): the token-to-byte transducer f α and the DNA-to-amino-acid transducer f dna2aa , whose quotients are finite and remainders empty, but not by the PTB transducer f ptb , whose quotients are infinite. The lemma's conditions are sufficient but not necessary”

#### Overlapping prior work

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

The paper defines strict-prefix monotonicity as a sufficient structural property of its token-to-character decoder.

“Strict prefix monotonicity is the key structural property required by §3’s algorithms, as it allows us to replace an infinite sum with a finite sum in Proposition”

It then constructs the covering of a target string from minimally covering token prefixes and proves that this covering is finite, with an explicit size bound.

Quoted from the source but NOT confirmed verbatim:
In all cases, CF M(N) < ∞.

However, the paper does not give transducer-level safety or cycle conditions, and its algorithms assume strict-prefix monotonicity rather than handling transformations that are not prefix monotone.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a substantive overlap in the current claim: both works provide a sufficient condition or structural method yielding a finite prefix-based decomposition/covering for every target string. The roles are compatible at the level of the claimed finiteness result, although the submission states transducer-level conditions and explicitly handles non-prefix-monotone functions, while the prior paper relies on prefix monotonicity and describes a finite summation set rather than the submission’s full characterization. This supports a meaningful but narrower shared component, hence partial overlap. The pair does not establish that the prior paper supplies transducer-level conditions, handles non-prefix-monotone transformations, or covers quotient/remainder finiteness; those delta assertions may remain qualified, but they are not needed to establish the partial overlap. No rejected pair is present, and no unsupported absence claim is required to justify the degree.

Submission contribution span
“Lemma 6.1 gives sufficient conditions on a transducer that guarantee a finite decomposition for every target string, even when the underlying function is not prefix monotone.”

Pair 1: Both works contribute sufficient conditions that turn an otherwise infinite prefix-based set into a finite decomposition or covering for each target string; the prior paper provides the narrower prefix-monotone case, whereas the submission gives transducer-level conditions that also cover non-prefix-monotone functions.

The prior work states:
“Although P(σ) is infinitely large, we can exploit the prefix monotone structure of κ to find a different way to perform the summation by summing over a finite set.”

Comparison with the submission

The prior paper delivers a meaningful function-level sufficient condition for finite decompositions and proves finiteness of its covering, so the relationship is more than topical or merely evaluative. Nevertheless, it does not provide transducer-level conditions or address non-prefix-monotone transformations; those are central contributions that remain in the submission. The overlap is therefore partial rather than substantial.

---

### Fourth extracted claim

The paper demonstrates inference-time adaptation of pretrained language models to bytes, words, and amino acids without retraining.

#### Claim-level conclusion

**Assessment:** not challenged in the examined literature. No comparison in the examined candidate set was found to substantially or equivalently overlap this claim under material evidence. This does not establish novelty across the wider literature -- only that none was found here.

**Main overlap:** Sampling from Your Language Model One Byte at a Time (Both papers substantively adapt pretrained token-based language models at inference time to operate over bytes without modifying or retraining the underlying language model.) [partial overlap · material]; Understanding and Mitigating Tokenization Bias in Language Models (Both papers perform inference-time transformation of a pretrained token-level language model into a byte- or character-level model without retraining, by aggregating probabilities over token sequences or encodings compatible with the desired output prefix.) [partial overlap · material]; How to Compute the Probability of a Word (Both papers substantively derive word-level distributions or probabilities from pretrained subword/token-level language models by accounting for the mappings between source units and words.) [partial overlap · material]; Language Models over Canonical Byte-Pair Encodings (Both works use inference-time operations on pretrained token language models to obtain distributions over a different representation without retraining.) [partial overlap · insufficient]; From Language Models over Tokens to Language Models over Characters (Both works adapt pretrained token-level language models at inference time to produce distributions over a different representation without retraining the underlying model.) [partial overlap · material]; Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities (Both works repurpose pretrained language models at inference time without retraining to obtain probabilities over a different unitization of text.) [partial overlap · material].

**Remaining contribution relative to the strongest supported comparison(s):**

- **Sampling from Your Language Model One Byte at a Time:** The submission provides a general transducer-based framework that extends inference-time adaptation beyond bytes to orthographic words and amino acids, supplies general exact and approximate algorithms for composing language models with string transformations, and empirically evaluates all three target domains.
- **Understanding and Mitigating Tokenization Bias in Language Models:** The submission provides a general transducer-based framework and algorithms covering not only tokens-to-bytes but also orthographic word boundaries and DNA-to-amino-acid conversion.
- **How to Compute the Probability of a Word:** The submission contributes a general transducer-based framework for inference-time language-model adaptation across output units, with algorithms for exact or approximate probability computation and demonstrations for bytes, orthographic words, and amino acids.
- **From Language Models over Tokens to Language Models over Characters:** The submission extends the adaptation framework beyond bytes to orthographic words and amino-acid sequences, using transducer-defined transformations and demonstrating all three settings. It also presents a more general transducer framework and associated algorithms for these transformations.
- **Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities:** The submission provides a general transducer-based framework and algorithms for inference-time transformation, including token-to-byte conversion, PTB-style word-boundary conversion, and DNA-to-amino-acid conversion.

These are comparison-specific differences, not a synthesis across all prior work. Evidence supporting overlap does not automatically verify every stated difference or absence claim; see each comparison’s evidence assessment.

**Evidence limits:** 10 of 24 comparisons have insufficient evidence, and 3 have no recorded evidence check. Insufficient evidence means the check could not settle the question, not that no overlap exists.

**Coverage:** 24 comparisons processed, 21 with an evidence check: 5 material, 6 nonmaterial, 10 insufficient.

#### What the submission does for this claim

The submission presents a transducer-based method for adapting pretrained language models at inference time: it composes an unchanged source model with a finite-state transformation, then uses exact or approximate decomposition algorithms to compute probabilities, sample, score, and condition over transformed units. The demonstrated transformations cover bytes, orthographic word boundaries, and amino acids.

“FSTs provide explicit structure for tracing how probabilities from the original model should map to output sequences. This allows us to develop exact and approximate algorithms for efficient sampling, scoring, and conditioning on transformed strings, all without modifying the underlying language model. We give sufficient conditions for when the transformations can be made exactly ( §6) and approximations when exact transformations are infeasible ( §5).”

Empirically, the approximation was evaluated on token models converted to bytes, token models converted to Penn Treebank word units, and a DNA model converted to amino-acid sequences. The reported evaluation used Wikitext-2 text for the byte and PTB settings and 65 sampled human proteins for DNA-to-amino-acid conversion; lower pruning thresholds generally reduced divergence from reference distributions but reduced throughput, while the amino-acid case additionally required capping the candidate set because its decomposition grows exponentially with sequence length.

“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining. Our theoretical analysis characterizes the conditions under which such mappings can be performed exactly.”

#### Overlapping prior work

##### Sampling from Your Language Model One Byte at a Time
partial overlap · Hayase et al. · 2025

How this paper realizes the claim

The paper presents an inference-time procedure that converts autoregressive language models with BPE tokenizers into byte- or character-level models, addressing arbitrary byte-prefix conditioning without retraining.

“In this work, we present an inference-time method to convert any autoregressive LM with a BPE tokenizer into a character-level or byte-level LM. Our method efficiently solves the PBP and is also able to unify the vocabularies of language models with different tokenizers, allowing one to ensemble LMs with different tokenizers at inference time or transfer the post-training from one model to another using proxy-tuning.”

It develops the Valid Covering Tree to sample one byte at a time and applies the resulting byte-level models to inference-time ensembling and proxy-tuning.

“We introduce an efficient procedure to condition a BPE tokenizer-based model on an arbitrary byte-prefix given only access to the tokenizer and log-probability queries to the model (Section 3). We demonstrate in experiments that this represents an exact solution to the Prompt Boundary Problem presented above (Section 4.2).”

“We show that our method can be used to convert the model into a byte-level language model and that this ability can be used to unify the vocabularies of different models. This enables exact byte-level ensembles of language models with different tokenizers (Section 4.3) and allows one to transfer the post-training of one model onto another model at inference time using proxy-tuning [33] (Section 4.4).”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 1 directly supports the asserted substantive overlap: both papers perform inference-time conversion/adaptation of pretrained token-based/autoregressive language models to byte-level representations without retraining. This is a meaningful component of the current claim, so the overlap is material and supports the proposed partial degree. Pair 2 provides weaker, compatible support for inference-time changes to the effective output representation, but it does not by itself establish the specific byte-level overlap as clearly as pair 1. The stated delta—that the submission additionally covers words and amino acids and presents a broader transducer-composition framework—is not fully established as an absence claim about the prior paper merely from these pairs; it should remain qualified rather than being treated as certified residual novelty. That limitation does not block the partial-overlap determination because pair 1 independently establishes the shared byte-level contribution, and the proposed degree does not require proving that every other component is absent from the prior paper.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time conversion of pretrained token-based/autoregressive language models into byte-level models without retraining the underlying model.

The prior work states:
“In this work, we present an inference-time method to convert any autoregressive LM with a BPE tokenizer into a character-level or byte-level LM. Our method efficiently solves the PBP and is also able to unify the vocabularies of language models with different tokenizers, allowing one to ensemble LMs with different tokenizers at inference time or transfer the post-training from one model to another using proxy-tuning.”

Comparison with the submission

The overlap is partial: the prior paper already contributes inference-time byte-level conversion of pretrained language models, which is a meaningful part of the claim. However, it does not itself demonstrate adaptation to orthographic words and amino acids or provide the submission's general transducer framework, so an important central contribution remains beyond the prior work.

##### Understanding and Mitigating Tokenization Bias in Language Models
partial overlap · Phan et al. · 2024

How this paper realizes the claim

The paper addresses inference-time adaptation of tokenized language models to token-free, character-level predictions by correcting the sampling bias introduced by tokenization, without fine-tuning.

“Our methods do not require finetuning the model, and the complexity, defined as the number of model runs, scales linearly with the sequence length in the case of MPE. As a result, we show that one can simulate token-free behavior from a tokenized language model.”

Its MPC algorithm recursively obtains probabilities for character prefixes from next-token probabilities, thereby simulating token-free behavior from a pretrained tokenized model.

“We present the MPC algorithm in Algorithm 1, that allows us to compute the probabilities P(xN nk+1|tk 1) and P(xn nk+1|tk 1) in Equation (1). Note that this algorithm does not require tk∈V∗.”

“As a result, we show that one can simulate token-free behavior from a tokenized language model. We empirically verify the correctness of our method through a Markov-chain setup, where it accurately recovers the transition probabilities, as opposed to the conventional method of directly prompting tokens into the language model.”

The paper also generalizes the correction procedure to BPE and MPE through its BPC algorithm, which aggregates probabilities over valid encodings covering a character string.

“The Byte-Pair Correction (BPC) algorithm, shown in Algorithm 2 and visualized in Figure 5 (right), which is an efficient algorithm that can search all valid encodings covering xn 1. The idea is that, for each cover encoding ⃗t, once the starting position of the last token is determined (say xi+1), we are guaranteed the prior tokens is unique and must be encode(xi 1).”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 supports a substantive shared component: both the submission and prior paper concern inference-time conversion of token-based language-model behavior to character/byte-level output, rather than merely sharing a topic or evaluation activity. The prior quote specifically establishes the next-character/token-free case, while the submission quote establishes byte-level transduction without retraining; this supports the proposed partial overlap, though the prior span does not by itself establish the full broader framework or all details of pretrained-model adaptation as explicitly as the submission does. The pair does not establish overlap for word-boundary or amino-acid transformations, nor equivalence of the general transducer framework, so it does not support a higher degree. Claims that the prior paper does not contribute word- or amino-acid-level adaptation, or lacks the submission's framework, should remain qualified because absence is not demonstrated by this single correspondence pair; those limitations are non-blocking for the partial-overlap decision.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time adaptation of a pretrained token-level language model to character- or byte-level output without retraining, although the prior paper delivers the narrower token-free/next-character case rather than the submission’s broader transducer framework and multiple output domains.

The prior work states:
“For N=n+1, this captures the behavior of a token-free model, i.e. sampling the next character instead of a whole token.”

Comparison with the submission

The prior paper itself delivers a meaningful part of the claimed contribution: inference-time byte/character adaptation of pretrained tokenized language models without retraining. However, it does not deliver the claimed word-boundary or amino-acid transformations, nor the submission's general transducer framework. The overlap is therefore substantive but limited to one major component of the broader claim, leaving important central novelty in the submission.

##### How to Compute the Probability of a Word
partial overlap · Pimentel et al. · 2024

How this paper realizes the claim

The paper derives how to obtain contextual word probabilities from subword language models, with tokeniser-dependent treatment of beginning-of-word and end-of-word markers.

“In this work, we discuss how to correctly compute a word’s contextual probability: p(wt | w<t). This value’s computation depends on the choice of tokeniser used to define an LM’s vocabulary.”

For beginning-of-word tokenisers, it identifies the need to discount continuations that do not begin a new word and gives an explicit computation using the model's existing subword probabilities.

Quoted from the source but NOT confirmed verbatim:
Computing probabilities with nearinstantaneous codes thus requires discounting the probability of continuations st+1 /∈Sbow ∪{eos}; we label this discount factor as Bug Fix 1 .

“Further, we can compute a word’s probability as: p(w | w<t) = (20) |sw| {s∈Sbow}p (s | sw<t◦sw) P t′ | sw<t ◦sw Y sw 竹 p <t′ {s∈Sbow}p (s | sw<t) P t′=1 | {z } | {z } p(sw | sw<t) Bug Fix”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly connects the submission’s transduced mapping from subword tokens to word-like PTB tokens with the prior paper’s method for computing contextual word probabilities from a subword language model. These spans support a substantive shared word-level probability-computation component, not merely a shared topic or generic evaluation activity. They do not establish equivalence of the full contributions: the submission span supports a broader transduced-language-model framework, while the prior span specifically states correct contextual word-probability computation. Thus the evidence supports the proposed partial degree and does not support substantial or same. The submission delta’s claims that the prior paper lacks byte and amino-acid transformations and the full general transducer framework are not established by the single pair; those limitations should remain qualified rather than treated as independently proven novelty. That limitation is non-blocking because the pair already establishes the meaningful shared word-level component required for partial overlap.

Submission contribution span
“Composing p X • f α • f ptb yields a transduced language model, mapping subword tokens to PTB tokens.”

Pair 1: Both contribute a method for obtaining word-level language-model probabilities from subword-token language models; the prior paper provides the narrower word-probability computation rather than the submission’s general transducer-based adaptation framework.

The prior work states:
“In this work, we discuss how to correctly compute a word’s contextual probability: p(wt | w<t).”

Comparison with the submission

The prior paper delivers a meaningful substantive part of the claimed contribution in the word case: it computes word probabilities from pretrained subword models without retraining and addresses an important tokenisation subtlety. However, it does not itself demonstrate the general transducer-based adaptation framework or the byte and amino-acid cases, so an important central contribution remains in the submission. The overlap is therefore partial rather than substantial or same.

##### Language Models over Canonical Byte-Pair Encodings
partial overlap · Vieira et al. · 2025

How this paper realizes the claim

The paper introduces inference-time canonicalization of a pretrained BPE language model by conditioning its token outputs to remain in the set of canonical encodings, without additional training.

“Canonicality by conditioning: We explore efficient testtime inference methods for conditionally generating text that satisfies the canonicality constraint without retraining. • Canonicality by construction: We explore methods that impose canonicality constraints directly in the language model’s parameterized architecture and give a method to fine-tune its parameters.”

This produces a character-string distribution by renormalizing the probability of the canonical BPE encoding of each string, rather than providing a general transducer framework for arbitrary output units.

“We note that gΣ(σ) = 1 Z p∆(τ(σ)), meaning that we may interpret the globally canonicalized model as renormalizing p′ Σ.”

Grounded evidence for the assessed overlap

Evidence check: insufficient

Pair 1 establishes that the submission performs inference-time transduction of a pretrained token-based language model into byte, word, and amino-acid models without retraining. The prior-paper quote establishes probabilistic conditioning on token strings belonging to a set D, but the quoted span does not itself show that D represents canonical character/byte strings or that the paper obtains a distribution over such a different representation. Thus the two spans do not yet establish the asserted shared contribution in compatible semantic roles. Pair 2 similarly supports test-time canonicality-constrained generation without retraining, but does not establish conversion to a byte- or character-level distribution. The pairs therefore do not provide a valid material overlap pair for the specific rationale. The submission-delta assertions about a general transducer framework, word- and amino-acid-level adaptation, and the prior paper’s restrictions are not established by these pairs; those limitations do not independently establish novelty, but the missing representation-level evidence is blocking because it determines whether any substantive overlap exists.

Submission contribution span
“Empirically, we have shown that our beam-summing approximation efficiently transduces tokenbased LLMs into models over bytes, words, and even amino acids, without requiring retraining.”

Pair 1: Both papers contribute inference-time adaptation of a pretrained token language model to a different, constrained output representation without retraining; the prior paper's narrower instance is canonical BPE/token-string conditioning rather than the submission's byte, word, and amino-acid transductions.

The prior work states:
“Our first approach to this problem defines a language model g that is the result of probabilistic conditioning on the event that the generated token string is in D. Definition”

Submission contribution span
“conditioning on transformed strings, all without modifying the underlying language model.”

Pair 2: Both papers contribute test-time inference procedures that adapt outputs of an existing language model without changing or retraining its underlying model; the prior paper addresses only canonicality-constrained generation.

The prior work states:
“We explore efficient testtime inference methods for conditionally generating text that satisfies the canonicality constraint without retraining. • Canonicality by construction: We explore methods that impose canonicality constraints directly in the language model’s parameterized architecture and give a method to fine-tune its parameters.”

evidence_sufficient=False
unresolved_deficit: Whether the prior paper’s constrained set D and canonicality-constrained generation establish inference-time conversion from BPE-token modeling to a canonical character/byte-string distribution, as asserted in the proposed shared contribution (primarily pair 1, with pair 2 only showing canonicality-constrained generation). Resolving this matters because, without that representation-level conversion, the pairs do not establish substantive overlap with the submission’s byte-level adaptation and therefore cannot support the proposed partial degree.

Comparison with the submission

The prior paper makes a substantive contribution to inference-time adaptation from BPE tokens to canonical character strings, which overlaps with the submission's byte-level use case. However, it does not itself provide the submission's general transducer framework or its adaptations to orthographic words and amino acids. Important central novelty therefore remains in the submission, making the overlap partial rather than substantial.

##### From Language Models over Tokens to Language Models over Characters
partial overlap · Vieira et al. · 2024

How this paper realizes the claim

“This paper presents algorithms for converting token-level language models to character-level ones. We present both exact and approximate algorithms.”

Quoted from the source but NOT confirmed verbatim:
We present both exact and approximate algorithms.

The paper empirically evaluates this conversion for byte-level character distributions, including approximation quality and runtime, but it does not itself demonstrate adaptation to orthographic words or amino acids.

Grounded evidence for the assessed overlap

Evidence check: material
1 of 2 grounded candidates support the overlap

Pair 1 establishes a substantive overlap in the bytes/character component: both works address conversion of token-level language models to a different byte/character-level representation using an algorithmic conversion procedure. This is a meaningful component of the current claim and supports the proposed partial degree, without establishing overlap in the word or amino-acid components. Pair 2 is not valid evidence for the proposed shared contribution: the submission span concerns an algorithm for computing next-symbol distributions, whereas the prior-paper span reports a compression-rate result; these do not express compatible contribution roles or establish the same finding. The delta's assertion that the prior paper does not deliver word- or amino-acid-level adaptation is not established by the listed pairs and should remain qualified, but that limitation is not necessary to establish the independently supported partial overlap.

Submission contribution span
“We revisit the algorithm for converting models from tokens to bytes, as in Vieira et al. (2025a).”

Pair 1: Both papers contribute inference-time conversion of token-level language models into byte/character-level models using exact or approximate inference, directly instantiating the bytes component of the claimed contribution.

The prior work states:
“This paper presents algorithms for converting token-level language models to character-level ones.”

Comparison with the submission

The prior paper itself makes a meaningful contribution to inference-time conversion of token-level models to byte/character-level models, which directly overlaps one component of the claim. However, it does not deliver the claimed word- or amino-acid-level adaptation, so important substantive novelty remains in the submission. The overlap is therefore partial rather than substantial or same.

##### Leading Whitespaces of Language Models’ Subword Vocabulary Pose a Confound for Calculating Word Probabilities
partial overlap · Oh et al. · 2024

How this paper realizes the claim

The paper proposes an inference-time decoding correction for pretrained subword language models that reallocates leading-whitespace probability to the preceding word, thereby producing consistent word probabilities without changing or retraining the model.

“We present a simple decoding technique to reaccount the probability of the trailing whitespace into that of the current word, which resolves this confound. Experiments show that this correction reveals lower estimates of garden-path effects in transitive/intransitive sentences and poorer fits to naturalistic reading times.”

“As WT decoding simply involves the factorization of whitespace probabilities by marginalizing over tokens in VB and rearranging them, it requires no modifications to the LM and minimal overhead. Additionally, the joint probability of the entire sequence, and therefore metrics like perplexity, changes minimally by a factor of the probability of the final trailing whitespace with WT decoding.”

Grounded evidence for the assessed overlap

Evidence check: material
1 of 1 grounded candidates support the overlap

Pair 1 validly establishes a substantive overlap: both works adapt a pretrained subword language model at inference time, without retraining, to obtain probabilities over orthographic word units. The roles are compatible: the submission uses transducers to encode transformations, while the prior paper reallocates trailing-whitespace probability to the current word. This supports the proposed partial overlap in the word-level use case, but not substantial or same overlap, because the pair does not establish equivalence of the broader transducer framework, byte transformation, amino-acid transformation, or the full set of probability-computation and sampling capabilities. The assertions that the prior paper does not provide those additional components are not established by the single correspondence pair and should remain qualified; they do not block the partial-overlap determination because the shared word-level contribution is independently demonstrated.

Submission contribution span
“We generalize these approaches to handle all of the examples given above. pose pretrained language models with transducers that encode such transformations”

Pair 1: Both works contribute an inference-time method for transforming the probability distribution of a pretrained subword language model into probabilities over orthographic word units without modifying or retraining the underlying language model.

The prior work states:
“We propose a simple and efficient decoding method that reaccounts the probability of the trailing whitespace into that of the current word, which resolves this confound.”

Comparison with the submission

The overlap is substantive but limited to the word-level, inference-time adaptation aspect. The prior paper does not provide the submission's general transducer framework or its byte and amino-acid transformations, so important central novelty remains beyond the prior paper.

---

Text in quotation marks (“…”) is quoted verbatim from the document it is attributed to and was checked against that document automatically. Everything else is the system's own prose.

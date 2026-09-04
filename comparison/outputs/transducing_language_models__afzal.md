# Novelty Assessment (Afzal et al. pipeline)

## Reviewer summary

This submission presents a general framework for composing language models (LMs) with deterministic string-to-string transformations using finite-state transducers (FSTs), enabling modular inference-time adaptation without retraining. The main novelty lies in generalizing and formalizing prior automata-based and inference-time adaptation methods to arbitrary deterministic mappings, subsuming earlier work on tokenization, canonicalization, and constraint enforcement as special cases. While the framework is broader and more modular than previous approaches, the underlying algorithms are adaptations of standard FST techniques, and the technical advances are primarily in scope rather than fundamentally new methods. The authors’ claims of “first formalization” and “novel algorithms” are somewhat overstated, as prior work formalizes and implements special cases and addresses similar marginalization challenges. Overall, the submission’s contribution is a substantive generalization and unification of existing methods, but reviewers should note that the technical depth is incremental and the practical novelty may be limited for common use cases.

---

# NOVELTY DELTA ANALYSIS FOR REVIEWER SUPPORT

## 1. RESEARCH CONTEXT POSITIONING

**Landscape Placement:**  
The submission sits at the intersection of automata-based formal methods and inference-time adaptation for language models (LMs). It proposes a general framework for composing LMs with deterministic string-to-string transformations, formalized via finite-state transducers (FSTs), and provides algorithms for exact and approximate marginalization over source strings mapping to a given target.

**Most Closely Related Prior Works:**
- **Automata-based constraints for language model decoding**: Uses FSTs to enforce output constraints during decoding.
- **Where is the signal in tokenization space?**: Studies marginalization over tokenizations, with approximate inference algorithms.
- **Language Models over Canonical Byte-Pair Encodings**: Enforces canonical tokenizations via automata and conditioning.
- **Sampling from Your Language Model One Byte at a Time**: Converts token-level LMs to byte-level at inference via marginalization.
- **Understanding and Mitigating Tokenization Bias in Language Models**: Corrects tokenization-induced bias via theoretical and algorithmic means.
- **Neural Finite-State Transducers: Beyond Rational Relations**: Explores neural FSTs for sequence modeling.

**Relation to Methodological Clusters:**
- **Automata/Formal Methods Cluster**: The submission generalizes automata-based adaptation, moving beyond constraint enforcement to full probabilistic marginalization and conditioning.
- **Inference-Time Adaptation Cluster**: It provides a unified, modular approach for adapting LMs at inference, subsuming several prior ad hoc or task-specific methods.
- **Tokenization Adaptation Cluster**: While prior work focuses on specific tokenization issues, the submission’s framework is more general, handling arbitrary deterministic string-to-string mappings.

**Problem Space and Evaluation:**
- **Problem**: Mismatch between LM outputs and application requirements, intractability of marginalization/conditioning after transformations, and the need for modular, retrain-free adaptation.
- **Evaluation**: Focuses on next-symbol accuracy, prefix probability, and efficiency—metrics common in both automata-based and inference-time adaptation literature.

**Independent Assessment:**  
The submission’s main novelty is the generalization and formalization of inference-time adaptation via FSTs, providing both exact and approximate algorithms for probability propagation and marginalization. This is broader than most prior work, which typically targets specific transformations (e.g., tokenization, canonicalization) or constraints.

---

## 2. AUTHOR CITATION ANALYSIS

**Patterns in Author Positioning:**
- Authors consistently position prior work as either limited to specific transformations (e.g., tokenization, canonicalization) or as lacking general, modular frameworks for adaptation.
- They emphasize that previous methods are either ad hoc, approximate, or only enforce constraints rather than enable full probabilistic adaptation.

**Accuracy and Balance:**
- **Where is the signal in tokenization space?**: Authors cite this as focusing on aggregating probability mass over noncanonical tokenizations, which is accurate, but the prior work also discusses the general hardness of marginalization and proposes approximate inference—closer to the submission’s aims than implied.
- **Language Models over Canonical Byte-Pair Encodings**: Cited as enforcing canonical tokenization via conditioning; this is accurate, but the submission’s claim of generalization is fair, as canonicalization is a special case of deterministic string-to-string mapping.
- **Automata-based constraints for language model decoding**: Cited as using FSTs for constraint enforcement, not for full probabilistic adaptation. This is accurate; prior work focuses on enforcing constraints, not marginalizing over all possible source strings.
- **Sampling from Your Language Model One Byte at a Time**: Cited as a practical method for byte-level adaptation from subword models. The submission’s framework subsumes this as a special case.
- **Neural Finite-State Transducers**: Cited as assigning neural weights to transitions and computing path-sums. The submission’s approach is more general in that it composes arbitrary LMs with deterministic FSTs, rather than learning FSTs directly.

**Discrepancies and Rhetoric:**
- In some cases, the authors understate the generality or technical sophistication of prior work (e.g., “bespoke procedure” for Pimentel & Meister (2024)), when those works do address general marginalization but in more limited settings.
- The claim that this is the “first formalization” of LM adaptation via deterministic string-to-string transformations as fully functional LMs is somewhat overstated, as prior work (e.g., canonicalization, byte-level adaptation) formalizes special cases, though not the general case.

**Substantiation of Claimed Improvements:**
- The authors’ claims of generality and modularity are mostly substantiated, but the degree of novelty over the most general prior work (e.g., “Where is the signal in tokenization space?”) is less than implied.

---

## 3. CONTRIBUTION DELTA ANALYSIS

### Contribution 1: **General Framework for Composing LMs with Deterministic String-to-String Transformations via FSTs**

- **Most Similar Prior Work:**  
  - *Language Models over Canonical Byte-Pair Encodings* (canonicalization via automata)
  - *Sampling from Your Language Model One Byte at a Time* (byte-level adaptation)
  - *Where is the signal in tokenization space?* (marginalization over tokenizations)
- **Claimed Difference:**  
  - First to formalize arbitrary deterministic string-to-string transformations as fully functional LMs.
- **Independently Verified Difference:**  
  - Prior works address specific transformations (tokenization, canonicalization, byte conversion), but do not provide a general, modular framework for arbitrary deterministic mappings.
  - The submission’s use of FSTs as a unifying abstraction is a substantive generalization.
- **Superficial vs. Substantive:**  
  - The difference is substantive in scope/generalization, but the underlying technical machinery (FST composition, marginalization) is well-established in automata theory.
- **Author Characterization vs. Reality:**  
  - The claim of “first formalization” is slightly overstated; prior work formalizes special cases, but not the general case.

### Contribution 2: **Algorithms for Exact and Approximate Marginalization over Source Strings via FSTs**

- **Most Similar Prior Work:**  
  - *Where is the signal in tokenization space?* (approximate marginalization)
  - *Pimentel & Meister (2024)* (bespoke marginalization for word probabilities)
- **Claimed Difference:**  
  - Provides both exact and efficient approximate algorithms for marginalization over arbitrary deterministic mappings.
- **Independently Verified Difference:**  
  - Prior work provides approximate algorithms for specific cases (e.g., tokenization), and exact algorithms for very restricted settings.
  - The submission’s algorithms are more general, but the technical novelty is incremental—extending known FST algorithms to a broader class of transformations.
- **Superficial vs. Substantive:**  
  - The extension is substantive in generality, but the core algorithmic ideas are adaptations of standard FST techniques.
- **Author Characterization vs. Reality:**  
  - The claim of “novel algorithms” is accurate in the sense of generalization, but the underlying techniques are not fundamentally new.

### Contribution 3: **Inference-Time Adaptation of Pretrained LMs to Application-Specific Output Requirements without Retraining**

- **Most Similar Prior Work:**  
  - *Sampling from Your Language Model One Byte at a Time*
  - *Language Models over Canonical Byte-Pair Encodings*
  - *Automata-based constraints for language model decoding*
- **Claimed Difference:**  
  - Enables modular, inference-time adaptation to arbitrary output formats.
- **Independently Verified Difference:**  
  - Prior work enables inference-time adaptation for specific output formats (bytes, canonical forms, constraints), but not arbitrary deterministic mappings.
  - The submission’s framework is more general, but the practical impact depends on the complexity of the FST and the efficiency of the algorithms.
- **Superficial vs. Substantive:**  
  - The difference is substantive in generality, but may be superficial in practical settings where only a few types of transformations are needed.
- **Author Characterization vs. Reality:**  
  - The claim is accurate in generality, but the practical novelty may be less pronounced for common use cases.

---

## 4. FIELD CONTEXT CONSIDERATIONS

- **Field Maturity:**  
  - The area is active and rapidly evolving, with a recent surge in interest in inference-time adaptation, automata-based methods, and tokenization correction.
- **Recent Surveys/Literature Reviews:**  
  - No comprehensive survey cited, but several recent papers (e.g., “Effect of tokenization on transformers for biological sequences”) provide overviews of tokenization issues.
- **Trends:**  
  - Shift from retraining to inference-time adaptation.
  - Increasing use of automata/FSTs for modular adaptation and constraint enforcement.
  - Growing recognition of tokenization as a central modeling challenge.
- **Incremental Advances:**  
  - Many recent advances are incremental—extending existing automata or marginalization techniques to new settings or broader classes of transformations.

---

## 5. CRITICAL ASSESSMENT CONSIDERATIONS

- **Potential Overstatement of Novelty:**  
  - The “first formalization” claim is somewhat overstated; prior work formalizes special cases.
  - The algorithms are generalizations of standard FST techniques, not fundamentally new algorithms.
- **Empirical Improvements:**  
  - Any empirical gains may be due to careful engineering or implementation, rather than conceptual breakthroughs.
- **Terminology Differences:**  
  - Differences in terminology (e.g., “canonicalization” vs. “deterministic mapping”) may exaggerate the conceptual gap.
- **Routine Extensions:**  
  - Some “extensions” (e.g., from tokenization to arbitrary deterministic mappings) may be routine adaptations of automata theory.
- **Novelty Alignment:**  
  - The authors’ characterization of their own novelty is mostly accurate in terms of generality, but less so in terms of technical depth.

---

## 6. RELATED WORK CONSIDERATIONS

- **Potentially Relevant Uncited Work:**  
  - *Differentiable Weighted Finite-State Transducers*: Explores differentiable FSTs for neural modeling.
  - *Speech Recognition using Weighted Finite-State Transducers*: Classic application of FSTs for sequence modeling.
  - *Improving Low-Resource Morphological Learning with Intermediate Forms from Finite State Transducers*: Applies FSTs for adaptation in low-resource settings.
  - *SQL-PaLM*: Adapts LMs for structured output tasks (Text-to-SQL), combining multiple adaptation strategies.
- **Additional Comparisons Needed:**  
  - Comparison with differentiable FSTs and neural FST hybrids could clarify the boundaries of the proposed framework.
  - More discussion of task-specific adaptation (e.g., SQL, biological sequences) would strengthen the empirical relevance.
- **Incomplete Characterizations:**  
  - The limitations of prior work (e.g., “bespoke” or “ad hoc” methods) may be exaggerated; some prior methods are more general than described.
- **Citation vs. Actual Relationship:**  
  - Some cited works (e.g., “Where is the signal in tokenization space?”) are closer in spirit to the submission than the authors suggest.

---

## 7. KEY OBSERVATION SUMMARY

- **Most Significant Independently Verified Differences:**
  - The submission generalizes prior automata-based and inference-time adaptation methods to arbitrary deterministic string-to-string transformations, formalized via FSTs.
  - Provides both exact and approximate algorithms for marginalization and probability propagation through FSTs, enabling modular adaptation of LMs at inference.
- **Main Relationships to Existing Research:**
  - Subsumes prior work on canonicalization, byte-level adaptation, and constraint enforcement as special cases.
  - Extends the scope of inference-time adaptation from specific transformations to arbitrary deterministic mappings.
- **Strongest Differentiation:**
  - Generality and modularity of the framework; ability to handle arbitrary deterministic mappings.
- **Weakest Differentiation:**
  - Underlying algorithms are adaptations of standard FST techniques; prior work already formalizes and implements special cases.
- **Discrepancies Between Author Characterizations and Independent Assessment:**
  - The “first formalization” claim is somewhat overstated; prior work formalizes special cases, and the technical novelty is primarily in generalization rather than new algorithms.
  - Some prior work is more general or sophisticated than acknowledged (e.g., “Where is the signal in tokenization space?”).
- **Reviewer Guidance:**
  - The main novelty is in the general, modular framework for inference-time adaptation via FSTs, not in fundamentally new algorithms.
  - The submission unifies and extends several strands of prior work, but the technical advances are incremental in nature.

---

**End of Analysis**
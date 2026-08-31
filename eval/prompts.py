#!/usr/bin/env python3
"""LLM-as-Judge prompts for the novelty-assessment evaluation.

These are Afzal et al. (2026) "Beyond 'Not Novel Enough'" Figures 13 & 14 verbatim
(supplied by the supervisor), wrapped for structured output so the four evaluation
dimensions can be aggregated. GPT-4.1 is the judge; the style-normalised human novelty
assessments are the ground truth. Two stages:

  Stage 1 (Fig 13): extract 2-3 stable core novelty judgments from the REFERENCE
                    (human) assessment -- done once, separately, so the judge fixes the
                    claims before comparing any system.
  Stage 2 (Fig 14): compare a system's assessment against the reference + those core
                    judgments -> judgment similarity, conclusion alignment, prior-work
                    engagement, depth of analysis.
"""
from typing import List
from pydantic import BaseModel, Field


# ----------------------------- Figure 13 ----------------------------- #

FIG13_CORE_JUDGMENT_EXTRACTION = """Extract 2-3 core novelty judgments from this assessment:
{reference_assessment}
Focus on statements that directly assess:
- How novel/original the contribution is
- How work relates to prior research
- Specific novelty limitations
- Whether advance is incremental/fundamental
Exclude general recommendations or writing suggestions.
For each judgment, explain why it's considered a core novelty assessment.
Provide rationale for your selection of these specific judgments."""


class CoreJudgment(BaseModel):
    judgment: str = Field(description="A core novelty judgment extracted from the reference assessment")
    why_core: str = Field(description="Why this is a core novelty assessment")


class Fig13Output(BaseModel):
    core_judgments: List[CoreJudgment] = Field(description="2-3 core novelty judgments")
    rationale: str = Field(description="Rationale for selecting these judgments")


# ----------------------------- Figure 14 ----------------------------- #

FIG14_NOVELTY_EVALUATION = """Compare reviewer assessment against reference using these core judgments:
Core Judgments: {extracted_core_judgments}
Reference: {reference_assessment}
Reviewer: {reviewer_assessment}
Evaluate three dimensions:
1. JUDGMENT SIMILARITY: Do they identify same novelty strengths/weaknesses?
- For each core judgment, find corresponding judgment in reviewer assessment
- Assess similarity and provide detailed explanation of alignment/differences
- Include confidence score for each comparison
- If the core judgement is referring to a very specific aspect of the methodology
  and the reviewer assessment does not mention it, then the core judgment is
  not similar to the reviewer assessment.
2. CONCLUSION ALIGNMENT: Same bottom-line about novelty sufficiency?
- Determine overall conclusions (SUFFICIENT / INSUFFICIENT / MIXED)
- Explain whether conclusions align and why
3. PRIOR_WORK_ENGAGEMENT:
- How does the reviewer engage with prior work?
- Does the reviewer mention prior work?
- Does the reviewer compare the current work to prior work?
- Does the reviewer provide evidence for their claims?
- Does the reviewer use prior work to support or critique the work?
- Evaluate number and relevance of citations to prior work
  (NONE: no citations; LIMITED: 1 to 2; EXTENSIVE: 3+ relevant citations).
4. DEPTH_OF_ANALYSIS:
- Assesses how deeply specific novelty aspects are compared to prior work
  (SURFACE LEVEL: vague; MODERATE: 1 to 2 aspects; DEEP: 3+ or highly detailed comparisons)
Provide explanations for all assessments to support reasoning."""


class JudgmentSimilarity(BaseModel):
    core_judgment: str = Field(description="The core judgment being matched")
    found_in_reviewer: bool = Field(description="Whether a corresponding judgment exists in the reviewer assessment")
    similarity: str = Field(description="One of: ALIGNED, PARTIAL, NOT_SIMILAR")
    confidence: float = Field(description="Confidence 0.0-1.0 for this comparison")
    explanation: str


class Fig14Output(BaseModel):
    judgment_similarities: List[JudgmentSimilarity]
    reference_conclusion: str = Field(description="Reference bottom line: SUFFICIENT / INSUFFICIENT / MIXED")
    reviewer_conclusion: str = Field(description="Reviewer bottom line: SUFFICIENT / INSUFFICIENT / MIXED")
    conclusion_aligned: bool = Field(description="Whether the two bottom-line novelty verdicts align")
    conclusion_explanation: str
    prior_work_engagement: str = Field(description="One of: NONE, LIMITED, EXTENSIVE")
    prior_work_explanation: str
    depth_of_analysis: str = Field(description="One of: SURFACE, MODERATE, DEEP")
    depth_explanation: str

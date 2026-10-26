import os
import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


novelty_delta_analysis_prompt = """
# Novelty Delta Analysis for Reviewer Support

## Task
Independently analyze how the submission paper's contributions relate to existing work in the field, critically examining both author claims and actual relationships. This analysis should help reviewers assess novelty by providing objective comparisons with prior work.

## Input Format
You will be provided with:
1. The structured information from the submission paper
2. A comprehensive research landscape analysis
3. Citation sentences for key related papers (how authors cite and characterize these works)

## Key Analysis Principles
- Independently verify relationships between submission and prior work
- Critically examine how authors characterize and compare with prior work
- Identify discrepancies between author characterizations and actual relationships
- Present evidence-based observations without making final judgments
- Distinguish between author-claimed differences and independently observed differences
- Provide context about field maturity and related work

## Output Format
Provide a detailed analysis with the following sections:

1. RESEARCH CONTEXT POSITIONING
   - Situate the submission within the identified research landscape
   - Identify the most closely related prior works
   - Independently assess how the submission relates to existing methodological clusters
   - Analyze its place within the problem space and evaluation approaches
   - Note: Do not accept author positioning claims without verification

2. AUTHOR CITATION ANALYSIS
   - Analyze how authors characterize and compare with each cited related work
   - Identify patterns in how authors position their contributions relative to others
   - Assess whether characterizations of prior work are accurate and balanced
   - Note discrepancies between how authors describe prior work and independent assessment
   - Evaluate whether claimed improvements or differences are substantiated
   - Identify rhetoric that may overstate differences or understate similarities

3. CONTRIBUTION DELTA ANALYSIS
   For each main contribution claimed in the submission:
   - Identify the most similar prior work for this specific contribution
   - Critically examine whether claimed differences actually exist
   - Detail exactly how this contribution differs from prior work, based on evidence
   - Compare author characterizations with independently verified relationships
   - Distinguish between substantive differences and superficial variations
   - Note when author claims about novelty or extension may be overstated
   - Consider whether improvements might be due to implementation details rather than conceptual advances
   - Note: Present factual observations about deltas without accepting author framing

4. FIELD CONTEXT CONSIDERATIONS
   - Provide information about how active/mature this research area is
   - Identify recent survey papers or literature reviews in this space
   - Note trends in how the field has been evolving
   - Present context about typical incremental advances in this field
   - Note: Offer context that helps reviewers calibrate their expectations

5. CRITICAL ASSESSMENT CONSIDERATIONS
   - Identify aspects where claimed novelty may be overstated
   - Analyze whether authors' characterizations of their own novelty align with evidence
   - Consider whether empirical improvements might result from factors other than claimed innovations
   - Assess whether terminology differences might mask conceptual similarities
   - Identify instances where "extensions" might be routine adaptations
   - Note: Frame these as considerations rather than definitive judgments

6. RELATED WORK CONSIDERATIONS
   - Identify potentially relevant work not addressed in the submission
   - Highlight areas where additional comparisons are necessary
   - Note incomplete or potentially misleading characterizations of prior work
   - Identify when claimed "limitations" of prior work may be exaggerated
   - Compare how authors cite specific works versus how they actually relate
   - Note: Present these as information that might help complete the picture

7. KEY OBSERVATION SUMMARY
   - Highlight the most significant independently verified differences from prior work
   - Summarize the main relationships to existing research
   - Identify which claimed contributions have the strongest and weakest differentiation
   - Note the most important discrepancies between author characterizations and independent assessment
   - Note: Frame as observations to inform the reviewer's independent judgment

## Evidence Standards
For each observation, provide:
- Specific references to prior work
- Clear distinction between author claims and independently verified differences
- Explicit identification of similarities and differences based on technical details
- Assessment of whether differences appear substantive or superficial
- Analysis of accuracy in how authors characterize related work

## Example Format for Citation Analysis
"For [Paper X], the authors characterize it as 'limited to simple datasets' and claim their work 'extends X to complex scenarios.' The citation sentences appear in the following contexts:
- 'Unlike X, which only works on simple datasets, our approach handles complex scenarios' (Introduction)
- 'X proposed the basic framework, but did not address challenge Y' (Related Work)

Independent analysis suggests that Paper X actually did address complex scenarios in Section 3.2, though using different terminology. The authors' characterization appears to understate X's capabilities to emphasize their contribution. The actual primary difference appears to be [specific technical difference] rather than the complexity of supported scenarios."

Remember that your role is to provide objective analysis that helps reviewers make informed judgments about novelty. Carefully examine both what authors explicitly claim and how they implicitly position their work through their characterizations of prior research.

{structured_representation}

## Papers from related work not cited
{not_cited_paper_titles}


##Citation Context
{citation_contexts}

## Research Landscape
{research_landscape}
"""


class PaperInformation(BaseModel):
    """Structured information extracted from a research paper."""

    paper_id: str
    title: str
    methods: List[str] = Field(description="List of methods/approaches proposed in the paper")
    problems: List[str] = Field(description="List of problems the paper addresses")
    datasets: List[str] = Field(description="List of datasets used for evaluation")
    metrics: List[str] = Field(description="List of evaluation metrics used")
    results: List[Dict[str, str]] = Field(
        description="Key quantitative results with metric name -> value pairs"
    )
    novelty_claims: List[str] = Field(description="Claims about what is novel in this work")
    is_submission: bool = False


class NoveltyAssessor:
    """Assesses the novelty of a submission paper in the context of related work."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        """Initialize the novelty assessor with the specified LLM."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            api_key=api_key,
        )

    @staticmethod
    def get_citation_matches(citation_contexts) -> str:
        """Format citation contexts for analysis."""
        output_lines = []
        for title, context in citation_contexts.items():
            output_lines.append(f"📄 {title}\n")
            for ctx in context:
                output_lines.append(f"↳ Context: {ctx}\n")
        return "\n".join(output_lines)

    def load_submission_paper(
        self, data_dir: str, submission_id: str
    ) -> Optional[PaperInformation]:
        """Load the submission paper information from JSON file."""
        file_path = os.path.join(data_dir, submission_id, "structured_representation.json")

        if not os.path.exists(file_path):
            raise ValueError(f"Submission paper file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with open(f"{data_dir}/{submission_id}/{submission_id}.json", "r") as f:
            paper_obj = json.load(f)

        structured_representation = data["structured_representation"]
        structured_representation["main_paper"]["parsed"]["paper_id"] = submission_id
        structured_representation["main_paper"]["parsed"]["is_submission"] = True
        structured_representation["main_paper"]["parsed"]["title"] = paper_obj["title"]
        paper_info = PaperInformation(**structured_representation["main_paper"]["parsed"])

        return paper_info

    def load_citation_contexts(self, data_dir: str, submission_id: str) -> str:
        with open(f"{data_dir}/{submission_id}/{submission_id}.json", "r") as f:
            paper_obj = json.load(f)

        with open(f"{data_dir}/{submission_id}/related_work_data/ranked_papers.json", "r") as f:
            ranked_papers = json.load(f)

        title_and_sentences = {}

        for i in ranked_papers:
            ss_paper_id = i["paper_id"]
            citation_contexts = []
            for j in paper_obj["cited_papers"]:
                if "ss_paper_obj" not in j or j["ss_paper_obj"] is None:
                    continue
                if j["ss_paper_obj"]["paper_id"].strip() == ss_paper_id.strip():
                    if j["id"] not in [m[0] for m in citation_contexts]:
                        citation_contexts.append([j["id"], j["ss_paper_obj"]["title"]])

            for c in citation_contexts:
                title_and_sentences[c[1]] = [
                    k["context_sentence"]
                    for k in paper_obj["citation_contexts"]
                    if k["cited_paper_id"].strip() == c[0].strip()
                ]
                if len(title_and_sentences[c[1]]) == 0:
                    del title_and_sentences[c[1]]

        citation_contexts = self.get_citation_matches(title_and_sentences)

        return citation_contexts

    def load_landscape_analysis(self, landscape_file: str) -> str:
        """Load the research landscape analysis from file."""
        if not os.path.exists(landscape_file):
            raise ValueError(f"Landscape analysis file not found: {landscape_file}")

        with open(landscape_file, "r", encoding="utf-8") as f:
            analysis = f.read()

        return analysis

    def format_submission_for_prompt(self, submission: PaperInformation) -> str:
        """Format the submission paper information for the prompt."""
        formatted_text = f"# SUBMISSION PAPER: {submission.title}\n\n"

        formatted_text += (
            "## METHODS:\n" + "\n".join([f"- {m}" for m in submission.methods]) + "\n\n"
        )
        formatted_text += (
            "## PROBLEMS:\n" + "\n".join([f"- {p}" for p in submission.problems]) + "\n\n"
        )
        formatted_text += (
            "## DATASETS:\n" + "\n".join([f"- {d}" for d in submission.datasets]) + "\n\n"
        )
        formatted_text += (
            "## METRICS:\n" + "\n".join([f"- {m}" for m in submission.metrics]) + "\n\n"
        )
        formatted_text += (
            "## RESULTS:\n" + "\n".join([f"- {json.dumps(r)}" for r in submission.results]) + "\n\n"
        )
        formatted_text += (
            "## NOVELTY CLAIMS:\n"
            + "\n".join([f"- {c}" for c in submission.novelty_claims])
            + "\n\n"
        )

        return formatted_text

    def assess_novelty(
        self,
        submission: PaperInformation,
        landscape_analysis: str,
        not_cited_paper_titles: str,
        citation_contexts,
    ) -> str:
        """Assess the novelty of the submission paper in the context of the research landscape."""
        formatted_submission = self.format_submission_for_prompt(submission)

        prompt = novelty_delta_analysis_prompt.format(
            structured_representation=formatted_submission,
            research_landscape=landscape_analysis,
            not_cited_paper_titles=not_cited_paper_titles,
            citation_contexts=citation_contexts,
        )

        assessment = self.llm.invoke(prompt)

        return assessment

    def format_not_cited_papers(self, non_cited_papers: list):
        formatted_text = "\n-".join([i for i in non_cited_papers])
        return formatted_text

    def run_assessment(
        self,
        data_dir: str,
        submission_id: str,
    ) -> str:
        """Run the complete novelty assessment pipeline."""
        submission = self.load_submission_paper(data_dir, submission_id)

        landscape_path = os.path.join(data_dir, submission_id, "research_landscape.txt")
        landscape_analysis = self.load_landscape_analysis(landscape_path)

        with open(f"{data_dir}/{submission_id}/related_work_data/ranked_papers.json", "r") as f:
            ranked_papers = json.load(f)
        not_cited_papers = [i["title"] for i in ranked_papers if not i["cited_paper"]]
        formatted_not_cited_papers = self.format_not_cited_papers(not_cited_papers)

        citation_contexts = self.load_citation_contexts(data_dir, submission_id)

        assessment = self.assess_novelty(
            submission,
            landscape_analysis,
            formatted_not_cited_papers,
            citation_contexts,
        )

        output_path = os.path.join(data_dir, submission_id, "novelty_delta_analysis.txt")
        if assessment:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(assessment.content)

        print("Novelty assessment saved to novelty_delta_analysis.txt")

        from litellm import cost_per_token

        tok_used = assessment.response_metadata["token_usage"]
        total_cost = sum(
            cost_per_token(
                model="gpt-4.1",
                prompt_tokens=tok_used["prompt_tokens"],
                completion_tokens=tok_used["completion_tokens"],
            )
        )

        meta_path = os.path.join(data_dir, submission_id, "metadata.json")
        current_meta = json.load(open(meta_path, "r"))

        current_meta["novelty_assessment"] = {
            "total_cost": total_cost,
            "token_usage": tok_used,
        }

        with open(meta_path, "w") as f:
            json.dump(current_meta, f, indent=3)

        return assessment

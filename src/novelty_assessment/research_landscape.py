import os
import json
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


research_landscape_prompt = """
# Research Landscape Analysis

## Task
Analyze the collection of research papers provided below to create a comprehensive map of the research landscape they represent. The submission paper is the focus of our analysis, and the related papers provide context.

## Input Format
You will be provided with structured information extracted from multiple research papers including:
- A submission paper that is the focus of our analysis
- Multiple related papers that form the research context

Each paper contains:
- methods: List of methods/approaches proposed
- problems: List of problems addressed
- datasets: List of datasets used
- metrics: List of evaluation metrics
- results: Key quantitative results
- novelty_claims: Claims about what is novel in the work

## Output Format
Provide a comprehensive analysis with the following sections:

1. METHODOLOGICAL LANDSCAPE
   - Identify and describe the main methodological approaches across the papers
   - Group similar or related methods into clusters
   - Highlight methodological trends or patterns
   - Describe relationships between different methodological approaches

2. PROBLEM SPACE MAPPING
   - Identify the key problems being addressed across the papers
   - Analyze how different papers approach similar problems
   - Highlight patterns in problem formulation

3. EVALUATION LANDSCAPE
   - Analyze the common datasets and evaluation methods
   - Identify patterns in how performance is measured
   - Compare evaluation approaches across papers

4. RESEARCH CLUSTERS
   - Identify groups of papers that appear closely related
   - Describe the key characteristics of each cluster
   - Analyze relationships between clusters

5. TECHNICAL EVOLUTION
   - Identify any visible progression or evolution of ideas
   - Highlight building blocks and their extensions
   - Note any competing or complementary approaches

## Example Output Format
METHODOLOGICAL LANDSCAPE
- Cluster 1: [Description of similar methods across papers]
  - Papers X, Y, Z employ transformer-based approaches with variations in...
  - These methods share characteristics such as...
  - They differ primarily in...

PROBLEM SPACE MAPPING
- Problem Area 1: [Description of a common problem addressed]
  - Papers A, B, C all address this problem but differ in...
  - The problem is formulated differently in Paper D which focuses on...

... [additional sections] ...

Ensure your analysis is comprehensive, identifying significant patterns and relationships across the collection of papers.

## Papers:
{papers}

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


class ResearchLandscapeAnalyzer:
    """Analyzes a collection of papers to create a comprehensive research landscape."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        """Initialize the analyzer with the specified LLM."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)

        self.research_landscape_prompt = research_landscape_prompt

    def load_papers(self, data_dir: str, submission_id: str) -> List[PaperInformation]:
        """Load paper information from JSON files in the specified directory."""
        papers = []

        with open(
            os.path.join(data_dir, submission_id, f"{submission_id}.json"),
            "r",
            encoding="utf-8",
        ) as f:
            submission_paper_obj = json.load(f)

        with open(
            os.path.join(data_dir, submission_id, "related_work_data", "ranked_papers.json"),
            "r",
            encoding="utf-8",
        ) as f:
            ranked_papers = json.load(f)

        structured_representation_path = os.path.join(
            data_dir, submission_id, "structured_representation.json"
        )
        if not os.path.exists(structured_representation_path):
            return []

        with open(structured_representation_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            structured_representation = data["structured_representation"]
            structured_representation["main_paper"]["parsed"]["paper_id"] = submission_id
            structured_representation["main_paper"]["parsed"]["is_submission"] = True
            structured_representation["main_paper"]["parsed"]["title"] = submission_paper_obj[
                "title"
            ]
            paper_info = PaperInformation(**structured_representation["main_paper"]["parsed"])
            papers.append(paper_info)

            selected_papers = {i["paper_id"]: i for i in ranked_papers}

            for item in structured_representation["selected_papers"]:
                item["parsed"]["paper_id"] = item["paper_id"]
                item["parsed"]["title"] = selected_papers[item["paper_id"]]["title"]
                item["parsed"]["is_submission"] = False
                paper_info = PaperInformation(**item["parsed"])
                papers.append(paper_info)

        return papers

    def format_papers_for_prompt(self, papers: List[PaperInformation]) -> str:
        """Format the paper information for the prompt."""
        submission_papers = [p for p in papers if p.is_submission]
        related_papers = [p for p in papers if not p.is_submission]

        if not submission_papers:
            raise ValueError("No submission paper found")

        submission = submission_papers[0]

        formatted_text = "## SUBMISSION PAPER\n\n"
        formatted_text += f"TITLE: {submission.title}\n\n"
        formatted_text += "METHODS:\n" + "\n".join([f"- {m}" for m in submission.methods]) + "\n\n"
        formatted_text += (
            "PROBLEMS:\n" + "\n".join([f"- {p}" for p in submission.problems]) + "\n\n"
        )
        formatted_text += (
            "DATASETS:\n" + "\n".join([f"- {d}" for d in submission.datasets]) + "\n\n"
        )
        formatted_text += "METRICS:\n" + "\n".join([f"- {m}" for m in submission.metrics]) + "\n\n"
        formatted_text += (
            "RESULTS:\n" + "\n".join([f"- {json.dumps(r)}" for r in submission.results]) + "\n\n"
        )
        formatted_text += (
            "NOVELTY CLAIMS:\n" + "\n".join([f"- {c}" for c in submission.novelty_claims]) + "\n\n"
        )

        formatted_text += "## RELATED PAPERS\n\n"

        for i, paper in enumerate(related_papers, 1):
            formatted_text += f"### RELATED PAPER {i}: {paper.title}\n\n"
            formatted_text += "METHODS:\n" + "\n".join([f"- {m}" for m in paper.methods]) + "\n\n"
            formatted_text += "PROBLEMS:\n" + "\n".join([f"- {p}" for p in paper.problems]) + "\n\n"
            formatted_text += "DATASETS:\n" + "\n".join([f"- {d}" for d in paper.datasets]) + "\n\n"
            formatted_text += "METRICS:\n" + "\n".join([f"- {m}" for m in paper.metrics]) + "\n\n"
            formatted_text += (
                "RESULTS:\n" + "\n".join([f"- {json.dumps(r)}" for r in paper.results]) + "\n\n"
            )
            formatted_text += (
                "NOVELTY CLAIMS:\n" + "\n".join([f"- {c}" for c in paper.novelty_claims]) + "\n\n"
            )

        return formatted_text

    def analyze_landscape(self, papers: List[PaperInformation]) -> str:
        """Analyze the research landscape based on the provided papers."""
        formatted_papers = self.format_papers_for_prompt(papers)

        prompt = self.research_landscape_prompt.format(papers=formatted_papers)

        analysis = self.llm.invoke(prompt)

        return analysis

    def run_analysis(self, data_dir: str, submission_id: str, output_file: str) -> str:
        """Run the complete analysis pipeline."""
        papers = self.load_papers(data_dir, submission_id)

        if len(papers) < 2:
            raise ValueError(f"Not enough papers found. Need at least 2, got {len(papers)}")

        analysis = self.analyze_landscape(papers)

        output_path = os.path.join(data_dir, submission_id, output_file)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(analysis.content)

        print(f"Analysis saved to {output_file}")

        from litellm import cost_per_token

        tok_used = analysis.response_metadata["token_usage"]
        total_cost = sum(
            cost_per_token(
                model="gpt-4.1",
                prompt_tokens=tok_used["prompt_tokens"],
                completion_tokens=tok_used["completion_tokens"],
            )
        )

        meta_path = os.path.join(data_dir, submission_id, "metadata.json")

        current_meta = {}
        if os.path.exists(meta_path):
            current_meta = json.load(open(meta_path, "r"))

        current_meta["research_landscape"] = {
            "total_cost": total_cost,
            "token_usage": tok_used,
        }

        with open(meta_path, "w") as f:
            json.dump(current_meta, f, indent=3)

        return analysis

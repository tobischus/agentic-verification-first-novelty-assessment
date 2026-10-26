import os
import json
import textwrap
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class ResultEntry(BaseModel):
    """Individual result entries for structured paper information."""

    metric: str = Field(description="Name of the evaluation metric")
    value: str = Field(description="Value of the metric")


class StructuredPaperInformation(BaseModel):
    """Structured information extracted from a research paper."""

    methods: List[str] = Field(description="List of methods/approaches proposed in the paper")
    problems: List[str] = Field(description="List of problems the paper addresses")
    datasets: List[str] = Field(description="List of datasets used for evaluation")
    metrics: List[str] = Field(description="List of evaluation metrics used")
    results: List[ResultEntry] = Field(
        description="Key quantitative results with metric name and value"
    )
    novelty_claims: List[str] = Field(description="Claims about what is novel in this work")


class StructuredRepresentationGenerator:
    """Generates structured representations of research papers."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        """Initialize the generator with the specified LLM."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)

        self.template = textwrap.dedent(
            """
        You are tasked with extracting key information from a research paper for building a knowledge graph.

        Paper title: {title}

        Based on the paper content provided below, extract the following information:
        - "methods": [List of methods/approaches proposed in the paper],
        - "problems": [List of problems the paper addresses],
        - "datasets": [List of datasets used for evaluation],
        - "metrics": [List of evaluation metrics used],
        - "results": [List of objects with 'metric' and 'value' fields representing key quantitative results],
        - "novelty_claims": [Claims about what is novel in this work]

        Be precise and specific.

        Paper content:
        {abstract}
        {introduction} 
        """
        )

    def extract_paper_information(self, paper_title: str, abstract: str, introduction: str = ""):
        """Extract structured information from a research paper."""
        prompt = self.template.format(
            title=paper_title, abstract=abstract, introduction=introduction
        )

        result = self.llm.with_structured_output(StructuredPaperInformation).invoke(prompt)

        return {"raw": str(result), "parsed": dict(result)}

    def process_single_submission(self, data_dir: str, submission_id: str):
        """Process a single submission using LangChain batch for related papers."""
        submission_path = os.path.join(data_dir, submission_id)

        with open(f"{submission_path}/{submission_id}.json", "r") as f:
            main_paper = json.load(f)

        intro = ""
        if os.path.exists(f"{submission_path}/introductions/{submission_id}_intro.txt"):
            with open(f"{submission_path}/introductions/{submission_id}_intro.txt", "r") as f:
                intro = f.read()

        main_result = self.extract_paper_information(
            main_paper["title"], main_paper["abstract"], intro
        )

        with open(f"{submission_path}/related_work_data/ranked_papers.json", "r") as f:
            related_papers = json.load(f)

        prompts = []
        for paper in related_papers[:10]:
            paper_intro = ""
            intro_path = f"{submission_path}/introductions/{paper['paper_id']}_intro.txt"
            if os.path.exists(intro_path):
                with open(intro_path, "r") as f:
                    paper_intro = f.read()

            prompt = self.template.format(
                title=paper["title"],
                abstract=paper["abstract"],
                introduction=paper_intro,
            )
            prompts.append(prompt)

        chain = self.llm.with_structured_output(StructuredPaperInformation)
        related_raw_results = chain.batch(prompts)

        related_results = []
        for i, result in enumerate(related_raw_results):
            related_results.append(
                {
                    "paper_id": related_papers[i]["paper_id"],
                    "raw": str(result),
                    "parsed": dict(result),
                }
            )

        def serialize_result_entries(results):
            """Convert ResultEntry objects to dicts"""
            if not results:
                return []
            return [
                {"metric": r.metric, "value": r.value} if hasattr(r, "metric") else r
                for r in results
            ]

        main_parsed = dict(main_result["parsed"])
        if "results" in main_parsed:
            main_parsed["results"] = serialize_result_entries(main_parsed["results"])

        output = {
            "main_paper": {
                "raw": str(main_result["raw"]),
                "parsed": main_parsed,
            },
            "selected_papers": [],
        }

        for r in related_results:
            related_parsed = dict(r["parsed"])
            if "results" in related_parsed:
                related_parsed["results"] = serialize_result_entries(related_parsed["results"])

            output["selected_papers"].append(
                {
                    "paper_id": r["paper_id"],
                    "raw": str(r["raw"]),
                    "parsed": related_parsed,
                }
            )

        output_path = f"{submission_path}/structured_representation.json"
        with open(output_path, "w") as f:
            json.dump({"structured_representation": output}, f, indent=4)

        return output

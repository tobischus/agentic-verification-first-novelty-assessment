import os
import json
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

reviewer_summary_prompt = """
Summarize the following assessment in 5 sentences for a reviewer reviewing at an AI conference.

## Delta Assessment
{novelty_assessment}
"""


class ReviewGuidanceGenerator:
    """Generates targeted guidance for reviewers based on novelty assessment and research landscape analysis."""

    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        """Initialize the review guidance generator with the specified LLM."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            api_key=api_key,
        )

    def load_novelty_assessment(self, assessment_file: str) -> str:
        """Load the novelty assessment from file."""
        if not os.path.exists(assessment_file):
            raise ValueError(f"Novelty assessment file not found: {assessment_file}")

        with open(assessment_file, "r", encoding="utf-8") as f:
            assessment = f.read()

        return assessment

    def generate_guidance(self, novelty_assessment: str) -> str:
        """Generate reviewer guidance based on novelty assessment and landscape analysis."""
        prompt = reviewer_summary_prompt.format(novelty_assessment=novelty_assessment)

        guidance = self.llm.invoke(prompt)

        return guidance

    def run_guidance_generation(self, data_dir: str, submission_id: str) -> str:
        """Run the complete review guidance generation pipeline."""
        assessment_file = os.path.join(data_dir, submission_id, "novelty_delta_analysis.txt")
        novelty_assessment = self.load_novelty_assessment(assessment_file)

        guidance = self.generate_guidance(novelty_assessment)

        output_file = os.path.join(data_dir, submission_id, "summary.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(guidance.content)

        print("Review guidance saved to summary.txt")

        from litellm import cost_per_token

        tok_used = guidance.response_metadata["token_usage"]
        total_cost = sum(
            cost_per_token(
                model="gpt-4.1",
                prompt_tokens=tok_used["prompt_tokens"],
                completion_tokens=tok_used["completion_tokens"],
            )
        )

        data_dir = os.path.dirname(os.path.dirname(output_file))
        meta_path = os.path.join(data_dir, "metadata.json")

        current_meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                current_meta = json.load(f)

        current_meta["summary"] = {"total_cost": total_cost, "token_usage": tok_used}

        with open(meta_path, "w") as f:
            json.dump(current_meta, f, indent=3)

        return guidance

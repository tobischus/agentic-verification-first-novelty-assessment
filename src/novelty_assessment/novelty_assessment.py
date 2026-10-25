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
    methods: List[str] = Field(
        description="List of methods/approaches proposed in the paper"
    )
    problems: List[str] = Field(description="List of problems the paper addresses")
    datasets: List[str] = Field(description="List of datasets used for evaluation")
    metrics: List[str] = Field(description="List of evaluation metrics used")
    results: List[Dict[str, str]] = Field(
        description="Key quantitative results with metric name -> value pairs"
    )
    novelty_claims: List[str] = Field(
        description="Claims about what is novel in this work"
    )
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
        file_path = os.path.join(
            data_dir, submission_id, f"structured_representation.json"
        )

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
        paper_info = PaperInformation(
            **structured_representation["main_paper"]["parsed"]
        )

        return paper_info

    def load_citation_contexts(self, data_dir: str, submission_id: str) -> str:
        with open(f"{data_dir}/{submission_id}/{submission_id}.json", "r") as f:
            paper_obj = json.load(f)

        with open(
            f"{data_dir}/{submission_id}/related_work_data/ranked_papers.json", "r"
        ) as f:
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
            f"## METHODS:\n"
            + "\n".join([f"- {m}" for m in submission.methods])
            + "\n\n"
        )
        formatted_text += (
            f"## PROBLEMS:\n"
            + "\n".join([f"- {p}" for p in submission.problems])
            + "\n\n"
        )
        formatted_text += (
            f"## DATASETS:\n"
            + "\n".join([f"- {d}" for d in submission.datasets])
            + "\n\n"
        )
        formatted_text += (
            f"## METRICS:\n"
            + "\n".join([f"- {m}" for m in submission.metrics])
            + "\n\n"
        )
        formatted_text += (
            f"## RESULTS:\n"
            + "\n".join([f"- {json.dumps(r)}" for r in submission.results])
            + "\n\n"
        )
        formatted_text += (
            f"## NOVELTY CLAIMS:\n"
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

        print(f"Novelty assessment saved to novelty_delta_analysis.txt")

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

    def prepare_batch_inference_data(
        self,
        data_dir: str,
        landscape_file: str = "research_landscape.txt",
        model_name: str = "gpt-4.1",
    ) -> str:
        """Prepare data for batched inference with OpenAI API for novelty assessment."""
        batch_entries = []

        submission_ids = os.listdir(data_dir)

        total_submissions = len(submission_ids)
        valid_submissions = 0
        missing_landscape = 0
        missing_structured_rep = 0

        for submission_id in submission_ids:
            landscape_path = os.path.join(
                data_dir, submission_id, "ours", landscape_file
            )
            structured_rep_path = os.path.join(
                data_dir, submission_id, "ours", "structured_representation.json"
            )

            if not os.path.exists(
                f"{data_dir}/{submission_id}/related_work_data/ranked_papers.json"
            ):
                print(f"Missing abstract and introduction for {submission_id}")
                continue

            with open(
                f"{data_dir}/{submission_id}/related_work_data/ranked_papers.json",
                "r",
            ) as f:
                ranked_papers = json.load(f)

            not_cited_papers = [
                i["title"] for i in ranked_papers if not i["cited_paper"]
            ]

            if not os.path.exists(landscape_path):
                print(f"Missing landscape analysis for {submission_id}")
                missing_landscape += 1
                continue

            if not os.path.exists(structured_rep_path):
                print(f"Missing structured representation for {submission_id}")
                missing_structured_rep += 1
                continue

            submission = self.load_submission_paper(data_dir, submission_id)

            landscape_analysis = self.load_landscape_analysis(landscape_path)

            citation_contexts = self.load_citation_contexts(data_dir, submission_id)

            formatted_submission = self.format_submission_for_prompt(submission)

            formatted_not_cited_papers = self.format_not_cited_papers(not_cited_papers)

            prompt = novelty_delta_analysis_prompt.format(
                structured_representation=formatted_submission,
                research_landscape=landscape_analysis,
                not_cited_paper_titles=formatted_not_cited_papers,
                citation_contexts=citation_contexts,
            )

            batch_entry = {
                "custom_id": f"novelty-assessment-{submission_id}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                },
            }

            batch_entries.append(batch_entry)
            valid_submissions += 1

        print(
            f"Valid submissions for novelty assessment: {valid_submissions}/{total_submissions} ({valid_submissions/total_submissions*100:.1f}%)"
        )
        if missing_landscape > 0:
            print(f"Submissions missing landscape analysis: {missing_landscape}")
        if missing_structured_rep > 0:
            print(
                f"Submissions missing structured representation: {missing_structured_rep}"
            )

        output_path = os.path.join(
            "./openai_inputs", "batch_novelty_assessment_input.jsonl"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in batch_entries:
                f.write(json.dumps(entry) + "\n")

        print(
            f"Batch inference data saved to {output_path} with {len(batch_entries)} total entries"
        )
        return output_path

    def process_batch_results(
        self,
        data_dir: str,
        results_file: str,
        output_file: str = "novelty_delta_analysis.txt",
    ) -> Dict:
        """Process the results from batched inference for novelty assessment."""
        from litellm import cost_per_token

        print(f"Processing novelty assessment batch results from {results_file}")

        stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "total_cost": 0.0,
            "submissions": [],
        }

        with open(results_file, "r", encoding="utf-8") as f:
            results = [json.loads(line) for line in f]

        for result in results:
            custom_id = result.get("custom_id", "")

            if not custom_id.startswith("novelty-assessment-"):
                print(f"Skipping non-novelty-assessment result: {custom_id}")
                continue

            stats["total_processed"] += 1

            submission_id = custom_id.replace("novelty-assessment-", "")

            response_data = result.get("response", {}).get("body", {})
            choices = response_data.get("choices", [])

            submission_stats = {"submission_id": submission_id, "status": "success"}

            if not choices:
                print(f"No content found for {submission_id}")
                stats["failed"] += 1
                submission_stats["status"] = "failed"
                submission_stats["error"] = "No content in choices"
                stats["submissions"].append(submission_stats)
                continue

            content = choices[0].get("message", {}).get("content", "")

            if not content:
                print(f"Empty content for {submission_id}")
                stats["failed"] += 1
                submission_stats["status"] = "failed"
                submission_stats["error"] = "Empty content"
                stats["submissions"].append(submission_stats)
                continue

            submission_dir = os.path.join(data_dir, submission_id, "ours")
            os.makedirs(submission_dir, exist_ok=True)

            output_path = os.path.join(submission_dir, output_file)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"Saved novelty assessment for {submission_id}")

            token_usage = response_data.get("usage", {})

            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)

            try:
                cost = sum(
                    cost_per_token(
                        model="gpt-4.1",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                )
                stats["total_cost"] += cost
                submission_stats["cost"] = cost
            except Exception as e:
                print(f"Error calculating cost for {submission_id}: {e}")
                submission_stats["cost_error"] = str(e)

            submission_stats["token_usage"] = token_usage

            meta_path = os.path.join(submission_dir, "metadata.json")
            current_meta = {}

            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        current_meta = json.load(f)
                except json.JSONDecodeError:
                    print(f"Error reading metadata file for {submission_id}")

            current_meta["novelty_assessment"] = {
                "total_cost": submission_stats.get("cost", 0),
                "token_usage": token_usage,
            }

            with open(meta_path, "w") as f:
                json.dump(current_meta, f, indent=3)

            stats["successful"] += 1
            stats["submissions"].append(submission_stats)

        success_rate = (
            (stats["successful"] / stats["total_processed"]) * 100
            if stats["total_processed"] > 0
            else 0
        )
        print(
            f"Processed {stats['total_processed']} submissions with {stats['successful']} successes ({success_rate:.1f}%)"
        )
        print(f"Total estimated cost: ${stats['total_cost']:.4f}")

        summary_path = "./openai_outputs/novelty_assessment_processing_summary.json"
        with open(summary_path, "w") as f:
            json.dump(stats, f, indent=3)

        return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Assess novelty of research papers")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="../../novelty_assessment/data_iclr_all_topics/iclr_compiled_v2",
        help="Directory containing submission data"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1",
        help="OpenAI model to use"
    )
    parser.add_argument(
        "--submission-id",
        type=str,
        help="Process single submission (for run_assessment)"
    )
    parser.add_argument(
        "--landscape-file",
        type=str,
        default="research_landscape.txt",
        help="Path to landscape analysis file"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="novelty_delta_analysis.txt",
        help="Output file for assessment"
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Prepare batch inference data"
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Process batch results"
    )
    parser.add_argument(
        "--results-file",
        type=str,
        default="./openai_outputs/batch_novelty_assessment_output.jsonl",
        help="Path to batch results file"
    )
    
    args = parser.parse_args()
    
    assessor = NoveltyAssessor(model_name=args.model)
    
    if args.submission_id:
        assessor.run_assessment(
            args.data_dir,
            args.submission_id
        )
    
    if args.prepare:
        assessor.prepare_batch_inference_data(args.data_dir)
    
    if args.process:
        assessor.process_batch_results(
            args.data_dir,
            args.results_file,
            "novelty_delta_analysis.txt"
        )

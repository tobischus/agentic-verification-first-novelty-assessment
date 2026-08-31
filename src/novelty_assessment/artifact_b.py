#!/usr/bin/env python3
"""
Step 5: Artifact B — synthesized novelty assessment, generated ONLY from Artifact A.

The verification-first constraint: Artifact B is produced solely from the
structured, evidence-backed comparisons in Artifact A ({id}_artifact_a.json).
The LLM may NOT introduce prior work, comparisons, or judgments that are not
present in Artifact A. Every statement about prior work must trace back to a
verified comparison entry. This makes B auditable and lets Step 6 (Judge) check
that B follows from A.

Outputs:
  - {id}_artifact_b.json : per-claim verdicts + overall assessment (structured)
  - {id}_assessment.txt  : the reviewer-facing prose (for comparison with humans)
"""
import argparse
import json
import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


ARTIFACT_B_PROMPT = """You are writing a novelty assessment of a paper to support a peer reviewer.

You are given STRUCTURED EVIDENCE (Artifact A): for each claimed contribution of the submission, the result of comparing it against retrieved prior work — which prior papers CHALLENGE the claim (each backed by verified verbatim quotes from both the submission and the prior paper), and which related papers were examined but do NOT challenge it (with the reason they differ).

## STRICT GROUNDING RULES (verification-first)
- Base your assessment ONLY on the evidence below (Artifact A). Do NOT use any outside knowledge, prior work, comparison, or fact that is not present in the evidence. Artifact A is your ONLY source.
- Every statement about prior work must correspond to a specific entry in the evidence; name the prior paper(s) by their titles exactly as given.
- Quote or paraphrase only the verified evidence shown; never invent overlaps or quotes.
- If a claim has no challenging prior work in the evidence, conclude its novelty is NOT challenged WITHIN the examined literature. Do NOT assert it is novel in an absolute sense (the search scope is limited).
- Do not output numeric scores.

## Evidence (Artifact A)
{evidence}

## Produce
1. per_claim: for each claim provide:
   - verdict: exactly one of "challenged" (verified prior work substantially presents the same contribution), "not_challenged" (no examined prior work challenges it), or "uncertain" (evidence insufficient to decide).
   - rationale: a SELF-CONTAINED, ARGUMENTATIVE assessment of 3-6 sentences that a reviewer could read on its own and find convincing. Build the argument STEP BY STEP from the evidence:
       * Open with the verdict and how strongly it holds.
       * If CHALLENGED: name the specific prior paper(s); state precisely WHAT overlaps, grounding it in the verified submission-vs-prior-work quotes; judge whether the overlap is substantial (the same contribution) or only partial; and explicitly note any remaining differentiator of the submission if the evidence shows one.
       * If NOT CHALLENGED: name the closest examined prior work and explain, using the recorded reason it differs, WHY it does not cover the claimed contribution; then state that novelty holds within the examined literature (not absolutely).
       * Reflect the STRENGTH of the evidence so the reader can gauge credibility — e.g. whether the comparison rested on the prior work's full text or only its abstract+introduction, and whether the overlap quotes were verified.
       Keep it strictly grounded; introduce nothing beyond the evidence.
   - challenging_papers: titles of the prior papers that challenge this claim (empty if none).
2. overall_assessment: one coherent, argumentative paragraph synthesizing ACROSS all claims for the reviewer — which contributions appear genuinely novel within the examined literature, which are challenged by prior work (name them), how the submission positions itself relative to that prior work, and the overall novelty picture. Strictly grounded in the evidence above.
"""


class ClaimVerdict(BaseModel):
    claim_id: str = Field(description="The claim id from the evidence")
    claim_name: str = Field(description="The claim name from the evidence")
    verdict: str = Field(description="One of: challenged, not_challenged, uncertain")
    rationale: str = Field(
        description="A self-contained, argumentative 3-6 sentence assessment grounded "
                    "ONLY in the evidence (see prompt for the required structure)."
    )
    challenging_papers: List[str] = Field(
        default_factory=list, description="Titles of prior papers that challenge this claim (if any)"
    )


class ArtifactB(BaseModel):
    per_claim: List[ClaimVerdict]
    overall_assessment: str = Field(description="Reviewer-facing prose, grounded only in the evidence")


class ArtifactBBuilder:
    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)

    @staticmethod
    def _format_evidence(artifact_a: dict) -> str:
        lines = []
        for e in artifact_a["claims"]:
            lines.append(f"### Claim {e['claim_id']}: {e['claim_name']}")
            lines.append(f'Claimed contribution (verbatim): "{e["claim_text"]}"')
            lines.append(f"Prior-work papers examined for this claim: {e['candidates_examined']}")
            comps = e["comparisons"]
            refuters = [c for c in comps if c["refutation_status"] == "can_refute"]
            others = [c for c in comps if c["refutation_status"] != "can_refute"]

            if refuters:
                lines.append("CHALLENGING PRIOR WORK (verified overlap):")
                for c in refuters:
                    cited = "yes" if c["cited_by_submission"] else "no"
                    src = c.get("content_source", "")
                    lines.append(
                        f'- "{c["title"]}" (cited by the submission: {cited}; '
                        f"compared against: {src}; overlap: {c.get('overlap_degree', '?')})"
                    )
                    for ep in c["evidence_pairs"]:
                        # only surface pairs verified on BOTH sides (claim + prior work)
                        if ep.get("paper_quote_verified") and ep.get("claim_quote_verified", True):
                            lines.append(f'    - submission says: "{ep["claim_quote"][:240]}"')
                            lines.append(f'      prior work says: "{ep["paper_quote"][:240]}"')
                    if c.get("what_is_shared"):
                        lines.append(f"    - shared: {c['what_is_shared']}")
                    if c.get("submission_delta"):
                        lines.append(f"    - submission adds beyond it: {c['submission_delta']}")
                    if c.get("brief_note"):
                        lines.append(f"    - analysis: {c['brief_note']}")
            else:
                lines.append("No examined prior work challenges this claim (no verified overlap found).")

            # Always surface the most-similar NON-challenging papers + WHY they differ (and what
            # the submission adds), so B can argue novel vs incremental against close prior work.
            if others:
                top_others = sorted(others, key=lambda c: c.get("similarity", 0.0), reverse=True)[:4]
                lines.append("RELATED BUT NOT CHALLENGING (examined, with reason they differ):")
                for c in top_others:
                    src = c.get("content_source", "")
                    note = c.get("brief_note") or "no specific overlap found"
                    deg = c.get("overlap_degree")
                    extra = f" [overlap: {deg}]" if deg else ""
                    lines.append(f'- "{c["title"]}" (compared against: {src}){extra}: {note}')
                    if c.get("submission_delta"):
                        lines.append(f"    - submission adds: {c['submission_delta']}")
            lines.append("")
        return "\n".join(lines)

    def build_one(self, entry: dict) -> dict:
        """Synthesize the verdict for a SINGLE claim's Artifact-A entry (on-demand)."""
        evidence = self._format_evidence({"claims": [entry]})
        prompt = ARTIFACT_B_PROMPT.format(evidence=evidence)
        result = self.llm.with_structured_output(ArtifactB).invoke(prompt)
        if result.per_claim:
            v = result.per_claim[0].model_dump()
        else:
            v = {"claim_id": entry["claim_id"], "claim_name": entry["claim_name"],
                 "verdict": "uncertain", "rationale": "", "challenging_papers": []}
        return v

    def build(self, data_dir: str, submission_id: str) -> dict:
        sub_dir = Path(data_dir) / submission_id
        artifact_a = json.loads((sub_dir / f"{submission_id}_artifact_a.json").read_text(encoding="utf-8"))

        evidence = self._format_evidence(artifact_a)
        prompt = ARTIFACT_B_PROMPT.format(evidence=evidence)
        result = self.llm.with_structured_output(ArtifactB).invoke(prompt)

        per_claim = [v.model_dump() for v in result.per_claim]
        artifact_b = {
            "submission_id": submission_id,
            "generated_from": f"{submission_id}_artifact_a.json",
            "per_claim": per_claim,
            "overall_assessment": result.overall_assessment,
        }
        (sub_dir / f"{submission_id}_artifact_b.json").write_text(
            json.dumps(artifact_b, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (sub_dir / f"{submission_id}_assessment.txt").write_text(
            result.overall_assessment, encoding="utf-8"
        )
        return artifact_b


def main():
    ap = argparse.ArgumentParser(description="Step 5: synthesize Artifact B from Artifact A")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    args = ap.parse_args()

    b = ArtifactBBuilder(model_name=args.model).build(args.data_dir, args.submission_id)
    print("Per-claim verdicts:")
    for v in b["per_claim"]:
        cp = f" -> {', '.join(v['challenging_papers'])}" if v["challenging_papers"] else ""
        print(f"  [{v['claim_id']}] {v['verdict']:15} {v['claim_name']}{cp}")
    print("\nOverall assessment:\n" + b["overall_assessment"])


if __name__ == "__main__":
    main()

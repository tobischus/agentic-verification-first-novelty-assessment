#!/usr/bin/env python3
"""
Step 6: Judge — check that Artifact B follows from Artifact A.

The verification-first guarantee: the synthesized assessment (Artifact B) must
be entailed by the structured evidence (Artifact A), with no unsupported or
contradictory statements. The Judge is hybrid:

  1. DETERMINISTIC per-claim consistency: B's verdict ("challenged" /
     "not_challenged") must match whether A actually contains a verified
     can_refute for that claim, and B's named challenging papers must be a
     subset of A's refuting papers for that claim. No LLM, fully auditable.

  2. LLM ENTAILMENT of the prose: an LLM-as-judge checks the overall_assessment
     text against the facts in A and flags any statement not supported by A
     (hallucinated prior work, over-claims, contradictions).

Output: {id}_judge.json with per-claim checks, prose entailment, and an overall
`follows_from_a` flag (deterministic checks pass AND prose entailed).
"""
import argparse
import json
import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


JUDGE_PROMPT = """You are an auditor verifying that a novelty ASSESSMENT is fully supported by the EVIDENCE it was supposed to be derived from. You are NOT judging whether the paper is novel — only whether the assessment stays within what the evidence supports.

## EVIDENCE (Artifact A) — the only admissible facts
{facts}

## ASSESSMENT (Artifact B) to audit
{assessment}

## Task
Check every factual statement in the assessment about prior work and about what challenges what. A statement is SUPPORTED only if it follows from the evidence above. Flag any statement that:
- names or implies prior work not present in the evidence,
- claims a contribution is challenged/refuted when the evidence shows no verified challenge (or vice versa),
- overstates or contradicts the evidence.

Return:
- entailed: true only if the entire assessment is supported by the evidence.
- unsupported_statements: the specific statements that are not supported (empty if entailed).
- explanation: a brief justification.
"""


class EntailmentVerdict(BaseModel):
    entailed: bool = Field(description="True iff the whole assessment is supported by the evidence")
    unsupported_statements: List[str] = Field(
        default_factory=list, description="Statements not supported by the evidence"
    )
    explanation: str = Field(description="Brief justification")


class Judge:
    def __init__(self, model_name: str = "gpt-4.1", temperature: float = 0.0):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)

    @staticmethod
    def _refuters_from_a(artifact_a: dict) -> dict:
        """claim_id -> set of titles with a verified can_refute in Artifact A."""
        out = {}
        for e in artifact_a["claims"]:
            out[e["claim_id"]] = {
                c["title"]
                for c in e["comparisons"]
                if c["refutation_status"] == "can_refute"
            }
        return out

    def _deterministic_checks(self, artifact_a: dict, artifact_b: dict):
        refuters = self._refuters_from_a(artifact_a)
        checks, issues = [], []
        for v in artifact_b["per_claim"]:
            cid = v["claim_id"]
            verdict = v["verdict"]
            b_papers = v.get("challenging_papers", []) or []
            a_titles = refuters.get(cid, set())
            a_has = len(a_titles) > 0

            problems = []
            if verdict == "challenged" and not a_has:
                problems.append("B verdict 'challenged' but A has no verified can_refute for this claim")
            if verdict == "not_challenged" and a_has:
                problems.append("B verdict 'not_challenged' but A HAS a verified can_refute for this claim")
            # named challenging papers must exist among A's refuters (fuzzy title match)
            for p in b_papers:
                if not any(fuzz.token_set_ratio(p, at) >= 85 for at in a_titles):
                    problems.append(f"challenging paper not in A's verified refuters: '{p[:60]}'")

            consistent = not problems
            checks.append({"claim_id": cid, "verdict": verdict, "consistent": consistent, "problems": problems})
            issues.extend(f"{cid}: {p}" for p in problems)
        return checks, issues

    @staticmethod
    def _facts_from_a(artifact_a: dict) -> str:
        lines = []
        for e in artifact_a["claims"]:
            refuters = [c["title"] for c in e["comparisons"] if c["refutation_status"] == "can_refute"]
            if refuters:
                lines.append(
                    f"- {e['claim_id']} ({e['claim_name']}): CHALLENGED by verified prior work: "
                    + "; ".join(f'"{t}"' for t in refuters)
                    + f". (examined {e['candidates_examined']} papers)"
                )
            else:
                lines.append(
                    f"- {e['claim_id']} ({e['claim_name']}): NOT challenged by any of the "
                    f"{e['candidates_examined']} examined papers."
                )
        return "\n".join(lines)

    def _llm_entailment(self, artifact_a: dict, artifact_b: dict) -> dict:
        prompt = JUDGE_PROMPT.format(
            facts=self._facts_from_a(artifact_a),
            assessment=artifact_b["overall_assessment"],
        )
        r = self.llm.with_structured_output(EntailmentVerdict).invoke(prompt)
        return r.model_dump()

    def judge(self, data_dir: str, submission_id: str) -> dict:
        sub_dir = Path(data_dir) / submission_id
        artifact_a = json.loads((sub_dir / f"{submission_id}_artifact_a.json").read_text(encoding="utf-8"))
        artifact_b = json.loads((sub_dir / f"{submission_id}_artifact_b.json").read_text(encoding="utf-8"))

        checks, det_issues = self._deterministic_checks(artifact_a, artifact_b)
        entailment = self._llm_entailment(artifact_a, artifact_b)

        report = {
            "submission_id": submission_id,
            "follows_from_a": bool(not det_issues and entailment.get("entailed")),
            "deterministic_per_claim": checks,
            "deterministic_issues": det_issues,
            "prose_entailment": entailment,
        }
        (sub_dir / f"{submission_id}_judge.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report


def main():
    ap = argparse.ArgumentParser(description="Step 6: Judge — does Artifact B follow from Artifact A?")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    args = ap.parse_args()

    r = Judge(model_name=args.model).judge(args.data_dir, args.submission_id)
    print(f"follows_from_a: {r['follows_from_a']}\n")
    print("Deterministic per-claim consistency:")
    for c in r["deterministic_per_claim"]:
        flag = "OK " if c["consistent"] else "FAIL"
        print(f"  [{flag}] {c['claim_id']} verdict={c['verdict']}"
              + ("" if c["consistent"] else f" -> {c['problems']}"))
    pe = r["prose_entailment"]
    print(f"\nProse entailment: entailed={pe['entailed']}")
    if pe["unsupported_statements"]:
        for s in pe["unsupported_statements"]:
            print(f"  - UNSUPPORTED: {s}")
    print(f"  explanation: {pe['explanation']}")


if __name__ == "__main__":
    main()

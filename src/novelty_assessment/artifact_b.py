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

import verdict as vd

load_dotenv()


ARTIFACT_B_PROMPT = """You are writing a novelty assessment of a paper to support a peer reviewer.

You are given STRUCTURED EVIDENCE (Artifact A).

## STRICT GROUNDING RULES
- Base the assessment ONLY on Artifact A.
- The claim verdict in Artifact A is FIXED by the deterministic evidence controller.
- Copy that verdict exactly. Do NOT infer, revise, strengthen, or weaken it.
- `not_challenged` means that no verifier-approved strong refuter was found.
  It does NOT mean that no prior-work overlap was found.
- Partial material overlaps must still be described when present.
- Individual paper comparisons may be marked UNRESOLVED because their
  reading/comparison budget was exhausted.
- An unresolved paper does NOT change the FIXED CONTROLLER VERDICT.
- `EVIDENCE SUFFICIENT` refers to whether the claim-level strong-refuter
  decision could be made.
- `REVIEW COMPLETE` refers to whether every individual paper comparison
  was fully resolved.
- A claim may therefore be `not_challenged` while `REVIEW COMPLETE` is false.
- If unresolved papers exist, mention their number and briefly report their
  last semantic assessment and the recorded budget reason.
- Do not describe the claim itself as uncertain merely because individual
  paper comparisons remain unresolved.
- The last semantic assessment of an unresolved paper is the best available
  semantic assessment, but its evidence conflict was not fully resolved.
- Every statement about prior work must correspond to an entry in Artifact A.
- Do not introduce outside knowledge.
- Do not output numeric scores.

## Evidence
{evidence}

## Produce
For every claim:
- copy the FIXED CONTROLLER VERDICT exactly;
- write a concise 3-6 sentence rationale explaining that verdict from the evidence;
- if partial material overlap exists without a strong refuter, say so explicitly;
- if challenged, identify the verified strong refuter(s);
- if unresolved papers exist, report how many remain unresolved and briefly
  state their last semantic assessment and recorded budget reason;
- do not equate "no strong refuter" with "no overlap";
- do not equate an unresolved paper comparison with an uncertain claim verdict.

Also produce an overall_assessment grounded only in the supplied claims.
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
    def __init__(self, model_name="gpt-4.1", temperature=0.0):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        if model_name.startswith(("gpt-5", "o1", "o3", "o4")):
            kw = {
                "reasoning_effort": os.getenv(
                    "NOVELTY_CONCLUSION_EFFORT", "low"
                )
            }
        else:
            kw = {"temperature": temperature}

        self.llm = ChatOpenAI(
            model_name=model_name,
            api_key=api_key,
            **kw,
        )

    @staticmethod
    def _format_evidence(artifact_a: dict) -> str:
        lines = []
        for e in artifact_a["claims"]:
            lines.append(f"### Claim {e['claim_id']}: {e['claim_name']}")
            lines.append(f'Claimed contribution (verbatim): "{e["claim_text"]}"')
            lines.append(f"Prior-work papers examined for this claim: {e['candidates_examined']}")
            lines.append(
                f"FIXED CONTROLLER VERDICT: {e.get('agent_verdict', 'uncertain')}"
            )
            lines.append(
                f"EVIDENCE SUFFICIENT: {bool(e.get('evidence_sufficient', False))}"
            )
            lines.append(
                f"STOP REASON: {e.get('stop_reason', '')}"
            )
            lines.append(
                f"REVIEW COMPLETE: {bool(e.get('review_complete', True))}"
            )
            lines.append(
                f"UNRESOLVED PAPERS: {int(e.get('unresolved_count', 0))}"
            )

            for u in e.get("unresolved_papers", []):
                lines.append(
                    f'- UNRESOLVED: "{u.get("title", "")}" | '
                    f'best semantic assessment: {u.get("semantic_degree", "")} | '
                    f'reason: {u.get("reason", "")}'
                )
                if u.get("deficit"):
                    lines.append(
                        f'  open evidence issue: {u["deficit"]}'
                    )
            comps = e["comparisons"]
            refuters = [c for c in comps if vd.challenges(c)]
            others = [c for c in comps if not vd.challenges(c)]

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
                        # Only pairs verified on BOTH sides (claim + prior work). The claim
                        # side defaults to FALSE when the field is absent: artifacts written
                        # before artifact_a checked the claim side carry no such flag, and
                        # treating that as verified would let an unchecked quote reach the
                        # synthesis -- exactly where the evidence invariant must hold.
                        if ep.get("paper_quote_verified") and ep.get("claim_quote_verified"):
                            lines.append(f'    - submission says: "{ep["claim_quote"][:240]}"')
                            lines.append(f'      prior work says: "{ep["paper_quote"][:240]}"')
                    if c.get("what_is_shared"):
                        lines.append(f"    - shared: {c['what_is_shared']}")
                    if c.get("submission_delta"):
                        lines.append(f"    - submission adds beyond it: {c['submission_delta']}")
                    if c.get("brief_note"):
                        lines.append(f"    - analysis: {c['brief_note']}")
            else:
                lines.append(
                    "No verified strong refuter was found for this claim."
                )

            # Every non-refuting paper the review found to OVERLAP the claim, plus a few of the
            # closest remaining ones for context. Selecting these by similarity alone (the old
            # top-4) meant the synthesis silently ignored most of the overlapping prior work the
            # UI lists directly beneath it -- on one claim, 8 of 11 -- so B argued about papers
            # the reader could not see while skipping ones they could. The overlap rule here is
            # deliberately the same one api.review_summary renders with.
            if others:
                overlapping = [c for c in others if vd.is_overlap(c)]
                rest = sorted((c for c in others if c not in overlapping),
                              key=lambda c: c.get("similarity", 0.0), reverse=True)[:3]
                top_others = sorted(overlapping, key=lambda c: c.get("similarity", 0.0),
                                    reverse=True) + rest
                lines.append("RELATED BUT NOT CHALLENGING (examined, with reason they differ):")
                for c in top_others:
                    src = c.get("content_source", "")
                    note = c.get("brief_note") or c.get("assessment") or "no specific overlap found"
                    deg = c.get("overlap_degree")
                    extra = f" [overlap: {deg}]" if deg else ""

                    is_unresolved = bool(
                        c.get("unresolved") or c.get("insufficient")
                    )
                    unresolved_tag = " [UNRESOLVED]" if is_unresolved else ""

                    lines.append(
                        f'- "{c["title"]}" (compared against: {src})'
                        f'{extra}{unresolved_tag}: {note}'
                    )

                    if c.get("submission_delta"):
                        lines.append(
                            f"    - submission adds: {c['submission_delta']}"
                        )

                    if is_unresolved:
                        reason = c.get("unresolved_reason", "budget_exhausted")
                        deficit = c.get("unresolved_deficit", "")

                        lines.append(
                            f"    - unresolved reason: {reason}"
                        )

                        if deficit:
                            lines.append(
                                f"    - open evidence issue: {deficit}"
                            )
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _force_controller_fields(entry: dict, value: dict | None = None) -> dict:
            v = dict(value or {})
    
            v["claim_id"] = entry["claim_id"]
            v["claim_name"] = entry.get("claim_name", "")
            v["verdict"] = entry.get("agent_verdict", "uncertain")
            v["challenging_papers"] = [
                c["title"]
                for c in entry.get("comparisons", [])
                if vd.challenges(c)
            ]
    
            return v


    def build_one(self, entry: dict) -> dict:
        evidence = self._format_evidence({"claims": [entry]})
        prompt = ARTIFACT_B_PROMPT.format(evidence=evidence)
        result = self.llm.with_structured_output(ArtifactB).invoke(prompt)

        raw = (
            result.per_claim[0].model_dump()
            if result.per_claim
            else {"rationale": ""}
        )

        return self._force_controller_fields(entry, raw)

    def build(self, data_dir: str, submission_id: str, variant: str = "") -> dict:
        sub_dir = Path(data_dir) / submission_id
        from artifact_a import variant_path
        artifact_a = json.loads(
            variant_path(sub_dir, submission_id, "artifact_a", variant).read_text(encoding="utf-8"))

        evidence = self._format_evidence(artifact_a)
        prompt = ARTIFACT_B_PROMPT.format(evidence=evidence)
        result = self.llm.with_structured_output(ArtifactB).invoke(prompt)

        raw_by = {
            v.claim_id: v.model_dump()
            for v in result.per_claim
        }

        per_claim = [
            self._force_controller_fields(
                entry,
                raw_by.get(entry["claim_id"], {"rationale": ""}),
            )
            for entry in artifact_a["claims"]
        ]
        artifact_b = {
            "submission_id": submission_id,
            "generated_from": variant_path(sub_dir, submission_id, "artifact_a", variant).name,
            "per_claim": per_claim,
            "overall_assessment": result.overall_assessment,
        }
        variant_path(sub_dir, submission_id, "artifact_b", variant).write_text(
            json.dumps(artifact_b, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (sub_dir / f"{submission_id}_assessment{('_' + variant) if variant else ''}.txt").write_text(
            result.overall_assessment, encoding="utf-8"
        )
        return artifact_b


def main():
    ap = argparse.ArgumentParser(description="Step 5: synthesize Artifact B from Artifact A")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    ap.add_argument("--model", default="gpt-4.1")
    ap.add_argument("--variant", default="", help="read/write the {variant}-suffixed artifacts")
    args = ap.parse_args()

    b = ArtifactBBuilder(model_name=args.model).build(args.data_dir, args.submission_id,
                                                       variant=args.variant)
    print("Per-claim verdicts:")
    for v in b["per_claim"]:
        cp = f" -> {', '.join(v['challenging_papers'])}" if v["challenging_papers"] else ""
        print(f"  [{v['claim_id']}] {v['verdict']:15} {v['claim_name']}{cp}")
    print("\nOverall assessment:\n" + b["overall_assessment"])


if __name__ == "__main__":
    main()

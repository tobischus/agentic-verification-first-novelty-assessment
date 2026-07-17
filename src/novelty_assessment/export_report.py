#!/usr/bin/env python3
"""
Step 7: Final Reviewer Guidance / Export.

Assembles a human-readable Markdown report for the reviewer from the pipeline
artifacts (claims, Artifact A, Artifact B, Judge). This phase is purely
template-based -- NO LLM calls -- so the report is a deterministic, auditable
rendering of the verified evidence and the synthesized assessment.

Output: {id}_report.md
"""
import argparse
import json
from pathlib import Path


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def build_report(data_dir: str, submission_id: str) -> str:
    sub = Path(data_dir) / submission_id
    meta = _load(sub / f"{submission_id}.json") or {}
    claims_doc = _load(sub / f"{submission_id}_claims.json") or {}
    a = _load(sub / f"{submission_id}_artifact_a.json") or {"claims": []}
    b = _load(sub / f"{submission_id}_artifact_b.json") or {}
    judge = _load(sub / f"{submission_id}_judge.json") or {}

    a_by_id = {e["claim_id"]: e for e in a.get("claims", [])}
    title = meta.get("title", submission_id)

    out = []
    out.append(f"# Novelty Assessment — {title}")
    out.append("")
    out.append(f"_Submission `{submission_id}` · verification-first automated assessment_")
    out.append("")

    if b.get("overall_assessment"):
        out.append("## Overall novelty assessment")
        out.append(b["overall_assessment"])
        out.append("")

    out.append("## Per-claim findings")
    verdict_label = {"challenged": "⚠ challenged by prior work",
                     "not_challenged": "✓ not challenged within examined scope",
                     "uncertain": "? uncertain"}
    for v in b.get("per_claim", []):
        cid = v["claim_id"]
        ae = a_by_id.get(cid, {})
        out.append(f"### {v['claim_name']} — **{verdict_label.get(v['verdict'], v['verdict'])}**")
        if ae.get("claim_text"):
            out.append(f"> {ae['claim_text']}")
        out.append("")
        if v["rationale"]:
            out.append(v["rationale"])
            out.append("")
        refuters = [c for c in ae.get("comparisons", []) if c["refutation_status"] == "can_refute"]
        if refuters:
            out.append("**Challenged by:**")
            for c in refuters:
                cited = "cited by submission" if c["cited_by_submission"] else "not cited by submission"
                src = c.get("content_source", "")
                out.append(f"- *{c['title']}* ({cited}; comparison on {src})")
                for ep in c.get("evidence_pairs", []):
                    if ep.get("paper_quote_verified"):
                        out.append(f"    - submission: “{ep['claim_quote'][:220]}”")
                        out.append(f"    - prior work: “{ep['paper_quote'][:220]}” ✓ verified")
            out.append("")
        else:
            n = ae.get("candidates_examined", 0)
            closest = max(ae.get("comparisons", []), key=lambda c: c.get("similarity", 0.0), default=None)
            ctext = f" Closest examined: *{closest['title']}*." if closest else ""
            out.append(f"No challenging prior work among {n} examined papers.{ctext}")
            out.append("")

    # Verification + scope
    out.append("## Verification")
    follows = judge.get("follows_from_a")
    out.append(f"- Assessment synthesized **only** from the verified evidence above (Artifact A).")
    out.append(f"- Consistency audit (does the assessment follow from the evidence?): "
               f"**{'PASS' if follows else 'FAIL' if follows is not None else 'n/a'}**")
    if judge.get("deterministic_issues"):
        for iss in judge["deterministic_issues"]:
            out.append(f"    - issue: {iss}")
    pe = judge.get("prose_entailment", {})
    if pe and not pe.get("entailed", True):
        for s in pe.get("unsupported_statements", []):
            out.append(f"    - unsupported: {s}")
    out.append("")

    out.append("## Scope & limitations")
    out.append(f"- Related-work pool examined: {a.get('n_related_pool', '?')} papers; "
               f"top-{a.get('k_per_claim', '?')} compared per claim.")
    out.append("- Comparison uses candidate full text where an open-access PDF was obtainable, "
               "otherwise abstract + introduction.")
    out.append("- Findings are bounded by the retrieved literature; absence of a challenge means "
               "none was found within scope, not that the contribution is novel in an absolute sense.")
    out.append("")

    report = "\n".join(out)
    (sub / f"{submission_id}_report.md").write_text(report, encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description="Step 7: export reviewer report (template-based, no LLM)")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--submission-id", required=True)
    args = ap.parse_args()
    report = build_report(args.data_dir, args.submission_id)
    print(report)


if __name__ == "__main__":
    main()

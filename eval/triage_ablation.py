#!/usr/bin/env python3
"""
What does the abstract-only triage throw away?

The agent screens the whole pool from abstracts in one batched call, then reads only the
papers that screen said might overlap. Everything else is settled on its abstract and
never looked at again. That single cheap decision therefore fixes the ceiling on the
entire assessment: a paper dismissed here cannot be recovered by any later stage, because
no later stage revisits it.

This measures the cost of that. Every paper the triage dismissed is put through the SAME
deep dive the agent runs on the papers it kept -- the agent's own `_section_compare`, its
own prompt, its own schema, its own verifier -- and the resulting overlap degree is
compared with the one the triage assigned. A flip means the pipeline's own machinery
disagrees with its own screening, on a paper it had already decided not to read.

Nothing is written back into the run; the artifacts stay as they are.

Usage
-----
  python eval/triage_ablation.py --submission graphrag_when_to_use
  python eval/triage_ablation.py --submission ID --claim claim_1 --limit 5 --model gpt-5-mini
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                      # noqa: E402

load_dotenv()

OVERLAP = ("same", "substantial", "partial")
DISMISSED = ("none", "superficial", "")


def _deg(c: dict) -> str:
    return (c.get("overlap_degree") or "").lower()


def run(data_dir: str, sid: str, only_claim: str, limit: int, model: str, out: str) -> dict:
    from agent.claim_agent import ClaimNoveltyAgent, _segments_to_text
    from agent.tools import ClaimToolbox

    sub = Path(data_dir) / sid
    art = json.loads((sub / f"{sid}_artifact_a.json").read_text(encoding="utf-8"))
    claims_doc = json.loads((sub / f"{sid}_claims.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in claims_doc.get("claims", [])}

    agent = ClaimNoveltyAgent(data_dir, sid, model_name=model)
    results, t0 = [], time.perf_counter()

    for entry in art.get("claims", []):
        cid = entry.get("claim_id")
        if only_claim and cid != only_claim:
            continue
        claim = by_id.get(cid)
        if claim is None:
            continue

        # The context every comparison is made against: reuse what the run itself derived,
        # rather than re-deriving it. A fresh realization would be a second variable, and
        # this experiment is about the triage decision alone.
        claim_ctx = _segments_to_text(entry.get("claim_realization") or [])

        dismissed = [c for c in entry.get("comparisons", [])
                     if c.get("depth") == "abstract_only" and _deg(c) in DISMISSED]
        if limit:
            dismissed = dismissed[:limit]
        if not dismissed:
            continue

        tb = ClaimToolbox(data_dir, sid, claim, agent.embedder)
        print(f"\n=== {cid}: deep-diving {len(dismissed)} papers the triage dismissed ===")
        for i, c in enumerate(dismissed, 1):
            pid = c["paper_id"]
            title = (c.get("title") or "")[:58]
            try:
                tb.ensure_fulltext(pid)
                comp, _, _ = agent._section_compare(tb, claim, pid, claim_ctx)
            except Exception as e:                       # one bad PDF must not end the run
                print(f"  [{i:2}/{len(dismissed)}] ERROR {title}: {type(e).__name__}")
                continue
            after = (comp.get("overlap_degree") or "").lower()
            flip = after in OVERLAP
            verified = [p for p in (comp.get("evidence_pairs") or [])
                        if p.get("claim_quote_verified") and p.get("paper_quote_verified")]
            print(f"  [{i:2}/{len(dismissed)}] {_deg(c):11} -> {after:11} "
                  f"{'FLIP' if flip else '    '}  {title}")
            results.append({
                "claim_id": cid, "paper_id": pid, "title": c.get("title"),
                "triage_degree": _deg(c), "deep_degree": after, "flip": flip,
                "refutation_status": comp.get("refutation_status"),
                "verified_pairs": len(verified),
                "what_is_shared": comp.get("what_is_shared", ""),
                "submission_delta": comp.get("submission_delta", ""),
            })

    _report(results, time.perf_counter() - t0)
    payload = {"submission_id": sid, "model": model, "n": len(results), "results": results}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {out}")
    return payload


def _report(results, seconds):
    if not results:
        print("\nnothing to report")
        return
    flips = [r for r in results if r["flip"]]
    grounded = [r for r in flips if r["verified_pairs"] > 0]
    print("\n" + "=" * 76)
    print("TRIAGE ABLATION -- papers the abstract screen dismissed, then read in full")
    print("=" * 76)
    print(f"papers re-examined      : {len(results)}")
    print(f"overlap after reading   : {len(flips)}  ({100 * len(flips) / len(results):.0f}%)")
    print(f"  ...with a verified quote pair: {len(grounded)}")
    by_deg = {}
    for r in flips:
        by_deg[r["deep_degree"]] = by_deg.get(r["deep_degree"], 0) + 1
    for deg, n in sorted(by_deg.items()):
        print(f"    {deg:12} {n}")
    print(f"wall clock              : {seconds / 60:.1f} min")
    if flips:
        print("\nThe pipeline's own deep dive disagrees with its own screening on:")
        for r in flips[:12]:
            print(f"  {r['deep_degree']:12} {r['title'][:60]}")
    print("\nNothing was written back into the run.")


def main():
    ap = argparse.ArgumentParser(description="Deep-dive the papers the triage dismissed")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--claim", default="", help="restrict to one claim id")
    ap.add_argument("--limit", type=int, default=0, help="at most N papers per claim")
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)
    out = args.out or f"eval/out/triage_ablation_{args.submission}.json"
    run(args.data_dir, args.submission, args.claim, args.limit, args.model, out)


if __name__ == "__main__":
    main()

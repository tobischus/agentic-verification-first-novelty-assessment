#!/usr/bin/env python3
"""Run the agent and the linear baseline over the same claims, from one entry point.

The two systems share every module that touches a judgement and differ only in control
flow (see src/novelty_assessment/agent/linear_baseline.py). What this script adds is the
other half of that guarantee: they are constructed with the SAME arguments, from the same
files, in one process, so a pilot cannot end up comparing two different configurations
because a shell variable was set for one run and not the other.

It writes each variant to its own artifact pair -- {id}_artifact_a_{variant}.json and
{id}_artifact_b_{variant}.json -- so both can sit side by side and be rendered by the
same exporter:

  python src/novelty_assessment/battle_export.py --data-dir data \
      --submission-id ID --variant agent
  python src/novelty_assessment/battle_export.py --data-dir data \
      --submission-id ID --variant linear

Quality is not the only output that matters here. The agent may spend more calls on the
same claim, so USD and wall-clock time per claim are reported next to the verdicts, and
written into the artifact as `run_cost`. A quality difference that cost three times as
much is a different finding from one that did not.

Usage
-----
  python eval/run_pilot.py --submission transducing_language_models --variant both
  python eval/run_pilot.py --submission ID --variant linear --claims claim_1,claim_2
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                          # noqa: E402

load_dotenv()

# The agent's validated configuration, pinned here instead of assumed from the shell.
# NOVELTY_PAPER_LOOP and NOVELTY_NO_TRIAGE are read at IMPORT time in claim_agent, so a
# variable forgotten before the run would silently execute a different agent -- and the
# pilot would report that difference as an effect of the control flow. setdefault leaves
# an explicitly exported value authoritative, so an ablation can still override one.
for _k, _v in (("NOVELTY_PAPER_LOOP", "1"), ("NOVELTY_NO_TRIAGE", "1")):
    os.environ.setdefault(_k, _v)

VARIANTS = ("agent", "linear")

#: Reasoning effort per role, identical for both variants. Same rationale as above: the
#: roles are what the models are actually asked to do, and they have to match.
ROLE_EFFORT = {"NOVELTY_READING_EFFORT": "low", "NOVELTY_COMPARE_EFFORT": "low",
               "NOVELTY_EVIDENCE_EFFORT": "low"}
ROLE_MODEL_VARS = ("NOVELTY_READING_MODEL", "NOVELTY_COMPARE_MODEL", "NOVELTY_EVIDENCE_MODEL")


def _pool_size(sub: Path) -> int:
    try:
        return len(json.loads(
            (sub / "related_work_data" / "ranked_papers.json").read_text(encoding="utf-8")))
    except Exception:
        return 0


def _agent_class(variant: str):
    from agent.claim_agent import ClaimNoveltyAgent
    from agent.linear_baseline import LinearBaselineAgent
    return LinearBaselineAgent if variant == "linear" else ClaimNoveltyAgent


def run_variant(data_dir: str, sid: str, variant: str, claims: list, model: str,
                closest_n: int, max_retrievals: int, workers) -> dict:
    """One variant over all claims; returns the artifact_a-shaped dict it wrote."""
    from agent.claim_agent import _usd

    cls = _agent_class(variant)
    sub = Path(data_dir) / sid
    entries, per_claim_b, costs = [], [], []

    for claim in claims:
        # A fresh instance per claim, exactly as the backend runs it -- the toolbox, the
        # pool snapshot and the run log are per-claim objects in both systems.
        ag = cls(data_dir, sid, model_name=model, closest_n=closest_n,
                 max_retrievals=max_retrievals, deep_dive_workers=workers)
        t0 = time.perf_counter()
        res = ag.run(claim)
        secs = round(time.perf_counter() - t0, 1)

        # `run()` returns the artifact entry itself (tools.artifact_entry, updated with
        # the verdict, cost and timings), so the comparisons are already at the top level.
        cost = res.get("cost") or {}
        pt = cost.get("prompt_tokens", 0)
        ct = cost.get("completion_tokens", 0)
        usd = _usd(model, pt, ct)
        comps = res.get("comparisons") or []

        entries.append({
            "claim_id": claim["id"],
            "claim_name": claim.get("name", ""),
            "claim_text": claim.get("claim_text", ""),
            "claim_realization": res.get("claim_realization") or claim.get("realization") or [],
            "candidates_examined": len(comps),
            "comparisons": comps,
            "submission_basis": res.get("submission_basis") or {},
            "run_log": res.get("run_log") or {},
            "evidence_sufficient": res.get("evidence_sufficient"),
            "review_complete": res.get("review_complete"),
            "unresolved_count": res.get("unresolved_count"),
            "unresolved_papers": res.get("unresolved_papers") or [],
            "timings": res.get("timings") or {},
            # Reported per claim, not only in total: the agent's extra calls are spent on
            # particular papers, and an average over claims hides which.
            "run_cost": {"prompt_tokens": pt, "completion_tokens": ct,
                         "usd": round(usd, 4), "seconds": secs},
            "stop_reason": res.get("stop_reason", ""),
        })
        per_claim_b.append({
            "claim_id": claim["id"],
            "claim_name": claim.get("name", ""),
            # The run's own deterministic verdict (`agent_verdict`), which both systems
            # derive from the ledger by the same rule. The prose rationale stays empty:
            # the claim-level synthesis is a separate pipeline step, and generating one
            # per variant here would add a second difference to the comparison. The
            # exporter's own deterministic claim conclusion covers both alike.
            "verdict": res.get("agent_verdict"),
            "rationale": res.get("agent_rationale", "") or "",
            "challenging_papers": [],
        })
        costs.append((claim["id"], usd, secs, len(comps)))
        print(f"  [{variant}] {claim['id']}: {len(comps)} comparisons, "
              f"${usd:.4f}, {secs}s", flush=True)

    a = {
        "submission_id": sid,
        "variant": variant,
        "control_flow": getattr(cls, "control_flow", "agentic_loop"),
        "agentic": variant == "agent",
        "closest_n": closest_n,
        "model": model,
        # The retrieval snapshot both variants were handed, read from the file rather than
        # from either run -- so an unequal pool would show up here instead of hiding.
        "n_related_pool": _pool_size(sub),
        "claims": entries,
        "run_cost_total": {
            "usd": round(sum(c[1] for c in costs), 4),
            "seconds": round(sum(c[2] for c in costs), 1),
        },
    }
    b = {
        "submission_id": sid,
        "variant": variant,
        "generated_from": f"{a['control_flow']} run ({model})",
        "per_claim": per_claim_b,
        "overall_assessment": "",
    }
    (sub / f"{sid}_artifact_a_{variant}.json").write_text(
        json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    (sub / f"{sid}_artifact_b_{variant}.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    return a


def _degree_counts(art: dict) -> dict:
    out = {}
    for e in art["claims"]:
        for c in e["comparisons"]:
            deg = (c.get("overlap_degree") or "").lower() or "-"
            out[deg] = out.get(deg, 0) + 1
    return out


def _status_counts(art: dict) -> dict:
    out = {}
    for e in art["claims"]:
        for c in e["comparisons"]:
            st = ((c.get("evidence_check") or {}).get("status") or "").lower() or "no check"
            out[st] = out.get(st, 0) + 1
    return out


def main():
    ap = argparse.ArgumentParser(description="Pilot: agent vs. linear baseline")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--variant", default="both", choices=(*VARIANTS, "both"))
    ap.add_argument("--claims", default="", help="comma-separated claim ids (default: all)")
    ap.add_argument("--model", default="gpt-5.6-luna")
    ap.add_argument("--closest-n", type=int, default=10)
    ap.add_argument("--max-retrievals", type=int, default=1)
    ap.add_argument("--workers", type=int, default=None,
                    help="concurrent papers; decision flow is unaffected either way")
    args = ap.parse_args()

    sub = Path(args.data_dir) / args.submission
    claims_doc = json.loads(
        (sub / f"{args.submission}_claims.json").read_text(encoding="utf-8"))
    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    if args.claims:
        want = {x.strip() for x in args.claims.split(",") if x.strip()}
        claims = [c for c in claims if c["id"] in want]
    if not claims:
        raise SystemExit("no claims selected")

    # One model and one effort per role for both variants, set before either runs.
    for var in ROLE_MODEL_VARS:
        os.environ.setdefault(var, args.model)
    for var, eff in ROLE_EFFORT.items():
        os.environ.setdefault(var, eff)
    print(f"config: model={args.model}, roles="
          + ", ".join(f"{v.split('_')[1].lower()}={os.environ[v]}" for v in ROLE_MODEL_VARS)
          + f", effort={os.environ['NOVELTY_READING_EFFORT']}/"
            f"{os.environ['NOVELTY_COMPARE_EFFORT']}/{os.environ['NOVELTY_EVIDENCE_EFFORT']}"
          + f", no_triage={os.environ['NOVELTY_NO_TRIAGE']}, "
            f"paper_loop={os.environ['NOVELTY_PAPER_LOOP']}, pool={_pool_size(sub)}")

    variants = VARIANTS if args.variant == "both" else (args.variant,)
    results = {}
    for v in variants:
        print(f"\n=== {v} ===", flush=True)
        results[v] = run_variant(args.data_dir, args.submission, v, claims, args.model,
                                 args.closest_n, args.max_retrievals, args.workers)

    print("\n=== summary ===")
    for v, art in results.items():
        tot = art["run_cost_total"]
        print(f"{v:>7}: ${tot['usd']:.4f}, {tot['seconds']}s, "
              f"degrees={_degree_counts(art)}, evidence={_status_counts(art)}")


if __name__ == "__main__":
    main()

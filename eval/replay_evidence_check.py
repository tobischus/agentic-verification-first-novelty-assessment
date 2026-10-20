#!/usr/bin/env python3
"""Small development replay of the EXISTING evidence checker; no agent run.

Place at eval/replay_evidence_check.py in the repository. Preparation is offline:
  python eval/replay_evidence_check.py --artifact data/ID/ID_artifact_a.json --out-dir eval/out/evidence_pilot
Inspect cases.json and record human expectations before requesting new judgments:
  python eval/replay_evidence_check.py --run eval/out/evidence_pilot/cases.json

Six cases by default, two calls per case, zero automatic retries. Both arms use
the same stored claim, original comparison proposal, pairs, model and effort.
Only the evidence-check prompt differs. No original artifacts are changed.
This is a development diagnostic, not a final evaluation or an exact replay of
the historical model request. It reuses the current local checker and schema.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time


PAIR_RULE = """INDEPENDENT PAIR SELECTION
Decide separately for each pair whether its two passages establish the
specific shared contribution asserted for that pair. A valid overall overlap
does not make every accompanying pair a valid material correspondence.
Do not fill missing evidence from the pair's rationale or the comparison's
assertions. Generic expected system behavior, routine validation, or naming
a model/task is insufficient unless the passages establish a concrete shared
contribution relevant to the current claim. Such a contribution may be a
meaningful component; it need not reproduce the entire central contribution.
Include an index in supporting_pair_indices only on that pair's own evidence.
Other independently valid pairs can still support the overall decision.

"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(args):
    rng = random.Random(args.seed)
    pools, sources = [], []
    for path in args.artifact:
        raw = path.read_bytes()
        doc = json.loads(raw)
        sources.append({"path": str(path.resolve()), "sha256": digest(raw)})
        strata = {"material": [], "nonmaterial": [], "other": []}
        for entry in doc.get("claims", []):
            log = entry.get("run_log") or {}
            role = (log.get("config", {}).get("roles", {}).get("evidence") or {})
            model = args.model or role.get("model") or doc.get("model")
            effort = role.get("reasoning_effort") or "low"
            for c in entry.get("comparisons", []) or []:
                if not c.get("evidence_pairs"):
                    continue
                proposal = c.get("comparison_proposal")
                if not proposal:
                    # Without the pre-check proposal, reconstructing it from the final
                    # degree could test a different hypothesis. Skip rather than guess.
                    continue
                if not model:
                    raise SystemExit(f"No recorded model in {path}; specify --model.")
                status = (c.get("evidence_check") or {}).get("status")
                bucket = status if status in ("material", "nonmaterial") else "other"
                strata[bucket].append({
                    "submission_id": doc.get("submission_id"),
                    "claim_id": entry.get("claim_id"),
                    "paper_id": c.get("paper_id"), "title": c.get("title"),
                    "claim": entry.get("claim_text") or entry.get("claim_name") or "",
                    "comparison": proposal, "pairs": c["evidence_pairs"],
                    "model": model, "reasoning_effort": effort,
                    "source_sha256": digest(raw), "run_id": log.get("run_id"),
                })
        for pool in strata.values():
            rng.shuffle(pool)
        pools.append(strata)
    # Balance existing check-status strata AND artifacts, without selecting based
    # on the new candidate's outcomes. These are development cases, not test data.
    pools = [groups[bucket] for bucket in ("material", "nonmaterial", "other")
             for groups in pools]
    selected = []
    while len(selected) < args.limit and any(pools):
        for pool in pools:
            if pool and len(selected) < args.limit:
                selected.append(pool.pop())
    if not selected:
        raise SystemExit("No comparisons with stored original proposal and evidence pairs found.")
    for i, case in enumerate(selected, 1):
        case["case_id"] = f"C{i:02d}"
    output = args.out_dir / "cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"purpose": "development diagnostic", "seed": args.seed,
                "sources": sources, "candidate_rule": PAIR_RULE, "cases": selected}
    with output.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    for c in selected:
        print(f"{c['case_id']}: {c['submission_id']} / {c['claim_id']} / {c['title']} "
              f"({len(c['pairs'])} pairs; {c['model']}, {c['reasoning_effort']})")
    print(f"\nPrepared {output}; maximum {2 * len(selected)} model calls if run.")
    print("No model calls made. Before running, inspect the pairs and record expected supporting indices.")


def run(args):
    raw = args.run.read_bytes()
    manifest = json.loads(raw)
    cases = manifest["cases"]
    if not 1 <= len(cases) <= 12:
        raise SystemExit("This diagnostic is limited to 1–12 cases.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY as for your existing pipeline.")
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo / "src" / "novelty_assessment"))
    from agent import evidence_map
    from langchain_openai import ChatOpenAI

    baseline = evidence_map.EVIDENCE_CHECK_PROMPT
    anchor = "3. SUPPORT FOR THE PROPOSED RATIONALE"
    if baseline.count(anchor) != 1:
        raise SystemExit("Current prompt differs from the supplied code; expected insertion anchor missing.")
    candidate = baseline.replace(anchor, manifest["candidate_rule"] + anchor, 1)
    prompts = {"baseline": baseline, "candidate": candidate}
    output = args.run.with_name("results.jsonl")
    # Exclusive creation prevents accidentally paying for the same experiment twice.
    with output.open("x", encoding="utf-8", newline="\n") as f:
        metadata = {"type": "metadata", "cases_sha256": digest(raw),
                    "prompts": prompts,
                    "prompt_hashes": {k: digest(v.encode()) for k, v in prompts.items()},
                    "max_calls": len(cases) * 2, "max_retries": 0}
        f.write(json.dumps(metadata, ensure_ascii=False) + "\n"); f.flush()
        clients = {}
        try:
            for n, case in enumerate(cases):
                # Alternate which prompt goes first; keep all other settings fixed.
                arms = ("baseline", "candidate") if n % 2 == 0 else ("candidate", "baseline")
                model, effort = case["model"], case["reasoning_effort"]
                key = (model, effort)
                if key not in clients:
                    kw = ({"reasoning_effort": effort}
                          if model.startswith(("gpt-5", "o1", "o3", "o4"))
                          else {"temperature": 0.0})
                    clients[key] = ChatOpenAI(model_name=model, api_key=os.environ["OPENAI_API_KEY"],
                                               max_retries=0, timeout=90, **kw)
                for arm in arms:
                    usage, parse_errors = [], []
                    def struct_call(schema, prompt):
                        response = clients[key].with_structured_output(schema, include_raw=True).invoke(prompt)
                        message = response.get("raw")
                        usage.append({"usage_metadata": getattr(message, "usage_metadata", None),
                                      "token_usage": (getattr(message, "response_metadata", {}) or {}).get("token_usage")})
                        if response.get("parsing_error") or response.get("parsed") is None:
                            parse_errors.append(str(response.get("parsing_error") or "No parsed response"))
                        return response.get("parsed")
                    evidence_map.EVIDENCE_CHECK_PROMPT = prompts[arm]
                    started = time.monotonic()
                    record = {"type": "result", "case_id": case["case_id"], "arm": arm,
                              "model": model, "reasoning_effort": effort}
                    try:
                        record["check"] = evidence_map.check_evidence(
                            struct_call, case["claim"], {"pairs": case["pairs"]},
                            comparison=case["comparison"])
                        record["parse_errors"] = parse_errors
                    except Exception as exc:
                        record["error_type"] = type(exc).__name__
                        record["seconds"] = round(time.monotonic() - started, 2)
                        record["usage"] = usage
                        f.write(json.dumps(record, ensure_ascii=False) + "\n"); f.flush()
                        raise SystemExit(f"Stopped on {type(exc).__name__}; partial results saved. No automatic retry.")
                    record["usage"] = usage
                    record["seconds"] = round(time.monotonic() - started, 2)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n"); f.flush()
                    check = record["check"]
                    print(f"{case['case_id']} {arm}: {check.get('status')} | "
                          f"supporting pairs {check.get('supporting_pair_indices')} | "
                          f"degree supported {check.get('proposed_degree_supported')}" +
                          (" | PARSE ERROR: exclude from quality comparison" if parse_errors else ""))
        finally:
            evidence_map.EVIDENCE_CHECK_PROMPT = baseline
    print(f"Saved {output}. Original artifacts and production prompt unchanged.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--artifact", type=Path, nargs="+")
    mode.add_argument("--run", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("eval/out/evidence_pilot"))
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model", help="Preparation only: override the model for BOTH arms.")
    args = ap.parse_args()
    if not 1 <= args.limit <= 12:
        ap.error("--limit must be between 1 and 12")
    if args.run:
        run(args)
    else:
        prepare(args)


if __name__ == "__main__":
    main()

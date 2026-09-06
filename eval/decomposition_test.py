#!/usr/bin/env python3
"""
Does splitting a claim into atomic elements produce a better comparison than one scalar?

The experiment holds the evidence constant and changes only the question. For every paper
an existing run deep-dived, the SAME sections that run read are read again -- recorded in
`sections_used` -- and the element-wise question is put to the same model. Any difference
in what comes out is therefore attributable to the decomposition, not to reading more.

What is compared, judge-free:

  grounding    share of overlap assertions carrying a verbatim span verified against its
               own document. Today an assertion is the scalar `overlap_degree`; under the
               decomposition it is a filled cell.
  two-sided    share of those that pair a verified span of the SUBMISSION with a verified
               span of the PAPER. This is the claim-evidence map the thesis argues for, and
               the scalar cannot have it at all.
  specificity  whether the output can name WHICH part of the contribution is taken.
  agreement    where the derived degree and the run's asserted degree differ, so the cases
               worth reading by hand are listed rather than averaged away.

Usage
-----
  python eval/decomposition_test.py --submission graphrag_when_to_use
  python eval/decomposition_test.py --submission ID --claim claim_2 --model gpt-5-mini
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

OVERLAP = ("same", "substantial", "partial")


def _verified_pairs(comp: dict) -> int:
    return sum(1 for p in (comp.get("evidence_pairs") or [])
               if p.get("claim_quote_verified") and p.get("paper_quote_verified"))


def _verified_quotes(comp: dict) -> int:
    return sum(1 for s in (comp.get("paper_realization") or [])
               if s.get("kind") == "quote" and s.get("verified"))


def run(data_dir: str, sid: str, only_claim: str, model: str, out_path: str) -> dict:
    from agent import elements as el
    from agent.claim_agent import ClaimNoveltyAgent, _fmt_sections_full
    from agent.tools import ClaimToolbox

    sub = Path(data_dir) / sid
    art = json.loads((sub / f"{sid}_artifact_a.json").read_text(encoding="utf-8"))
    claims_doc = json.loads((sub / f"{sid}_claims.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in claims_doc.get("claims", [])}

    agent = ClaimNoveltyAgent(data_dir, sid, model_name=model)
    # agent._struct returns (parsed, prompt_tokens, completion_tokens); the elements module
    # wants only the parsed object, so unwrap here and keep the token count for the report.
    spend = {"pt": 0, "ct": 0, "calls": 0}

    def struct(schema, prompt):
        parsed, pt, ct = agent._struct(schema, prompt)
        spend["pt"] += pt; spend["ct"] += ct; spend["calls"] += 1
        return parsed

    report, t0 = [], time.perf_counter()

    for entry in art.get("claims", []):
        cid = entry.get("claim_id")
        if only_claim and cid != only_claim:
            continue
        claim = by_id.get(cid)
        if claim is None:
            continue
        tb = ClaimToolbox(data_dir, sid, claim, agent.embedder)
        claim_str = agent._claim_str(claim)
        # the realization's quote segments are already verified against the submission,
        # so they are exactly the passages an element may be anchored to
        passages = [s["content"] for s in (entry.get("claim_realization") or [])
                    if s.get("kind") == "quote" and s.get("verified")]

        elems = el.decompose(struct, claim_str, passages)
        n_core = sum(1 for e in elems if e["core"])
        print(f"\n=== {cid}: {len(elems)} elements ({n_core} core) ===")
        for i, e in enumerate(elems, 1):
            print(f"  E{i} [{e['kind']:8}{'core' if e['core'] else '    '}] {e['text'][:78]}")
        if not elems:
            print("  decomposition produced nothing verifiable -- skipping this claim")
            continue

        # only papers the run actually read: same evidence, different question
        deep = [c for c in entry.get("comparisons", []) if c.get("sections_used")]
        print(f"  re-examining {len(deep)} papers the run deep-dived\n")
        papers = []
        for c in deep:
            pid = c["paper_id"]
            tb.ensure_fulltext(pid)
            got = tb.read_sections(pid, c["sections_used"])
            sections_text = _fmt_sections_full(got.get("sections") or [])
            if not sections_text.strip():
                continue
            cov = el.cover(struct, claim_str, elems, c.get("title", ""),
                           sections_text, tb._paper_source_text(pid))
            cells = cov["cells"]
            score = el.coverage_score(elems, cells)
            derived = el.degree_from_coverage(score, n_core)
            asserted = (c.get("overlap_degree") or "").lower()
            filled = [x for x in cells if x["status"] in ("disclosed", "partial")]
            marks = " ".join({"disclosed": "V", "partial": "~", "absent": "-",
                              "unsupported": "!"}[x["status"]] for x in cells)
            print(f"  [{marks}] cov={score if score is None else round(score, 2)} "
                  f"{asserted:12}->{derived:12} {c.get('title', '')[:44]}")
            papers.append({
                "paper_id": pid, "title": c.get("title"), "cells": cells,
                "coverage": score, "derived_degree": derived, "asserted_degree": asserted,
                "relevance": cov["relevance"],
                "filled_cells": len(filled),
                "cells_with_quote": sum(1 for x in filled if x["quote_verified"]),
                "run_verified_pairs": _verified_pairs(c),
                "run_verified_quotes": _verified_quotes(c),
            })
        report.append({"claim_id": cid, "elements": elems, "n_core": n_core, "papers": papers})

    _report(report, time.perf_counter() - t0, spend)
    payload = {"submission_id": sid, "model": model, "spend": spend, "claims": report}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {out_path}")
    return payload


def _report(report, seconds, spend=None):
    papers = [p for c in report for p in c["papers"]]
    if not papers:
        print("\nnothing to report")
        return
    filled = sum(p["filled_cells"] for p in papers)
    with_q = sum(p["cells_with_quote"] for p in papers)

    # The run's side: an overlap assertion is a comparison whose degree says it overlaps.
    run_overlaps = [p for p in papers if p["asserted_degree"] in OVERLAP]
    run_paired = sum(1 for p in run_overlaps if p["run_verified_pairs"] > 0)
    run_quoted = sum(1 for p in run_overlaps if p["run_verified_quotes"] > 0)

    print("\n" + "=" * 78)
    print("DECOMPOSITION vs SCALAR -- same papers, same sections, same model")
    print("=" * 78)
    print(f"papers compared              : {len(papers)}")
    print()
    print("THE RUN (one degree per paper)")
    print(f"  overlap assertions         : {len(run_overlaps)}")
    print(f"    with any verified quote  : {run_quoted}")
    print(f"    with a two-sided pair    : {run_paired}")
    print()
    print("THE DECOMPOSITION (one cell per element per paper)")
    print(f"  filled cells (disclosed/partial): {filled}")
    print(f"    with a verified quote         : {with_q}"
          f"  ({100 * with_q / filled:.0f}%)" if filled else "")
    print(f"  every filled cell also carries its element's verified submission span,")
    print(f"  so each is a two-sided pair by construction.")
    print()
    disagree = [p for p in papers if p["derived_degree"] != p["asserted_degree"]]
    print(f"derived degree differs from the run's on {len(disagree)} of {len(papers)}:")
    for p in disagree[:14]:
        print(f"  {p['asserted_degree']:12} -> {p['derived_degree']:12} "
              f"cov={p['coverage'] if p['coverage'] is None else round(p['coverage'], 2)}  "
              f"{(p['title'] or '')[:46]}")
    print(f"\nwall clock: {seconds / 60:.1f} min")


def main():
    ap = argparse.ArgumentParser(description="Element-wise comparison vs the scalar")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--claim", default="")
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)
    out = args.out or f"eval/out/decomposition_{args.submission}.json"
    run(args.data_dir, args.submission, args.claim, args.model, out)


if __name__ == "__main__":
    main()

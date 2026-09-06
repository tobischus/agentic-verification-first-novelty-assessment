#!/usr/bin/env python3
"""
The evidence-sufficiency gate, as a measurement only -- it changes nothing.

Section 2.4 of the thesis names one property that no reviewed system has: a failed
evidence check that triggers renewed retrieval. Building that loop is a large change, so
this runs the check alone, over artifacts that already exist on disk, to answer the
question that has to come first: how often would the gate actually fail, and on what?

`gate()` is deliberately a pure function of one Artifact-A claim entry. Nothing here reads
files, calls a model, or mutates state, so if the loop is worth building the same function
can move into the agent unchanged -- and until then it cannot affect a single run.

What it checks, and why each deficit is one a next action could actually close:

  ungrounded_challenge  A paper drives the "challenged" verdict but carries no quote pair
                        verified on both sides. The verdict rests on an assertion, which is
                        precisely what Section 2.3 rules out.
  closest_not_read      A paper among the closest by similarity plausibly overlaps but was
                        only triaged from its abstract. The comparison was never made.
  fulltext_missing      A plausibly overlapping paper was compared without its full text.
                        Resolvable by fetching the PDF, so it is a deficit, not a fact.
  absence_from_abstracts_only
                        The claim was found unchallenged, but not one of its closest papers
                        was read beyond its abstract. The finding then rests entirely on
                        triage.

A first version of this gate demanded a verified quote pair from EVERY claim, and failed
63% of them. That was miscalibrated, and the measurement is what exposed it: a claim that
genuinely has no overlapping prior work cannot produce a quote pair, because there is
nothing to quote. What has to be grounded differs by verdict -- an assertion of overlap
needs evidence of overlap, whereas an assertion of absence needs evidence that the search
was adequate. The two deficits above are those two demands.

Deliberately NOT a deficit: a paper judged clearly distinct from its abstract. Reading it
in full would spend budget to confirm a negative, and the gate is meant to name work worth
doing, not work that could be done.

Usage
-----
  python eval/evidence_gate.py
  python eval/evidence_gate.py --variant linear --detail
  python eval/evidence_gate.py --submission transducing_language_models --detail
"""
import argparse
import glob
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

# Mirrors agent/tools.py: depths at which a paper counts as actually read.
SUFFICIENT_DEPTHS = {"abstract_intro", "fulltext_unavailable", "targeted_sections",
                     "fulltext_available_targeted_read"}
# Degrees at which a paper is close enough that leaving it unread is a gap.
PLAUSIBLE = ("partial", "substantial", "same")
# Degrees that make a claim "challenged" even without a refutation (agent's Fix A).
STRONG = ("substantial", "same")


def _verified_pairs(comparison: dict) -> List[dict]:
    return [p for p in (comparison.get("evidence_pairs") or [])
            if p.get("claim_quote_verified") and p.get("paper_quote_verified")]


def _degree(c: dict) -> str:
    return (c.get("overlap_degree") or "").lower()


def _challenges(c: dict) -> bool:
    return c.get("refutation_status") == "can_refute"


def claim_verdict(entry: dict) -> str:
    """The verdict recorded for this claim, however the builder spelled it."""
    return entry.get("agent_verdict") or ("challenged" if entry.get("can_refute_count")
                                          else "not_challenged")


def gate(entry: dict, closest_n: int = 10) -> dict:
    """Is this claim's evidence sufficient, and if not, what exactly is missing?

    Returns {"sufficient": bool, "deficits": [{kind, paper, detail, next_action}, ...]}.
    Each deficit names a paper, because an action that cannot be aimed at a document is a
    blind retry rather than a next step.
    """
    comps = entry.get("comparisons") or []
    verdict = claim_verdict(entry)
    deficits = []

    # 1. anything that drives "challenged" must carry a two-sided verified pair
    for c in comps:
        if _challenges(c) or _degree(c) in STRONG:
            if not _verified_pairs(c):
                deficits.append({
                    "kind": "ungrounded_challenge",
                    "paper": c.get("title", ""),
                    "detail": f"status={c.get('refutation_status')}, overlap={_degree(c)}, "
                              f"no quote pair verified on both sides",
                    "next_action": "re-read this paper for a passage that supports the "
                                   "overlap, or withdraw it",
                })

    # 2/3. the closest papers: plausibly overlapping but never read at depth, or read
    # without their full text. Ranked by similarity when the artifact records it.
    ranked = [c for c in comps if c.get("similarity") is not None]
    ranked.sort(key=lambda c: c.get("similarity") or 0.0, reverse=True)
    for c in ranked[:closest_n]:
        if _degree(c) not in PLAUSIBLE:
            continue
        depth = c.get("depth")
        if depth is not None and depth not in SUFFICIENT_DEPTHS:
            deficits.append({
                "kind": "closest_not_read",
                "paper": c.get("title", ""),
                "detail": f"overlap={_degree(c)} but examined at depth={depth}",
                "next_action": "deep-dive this paper",
            })
        elif (c.get("content_source") or "").startswith("abstract") or \
                depth == "fulltext_unavailable":
            deficits.append({
                "kind": "fulltext_missing",
                "paper": c.get("title", ""),
                "detail": f"overlap={_degree(c)} but compared against "
                          f"{c.get('content_source') or depth}",
                "next_action": "fetch and parse this paper's full text, then compare again",
            })

    # 4. what an unchallenged claim owes: evidence that the search was adequate, not a
    # quote pair it could not possibly have.
    if verdict == "not_challenged":
        read_deeper = [c for c in ranked[:closest_n]
                       if c.get("depth") in SUFFICIENT_DEPTHS
                       or not (c.get("content_source") or "").startswith("abstract")]
        if ranked and not read_deeper:
            deficits.append({
                "kind": "absence_from_abstracts_only",
                "paper": "",
                "detail": f"none of the {min(closest_n, len(ranked))} closest papers was "
                          f"read beyond its abstract",
                "next_action": "deep-dive the closest papers before concluding absence",
            })
    elif not any(_verified_pairs(c) for c in comps):
        deficits.append({
            "kind": "verdict_without_evidence",
            "paper": "",
            "detail": f"verdict={verdict} but not one verified quote pair among "
                      f"{len(comps)} papers compared",
            "next_action": "ground the verdict or widen retrieval",
        })

    return {"sufficient": not deficits, "deficits": deficits}


# ------------------------------- reporting -------------------------------- #

def _entries(data_dir: Path, variant: str, only: str = ""):
    tail = f"_{variant}" if variant else ""
    for f in sorted(glob.glob(str(data_dir / "*" / f"*_artifact_a{tail}.json"))):
        sid = Path(f).parent.name
        if only and sid != only:
            continue
        try:
            a = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in a.get("claims", []):
            yield sid, e


def _is_agentic(entry: dict) -> bool:
    """Written by the agent, not by the one-pass builder (which records no verdict)."""
    return "agent_verdict" in entry


def run(data_dir: Path, variant: str, only: str, closest_n: int, detail: bool,
        agentic_only: bool = True) -> None:
    kinds = Counter()
    verdict_by_suff = Counter()
    n = n_insufficient = 0
    claims_with_kind: Dict[str, set] = {}
    per_submission = Counter()

    for sid, e in _entries(data_dir, variant, only):
        if agentic_only and not _is_agentic(e):
            continue
        n += 1
        g = gate(e, closest_n)
        verdict = claim_verdict(e)
        verdict_by_suff[(verdict, g["sufficient"])] += 1
        if not g["sufficient"]:
            n_insufficient += 1
            per_submission[sid] += 1
            for d in g["deficits"]:
                kinds[d["kind"]] += 1
                claims_with_kind.setdefault(d["kind"], set()).add((sid, e.get("claim_id")))
        if detail:
            mark = "OK  " if g["sufficient"] else "FAIL"
            print(f"\n[{mark}] {sid} / {e.get('claim_id')}  verdict={verdict}")
            for d in g["deficits"]:
                paper = f' "{d["paper"][:60]}"' if d["paper"] else ""
                print(f"    - {d['kind']}{paper}")
                print(f"        {d['detail']}")
                print(f"        -> {d['next_action']}")

    label = variant or "agentic"
    print("\n" + "=" * 78)
    print(f"EVIDENCE GATE, measured only ({label} artifacts, closest_n={closest_n})")
    print("=" * 78)
    if not n:
        print("no artifacts found")
        return
    print(f"claims examined      : {n}")
    print(f"gate would FAIL on   : {n_insufficient}  ({100 * n_insufficient / n:.0f}%)")
    print("\ndeficits (a claim can carry several, and several of one kind):")
    for kind, count in kinds.most_common():
        print(f"  {kind:22} {count:5} occurrences   in {len(claims_with_kind[kind]):3} claims")
    print("\nverdict x sufficiency:")
    for (verdict, suff), count in sorted(verdict_by_suff.items()):
        print(f"  {verdict:16} {'sufficient' if suff else 'INSUFFICIENT':13} {count:4}")
    worst = per_submission.most_common(5)
    if worst and not only:
        print("\nsubmissions with the most failing claims:")
        for sid, c in worst:
            print(f"  {c:3}  {sid}")
    print("\nNothing was changed. This is a measurement of artifacts already on disk.")


def main():
    ap = argparse.ArgumentParser(description="Measure the evidence gate (changes nothing)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--variant", default="", help="'' for the agent, 'linear' for the baseline")
    ap.add_argument("--submission", default="", help="restrict to one submission id")
    ap.add_argument("--closest-n", type=int, default=10)
    ap.add_argument("--detail", action="store_true", help="print every claim and deficit")
    ap.add_argument("--all-entries", action="store_true",
                    help="include claims written by the one-pass builder, not only the agent's")
    args = ap.parse_args()
    run(Path(args.data_dir), args.variant, args.submission, args.closest_n, args.detail,
        agentic_only=not args.all_entries)


if __name__ == "__main__":
    main()

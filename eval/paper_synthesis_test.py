#!/usr/bin/env python3
"""The three properties of the paper-level summary that must hold without a model.

The summary itself is written by a model, so it cannot be asserted. What CAN be asserted is
everything around it -- and each of these is a way the step could quietly mislead a reader:

  1. A proposed `substantial` whose evidence check did not support it must never reach the
     model inside the supported group. The prompt also says so, but a prompt is a request;
     the split in the context is the actual guarantee.
  2. Staleness must trip when, and only when, a claim result the summary rests on changes.
     A check that never fires is decoration; one that always fires gets ignored.
  3. The R# ids the summary cites must be the ids the report prints. A summary pointing at
     R7 while the table's R7 is a different paper is worse than one citing nothing.

Pure functions over synthetic and on-disk artifacts. No model call, no network, no cost.

    python eval/paper_synthesis_test.py [--data-dir data]
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

import battle_export  # noqa: E402
import paper_synthesis as ps  # noqa: E402
import source_refs  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def _comparison(pid, title, degree, status, degree_supported=True):
    """A stored comparison, shaped the way check_evidence actually writes one.

    `proposed_degree_supported` is not optional in real data: for an overlap degree the
    check normalises it to a strict boolean, and only none/superficial leave it null.
    A fixture that omitted it made `material` look like confirmation, which is precisely
    the conflation these tests exist to catch."""
    c = {"paper_id": pid, "title": title, "overlap_degree": degree,
         "what_is_shared": f"shared-{pid}", "submission_delta": f"delta-{pid}",
         "assessment": f"argument-{pid}"}
    if status:
        overlap = degree in ("same", "substantial", "partial")
        c["evidence_check"] = {
            "status": status, "supporting_pair_indices": [1, 2],
            "proposed_degree_supported": (
                bool(degree_supported and status == "material") if overlap else None),
        }
    return c


def _sections(findings):
    """{heading: body} for the findings document, so each group can be inspected alone."""
    parts = re.split(r"^## ", findings, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts}


# --- 1. supported and merely proposed are separated -------------------------------
a = {"claims": [{"claim_id": "c1", "claim_name": "n1", "claim_text": "t1", "comparisons": [
    _comparison("p_supported", "Supported paper", "substantial", "material"),
    _comparison("p_proposed", "Proposed paper", "substantial", "insufficient"),
    _comparison("p_refuted", "Refuted paper", "same", "nonmaterial"),
    _comparison("p_minor", "Minor paper", "partial", "material"),
]}]}
b = {"per_claim": [{"claim_id": "c1", "verdict": "challenged", "rationale": "because"}]}
refs = source_refs.refs_for(a, ["c1"])
sec = _sections(ps.build_findings(a, b, ["c1"], {"c1": "n1"}, refs))

supported = sec["SUBSTANTIAL-OR-STRONGER OVERLAP, SUPPORTED BY THE EVIDENCE CHECK"]
proposed = sec["SUBSTANTIAL-OR-STRONGER OVERLAP, PROPOSED BUT NOT SUPPORTED BY THE "
               "EVIDENCE CHECK"]
check("a supported substantial overlap is in the supported group",
      "Supported paper" in supported and "Supported paper" not in proposed)
check("a substantial overlap with INSUFFICIENT evidence is not in the supported group",
      "Proposed paper" not in supported and "Proposed paper" in proposed)
check("a `same` degree with NONMATERIAL evidence is not in the supported group",
      "Refuted paper" not in supported and "Refuted paper" in proposed)
check("a partial overlap is in neither strong group",
      "Minor paper" not in supported and "Minor paper" not in proposed)
# The case that put a declined comparison into a summary as established overlap: the
# check found a shared element (material) but explicitly did not confirm the proposed
# degree. It is not supported, and it is not absent either.
_unconf = _sections(ps.build_findings(
    {"claims": [{"claim_id": "c1", "claim_name": "n", "claim_text": "t", "comparisons": [
        _comparison("p_unconf", "Unconfirmed paper", "substantial", "material",
                    degree_supported=False)]}]},
    {"per_claim": [{"claim_id": "c1", "verdict": "not_challenged", "rationale": "because"}]},
    ["c1"], {"c1": "n"}, {"p_unconf": "R1"}))
check("material evidence without a confirmed degree is NOT in the supported group",
      "Unconfirmed paper" not in
      _unconf["SUBSTANTIAL-OR-STRONGER OVERLAP, SUPPORTED BY THE EVIDENCE CHECK"])
check("material evidence without a confirmed degree is named as unconfirmed",
      "proposed degree NOT confirmed" in _unconf["OPEN CONFLICTS AND EVIDENCE GAPS"])
check("every listed comparison states its evidence status next to its degree",
      supported.count("Evidence check:") == supported.count("Assessed overlap:") == 1,
      f"{supported.count('Evidence check:')} vs {supported.count('Assessed overlap:')}")
check("the claim's recorded rationale is carried into the context",
      "Rationale: because" in sec["CLAIMS AND THEIR FINAL VERDICTS"])
check("degree/evidence conflicts are listed as decision-relevant",
      "degree and evidence check disagree" in sec["OPEN CONFLICTS AND EVIDENCE GAPS"])

# With nothing strong at all, the orientation group appears -- and only then.
weak = {"claims": [{"claim_id": "c1", "claim_name": "n1", "claim_text": "t1", "comparisons": [
    _comparison("p_a", "Weak paper", "partial", "material")]}]}
sec_weak = _sections(ps.build_findings(weak, b, ["c1"], {"c1": "n1"}, source_refs.refs_for(weak, ["c1"])))
check("with no strong overlap the strongest available comparisons are offered instead",
      "STRONGEST COMPARISONS ACTUALLY FOUND" in sec_weak
      and "Weak paper" in sec_weak["STRONGEST COMPARISONS ACTUALLY FOUND"])
check("with a strong overlap present that orientation group is omitted",
      "STRONGEST COMPARISONS ACTUALLY FOUND" not in sec)

# --- 2. staleness ------------------------------------------------------------------
findings = ps.build_findings(a, b, ["c1"], {"c1": "n1"}, refs)
summary = {"main_novelty_concern": "x", "remaining_contribution": "y",
           "inputs_fingerprint": ps.fingerprint(findings)}
check("a summary over unchanged results is not stale", not ps.is_stale(summary, findings))
check("no stored summary is never reported as stale", not ps.is_stale(None, findings))

changed = copy.deepcopy(a)
changed["claims"][0]["comparisons"][0]["evidence_check"]["status"] = "insufficient"
check("flipping a supported overlap to insufficient makes the summary stale",
      ps.is_stale(summary, ps.build_findings(changed, b, ["c1"], {"c1": "n1"}, refs)))

reworded = copy.deepcopy(a)
reworded["claims"][0]["comparisons"][0]["what_is_shared"] = "rewritten shared contribution"
check("rewriting a field the summary was given also makes it stale",
      ps.is_stale(summary, ps.build_findings(reworded, b, ["c1"], {"c1": "n1"}, refs)))

untouched = copy.deepcopy(a)
untouched["claims"][0]["comparisons"][0]["evidence_pairs"] = [{"claim_quote": "not shown"}]
check("a change the summary never saw does not raise a false alarm",
      not ps.is_stale(summary, ps.build_findings(untouched, b, ["c1"], {"c1": "n1"}, refs)),
      "evidence pairs are not part of the summary's context")

# --- 3. the ids agree with the report ----------------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("--data-dir", default="data")
args = ap.parse_args()
data_dir = Path(args.data_dir)

checked = 0
for sub in sorted(p for p in data_dir.glob("*") if p.is_dir()):
    for variant in ("agent", "linear"):
        a_file = sub / f"{sub.name}_artifact_a_{variant}.json"
        b_file = sub / f"{sub.name}_artifact_b_{variant}.json"
        if not (a_file.exists() and b_file.exists()):
            continue
        try:
            text = battle_export.build(str(data_dir), sub.name, variant=variant)
            f2, _p, b2 = ps.context_for(str(data_dir), sub.name, variant)
        except Exception as e:
            check(f"{sub.name}/{variant}: renders", False, repr(e)[:90])
            continue
        checked += 1
        in_report = dict(re.findall(r"^\| (R\d+) \| ([^|]+?) \|", text, re.M))
        in_findings = dict(re.findall(r"^- (R\d+) — (.+?) \[Claim", f2, re.M))
        mismatched = [r for r, title in in_findings.items()
                      if r in in_report and title.strip() not in in_report[r]]
        check(f"{sub.name}/{variant}: the ids in the findings are the report's ids",
              not mismatched and set(in_findings) <= set(in_report),
              f"mismatched={mismatched} unknown={sorted(set(in_findings) - set(in_report))}")
        stored = (b2 or {}).get("paper_summary")
        if stored:
            cited = set(re.findall(r"\bR\d+\b", stored.get("main_novelty_concern", "")
                                   + " " + stored.get("remaining_contribution", "")))
            check(f"{sub.name}/{variant}: every id the summary cites exists in the report",
                  cited <= set(in_report), f"unknown={sorted(cited - set(in_report))}")
            check(f"{sub.name}/{variant}: the stored summary is current",
                  not ps.is_stale(stored, f2))
            check(f"{sub.name}/{variant}: the summary is within its word budget",
                  ps.WORDS_LO <= stored.get("word_count", 0) <= ps.WORDS_HI,
                  f"{stored.get('word_count')} words")
        check(f"{sub.name}/{variant}: the export prints the summary iff one is stored",
              ("## Novelty summary" in text) == bool(stored))

print(f"\nartifact pairs checked on disk: {checked}")
print("=" * 62)
failed = [r for r in results if not r[1]]
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
for name, ok, detail in failed:
    print(f"  FAILED: {name} -- {detail}")
sys.exit(1 if failed else 0)

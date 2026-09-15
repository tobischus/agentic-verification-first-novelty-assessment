"""E2: turn an admin export ZIP into win/tie/loss tallies, human-human agreement, and
(optionally) human-vs-E1-judge agreement. Reads ONLY `ratings.jsonl` from the export
(each line already carries system_a/system_b/orientation resolved server-side -- see
routers/admin.py's `_build_export`); this module never touches the live database.

Verified against Krippendorff's own textbook example before being wired into the CLI --
see the comment at the top of evaluation/e2/stats.py's test in tests/test_e2_stats.py.

Usage
-----
  python -m final_evaluation.cli analyze-human --input final_evaluation/results/pilot/export.zip
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .stats import bootstrap_ci, exact_agreement, krippendorff_alpha_nominal

CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
           "conclusion_warrant", "reviewer_usefulness")


def _load_ratings(input_path: str) -> list[dict]:
    p = Path(input_path)
    if p.suffix == ".zip":
        with zipfile.ZipFile(p) as z:
            raw = z.read("ratings.jsonl").decode("utf-8")
    else:
        raw = p.read_text(encoding="utf-8")
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def _pair_type(rec: dict) -> str:
    return "::".join(sorted((rec["system_a"], rec["system_b"])))


def _winner_system(criterion_val: dict, rec: dict) -> Optional[str]:
    w = (criterion_val or {}).get("winner")
    if w == "A":
        return rec["system_a"]
    if w == "B":
        return rec["system_b"]
    if w == "tie":
        return "tie"
    return None  # unclear or missing -> not a preference


def run(input_path: str, include_test: bool = False) -> dict:
    """`include_test`: the pilot's two raters are deliberately TEST participants
    (`is_test=True`), so analysing the pilot at all requires passing True -- the CLI's
    `--include-test` flag. The default stays False so a main-study analysis can never
    quietly mix a leftover test account's answers into real results."""
    all_records = _load_ratings(input_path)
    records = [r for r in all_records
              if r.get("status") == "submitted" and not r.get("is_practice")
              and (include_test or not r.get("is_test_participant"))]
    excluded_test = 0 if include_test else sum(
        1 for r in all_records if r.get("is_test_participant"))

    # tallies[criterion][pair_type] -> Counter-ish dict over {sysA_wins, sysB_wins, tie, unclear}
    # kept as named systems, not "A"/"B", labelled per-cell below.
    tallies = defaultdict(lambda: defaultdict(lambda: {"wins": defaultdict(int), "tie": 0,
                                                       "unclear": 0, "n": 0}))
    per_paper_tallies = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {"wins": defaultdict(int), "tie": 0, "unclear": 0, "n": 0})))

    # For agreement: unit_id -> {criterion: {participant: category}}, scoped per pair_type
    # so alpha/agreement are computed WITHIN a comparable pair, never across different pairs.
    units_by_pair_crit = defaultdict(lambda: defaultdict(dict))  # (pair_type) -> crit -> unit -> {participant: cat}

    for rec in records:
        pt = _pair_type(rec)
        paper = rec["paper_id"]
        unit_id = rec["task_id"]
        for crit in CRITERIA:
            c = (rec.get("criteria") or {}).get(crit)
            if not c or not c.get("winner"):
                continue
            winner_sys = _winner_system(c, rec)
            cell = tallies[crit][pt]
            paper_cell = per_paper_tallies[paper][crit][pt]
            for target in (cell, paper_cell):
                target["n"] += 1
                if winner_sys is None:
                    target["unclear"] += 1
                elif winner_sys == "tie":
                    target["tie"] += 1
                else:
                    target["wins"][winner_sys] += 1
            units_by_pair_crit[pt][crit].setdefault(unit_id, {})[rec["participant_code"]] = winner_sys

    # Human-human agreement + Krippendorff's alpha, per criterion per pair_type.
    agreement = {}
    for pt, by_crit in units_by_pair_crit.items():
        agreement[pt] = {}
        for crit, units in by_crit.items():
            exact = exact_agreement(units)
            alpha_res = krippendorff_alpha_nominal(units)
            agreement[pt][crit] = {
                "exact_agreement": exact,
                "krippendorff_alpha_nominal": {
                    "alpha": alpha_res.alpha, "n_pairable_values": alpha_res.n_pairable_values,
                    "n_units_used": alpha_res.n_units_used, "reason": alpha_res.reason,
                },
            }

    agent_linear_pair = "agent::linear"

    def _dictify(d):
        return {k: (_dictify(v) if isinstance(v, defaultdict) else
                   (dict(v) if isinstance(v, dict) else v)) for k, v in d.items()}

    result = {
        "n_responses_analyzed": len(records),
        "n_test_participant_responses_excluded": excluded_test,
        "tallies_by_criterion_and_pair": _dictify(tallies),
        "agent_linear_pair_key": agent_linear_pair,
        "agent_linear_tallies": {crit: _dictify(tallies[crit]).get(agent_linear_pair)
                                for crit in CRITERIA if agent_linear_pair in tallies.get(crit, {})},
        "per_paper_tallies": _dictify(per_paper_tallies),
        "human_human_agreement": agreement,
        "papers_seen": sorted({r["paper_id"] for r in records}),
        "note_paper_weighting": (
            "Per-pair tallies above are counted in raw response units, not paper-averaged. "
            "Where a pair type occurs on multiple papers (only agent::linear does, in the "
            "pilot), per_paper_tallies lets you weight papers equally by hand; with 2 pilot "
            "papers an automatic equal-weight average would not add information beyond "
            "looking at both entries directly."),
    }
    return result


def compare_to_e1(human_result_path: str, e1_jsonl_path: str, human_export_path: str) -> dict:
    """Optional: compare each human judgement to the E1 judge call of the SAME task in
    the SAME orientation, but ONLY where report/submission/rubric hashes match -- an
    incompatible old pilot output is reported as `not_comparable`, never silently matched
    by task id alone (a task id is not proof the underlying text was the same run)."""
    human_records = _load_ratings(human_export_path)
    e1_calls = [json.loads(ln) for ln in Path(e1_jsonl_path).read_text(encoding="utf-8").splitlines()
               if ln.strip()]
    e1_by_key = {}
    for c in e1_calls:
        key = (c.get("paper_id"), c.get("system_a"), c.get("system_b"))
        e1_by_key[key] = c

    compared = 0
    incompatible = 0
    confusion = defaultdict(lambda: defaultdict(int))  # crit -> (human_cat, judge_cat) -> n
    coverage = defaultdict(lambda: {"comparable": 0, "not_comparable": 0})

    for rec in human_records:
        if rec.get("status") != "submitted":
            continue
        key = (rec["paper_id"], rec["system_a"], rec["system_b"])
        judge = e1_by_key.get(key) or e1_by_key.get((rec["paper_id"], rec["system_b"], rec["system_a"]))
        for crit in CRITERIA:
            c = (rec.get("criteria") or {}).get(crit)
            if not c or not c.get("winner"):
                continue
            if judge is None:
                coverage[crit]["not_comparable"] += 1
                incompatible += 1
                continue
            # Compatibility gate: report/submission/rubric hashes must match this human
            # record's own (the export does not currently carry per-task content hashes
            # inline -- see README's noted follow-up; until then this comparison is
            # marked best-effort and under-verified rather than claimed exact).
            coverage[crit]["comparable"] += 1
            compared += 1
            human_sys = _winner_system(c, rec)
            jc = ((judge.get("parsed_result") or {}).get("criteria") or {}).get(crit) or {}
            judge_winner = jc.get("winner")
            judge_sys = None
            if judge_winner == "A":
                judge_sys = judge.get("system_a")
            elif judge_winner == "B":
                judge_sys = judge.get("system_b")
            elif judge_winner == "tie":
                judge_sys = "tie"
            confusion[crit][(human_sys, judge_sys)] += 1

    return {
        "compared": compared, "not_comparable": incompatible, "coverage_by_criterion": dict(coverage),
        "confusion_by_criterion": {c: {f"{h}->{j}": n for (h, j), n in v.items()}
                                   for c, v in confusion.items()},
        "warning": "Best-effort match by (paper, system_a, system_b) only -- this pilot's "
                  "E1 calls (eval/out/pilot_v1/judge_calls.jsonl) predate this dashboard's "
                  "rendered report content_version, so per PROTOCOL.md they are "
                  "NOT COMPARABLE to dashboard_pilot_v1 human ratings. Re-run plan-e1 "
                  "--execute against the CURRENT frozen reports before trusting this output.",
    }


def print_report(result: dict) -> None:
    print(f"responses analyzed: {result['n_responses_analyzed']} "
         f"({result['n_test_participant_responses_excluded']} test-participant responses excluded "
         f"from any 'real study' framing -- included here because this IS the test pilot)")
    print(f"papers: {result['papers_seen']}")

    print("\n=== agent vs linear (highlighted) ===")
    for crit, cell in result["agent_linear_tallies"].items():
        wins = ", ".join(f"{k}={v}" for k, v in cell.get("wins", {}).items())
        print(f"  {crit}: n={cell['n']} | {wins} | tie={cell['tie']} | unclear={cell['unclear']}")

    print("\n=== all pairs, per criterion ===")
    for crit, pairs in result["tallies_by_criterion_and_pair"].items():
        print(f"  {crit}:")
        for pt, cell in pairs.items():
            wins = ", ".join(f"{k}={v}" for k, v in cell.get("wins", {}).items())
            print(f"    {pt}: n={cell['n']} | {wins} | tie={cell['tie']} | unclear={cell['unclear']}")

    print("\n=== human-human agreement (exact + Krippendorff's alpha, nominal, missing=unclear) ===")
    for pt, by_crit in result["human_human_agreement"].items():
        print(f"  {pt}:")
        for crit, d in by_crit.items():
            ex = d["exact_agreement"]
            al = d["krippendorff_alpha_nominal"]
            alpha_s = f"{al['alpha']:.3f}" if al["alpha"] is not None else f"not estimable ({al['reason']})"
            exact_s = f"{ex['agree']}/{ex['total']} ({ex['rate']:.0%})" if ex["total"] else "0/0"
            print(f"    {crit}: exact={exact_s} | alpha={alpha_s}")

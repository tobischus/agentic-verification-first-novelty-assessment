"""E2: turn an admin export ZIP into win/tie/loss tallies, human-human agreement, and (optionally) human-vs-E1-judge agreement. Reads ONLY `ratings.jsonl` from the export (each line already carries system_a/system_b/orientation resolved server-side -- see routers/admin.py's `_build_export`); this module never touches the live database."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .stats import exact_agreement, krippendorff_alpha_nominal

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
    return None


def run(input_path: str, include_test: bool = False) -> dict:
    """`include_test`: the pilot's two raters are deliberately TEST participants (`is_test=True`), so analysing the pilot at all requires passing True -- the CLI's `--include-test` flag. The default stays False so a main-study analysis can never quietly mix a leftover test account's answers into real results."""
    all_records = _load_ratings(input_path)
    records = [r for r in all_records
              if r.get("status") == "submitted" and not r.get("is_practice")
              and (include_test or not r.get("is_test_participant"))]
    excluded_test = 0 if include_test else sum(
        1 for r in all_records if r.get("is_test_participant"))

    tallies = defaultdict(lambda: defaultdict(lambda: {"wins": defaultdict(int), "tie": 0,
                                                       "unclear": 0, "n": 0}))
    per_paper_tallies = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {"wins": defaultdict(int), "tie": 0, "unclear": 0, "n": 0})))

    units_by_pair_crit = defaultdict(lambda: defaultdict(dict))

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


def _load_export_manifest(export_path: str) -> dict:
    with zipfile.ZipFile(export_path) as z:
        return json.loads(z.read("manifest.json").decode("utf-8"))


PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def criteria_text(rubric_text: str) -> Optional[str]:
    """A rubric's CRITERIA section -- from the line `CRITERIA` to the line `PROCEDURE`, the part criteria.json and the rating form copy for the raters. None if absent."""
    m = re.search(r"^CRITERIA\n(.*?)^PROCEDURE\n", rubric_text, re.S | re.M)
    return m.group(1) if m else None


def _export_criteria(export_path: str) -> Optional[str]:
    """The criteria the raters read: the CRITERIA section of the export's rubric.txt."""
    with zipfile.ZipFile(export_path) as z:
        if "rubric.txt" not in z.namelist():
            return None
        return criteria_text(z.read("rubric.txt").decode("utf-8"))


def _judge_criteria(rubric_version: Optional[str], cache: dict) -> Optional[str]:
    if rubric_version not in cache:
        f = PROMPTS / f"{rubric_version}.txt"
        cache[rubric_version] = (criteria_text(f.read_text(encoding="utf-8"))
                                 if rubric_version and f.is_file() else None)
    return cache[rubric_version]


def _judge_system(judge: dict, crit: str) -> Optional[str]:
    w = (((judge.get("parsed_result") or {}).get("criteria") or {}).get(crit) or {}).get("winner")
    return {"A": judge.get("system_a"), "B": judge.get("system_b"), "tie": "tie"}.get(w)


def compare_to_e1(export_path: str, e1_jsonl_path: str, include_test: bool = False) -> dict:
    """Each human judgement against the E1 judge call of the SAME task in the SAME A/B orientation -- and only where the judge read the same criteria and the same report content: the CRITERIA section of the call's rubric must equal the one in the export's rubric.txt, and the call's `content_version_a/_b` must equal the export's manifest.json for exactly those reports. Anything else is `not_comparable` with its reason; nothing is matched by task id alone, since a task id is no proof the underlying text was the same. Human and judge votes are compared, never pooled."""
    manifest = _load_export_manifest(export_path)
    versions = {(r["paper_id"], r["system_id"]): r["content_version"]
                for r in manifest.get("reports") or []}
    rater_criteria = _export_criteria(export_path)
    criteria_cache = {}
    calls = [json.loads(ln) for ln in Path(e1_jsonl_path).read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    by_key = {(c["paper_id"], c["system_a"], c["system_b"]): c for c in calls if not c.get("failed")}

    records = [r for r in _load_ratings(export_path)
               if r.get("status") == "submitted" and not r.get("is_practice")
               and (include_test or not r.get("is_test_participant"))]

    not_comparable = defaultdict(int)
    per_crit = {c: {"compared": 0, "agree": 0, "human_unclear": 0, "judge_unclear": 0,
                    "stable_compared": 0, "stable_agree": 0, "confusion": defaultdict(int)}
                for c in CRITERIA}
    n_comparable = 0
    judge_rubrics = set()
    for rec in records:
        paper, a, b = rec["paper_id"], rec["system_a"], rec["system_b"]
        judge = by_key.get((paper, a, b))
        if judge is None:
            not_comparable["no successful judge call in this orientation"] += 1
            continue
        if judge.get("content_version_a") is None or judge.get("content_version_b") is None:
            not_comparable["judge record carries no content versions (older E1 output)"] += 1
            continue
        judge_criteria = _judge_criteria(judge.get("rubric_version"), criteria_cache)
        if rater_criteria is None or judge_criteria != rater_criteria:
            not_comparable[f"criteria differ (judge {judge.get('rubric_version')})"] += 1
            continue
        judge_rubrics.add(judge.get("rubric_version"))
        if (judge["content_version_a"] != versions.get((paper, a))
                or judge["content_version_b"] != versions.get((paper, b))):
            not_comparable["report content differs from what the raters saw"] += 1
            continue
        n_comparable += 1
        other = by_key.get((paper, b, a))
        for crit in CRITERIA:
            c = (rec.get("criteria") or {}).get(crit)
            if not c or not c.get("winner"):
                continue
            d = per_crit[crit]
            human_sys = _winner_system(c, rec)
            judge_sys = _judge_system(judge, crit)
            if human_sys is None:
                d["human_unclear"] += 1
                continue
            if judge_sys is None:
                d["judge_unclear"] += 1
                continue
            d["compared"] += 1
            d["agree"] += human_sys == judge_sys
            d["confusion"][f"{human_sys}->{judge_sys}"] += 1
            if other is not None and _judge_system(other, crit) == judge_sys:
                d["stable_compared"] += 1
                d["stable_agree"] += human_sys == judge_sys

    for d in per_crit.values():
        d["agreement"] = round(d["agree"] / d["compared"], 3) if d["compared"] else None
        d["stable_agreement"] = (round(d["stable_agree"] / d["stable_compared"], 3)
                                 if d["stable_compared"] else None)
        d["confusion"] = dict(d["confusion"])
    return {
        "export_study": manifest.get("study_id"),
        "raters_criteria_sha256": (hashlib.sha256(rater_criteria.encode("utf-8")).hexdigest()
                                   if rater_criteria is not None else None),
        "judge_rubric_versions": sorted(v for v in judge_rubrics if v),
        "e1_file": str(e1_jsonl_path), "human_responses": len(records),
        "comparable_responses": n_comparable, "not_comparable": dict(not_comparable),
        "by_criterion": per_crit,
        "note": "Per orientation: a rater who saw X as A is compared with the judge call "
                "that saw X as A. Agreement = same winning system or both tie; unclear on "
                "either side is missing. Human and judge votes are never pooled.",
    }


def print_e1_comparison(result: dict) -> None:
    print(f"export: {result['export_study']}; "
          f"{result['comparable_responses']}/{result['human_responses']} human responses "
          f"comparable with an E1 call")
    judged = result.get("judge_rubric_versions") or []
    if judged:
        print(f"  judge rubric: {', '.join(judged)} (same CRITERIA section as the raters')")
    for reason, n in result["not_comparable"].items():
        print(f"  not comparable: {n} -- {reason}")
    print(f"\n{'criterion':24} {'n':>4} {'agree':>7} {'stable n':>9} {'agree':>7}")
    for crit, d in result["by_criterion"].items():
        fmt = lambda x: "  -  " if x is None else f"{x:.2f}"
        print(f"{crit:24} {d['compared']:4} {fmt(d['agreement']):>7} "
              f"{d['stable_compared']:9} {fmt(d['stable_agreement']):>7}")


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

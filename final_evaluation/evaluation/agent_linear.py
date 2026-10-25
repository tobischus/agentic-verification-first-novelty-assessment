"""Agent vs linear from the run records -- read-only, no API call."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import yaml

from .e1 import analyze as an
from .e1 import sensitivity as sens

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "final_evaluation"
E1_CONFIG = FE / "config" / "e1_main.yaml"
VARIANTS = ("agent", "linear")

METRICS = [
    ("comparisons_recorded", "comparisons recorded (claim x prior paper)", True),
    ("detailed_in_report", "detailed comparisons shown in the report", True),
    ("dismissed", "dismissed before any comparison", False),
    ("compared", "compared and evidence-checked", False),
    ("first_check_failed", "first evidence check failed", True),
    ("first_check_failed_share", "  share of compared", True),
    ("resolved_by_reentry", "resolved by re-reading (re-entry)", False),
    ("unresolved", "unresolved at the end", True),
    ("unresolved_share", "  share of compared", True),
    ("evidence_material", "evidence check: material", True),
    ("evidence_nonmaterial", "evidence check: nonmaterial", True),
    ("evidence_insufficient", "evidence check: insufficient", True),
    ("insufficient_share", "  insufficient, share of checked", True),
    ("partial_or_stronger", "overlap partial or stronger", True),
    ("strong_supported", "substantial/same with material evidence", True),
    ("conflicts", "degree proposed but not supported (conflict)", True),
    ("pairs_returned", "quote pairs returned", True),
    ("pairs_unverified", "quote pairs failing verbatim verification", True),
    ("unverified_share", "  share of returned", True),
    ("usd", "cost, USD (list-price estimate)", True),
    ("seconds", "wall clock, seconds", True),
    ("tokens", "tokens", True),
    ("model_calls", "model calls", True),
]

MATCHED = [
    ("pairs", "pairs compared by both", False),
    ("first_check_failed", "first evidence check failed", True),
    ("unresolved", "unresolved at the end", True),
    ("evidence_material", "evidence check: material", True),
    ("evidence_nonmaterial", "evidence check: nonmaterial", True),
    ("evidence_insufficient", "evidence check: insufficient", True),
    ("conflicts", "degree proposed but not supported (conflict)", True),
    ("partial_or_stronger", "overlap partial or stronger", True),
    ("degree_confirmed", "overlap confirmed at the proposed degree", True),
    ("pairs_returned", "quote pairs returned", True),
    ("pairs_unverified", "quote pairs failing verbatim verification", True),
]


def _run_metrics():
    if str(ROOT / "eval") not in sys.path:
        sys.path.insert(0, str(ROOT / "eval"))
    import run_metrics
    return run_metrics


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _checked(path: str, sha: str, base: Path = ROOT) -> Path:
    """The manifest's artifact paths are relative to the repo, its report paths to final_evaluation/ -- hence `base`."""
    p = base / Path(path.replace("\\", "/"))
    got = _sha(p) if p.exists() else "missing"
    if got != sha:
        raise SystemExit(f"{path}: sha256 {got[:12]} != recorded {sha[:12]} -- not the "
                         f"file the frozen report was rendered from")
    return p


def paper_entries(config: Path = E1_CONFIG) -> list:
    """[(paper_set, paper, manifest entry)] for every paper of the E1 design."""
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    out = []
    for ps in cfg["paper_sets"]:
        sub = yaml.safe_load((ROOT / ps["config"]).read_text(encoding="utf-8"))
        man = json.loads((FE / "manifests" / sub["inputs_dir"] / "reports.json")
                         .read_text(encoding="utf-8"))
        out += [(ps["role"], paper, e) for paper, e in man["papers"].items()]
    return out


def pair_endings(artifact_a: dict) -> dict:
    """{(claim_id, paper_id): ending} from the run log; endings as in the docstring ("checked" = passed the first evidence check)."""
    out = {}
    for claim in artifact_a.get("claims") or []:
        for pw in (claim.get("run_log") or {}).get("prior_work") or []:
            compares = sum(1 for r in pw.get("rounds") or [] if r.get("call") == "semantic_compare")
            state = pw.get("final_state")
            if state == "dismissed" and compares == 0:
                end = "dismissed"
            elif compares == 0:
                end = "not_compared"
            elif state == "checked":
                end = "checked" if compares == 1 else "resolved_by_reentry"
            elif state == "budget_exhausted":
                end = "unresolved"
            else:
                end = f"other_after_failed_check:{state}"
            out[(claim.get("claim_id"), pw.get("paper_id"))] = end
    return out


def endings(artifact_a: dict) -> dict:
    """Counts of `pair_endings`, with `compared` and `first_check_failed` derived."""
    c = Counter(pair_endings(artifact_a).values())
    c["compared"] = sum(n for k, n in c.items() if k not in ("dismissed", "not_compared"))
    c["first_check_failed"] = c["compared"] - c["checked"]
    return {k: n for k, n in c.items() if n}


_TRACE_DEGREE = re.compile(r"^\[(\d+)\] SEMANTIC DEGREE: (\w+)")
_TRACE_STATUS = re.compile(r"^\[(\d+)\] EVIDENCE CHECK: status=(\w+)")


def reentry_outcomes(artifact_a: dict, overlap_degrees) -> Counter:
    """For every pair the agent compared more than once: how it ended, read from the decision trace lines `claim_agent` writes per turn ("[t] SEMANTIC DEGREE: x", "[t] EVIDENCE CHECK: status=y"), first turn against last."""
    c = Counter()
    for claim in artifact_a.get("claims") or []:
        for pw in (claim.get("run_log") or {}).get("prior_work") or []:
            if sum(1 for r in pw.get("rounds") or [] if r.get("call") == "semantic_compare") < 2:
                continue
            deg, st = {}, {}
            for line in pw.get("decision_trace") or []:
                if m := _TRACE_DEGREE.match(line):
                    deg[int(m[1])] = m[2]
                if m := _TRACE_STATUS.match(line):
                    st[int(m[1])] = m[2]
            if len(deg) < 2 or len(st) < 2:
                c[("unparsed", "", "")] += 1
                continue
            first, last = min(deg), max(deg)
            overlap = deg[last] in overlap_degrees
            material = st[last] == "material"
            outcome = ("overlap_confirmed" if overlap and material else
                       "overlap_rejected" if not overlap and not material else "disagreement")
            moved = (deg[first] != deg[last], st[first] != st[last])
            changed = {(True, False): "degree", (False, True): "evidence",
                       (True, True): "both", (False, False): "neither"}[moved]
            end = "resolved" if pw.get("final_state") == "checked" else "unresolved"
            c[(end, outcome, changed)] += 1
    return c


def _share(a, b):
    return round(a / b, 4) if b else 0.0


def variant_values(vm: dict, ends: dict, detailed: int) -> dict:
    """The METRICS for one variant of one paper. `vm` is run_metrics.variant_metrics."""
    ev, f, t = vm["distributions"]["evidence"], vm["findings"], vm["totals"]
    checked = sum(n for s, n in ev.items() if s != "no_check")
    compared = ends.get("compared", 0)
    return {
        "comparisons_recorded": vm["n_comparisons"],
        "detailed_in_report": detailed,
        "dismissed": ends.get("dismissed", 0),
        "compared": compared,
        "first_check_failed": ends.get("first_check_failed", 0),
        "first_check_failed_share": _share(ends.get("first_check_failed", 0), compared),
        "resolved_by_reentry": ends.get("resolved_by_reentry", 0),
        "unresolved": ends.get("unresolved", 0),
        "unresolved_share": _share(ends.get("unresolved", 0), compared),
        "evidence_material": ev.get("material", 0),
        "evidence_nonmaterial": ev.get("nonmaterial", 0),
        "evidence_insufficient": ev.get("insufficient", 0),
        "insufficient_share": _share(ev.get("insufficient", 0), checked),
        "partial_or_stronger": f["partial_or_stronger"],
        "strong_supported": f["strong_supported"],
        "conflicts": f["conflicts"],
        "pairs_returned": f["evidence_pairs_returned"],
        "pairs_unverified": f["evidence_pairs_unverified"],
        "unverified_share": _share(f["evidence_pairs_unverified"], f["evidence_pairs_returned"]),
        "usd": t["total_usd"],
        "seconds": t["seconds"],
        "tokens": t["total_tokens"],
        "model_calls": t["model_calls"],
    }


def matched_values(ends: dict, rows: list, keys: set, vd) -> dict:
    """The MATCHED metrics for one variant on the given (claim, paper) keys."""
    by = {(r["claim_id"], r["paper_id"]): r for r in rows}
    rs = [by[k] for k in keys]
    ev = Counter(r["evidence_status"] for r in rs)
    return {
        "pairs": len(keys),
        "first_check_failed": sum(1 for k in keys if ends[k] != "checked"),
        "unresolved": sum(1 for k in keys if ends[k] == "unresolved"),
        "evidence_material": ev.get("material", 0),
        "evidence_nonmaterial": ev.get("nonmaterial", 0),
        "evidence_insufficient": ev.get("insufficient", 0),
        "conflicts": sum(1 for r in rs if r["conflict"]),
        "partial_or_stronger": sum(1 for r in rs if r["overlap_degree"] in vd.OVERLAP_DEGREES),
        "degree_confirmed": sum(1 for r in rs if r["evidence_status"] == "material"
                                and r["proposed_degree_supported"] is True),
        "pairs_returned": sum(r["pairs_returned"] for r in rs),
        "pairs_unverified": sum(r["pairs_unverified"] for r in rs),
    }


def paired(per_paper: dict, key: str, block: str = "") -> dict:
    """Totals (or mean of per-paper shares), and the sign test over papers. `block` selects a nested block of each paper's record ("matched")."""
    rec = [v[block] if block else v for v in per_paper.values()]
    a = [v["agent"][key] for v in rec]
    b = [v["linear"][key] for v in rec]
    lower = sum(1 for x, y in zip(a, b) if x < y)
    higher = sum(1 for x, y in zip(a, b) if x > y)
    share = key.endswith("_share")
    agg = (lambda xs: round(statistics.mean(xs), 4)) if share else (lambda xs: round(sum(xs), 4))
    return {
        "aggregate": "mean of per-paper shares" if share else "sum over papers",
        "agent": agg(a), "linear": agg(b),
        "agent_lower": lower, "agent_higher": higher, "equal": len(a) - lower - higher,
        "median_difference": round(statistics.median(x - y for x, y in zip(a, b)), 4),
        "p": an.sign_test(lower, higher),
    }


def holm(ps: dict) -> dict:
    """Holm-Bonferroni adjusted p-values, monotone, capped at 1."""
    order = sorted(ps, key=ps.get)
    m, out, run = len(order), {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = run
    return out


def _dismissed_vs_linear(a_art: dict, l_rows: list, vd) -> Counter:
    """For every pair the agent dismissed: what linear's single pass made of it."""
    lin = {(r["claim_id"], r["paper_id"]): r for r in l_rows}
    c = Counter()
    for claim in a_art.get("claims") or []:
        for pw in (claim.get("run_log") or {}).get("prior_work") or []:
            if pw.get("final_state") != "dismissed":
                continue
            r = lin.get((claim["claim_id"], pw["paper_id"]))
            if not r:
                c["not_compared_by_linear"] += 1
                continue
            c[f"{r['overlap_degree']} / {r['evidence_status']}"] += 1
            if r["overlap_degree"] in vd.OVERLAP_DEGREES and r["evidence_status"] == "material":
                c["_partial_or_stronger_material"] += 1
            if r["refutes"]:
                c["_linear_refutes"] += 1
    return c


def analyze(config: Path = E1_CONFIG) -> dict:
    rm = _run_metrics()
    vd = rm.vd
    per_paper, verdicts, dismissed, flags, reentries = {}, [], Counter(), [], Counter()
    for role, paper, e in paper_entries(config):
        arts, vms, pends, vals = {}, {}, {}, {}
        for v in VARIANTS:
            sysm = e["systems"][v]
            prov = sysm["provenance"]
            pa = _checked(prov["artifact_a_path"], prov["artifact_a_sha256"])
            _checked(prov["artifact_b_path"], prov["artifact_b_sha256"])
            report = _checked(sysm["text_file"]["path"], sysm["text_file"]["sha256"], FE)
            arts[v] = json.loads(pa.read_text(encoding="utf-8"))
            vms[v] = rm.variant_metrics(pa.parent, paper, v)
            pends[v] = pair_endings(arts[v])
            ends = endings(arts[v])
            if any(k.startswith("other_after") or k == "not_compared" for k in ends):
                flags.append({"paper": paper, "variant": v, "endings": ends})
            vals[v] = variant_values(
                vms[v], ends, sens.detailed_comparisons(report.read_text(encoding="utf-8")))

        both = set.intersection(*({k for k, end in pends[v].items()
                                   if end not in ("dismissed", "not_compared")}
                                  for v in VARIANTS))
        per_paper[paper] = {
            "paper_set": role, **vals,
            "matched": {v: matched_values(pends[v], vms[v]["_rows"], both, vd) for v in VARIANTS},
        }

        agr = rm.agreement(vms["agent"], vms["linear"])
        for pc in agr["verdicts"]["per_claim"]:
            verdicts.append({"paper": paper, **pc})
        dismissed += _dismissed_vs_linear(arts["agent"], vms["linear"]["_rows"], vd)
        reentries += reentry_outcomes(arts["agent"], vd.OVERLAP_DEGREES)

    tests ={k: paired(per_paper, k) for k, _, _ in METRICS}
    matched = {k: paired(per_paper, k, "matched") for k, _, _ in MATCHED}
    tested = {**{("all", k): tests[k]["p"] for k, _, t in METRICS if t},
              **{("matched", k): matched[k]["p"] for k, _, t in MATCHED if t}}
    adj = holm(tested)
    for block, res in (("all", tests), ("matched", matched)):
        for k in res:
            res[k]["p_holm"] = adj.get((block, k))
            res[k]["tested"] = (block, k) in adj

    tot = {v: {k: sum(p[v][k] for p in per_paper.values())
               for k in ("compared", "first_check_failed", "resolved_by_reentry", "unresolved",
                         "dismissed")} for v in VARIANTS}
    diff = [x for x in verdicts if not x["agree"]]
    by_linear_only = sum(1 for x in diff if x["linear"] == "challenged" and x["agent"] != "challenged")
    return {
        "post_hoc": "test chosen 2026-09-25 after an ad-hoc look at these numbers; "
                    "metrics as named in PROTOCOL 5 (2026-09-23)",
        "papers": len(per_paper),
        "tests": tests,
        "matched": matched,
        "tested_metrics": len(tested),
        "reentry": {
            v: {**tot[v], "first_check_failed_rate": _share(tot[v]["first_check_failed"],
                                                            tot[v]["compared"])}
            for v in VARIANTS},
        "reentry_outcomes": [{"end": e, "outcome": o, "changed": ch, "n": n}
                             for (e, o, ch), n in sorted(reentries.items(),
                                                         key=lambda t: (t[0][0], -t[1]))],
        "verdicts":{"claims": len(verdicts), "agree": len(verdicts) - len(diff),
                     "differ": diff, "linear_challenges_agent_does_not": by_linear_only},
        "agent_dismissed_vs_linear": {
            "pairs": sum(n for k, n in dismissed.items() if not k.startswith("_")),
            "linear_partial_or_stronger_material": dismissed.get("_partial_or_stronger_material", 0),
            "linear_refutes": dismissed.get("_linear_refutes", 0),
            "breakdown": dict(Counter({k: n for k, n in dismissed.items()
                                       if not k.startswith("_")}).most_common()),
        },
        "unexpected_endings": flags,
        "per_paper": per_paper,
    }


def _fmt(x) -> str:
    if isinstance(x, float) and not x.is_integer():
        return f"{x:.3f}" if abs(x) < 10 else f"{x:,.1f}"
    return f"{int(x):,}"


def _print_block(title: str, metrics: list, res: dict) -> None:
    print(title)
    head = f"{'metric':48s} {'agent':>11s} {'linear':>11s}  lower/higher/equal   p        p_holm"
    print(head)
    print("-" * len(head))
    for k, label, _ in metrics:
        t = res[k]
        ps = f"{t['p']:.2g}" if t["tested"] else "(design)"
        ph = f"{t['p_holm']:.2g}" if t["tested"] else ""
        print(f"{label:48s} {_fmt(t['agent']):>11s} {_fmt(t['linear']):>11s}  "
              f"{t['agent_lower']:>5d}/{t['agent_higher']:<5d}/{t['equal']:<5d}  {ps:8s} {ph}")


def print_report(res: dict) -> None:
    print(f"Agent vs linear from the run records -- {res['papers']} papers, paired by paper")
    print(f"({res['post_hoc']})")
    print("Exact two-sided sign test over papers, equal values left out; "
          f"Holm across all {res['tested_metrics']} tested metrics of both blocks.")
    print("'lower/higher' = papers on which the agent's value is lower/higher than linear's;"
          " shares are means of per-paper shares.")
    print()
    _print_block("ALL PAIRS -- what each flow did with the whole pool", METRICS, res["tests"])
    print()
    _print_block("MATCHED PAIRS -- only the (claim, paper) pairs both flows compared",
                 MATCHED, res["matched"])
    print()
    print("Re-entry mechanism (totals over papers):")
    for v in VARIANTS:
        r = res["reentry"][v]
        print(f"  {v:6s}: dismissed {r['dismissed']}, compared {r['compared']}, first check "
              f"failed {r['first_check_failed']} ({r['first_check_failed_rate']:.1%}), "
              f"resolved by re-entry {r['resolved_by_reentry']}, unresolved {r['unresolved']}")
    print()
    print("Agent pairs compared twice, first turn vs last (from the decision trace):")
    print(f"  {'end':11s} {'outcome':18s} {'what changed':13s} n")
    for r in res["reentry_outcomes"]:
        print(f"  {r['end']:11s} {r['outcome']:18s} {r['changed']:13s} {r['n']}")
    print()
    vv = res["verdicts"]
    print(f"Claim verdicts: agree on {vv['agree']}/{vv['claims']}; "
          f"linear challenges where the agent does not: {vv['linear_challenges_agent_does_not']}")
    for d in vv["differ"]:
        print(f"  {d['paper']} {d['claim_id']}: agent {d['agent']}, linear {d['linear']}")
    print()
    dd = res["agent_dismissed_vs_linear"]
    print(f"Pairs the agent dismissed ({dd['pairs']}), as linear's single pass assessed them: "
          f"partial-or-stronger with material evidence {dd['linear_partial_or_stronger_material']}, "
          f"refuting {dd['linear_refutes']}")
    for k, n in dd["breakdown"].items():
        print(f"  {k:32s} {n}")
    if res["unexpected_endings"]:
        print()
        print("UNEXPECTED paper endings (not in the state model above):")
        for f in res["unexpected_endings"]:
            print(f"  {f}")

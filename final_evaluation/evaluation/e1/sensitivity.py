"""E1 sensitivity analyses -- post hoc, exploratory, read-only, no API call."""
from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import analyze as an

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT / "final_evaluation" / "inputs"
BETA_SD = 2.5
_CLAIM = re.compile(r"\n# (Claim \d+) — Review\n")
_DETAIL = re.compile(r"\n### R\d+ ")


def detailed_comparisons(text: str) -> int:
    """`### R<n>` blocks inside the per-claim review sections of an agent/linear export."""
    parts = _CLAIM.split(text)
    return sum(len(_DETAIL.findall(parts[i + 1])) for i in range(1, len(parts), 2))


def report_coverage(recs: list, systems=("agent", "linear")) -> dict:
    """(paper, system) -> detailed comparisons, read from the exact file each call used."""
    out = {}
    for r in recs:
        if r.get("failed"):
            continue
        for side in ("a", "b"):
            s = r[f"system_{side}"]
            if s not in systems or (r["paper_id"], s) in out:
                continue
            path = INPUTS / r["input_dir"] / r["paper_id"] / r[f"report_{side}_file"]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != r[f"report_{side}_file_sha256"]:
                raise SystemExit(f"{path}: not the file the judge read (sha256 differs)")
            out[(r["paper_id"], s)] = detailed_comparisons(raw.decode("utf-8"))
    return out


def fit(obs: list, prior: float = 0.5, beta_sd: float = BETA_SD,
        iters: int = 100, tol: float = 1e-10) -> tuple[dict, list]:
    """Bradley-Terry with covariates. obs: [(x, y, outcome for x in {1, .5, 0}, dz)], dz the covariate differences x minus y. Returns (log-strengths centred on 0, slopes)."""
    systems = sorted({s for x, y, _, _ in obs for s in (x, y)}, key=an.SYSTEMS.index)
    k, m = len(systems), len(obs[0][3]) if obs else 0
    if k < 2:
        return {}, []
    idx = {s: i for i, s in enumerate(systems)}
    pairs = sorted({tuple(sorted((idx[x], idx[y]))) for x, y, _, _ in obs})
    n, q = len(obs) + len(pairs), k - 1 + m
    X, o, w = np.zeros((n, q)), np.empty(n), np.ones(n)
    for r, (x, y, out, dz) in enumerate(obs):
        if idx[x] < k - 1:
            X[r, idx[x]] += 1
        if idx[y] < k - 1:
            X[r, idx[y]] -= 1
        X[r, k - 1:] = dz
        o[r] = out
    for r, (i, j) in enumerate(pairs, start=len(obs)):
        if i < k - 1:
            X[r, i] += 1
        if j < k - 1:
            X[r, j] -= 1
        o[r], w[r] = 0.5, 2 * prior
    pen = np.zeros(q)
    pen[k - 1:] = 1 / beta_sd ** 2
    par = np.zeros(q)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ par, -30, 30)))
        grad = X.T @ (w * (o - p)) - pen * par
        hess = -(X.T * (w * p * (1 - p))) @ X - np.diag(pen)
        step = np.clip(np.linalg.solve(hess, -grad), -5, 5)
        par += step
        if np.abs(step).max() < tol:
            break
    th = np.append(par[:k - 1], 0.0)
    th -= th.mean()
    return dict(zip(systems, th.tolist())), par[k - 1:].tolist()


def _obs_by_paper(us: dict, crits, covariate, pair=None) -> dict:
    """paper -> [(x, y, outcome, dz)] from the stable verdicts; covariate(paper, x, y, unit) gives dz (a tuple, empty for none)."""
    out = defaultdict(list)
    for (paper, (x, y)), u in us.items():
        if pair and (x, y) != pair:
            continue
        for crit in crits:
            v = an.stable_verdict(u, crit)
            if v in (x, y, "tie"):
                out[paper].append((x, y, 1.0 if v == x else 0.5 if v == "tie" else 0.0,
                                   covariate(paper, x, y, u)))
    return dict(out)


def _log_length(paper, x, y, u):
    cc = u["xy"]["context_chars"]
    return (math.log(cc["report_a"]) - math.log(cc["report_b"]),)


def _boot(by_paper: dict, stat) -> list:
    papers = sorted(by_paper)
    rng = random.Random(an.BOOT_SEED)
    return [stat([g for p in (rng.choice(papers) for _ in papers) for g in by_paper[p]])
            for _ in range(an.N_BOOT)]


def _ci(vals: list) -> list:
    v = sorted(vals)
    return [v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]]


def _elo(th: float) -> float:
    return an.ELO_BASE + an.ELO_PER_LOG * th


def length_adjusted(us: dict, crits) -> dict:
    """All five systems: Elo with and without the log-length covariate."""
    by_paper = _obs_by_paper(us, crits, _log_length)
    obs = [g for gs in by_paper.values() for g in gs]
    if not obs:
        return {}
    plain = lambda gs: fit([(x, y, o, ()) for x, y, o, _ in gs])[0]  # noqa: E731
    both = lambda gs: fit(gs)  # noqa: E731
    th0, (th1, beta) = plain(obs), both(obs)
    b0, b1 = _boot(by_paper, plain), _boot(by_paper, both)

    def ratings(th, boots):
        return {s: {"elo": round(_elo(th[s]), 1),
                    "ci95": [round(_elo(v), 1) for v in _ci([b[s] for b in boots if s in b])]}
                for s in sorted(th, key=lambda s: -th[s])}

    def share(boots, x="agent", y="linear"):
        both_in = [b for b in boots if x in b and y in b]
        return round(sum(b[x] > b[y] for b in both_in) / len(both_in), 3) if both_in else None

    betas = [bb[1][0] for bb in b1]
    return {
        "games": len(obs), "papers": len(by_paper),
        "unadjusted": {"ratings": ratings(th0, b0), "share_agent_above_linear": share(b0)},
        "length_adjusted": {"ratings": ratings(th1, [bb[0] for bb in b1]),
                            "share_agent_above_linear": share([bb[0] for bb in b1])},
        "beta_log_length": round(beta[0], 3), "beta_ci95": [round(v, 3) for v in _ci(betas)],
        "odds_per_doubling": round(math.exp(beta[0] * math.log(2)), 2),
        "odds_per_doubling_ci95": [round(math.exp(v * math.log(2)), 2) for v in _ci(betas)],
    }


OURS = {"agent", "linear"}
BASELINES = ("opennovelty", "deepreviewer", "afzal")


def length_overlap(us: dict) -> dict:
    """How often a baseline report is at least as long as an agent/linear report of the same paper -- the support the five-system length adjustment has for comparing the groups."""
    ln = {}
    for (p, (x, y)), u in us.items():
        cc = u["xy"]["context_chars"]
        ln[(p, x)], ln[(p, y)] = cc["report_a"], cc["report_b"]
    papers = sorted({p for p, _ in ln})
    cases = [(p, a, b) for p in papers for a in sorted(OURS) for b in BASELINES
             if (p, a) in ln and (p, b) in ln]
    return {"baseline_at_least_as_long": sum(ln[(p, b)] >= ln[(p, a)] for p, a, b in cases),
            "cases": len(cases)}


def within_group_slope(us: dict, crits) -> dict:
    """The length slope from agent-vs-linear and baseline-vs-baseline pairs only, where report lengths overlap. Two neutral games at equal length connect the two groups so the fit is defined; they fix the (meaningless) offset between the groups and leave the slope alone."""
    sub = {k: u for k, u in us.items() if set(k[1]) <= OURS or not set(k[1]) & OURS}
    bridge = [("agent", "opennovelty", 0.5, (0.0,)), ("linear", "deepreviewer", 0.5, (0.0,))]
    by_paper = _obs_by_paper(sub, crits, _log_length)
    obs = [g for gs in by_paper.values() for g in gs]
    if not obs:
        return {}
    slope = lambda gs: fit(gs + bridge)[1][0]  # noqa: E731
    b, boots = slope(obs), _boot(by_paper, slope)
    return {"games": len(obs), "odds_per_doubling": round(math.exp(b * math.log(2)), 2),
            "odds_per_doubling_ci95": [round(math.exp(v * math.log(2)), 2) for v in _ci(boots)]}


def agent_vs_linear(us: dict, crits, coverage: dict, covariate: str) -> dict:
    """Agent vs linear only: P(agent preferred) unadjusted and at equal `covariate`."""
    if covariate == "coverage":
        cov = lambda p, x, y, u: (math.log1p(coverage[(p, x)]) - math.log1p(coverage[(p, y)]),)  # noqa: E731
    else:
        cov = _log_length
    by_paper = _obs_by_paper(us, crits, cov, pair=("agent", "linear"))
    obs = [g for gs in by_paper.values() for g in gs]
    if not obs:
        return {}
    sig = lambda t: 1 / (1 + math.exp(-t))  # noqa: E731

    def plain(gs):
        th = fit([(x, y, o, ()) for x, y, o, _ in gs])[0]
        return sig(th["agent"] - th["linear"])

    def adjusted(gs):
        th, beta = fit(gs)
        return sig(th["agent"] - th["linear"]), beta[0]

    b0, b1 = _boot(by_paper, plain), _boot(by_paper, adjusted)
    p1, beta = adjusted(obs)
    return {
        "covariate": covariate, "games": len(obs), "papers": len(by_paper),
        "p_agent_unadjusted": round(plain(obs), 3), "p_agent_unadjusted_ci95": [round(v, 3) for v in _ci(b0)],
        "p_agent_at_equal": round(p1, 3), "p_agent_at_equal_ci95": [round(v, 3) for v in _ci([b[0] for b in b1])],
        "odds_per_doubling": round(math.exp(beta * math.log(2)), 2),
        "odds_per_doubling_ci95": [round(math.exp(v * math.log(2)), 2) for v in _ci([b[1] for b in b1])],
    }


def analyze(recs: list) -> dict:
    us = an.units(recs)
    coverage = report_coverage(recs)
    papers = sorted({p for p, _ in coverage})
    cov_tab = {p: {"agent": coverage[(p, "agent")], "linear": coverage[(p, "linear")]} for p in papers}
    scopes = {c: (c,) for c in an.CRITERIA} | {"all_criteria_pooled": an.CRITERIA}
    return {
        "post_hoc": True,
        "coverage": {"per_paper": cov_tab,
                     "total": {s: sum(v[s] for v in cov_tab.values()) for s in ("agent", "linear")},
                     "papers_agent_at_least_linear": sum(v["agent"] >= v["linear"] for v in cov_tab.values())},
        "length_overlap": length_overlap(us),
        "length": {k: length_adjusted(us, c) for k, c in scopes.items()},
        "length_within_groups": {k: within_group_slope(us, c) for k, c in scopes.items()},
        "agent_vs_linear": {k: {"coverage": agent_vs_linear(us, c, coverage, "coverage"),
                                "length": agent_vs_linear(us, c, coverage, "length")}
                            for k, c in scopes.items()},
    }


def print_report(res: dict) -> None:
    cv = res["coverage"]
    print("E1 sensitivity -- POST HOC, exploratory (the pre-specified analysis is analyze-e1)")
    print(f"\ndetailed comparisons shown: agent {cv['total']['agent']}, linear {cv['total']['linear']}; "
          f"agent >= linear on {cv['papers_agent_at_least_linear']} of {len(cv['per_paper'])} papers")

    def ci(v, fmt="{:.2f}"):
        return "[" + ", ".join(fmt.format(x) for x in v) + "]"

    ov = res["length_overlap"]
    print("\n[length] all five systems -- Bradley-Terry + log length ratio")
    print(f"  support: a baseline report is at least as long as an agent/linear report in "
          f"{ov['baseline_at_least_as_long']} of {ov['cases']} same-paper cases -- the adjusted "
          f"ranking between the two groups extrapolates")
    for k, d in res["length"].items():
        if not d:
            continue
        u, a = d["unadjusted"], d["length_adjusted"]
        print(f"\n  {k} ({d['games']} games): odds x{d['odds_per_doubling']} per doubling of length "
              f"{ci(d['odds_per_doubling_ci95'])}")
        for label, blk in (("unadjusted", u), ("adjusted  ", a)):
            print(f"    {label}: " + "  ".join(f"{s} {r['elo']:.0f}" for s, r in blk["ratings"].items())
                  + f"   P(agent>linear) {blk['share_agent_above_linear']:.2f}")
    print("\n[length within groups] slope from agent-vs-linear and baseline-vs-baseline pairs only")
    for k, d in res["length_within_groups"].items():
        if d:
            print(f"  {k:24s} odds x{d['odds_per_doubling']} per doubling {ci(d['odds_per_doubling_ci95'])}"
                  f" ({d['games']} games)")
    print("\n[agent vs linear] P(judge prefers agent) -- unadjusted vs at equal coverage / length")
    for k, d in res["agent_vs_linear"].items():
        c, ln = d["coverage"], d["length"]
        if not c:
            continue
        print(f"  {k:24s} n={c['games']:3d}  unadjusted {c['p_agent_unadjusted']:.2f} {ci(c['p_agent_unadjusted_ci95'])}"
              f"  | equal coverage {c['p_agent_at_equal']:.2f} {ci(c['p_agent_at_equal_ci95'])}"
              f" (odds x{c['odds_per_doubling']} per doubling)"
              f"  | equal length {ln['p_agent_at_equal']:.2f} {ci(ln['p_agent_at_equal_ci95'])}")

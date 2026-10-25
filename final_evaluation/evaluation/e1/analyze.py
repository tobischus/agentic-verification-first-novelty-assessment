"""E1 analysis over judge_calls.jsonl, offline."""
from __future__ import annotations

import itertools
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
            "conclusion_warrant", "reviewer_usefulness")
SYSTEMS = ("agent", "linear", "opennovelty", "deepreviewer", "afzal")
N_BOOT, BOOT_SEED = 1000, 2026


def load(path) -> tuple[list, dict]:
    p = Path(path)
    recs = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    corr = {}
    cp = p.with_name("billing_corrections.jsonl")
    if cp.is_file():
        for ln in cp.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                c = json.loads(ln)
                corr[c["call_index"]] = c
    return recs, corr


def _winner_system(rec: dict, crit: str) -> str:
    w = rec["parsed_result"]["criteria"][crit]["winner"]
    return {"A": rec["system_a"], "B": rec["system_b"]}.get(w, w)


def units(recs: list, paper_set: str | None = None) -> dict:
    """(paper, (x, y)) -> {"xy": call with x as A, "yx": call with y as A, ...}; x before y in SYSTEMS order. Technical failures are not units."""
    out = {}
    for r in recs:
        if r.get("failed") or (paper_set and r.get("paper_set") != paper_set):
            continue
        a, b = r["system_a"], r["system_b"]
        x, y = sorted((a, b), key=SYSTEMS.index)
        u = out.setdefault((r["paper_id"], (x, y)),
                           {"paper_set": r.get("paper_set"), "human_task": r.get("human_task")})
        u["xy" if a == x else "yx"] = r
    return out


def stable_verdict(u: dict, crit: str) -> str:
    """A system id, "tie", "inconsistent", "unclear" or "incomplete" (an order missing)."""
    if "xy" not in u or "yx" not in u:
        return "incomplete"
    v1, v2 = _winner_system(u["xy"], crit), _winner_system(u["yx"], crit)
    if "unclear" in (v1, v2):
        return "unclear"
    return v1 if v1 == v2 else "inconsistent"


def sign_test(k: int, m: int) -> float:
    """Exact two-sided binomial test of k vs m wins under p = 0.5."""
    n = k + m
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(k, m) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(ps: dict) -> dict:
    """Holm-Bonferroni adjusted p-values, monotone, capped at 1."""
    order = sorted(ps, key=ps.get)
    m, out, run = len(order), {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = run
    return out


def add_holm_across_criteria(criteria: dict) -> None:
    """Per pair, Holm-adjust the sign-test p-values of the criteria present (post hoc)."""
    tables = defaultdict(dict)
    for crit, d in criteria.items():
        for t in d["pairs"]:
            tables[tuple(t["pair"])][crit] = t
    for by_crit in tables.values():
        adj = holm({c: t["sign_test_p"] for c, t in by_crit.items()})
        for c, t in by_crit.items():
            t["sign_test_p_holm_criteria"] = adj[c]


def pair_table(us: dict, crit: str, pair: tuple) -> dict:
    x, y = pair
    verdicts = {paper: stable_verdict(u, crit) for (paper, p), u in us.items() if p == pair}
    c = Counter(verdicts.values())
    scored = [1 if v == x else -1 if v == y else 0 for v in verdicts.values()
              if v not in ("incomplete", "unclear")]
    n = len(scored)
    net = sum(scored) / n if n else None
    ci = None
    if n >= 2:
        rng = random.Random(BOOT_SEED)
        boots = sorted(sum(rng.choice(scored) for _ in range(n)) / n for _ in range(N_BOOT))
        ci = [boots[int(0.025 * N_BOOT)], boots[int(0.975 * N_BOOT) - 1]]
    return {"pair": [x, y], "papers": n, f"{x}_wins": c[x], f"{y}_wins": c[y], "tie": c["tie"],
            "inconsistent": c["inconsistent"], "unclear": c["unclear"], "incomplete": c["incomplete"],
            "net_preference": net, "ci95": ci, "sign_test_p": sign_test(c[x], c[y])}


ELO_BASE, ELO_PER_LOG = 1000.0, 400 / math.log(10)
ELO_K, ELO_ORDERS = 16, 1000


def games_by_paper(us: dict, crits) -> dict:
    """paper -> [(x, y, stable verdict)] over `crits`; inconsistent/unclear/incomplete left out."""
    out = defaultdict(list)
    for (paper, (x, y)), u in us.items():
        for crit in crits:
            v = stable_verdict(u, crit)
            if v not in ("inconsistent", "unclear", "incomplete"):
                out[paper].append((x, y, v))
    return dict(out)


def _solve(a: list, b: list) -> list:
    """Gaussian elimination with partial pivoting (the systems here are at most 4x4)."""
    m = [row[:] + [v] for row, v in zip(a, b)]
    k = len(m)
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        for r in range(c + 1, k):
            f = m[r][c] / m[c][c]
            for cc in range(c, k + 1):
                m[r][cc] -= f * m[c][cc]
    x = [0.0] * k
    for r in range(k - 1, -1, -1):
        x[r] = (m[r][k] - sum(m[r][cc] * x[cc] for cc in range(r + 1, k))) / m[r][r]
    return x


def _bt_fit(games: list, prior: float = 0.5, iters: int = 100, tol: float = 1e-12) -> dict:
    """Bradley-Terry maximum likelihood by Newton's method: system -> log strength, centred on 0."""
    wins, n = defaultdict(float), defaultdict(float)
    for x, y, v in games:
        n[frozenset((x, y))] += 1
        if v == "tie":
            wins[(x, y)] += 0.5
            wins[(y, x)] += 0.5
        else:
            wins[(v, y if v == x else x)] += 1
    systems = sorted({s for g in n for s in g}, key=SYSTEMS.index)
    if len(systems) < 2:
        return {}
    for g in list(n):
        i, j = tuple(g)
        n[g] += 2 * prior
        wins[(i, j)] += prior
        wins[(j, i)] += prior
    k = len(systems)
    th = [0.0] * k
    for _ in range(iters):
        grad = [0.0] * k
        hess = [[0.0] * k for _ in range(k)]
        for a in range(k):
            for b in range(k):
                nab = n.get(frozenset((systems[a], systems[b])), 0.0) if a != b else 0.0
                if not nab:
                    continue
                pab = 1 / (1 + math.exp(th[b] - th[a]))
                grad[a] += wins[(systems[a], systems[b])] - nab * pab
                hess[a][a] -= nab * pab * (1 - pab)
                hess[a][b] += nab * pab * (1 - pab)
        step = _solve([row[:-1] for row in hess[:-1]], [-g for g in grad[:-1]]) + [0.0]
        step = [max(-5.0, min(5.0, s)) for s in step]
        th = [t + s for t, s in zip(th, step)]
        if max(abs(s) for s in step) < tol:
            break
    mean = sum(th) / k
    return {s: t - mean for s, t in zip(systems, th)}


def bradley_terry(us: dict, crit: str, prior: float = 0.5) -> dict:
    fit = _bt_fit([g for gs in games_by_paper(us, (crit,)).values() for g in gs], prior)
    return {s: round(v, 3) for s, v in sorted(fit.items(), key=lambda kv: -kv[1])}


def elo(us: dict, crits=CRITERIA) -> dict:
    """Bradley-Terry on the Elo scale with paper-bootstrap CIs."""
    by_paper = games_by_paper(us, crits)
    papers = sorted(by_paper)
    fit = _bt_fit([g for p in papers for g in by_paper[p]])
    if not fit:
        return {}
    rng = random.Random(BOOT_SEED)
    boots = [_bt_fit([g for p in (rng.choice(papers) for _ in papers) for g in by_paper[p]])
             for _ in range(N_BOOT)]
    ranked = sorted(fit, key=lambda s: -fit[s])
    ratings = {}
    for s in ranked:
        vals = sorted(ELO_BASE + ELO_PER_LOG * b[s] for b in boots if s in b)
        ratings[s] = {"elo": round(ELO_BASE + ELO_PER_LOG * fit[s], 1),
                      "ci95": [round(vals[int(0.025 * len(vals))], 1),
                               round(vals[int(0.975 * len(vals)) - 1], 1)]}
    higher = {}
    for x, y in itertools.combinations(ranked, 2):
        both = [b for b in boots if x in b and y in b]
        higher[f"{x}>{y}"] = round(sum(b[x] > b[y] for b in both) / len(both), 3) if both else None
    for s, r in ratings.items():
        r["rank"] = shared_rank(ratings, s)
    return {"ratings": ratings, "bootstrap_share_higher": higher,
            "games": sum(len(v) for v in by_paper.values()), "papers": len(papers)}


def shared_rank(ratings: dict, s: str) -> int:
    """Arena rank (Chiang et al., 2024): 1 + the number of systems whose CI lies entirely above this one."""
    lo, hi = ratings[s]["ci95"]
    return 1 + sum(1 for t, r in ratings.items() if t != s and r["ci95"][0] > hi)


def online_elo(us: dict, crits=CRITERIA, k: float = ELO_K, orders: int = ELO_ORDERS) -> dict:
    """Sequential Elo, averaged over `orders` random game orders."""
    games = [g for gs in games_by_paper(us, crits).values() for g in gs]
    systems = sorted({s for x, y, _ in games for s in (x, y)}, key=SYSTEMS.index)
    if len(systems) < 2:
        return {}
    rng = random.Random(BOOT_SEED)
    total = defaultdict(float)
    for _ in range(orders):
        rng.shuffle(games)
        r = {s: ELO_BASE for s in systems}
        for x, y, v in games:
            delta = k * ((1.0 if v == x else 0.5 if v == "tie" else 0.0)
                         - 1 / (1 + 10 ** ((r[y] - r[x]) / 400)))
            r[x] += delta
            r[y] -= delta
        for s in systems:
            total[s] += r[s]
    return {s: round(total[s] / orders, 1) for s in sorted(systems, key=lambda s: -total[s])}


def position(recs: list, crit: str) -> dict:
    c = Counter(r["parsed_result"]["criteria"][crit]["winner"] for r in recs if not r.get("failed"))
    pref = c["A"] + c["B"]
    return {"A": c["A"], "B": c["B"], "tie": c["tie"], "unclear": c["unclear"],
            "share_A": c["A"] / pref if pref else None, "sign_test_p": sign_test(c["A"], c["B"])}


def length_effect(us: dict, crit: str) -> dict:
    won = total = 0
    for (_, (x, y)), u in us.items():
        v = stable_verdict(u, crit)
        if v not in (x, y):
            continue
        cc = u["xy"]["context_chars"]
        if cc["report_a"] == cc["report_b"]:
            continue
        longer = x if cc["report_a"] > cc["report_b"] else y
        total += 1
        won += v == longer
    return {"stable_preferences": total, "longer_won": won,
            "share_longer_won": won / total if total else None}


def cost(recs: list, corr: dict) -> dict:
    out = Counter()
    est = []
    for r in recs:
        if r.get("failed"):
            continue
        c = corr.get(r["call_index"], {})
        out["calls"] += 1
        out["input_tokens"] += r["input_tokens"]
        out["output_tokens"] += r["output_tokens"]
        out["cache_read_tokens"] += c.get("cache_tokens_derived", r.get("cache_tokens") or 0)
        out["cache_write_tokens"] += r.get("cache_write_tokens") or 0
        rt = c["reasoning_tokens_corrected"] if "reasoning_tokens_corrected" in c else r.get("reasoning_tokens")
        if rt is not None:
            out["reasoning_tokens"] += rt
            out["reasoning_recorded_calls"] += 1
        usd = c.get("billed_usd_corrected", r.get("billed_usd"))
        if usd is None:
            t, long = r["input_tokens"], r["input_tokens"] > 272_000
            usd = (t * 2.0 * 1.25 * (2 if long else 1) + r["output_tokens"] * 12.0 * (1.5 if long else 1)) / 1e6
            est.append(r["call_index"])
        out["billed_usd"] += usd
        out["latency_s"] += r.get("latency_s") or 0
        out["calls_with_retries"] += (r.get("n_attempts") or 1) > 1
    res = dict(out)
    res["billed_usd"] = round(res.get("billed_usd", 0.0), 2)
    res["billed_usd_estimated_for_calls"] = est
    return res


def completeness(recs: list, plan: dict | None) -> dict:
    ok = Counter((r["paper_id"], r["system_a"], r["system_b"]) for r in recs if not r.get("failed"))
    res = {"recorded_ok": sum(ok.values()), "technical_failures": sum(1 for r in recs if r.get("failed")),
           "duplicates": [list(k) for k, n in ok.items() if n > 1]}
    if plan:
        planned = {(c["paper_id"], c["system_a"], c["system_b"]) for c in plan["calls"]}
        res["planned"] = len(planned)
        res["missing"] = len(planned - set(ok))
        res["unplanned"] = [list(k) for k in set(ok) - planned]
    return res


def analyze(recs: list, corr: dict, plan: dict | None = None) -> dict:
    ids = {r.get("e1_id") for r in recs}
    rubrics = {r.get("rubric_version") for r in recs}
    if len(ids) > 1 or len(rubrics) > 1:
        raise SystemExit(f"mixed runs in one file: {ids} / {rubrics}")
    out = {"e1_id": ids.pop() if ids else None, "rubric_version": rubrics.pop() if rubrics else None,
           "completeness": completeness(recs, plan), "cost": cost(recs, corr), "by_paper_set": {}}
    sets = [None] + sorted({r.get("paper_set") for r in recs if r.get("paper_set")})
    for ps in sets:
        us = units(recs, ps)
        sel = [r for r in recs if not ps or r.get("paper_set") == ps]
        block = {"papers": len({p for p, _ in us}), "criteria": {}}
        for crit in CRITERIA:
            verdicts = Counter(stable_verdict(u, crit) for u in us.values())
            complete = sum(n for v, n in verdicts.items() if v != "incomplete")
            stable = sum(n for v, n in verdicts.items() if v not in ("incomplete", "inconsistent", "unclear"))
            block["criteria"][crit] = {
                "units_complete": complete,
                "order_consistency": stable / complete if complete else None,
                "position": position(sel, crit),
                "pairs": [pair_table(us, crit, pair) for pair in itertools.combinations(SYSTEMS, 2)],
                "bradley_terry_log_strength": bradley_terry(us, crit),
                "elo": elo(us, (crit,)),
                "length": length_effect(us, crit),
            }
        add_holm_across_criteria(block["criteria"])
        block["elo_all_criteria"] = elo(us, CRITERIA)
        block["online_elo_all_criteria"] = online_elo(us, CRITERIA)
        out["by_paper_set"][ps or "all"] = block
    return out


def print_report(res: dict, paper_set: str = "all") -> None:
    c, k = res["completeness"], res["cost"]
    print(f"E1 {res['e1_id']} ({res['rubric_version']})")
    print(f"  calls: {c['recorded_ok']} ok" + (f" of {c['planned']} planned, {c['missing']} missing" if "planned" in c else "")
          + f", {c['technical_failures']} technical failures, {len(c['duplicates'])} duplicates, "
          f"{k.get('calls_with_retries', 0)} with retries")
    print(f"  cost: ${k['billed_usd']:.2f} billed | {k.get('input_tokens', 0) / 1e6:.2f}M in "
          f"({k.get('cache_read_tokens', 0) / max(k.get('input_tokens', 1), 1):.0%} cache reads) | "
          f"{k.get('output_tokens', 0):,} out | reasoning recorded for {k.get('reasoning_recorded_calls', 0)} calls"
          + (f" | estimated for calls {k['billed_usd_estimated_for_calls']}" if k["billed_usd_estimated_for_calls"] else ""))
    b = res["by_paper_set"][paper_set]
    print(f"\n[{paper_set}] {b['papers']} papers")
    for crit, d in b["criteria"].items():
        pos, ln = d["position"], d["length"]
        oc = f"{d['order_consistency']:.0%}" if d["order_consistency"] is not None else "-"
        sa = f"{pos['share_A']:.0%}" if pos["share_A"] is not None else "-"
        sl = f"{ln['share_longer_won']:.0%}" if ln["share_longer_won"] is not None else "-"
        print(f"\n  {crit}: order-consistent {oc} of {d['units_complete']} units | share A {sa} "
              f"(p={pos['sign_test_p']:.2f}) | longer report won {sl} of {ln['stable_preferences']}")
        for t in d["pairs"]:
            if not t["papers"]:
                continue
            x, y = t["pair"]
            ci = f"[{t['ci95'][0]:+.2f}, {t['ci95'][1]:+.2f}]" if t["ci95"] else ""
            print(f"    {x:12} vs {y:12} n={t['papers']:2}  {t[f'{x}_wins']:2}:{t[f'{y}_wins']:<2} "
                  f"tie {t['tie']:2} incons {t['inconsistent']:2} uncl {t['unclear']}  "
                  f"net {t['net_preference']:+.2f} {ci} p={t['sign_test_p']:.3f} "
                  f"p_holm={t['sign_test_p_holm_criteria']:.3f}")
        if d["bradley_terry_log_strength"]:
            print("    Bradley-Terry: " + "  ".join(f"{s} {v:+.2f}" for s, v in d["bradley_terry_log_strength"].items()))
        if d.get("elo"):
            _print_elo("    Elo", d["elo"])
    if b.get("elo_all_criteria"):
        print(f"\n  all five criteria pooled ({b['elo_all_criteria']['games']} games, "
              f"{b['elo_all_criteria']['papers']} papers):")
        _print_elo("    Elo (Bradley-Terry)", b["elo_all_criteria"])
        print("    online Elo, K=%d, mean of %d orders: " % (ELO_K, ELO_ORDERS)
              + "  ".join(f"{s} {v:.0f}" for s, v in b["online_elo_all_criteria"].items()))


def _print_elo(label: str, e: dict) -> None:
    print(f"{label}: " + "  ".join(f"#{r['rank']} {s} {r['elo']:.0f} [{r['ci95'][0]:.0f}, {r['ci95'][1]:.0f}]"
                                   for s, r in e["ratings"].items()))
    ranked = list(e["ratings"])
    close = [f"P({x}>{y})={e['bootstrap_share_higher'][f'{x}>{y}']:.2f}"
             for x, y in zip(ranked, ranked[1:])]
    print(" " * (len(label) - len(label.lstrip()) + 2) + "adjacent ranks, bootstrap: " + "  ".join(close))

"""Metrics of a finished run, read from its artifacts."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

import verdict as vd  # noqa: E402

VARIANTS = ("agent", "linear")

STRONG_DEGREES = ("same", "substantial")


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _usd_for(model: str, pt: int, ct: int) -> float:
    """Price a call with the agent's price table."""
    from agent.claim_agent import _usd

    return _usd(model, pt or 0, ct or 0)


def _counter(values) -> dict:
    """Counts ordered by frequency."""
    return dict(Counter(v for v in values).most_common())


def _pairs(cmp_: dict) -> dict:
    """Evidence-pair bookkeeping for one comparison, from the map diagnostics."""
    d = cmp_.get("map_diag") or {}
    return {
        "returned": d.get("returned") or 0,
        "kept": d.get("kept") or 0,
        "unverified": d.get("unverified") or 0,
        "not_owned": d.get("not_owned") or 0,
        "ownership_unchecked": d.get("ownership_unchecked") or 0,
        "call_failed": bool(d.get("call_failed")),
        "submission_chars": d.get("submission_chars") or 0,
        "paper_chars": d.get("paper_chars") or 0,
    }


def _calls(entry: dict) -> int:
    """Number of model calls of a claim, from its run log."""
    return sum(
        len(p.get("rounds") or []) for p in (entry.get("run_log") or {}).get("prior_work", [])
    )


def comparison_row(variant: str, claim_id: str, cmp_: dict) -> dict:
    """One comparison, flattened."""
    ec = cmp_.get("evidence_check") or {}
    pr = _pairs(cmp_)
    deg = vd.degree(cmp_)
    return {
        "variant": variant,
        "claim_id": claim_id,
        "paper_id": cmp_.get("paper_id", ""),
        "title": cmp_.get("title", ""),
        "year": cmp_.get("year", ""),
        "cited_by_submission": bool(cmp_.get("cited_by_submission")),
        "similarity": cmp_.get("similarity"),
        "source": cmp_.get("source", ""),
        "overlap_degree": deg,
        "is_overlap": vd.is_overlap(cmp_),
        "refutes": vd.challenges(cmp_),
        "evidence_status": vd.evidence_status(cmp_) or "no_check",
        "proposed_degree_supported": ec.get("proposed_degree_supported"),
        "evidence_prompt_version": ec.get("prompt_version") or "unversioned",
        "conflict": bool(vd.conflicts(cmp_)),
        "depth": cmp_.get("depth", ""),
        "fulltext_fetch_status": cmp_.get("fulltext_fetch_status", ""),
        "n_sections_used": len(cmp_.get("sections_used") or []),
        "n_evidence_pairs": len(cmp_.get("evidence_pairs") or []),
        **{f"pairs_{k}": v for k, v in pr.items()},
    }


def variant_metrics(sub: Path, sid: str, variant: str) -> dict | None:
    a = _load(sub / f"{sid}_artifact_a_{variant}.json")
    b = _load(sub / f"{sid}_artifact_b_{variant}.json") or {}
    if not a:
        return None

    verdicts = {e.get("claim_id"): e.get("verdict") for e in b.get("per_claim") or []}
    claims, rows = [], []
    for e in a.get("claims") or []:
        cid = e.get("claim_id", "")
        comps = e.get("comparisons") or []
        rc = e.get("run_cost") or {}
        tm = e.get("timings") or {}
        out = (e.get("run_log") or {}).get("outcome") or {}
        rows += [comparison_row(variant, cid, c) for c in comps]
        claims.append(
            {
                "claim_id": cid,
                "claim_name": e.get("claim_name", ""),
                "verdict": verdicts.get(cid),
                "stop_reason": e.get("stop_reason", ""),
                "evidence_sufficient": e.get("evidence_sufficient"),
                "review_complete": e.get("review_complete"),
                "unresolved_count": e.get("unresolved_count"),
                "n_comparisons": len(comps),
                "candidates_examined": e.get("candidates_examined"),
                "papers_by_state": out.get("papers_by_state") or {},
                "model_calls": _calls(e),
                "cost": {
                    "usd": rc.get("usd", 0.0),
                    "seconds": rc.get("seconds", 0.0),
                    "prompt_tokens": rc.get("prompt_tokens", 0),
                    "completion_tokens": rc.get("completion_tokens", 0),
                    "cached_prompt_tokens": rc.get("cached_prompt_tokens", 0),
                    "cache_hit_rate": rc.get("cache_hit_rate", 0.0),
                },
                "timings": {
                    k: tm.get(k)
                    for k in ("understand_submission", "triage", "deep_dive_total", "total")
                },
                "degrees": _counter(vd.degree(c) for c in comps),
                "evidence": _counter(vd.evidence_status(c) for c in comps),
                "depths": _counter((c.get("depth") or "-") for c in comps),
            }
        )

    model = a.get("model", "")
    pt = sum(c["cost"]["prompt_tokens"] for c in claims)
    ct = sum(c["cost"]["completion_tokens"] for c in claims)
    cached = sum(c["cost"].get("cached_prompt_tokens", 0) for c in claims)
    run_usd = round(sum(c["cost"]["usd"] for c in claims), 4)

    ps = b.get("paper_summary") or {}
    ps_usage = ps.get("usage") or {}
    ps_pt, ps_ct = ps_usage.get("prompt_tokens") or 0, ps_usage.get("completion_tokens") or 0
    ps_usd = _usd_for(ps.get("model") or model, ps_pt, ps_ct) if (ps_pt or ps_ct) else 0.0

    cfg = ((a.get("claims") or [{}])[0].get("run_log") or {}).get("config") or {}
    git = cfg.get("git") or {}
    n_cmp = len(rows)
    strong = [r for r in rows if r["overlap_degree"] in STRONG_DEGREES]
    supported = [r for r in strong if r["evidence_status"] == "material"]

    return {
        "variant": variant,
        "control_flow": a.get("control_flow", ""),
        "agentic": a.get("agentic"),
        "model": model,
        "roles": cfg.get("roles") or {},
        "closest_n": a.get("closest_n"),
        "n_related_pool": a.get("n_related_pool"),
        "git": {k: git.get(k) for k in ("commit", "branch", "dirty")},
        "n_claims": len(claims),
        "n_comparisons": n_cmp,
        "totals": {
            "run_usd": run_usd,
            "paper_summary_usd": round(ps_usd, 4),
            "total_usd": round(run_usd + ps_usd, 4),
            "seconds": round(sum(c["cost"]["seconds"] for c in claims), 1),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "model_calls": sum(c["model_calls"] for c in claims),
            "cached_prompt_tokens": cached,
            "cache_hit_rate": round(cached / pt, 3) if pt else 0.0,
        },
        "per_comparison": {
            "usd": round(run_usd / n_cmp, 4) if n_cmp else 0.0,
            "seconds": round(sum(c["cost"]["seconds"] for c in claims) / n_cmp, 1)
            if n_cmp
            else 0.0,
            "tokens": round((pt + ct) / n_cmp) if n_cmp else 0,
        },
        "paper_summary": {
            "word_count": ps.get("word_count"),
            "word_budget": ps.get("word_budget"),
            "retried_for_length": ps.get("retried_for_length"),
            "prompt_version": ps.get("prompt_version"),
            "model": ps.get("model"),
            "generated_at": ps.get("generated_at"),
            "prompt_tokens": ps_pt,
            "completion_tokens": ps_ct,
            "usd": round(ps_usd, 4),
        }
        if ps
        else {},
        "evidence_check_prompt_versions": _counter(r["evidence_prompt_version"] for r in rows),
        "distributions": {
            "degrees": _counter(r["overlap_degree"] for r in rows),
            "evidence": _counter(r["evidence_status"] for r in rows),
            "depth": _counter(r["depth"] or "-" for r in rows),
            "fulltext_fetch_status": _counter(r["fulltext_fetch_status"] or "-" for r in rows),
            "degree_x_evidence": _counter(
                f"{r['overlap_degree']} / {r['evidence_status']}" for r in rows
            ),
        },
        "findings": {
            "strong_proposed": len(strong),
            "strong_supported": len(supported),
            "partial_or_stronger": sum(
                1 for r in rows if r["overlap_degree"] in vd.OVERLAP_DEGREES
            ),
            "refutations": sum(1 for r in rows if r["refutes"]),
            "conflicts": sum(1 for r in rows if r["conflict"]),
            "evidence_pairs_returned": sum(r["pairs_returned"] for r in rows),
            "evidence_pairs_kept": sum(r["pairs_kept"] for r in rows),
            "evidence_pairs_unverified": sum(r["pairs_unverified"] for r in rows),
            "map_call_failed": sum(1 for r in rows if r["pairs_call_failed"]),
            "comparisons_on_abstract_only": sum(1 for r in rows if r["depth"] == "abstract_only"),
        },
        "claims": claims,
        "_rows": rows,
    }


def agreement(av: dict, lv: dict) -> dict:
    """Where the two control flows differ."""
    by = {v["variant"]: {(r["claim_id"], r["paper_id"]): r for r in v["_rows"]} for v in (av, lv)}
    a_keys, l_keys = set(by["agent"]), set(by["linear"])
    keys = a_keys | l_keys
    get = lambda side, k, f: (by[side].get(k) or {}).get(f) or "-"  # noqa: E731

    same_deg = sum(
        1 for k in keys if get("agent", k, "overlap_degree") == get("linear", k, "overlap_degree")
    )
    same_ev = sum(
        1 for k in keys if get("agent", k, "evidence_status") == get("linear", k, "evidence_status")
    )
    a_verd = {c["claim_id"]: c["verdict"] for c in av["claims"]}
    l_verd = {c["claim_id"]: c["verdict"] for c in lv["claims"]}
    common = [c for c in a_verd if c in l_verd]

    diffs = [
        {
            "claim_id": k[0],
            "paper_id": k[1],
            "title": (by["agent"].get(k) or by["linear"].get(k) or {}).get("title", "")[:70],
            "agent": get("agent", k, "overlap_degree"),
            "linear": get("linear", k, "overlap_degree"),
        }
        for k in sorted(keys)
        if get("agent", k, "overlap_degree") != get("linear", k, "overlap_degree")
    ]

    at, lt = av["totals"], lv["totals"]
    ratio = lambda x, y: round(x / y, 2) if y else None  # noqa: E731
    return {
        "verdicts": {
            "claims_compared": len(common),
            "agree": sum(1 for c in common if a_verd[c] == l_verd[c]),
            "per_claim": [
                {
                    "claim_id": c,
                    "agent": a_verd[c],
                    "linear": l_verd[c],
                    "agree": a_verd[c] == l_verd[c],
                }
                for c in common
            ],
        },
        "comparisons": {
            "compared": len(keys),
            "shared": len(a_keys & l_keys),
            "agent_only": len(a_keys - l_keys),
            "linear_only": len(l_keys - a_keys),
            "degree_agree": same_deg,
            "degree_agree_pct": round(100 * same_deg / len(keys), 1) if keys else None,
            "evidence_agree": same_ev,
            "evidence_agree_pct": round(100 * same_ev / len(keys), 1) if keys else None,
            "degree_differences": diffs,
        },
        "cost_ratio_agent_over_linear": {
            "usd": ratio(at["total_usd"], lt["total_usd"]),
            "seconds": ratio(at["seconds"], lt["seconds"]),
            "tokens": ratio(at["total_tokens"], lt["total_tokens"]),
            "model_calls": ratio(at["model_calls"], lt["model_calls"]),
        },
    }


def _tbl(rows: list[list], head: list[str]) -> list[str]:
    w = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    line = lambda r: "| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"  # noqa: E731
    return [line(head), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows]


def report(rec: dict) -> str:
    out = [f"# Run metrics -- {rec['submission']}", ""]
    out += [
        f"Paper: {rec['title']}",
        "",
        f"- claims: {rec['n_claims']} | retrieval pool: {rec['n_related_pool']}",
        f"- run finished: {rec.get('collected_at', '')}",
        "",
    ]

    vs = [v for v in (rec.get("variants") or {}).values()]
    if vs:
        out += ["## Cost, time and tokens", ""]
        out += _tbl(
            [
                [
                    v["variant"],
                    f"${v['totals']['total_usd']:.4f}",
                    f"{v['totals']['seconds']:.0f}s",
                    f"{v['totals']['total_tokens']:,}",
                    v["totals"]["model_calls"],
                    v["n_comparisons"],
                    f"${v['per_comparison']['usd']:.4f}",
                    f"{v['per_comparison']['seconds']:.0f}s",
                ]
                for v in vs
            ],
            [
                "variant",
                "USD ceiling",
                "time",
                "tokens",
                "calls",
                "comparisons",
                "USD/cmp",
                "s/cmp",
            ],
        )
        out += [
            "",
            "Prompt cache: "
            + " | ".join(
                f"{v['variant']} {v['totals']['cache_hit_rate']:.0%} "
                f"({v['totals']['cached_prompt_tokens']:,} of "
                f"{v['totals']['prompt_tokens']:,} prompt tokens)"
                for v in vs
            ),
            "Every USD figure prices all prompt tokens at the full rate. Cached tokens "
            "bill at a fraction of it, so these are ceilings, not amounts charged.",
        ]
        out += [
            "",
            f"Model: {vs[0]['model']} | commit {(vs[0]['git'].get('commit') or '')[:10]}"
            f"{' (dirty)' if vs[0]['git'].get('dirty') else ''}",
            "",
        ]
        vers = {v["variant"]: v.get("evidence_check_prompt_versions") or {} for v in vs}
        out += [
            "Evidence-check rubric: "
            + " | ".join(f"{k}: {', '.join(x.keys()) or '-'}" for k, x in vers.items())
        ]
        if len({tuple(sorted(x)) for x in vers.values()}) > 1:
            out += [
                "",
                "> The variants were judged by DIFFERENT evidence-check rubrics. "
                "Their comparison below mixes the control flow with that change, "
                "and is not a clean agent-vs-linear result.",
            ]
        out += [""]

        prep = rec.get("prep") or {}
        if prep.get("stages"):
            out += ["Preparation (once per paper, shared by both variants):", ""]
            out += _tbl(
                [
                    [
                        n,
                        f"${s['usd']:.4f}",
                        f"{s['seconds']:.0f}s",
                        f"{(s['prompt_tokens'] + s['completion_tokens']):,}",
                    ]
                    for n, s in prep["stages"].items()
                ],
                ["stage", "USD", "time", "tokens"],
            )
            pt_ = prep["totals"]
            tot_ = rec.get("paper_total") or {}
            out += [
                "",
                f"- preparation total: ${pt_['usd']:.4f}, {pt_['seconds']:.0f}s",
                f"- **paper end to end** (preparation + both variants): "
                f"${tot_.get('usd', 0):.4f}, {tot_.get('seconds', 0):.0f}s, "
                f"{tot_.get('tokens', 0):,} tokens",
                "",
            ]

        out += ["## What the runs found", ""]
        out += _tbl(
            [
                [
                    v["variant"],
                    v["findings"]["strong_proposed"],
                    v["findings"]["strong_supported"],
                    v["findings"]["partial_or_stronger"],
                    v["findings"]["refutations"],
                    v["findings"]["conflicts"],
                    v["findings"]["evidence_pairs_kept"],
                    v["findings"]["evidence_pairs_unverified"],
                    v["findings"]["comparisons_on_abstract_only"],
                ]
                for v in vs
            ],
            [
                "variant",
                "substantial+",
                "…of those material",
                "partial+",
                "refutations",
                "conflicts",
                "pairs kept",
                "pairs unverified",
                "abstract-only",
            ],
        )
        out += [
            "",
            "`substantial+` is degree same/substantial -- what the paper summary "
            "treats as a novelty concern; `…of those material` is the subset the "
            "evidence check backed. `partial+` is the wider band the report surfaces "
            "as overlap.",
            "",
        ]
        out += [""]
        for v in vs:
            out += [
                f"**{v['variant']}** degrees: {v['distributions']['degrees']}",
                f"**{v['variant']}** evidence: {v['distributions']['evidence']}",
                f"**{v['variant']}** reading depth: {v['distributions']['depth']}",
                "",
            ]

        out += ["## Per claim", ""]
        for v in vs:
            out += [f"### {v['variant']}", ""]
            out += _tbl(
                [
                    [
                        c["claim_id"],
                        c["verdict"] or "-",
                        c["n_comparisons"],
                        c["model_calls"],
                        f"${c['cost']['usd']:.4f}",
                        f"{c['cost']['seconds']:.0f}s",
                        c["stop_reason"] or "-",
                        c["unresolved_count"],
                    ]
                    for c in v["claims"]
                ],
                ["claim", "verdict", "cmp", "calls", "USD", "time", "stop reason", "unresolved"],
            )
            out += [""]

    ag = rec.get("agreement")
    if ag:
        out += ["## Agent vs. linear", ""]
        vr = ag["verdicts"]
        out += [f"- claim verdicts: {vr['agree']}/{vr['claims_compared']} identical"]
        cm = ag["comparisons"]
        out += [
            f"- comparisons in total: {cm['compared']} "
            f"(both: {cm['shared']}, agent only: {cm['agent_only']}, "
            f"linear only: {cm['linear_only']})",
            f"- same overlap degree: {cm['degree_agree']}/{cm['compared']}"
            f" ({cm['degree_agree_pct']}%)",
            f"- same evidence status: {cm['evidence_agree']}/{cm['compared']}"
            f" ({cm['evidence_agree_pct']}%)",
            f"- agent/linear cost: {ag['cost_ratio_agent_over_linear']}",
            "",
        ]
        if cm["degree_differences"]:
            out += ["Where the degree differed:", ""]
            out += _tbl(
                [
                    [d["claim_id"], d["title"], d["agent"], d["linear"]]
                    for d in cm["degree_differences"]
                ],
                ["claim", "paper", "agent", "linear"],
            )
            out += [""]
        if vr["per_claim"]:
            out += ["Claim verdicts side by side:", ""]
            out += _tbl(
                [
                    [
                        p["claim_id"],
                        p["agent"] or "-",
                        p["linear"] or "-",
                        "=" if p["agree"] else "DIFFERENT",
                    ]
                    for p in vr["per_claim"]
                ],
                ["claim", "agent", "linear", ""],
            )
            out += [""]
    return "\n".join(out)

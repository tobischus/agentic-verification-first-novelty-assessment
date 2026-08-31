#!/usr/bin/env python3
"""Conclusion re-scoring experiment (does a better final paragraph fix the scores?).

For each paper that the main eval already ran, this:
  1. REBUILDS ONLY THE CONCLUSION from that paper's existing Artifact A -- faithfully
     carrying the agent's per-claim verdicts (challenged / not_challenged, overlap degree,
     what-is-shared, submission-delta) and adopting a *critical reviewer* stance ("is this
     novel ENOUGH vs the closest prior work?"). The pipeline / Artifact A is NOT re-run.
  2. Re-runs the IDENTICAL LLM-as-Judge (Fig 13 + 14, same prompts.py, same model) on the
     NEW conclusion vs Afzal's ours/summary.txt, both against the human assessments.
  3. Writes a fresh report + scores + per-paper JSONs to a SEPARATE folder (eval/out_v2/),
     plus an explicit OLD-vs-NEW comparison so you can see whether the numbers improved.

It never touches the original eval/out/ outputs or conclusions. Everything is logged to the
terminal (and out_v2/run.log) so you can watch progress.

Run:  python eval/rescore_conclusions.py         (or: .\run-rescore.ps1)
"""
import argparse
import csv
import glob
import json
import logging
import os
import sys
import time
import traceback
import warnings
from pathlib import Path

# harmless langchain/pydantic serializer warning on with_structured_output
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_DATASET = (_REPO.parent.parent / "Afzal Dataset" / "data_for_release")

ap = argparse.ArgumentParser(description="Rebuild conclusions from Artifact A and re-judge")
ap.add_argument("--dataset", default=str(_DEFAULT_DATASET), help="path to data_for_release")
ap.add_argument("--src-out", default=str(_REPO / "eval" / "out"),
                help="the ORIGINAL eval run to read Artifact A + old scores from")
ap.add_argument("--out", default=str(_REPO / "eval" / "out_v2"),
                help="NEW isolated output dir (never overwrites the original)")
ap.add_argument("--ids", default=None, help="comma-separated forum_ids (default: all in src results)")
ap.add_argument("--n", type=int, default=0, help="limit to first N papers (0 = all)")
ap.add_argument("--conclusion-model", default=os.getenv("NOVELTY_CONCLUSION_MODEL", "gpt-4.1"))
ap.add_argument("--judge-model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
ap.add_argument("--force", action="store_true", help="re-do papers already scored in out_v2")
args = ap.parse_args()

SRC = Path(args.src_out)
SRC_DATA = SRC / "data"
SRC_RESULTS = SRC / "results"
OUT = Path(args.out)
CONCL_DIR = OUT / "conclusions"
RESULTS = OUT / "results"
for d in (OUT, CONCL_DIR, RESULTS):
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(_REPO / "eval"))          # prompts.py
sys.path.insert(0, str(_REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv
load_dotenv(_REPO / ".env")

LOG_PATH = OUT / "run.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("rescore")
for noisy in ("httpx", "urllib3", "openai", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:
    from langchain.callbacks import get_openai_callback


# ----------------------------------------------------------------------------- #
# small helpers (mirrors of api.py, kept local so this script stands alone)
# ----------------------------------------------------------------------------- #
def _read(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _author_year(authors: str, year) -> str:
    names = [a.strip() for a in (authors or "").split(",") if a.strip()]
    if not names:
        return ""
    surname = names[0].split()[-1] if names[0].split() else names[0]
    cite = f"{surname} et al." if len(names) > 1 else names[0]
    return f"{cite} ({year})" if year else cite


def _segments_text(segments) -> str:
    return " ".join((s.get("content") or "").strip() for s in (segments or [])
                    if (s.get("content") or "").strip())


_OVERLAP_DEGREES = ("same", "substantial", "partial")
_DEG_RANK = {"same": 3, "substantial": 2, "partial": 1, "superficial": 0, "none": 0, "": 0}


# ----------------------------------------------------------------------------- #
# NEW conclusion: critical reviewer stance, grounded in the agent's per-claim verdicts
# ----------------------------------------------------------------------------- #
CRITICAL_CONCLUSION_PROMPT = """You are a critical peer reviewer at a top ML venue (ICLR/NeurIPS) writing the concluding novelty verdict for a paper under review. Your bar is NOT "is there any contribution" — it is "is the contribution novel ENOUGH, relative to the closest prior work, to count as a genuine advance". Reviewers routinely conclude "not novel enough" when the core method is borrowed from existing work, when overlap with prior work is substantial, or when the delta over the closest baseline is only incremental.

You are given the output of a claim-by-claim novelty investigation of this paper. For EACH claimed contribution an evidence-grounded agent already reached a verdict:
- CHALLENGED = prior work was found that substantially overlaps with or refutes the claim's novelty.
- NOT CHALLENGED = no prior work delivering this contribution was found among the papers examined (the claim's novelty stands, given what was examined).
For each claim you also get what the submission does, and the overlapping prior work found (degree of overlap, what is shared, and what the submission adds beyond it).

Reach the overall verdict by WEIGHTING THE CENTRAL CONTRIBUTION — do NOT average across claims. This is how expert reviewers actually judge novelty: a paper is "not novel enough" when its core is already done by prior work, regardless of how many peripheral claims are new.
- FIRST identify the paper's central contribution (usually its main method / mechanism, or the primary claim it is built around).
- If that CENTRAL contribution is CHALLENGED — prior work already delivers it (`same`/`substantial` overlap) — conclude the novelty is INSUFFICIENT (not novel enough). Do NOT soften this to "mixed" just because secondary claims (added scope, extra experiments, framing, an evaluation protocol) are unchallenged; a new wrapper around a borrowed core is still not novel.
- Conclude MIXED only when the central contribution itself is genuinely novel but an important secondary claim is challenged, OR when the central contribution is only PARTIALLY overlapped and a real, substantive delta remains.
- Conclude the paper is clearly novel (a genuine advance) ONLY if the central contribution is NOT challenged and overlaps are at most partial/superficial.
- Do NOT invent overlap the agent did not find, and do NOT manufacture novelty the evidence does not support. Stay strictly within the evidence below.

Write ONE cohesive paragraph (roughly 120–220 words), structured like a reviewer's novelty verdict:
1. Name the paper's central contribution, and lead with the closest prior work and what it ALREADY does that this central contribution also claims (cite inline exactly as "Surname et al. (Year)" from the evidence).
2. State precisely what, if anything, the submission adds beyond that prior work (the delta) — and whether that delta is central or peripheral.
3. End with an explicit, unambiguous novelty verdict driven by the CENTRAL contribution: not novel enough / mixed / a genuine advance — not by a tally of how many claims were challenged.
Neutral, precise, evidence-based academic prose. No headings, no bullet lists, no preamble — just the paragraph.

SUBMISSION TITLE: {title}
SUBMISSION ABSTRACT: {abstract}

AGENT'S PER-CLAIM VERDICTS: {verdict_summary}

EVIDENCE BY CLAIM:
{evidence}
"""


def build_grounded_input(sid: str):
    """Assemble (title, abstract, verdict_summary, evidence) for the NEW conclusion from
    the paper's existing Artifact A. Faithful to the agent's per-claim verdicts."""
    sub = SRC_DATA / sid
    a = _read(sub / f"{sid}_artifact_a.json")
    if not a or not a.get("claims"):
        return None
    submeta = _read(sub / f"{sid}.json", {}) or {}
    claims_doc = _read(sub / f"{sid}_claims.json", {"claims": []}) or {"claims": []}
    order = [c["id"] for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]
    ranked = _read(sub / "related_work_data" / "ranked_papers.json", []) or []
    meta = {p.get("paper_id"): p for p in ranked}
    a_by = {e.get("claim_id"): e for e in a.get("claims", [])}
    if not order:                       # fall back to artifact order
        order = [e.get("claim_id") for e in a.get("claims", [])]

    blocks = []
    n_claims = n_challenged = 0
    deg_counts = {"same": 0, "substantial": 0, "partial": 0, "superficial": 0}
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        n_claims += 1
        verdict = (e.get("agent_verdict") or "").lower()
        challenged = verdict == "challenged" or (e.get("can_refute_count") or 0) > 0
        if challenged:
            n_challenged += 1
        lines = [f"CLAIM: {e.get('claim_text') or e.get('claim_name', '')}",
                 f"  AGENT VERDICT: {'CHALLENGED' if challenged else 'NOT CHALLENGED'}"
                 f" (can_refute={e.get('can_refute_count', 0)}, "
                 f"candidates_examined={e.get('candidates_examined', '?')})"]
        real = _segments_text(e.get("claim_realization"))
        if real:
            lines.append(f"  What the submission does: {real[:800]}")

        # keep the strongest overlapping/challenging comparisons (bounded prompt)
        cand = []
        for c in (e.get("comparisons") or []):
            deg = (c.get("overlap_degree") or "").lower()
            challenges = c.get("refutation_status") == "can_refute"
            if not (challenges or deg in _OVERLAP_DEGREES):
                continue
            cand.append((challenges, _DEG_RANK.get(deg, 0), c))
            if deg in deg_counts:
                deg_counts[deg] += 1
        cand.sort(key=lambda t: (t[0], t[1]), reverse=True)

        if cand:
            lines.append("  Overlapping prior work (strongest first):")
            for challenges, _, c in cand[:5]:
                _m = meta.get(c.get("paper_id"), {})
                cite = _author_year(c.get("authors") or _m.get("authors", ""),
                                    c.get("year") or _m.get("year", ""))
                head = f"{cite} — \"{c.get('title', '')}\"" if cite else f"\"{c.get('title', '')}\""
                bits = [f"overlap: {(c.get('overlap_degree') or '?').lower()}"
                        + (" (CHALLENGES the claim's novelty)" if challenges else "")]
                if c.get("what_is_shared"):
                    bits.append(f"shared: {c['what_is_shared'][:400]}")
                if c.get("submission_delta"):
                    bits.append(f"submission adds: {c['submission_delta'][:400]}")
                if c.get("assessment"):
                    bits.append(f"assessment: {c['assessment'][:300]}")
                lines.append(f"    - {head}; " + "; ".join(bits))
        else:
            lines.append("  Overlapping prior work: none of substance found among the papers "
                         "examined (no prior work delivering this contribution).")
        blocks.append("\n".join(lines))

    verdict_summary = (
        f"{n_challenged} of {n_claims} claim(s) CHALLENGED by prior work. "
        f"Overlap degrees found across claims: same x{deg_counts['same']}, "
        f"substantial x{deg_counts['substantial']}, partial x{deg_counts['partial']}, "
        f"superficial x{deg_counts['superficial']}."
    )
    return {
        "title": submeta.get("title", ""),
        "abstract": (submeta.get("abstract", "") or "")[:2500],
        "verdict_summary": verdict_summary,
        "evidence": "\n\n".join(blocks),
        "n_claims": n_claims,
        "n_challenged": n_challenged,
        "deg_counts": deg_counts,
    }


def make_conclusion_llm(model):
    from langchain_openai import ChatOpenAI
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.2}
    return ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                      max_retries=4, timeout=180, **kw)


def generate_conclusion(sid: str, llm):
    data = build_grounded_input(sid)
    if data is None:
        return None, None
    prompt = CRITICAL_CONCLUSION_PROMPT.format(
        title=data["title"], abstract=data["abstract"],
        verdict_summary=data["verdict_summary"], evidence=data["evidence"])
    with get_openai_callback() as cb:
        text = (llm.invoke(prompt).content or "").strip()
    meta = {
        "text": text, "model": args.conclusion_model,
        "n_claims": data["n_claims"], "n_challenged": data["n_challenged"],
        "verdict_summary": data["verdict_summary"],
        "cost_usd": round(cb.total_cost, 4), "tokens": cb.prompt_tokens + cb.completion_tokens,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return text, meta


# ----------------------------------------------------------------------------- #
# LLM-as-Judge (identical to run_eval.py: same prompts.py, same logic)
# ----------------------------------------------------------------------------- #
_ENGAGE = {"NONE": 0, "LIMITED": 1, "EXTENSIVE": 2}
_DEPTH = {"SURFACE": 0, "MODERATE": 1, "DEEP": 2}
_CONCL = {"INSUFFICIENT": 0, "MIXED": 1, "SUFFICIENT": 2}


def _judge_llm(model):
    from langchain_openai import ChatOpenAI
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    return ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                      max_retries=4, timeout=180, **kw)


def judge_pair(llm, reference: str, assessment: str) -> dict:
    from prompts import (FIG13_CORE_JUDGMENT_EXTRACTION, Fig13Output,
                         FIG14_NOVELTY_EVALUATION, Fig14Output)
    with get_openai_callback() as cb:
        core = llm.with_structured_output(Fig13Output).invoke(
            FIG13_CORE_JUDGMENT_EXTRACTION.format(reference_assessment=reference))
        core_text = "\n".join(f"- {c.judgment}" for c in core.core_judgments)
        ev = llm.with_structured_output(Fig14Output).invoke(
            FIG14_NOVELTY_EVALUATION.format(
                extracted_core_judgments=core_text,
                reference_assessment=reference, reviewer_assessment=assessment))
    sims = ev.judgment_similarities or []
    found = [s for s in sims if s.found_in_reviewer and s.similarity.upper() != "NOT_SIMILAR"]
    ref_c = _CONCL.get((ev.reference_conclusion or "").upper().strip(), None)
    rev_c = _CONCL.get((ev.reviewer_conclusion or "").upper().strip(), None)
    shift = 0
    if ref_c is not None and rev_c is not None:
        shift = rev_c - ref_c
    return {
        "n_core": len(sims),
        "judgment_similarity": round(sum(s.confidence for s in found) / len(sims), 3) if sims else 0.0,
        "frac_found": round(len(found) / len(sims), 3) if sims else 0.0,
        "conclusion_aligned": bool(ev.conclusion_aligned),
        "reference_conclusion": ev.reference_conclusion,
        "reviewer_conclusion": ev.reviewer_conclusion,
        "positive_shift": shift > 0, "negative_shift": shift < 0,
        "prior_work_engagement": ev.prior_work_engagement,
        "prior_work_ordinal": _ENGAGE.get((ev.prior_work_engagement or "").upper().strip(), None),
        "depth_of_analysis": ev.depth_of_analysis,
        "depth_ordinal": _DEPTH.get((ev.depth_of_analysis or "").upper().strip(), None),
        "cost_usd": round(cb.total_cost, 4),
        "tokens": cb.prompt_tokens + cb.completion_tokens,
        "core_judgments": [c.judgment for c in core.core_judgments],
    }


def judge_paper(sid: str, dataset: Path, my_conclusion: str, llm) -> dict:
    p = dataset / sid
    afzal = (p / "ours" / "summary.txt").read_text(encoding="utf-8").strip()
    humans = sorted(glob.glob(str(p / "human_novelty_assessments" / "*.txt")))
    per_ref = []
    for hp in humans:
        ref = Path(hp).read_text(encoding="utf-8").strip()
        entry = {"human_file": Path(hp).name}
        entry["afzal"] = judge_pair(llm, ref, afzal)
        entry["mine"] = judge_pair(llm, ref, my_conclusion) if my_conclusion else None
        per_ref.append(entry)
    return {"n_human_refs": len(humans), "per_ref": per_ref}


# ----------------------------------------------------------------------------- #
# Aggregation + report (with OLD-vs-NEW comparison)
# ----------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def aggregate(results: list) -> dict:
    agg = {}
    for system in ("afzal", "mine"):
        js, cf, ca, ps, ns, pw, dp = [], [], [], [], [], [], []
        for r in results:
            for pr in (r.get("judge", {}).get("per_ref", []) or []):
                s = pr.get(system)
                if not s:
                    continue
                js.append(s["judgment_similarity"]); cf.append(s["frac_found"])
                ca.append(1.0 if s["conclusion_aligned"] else 0.0)
                ps.append(1.0 if s["positive_shift"] else 0.0)
                ns.append(1.0 if s["negative_shift"] else 0.0)
                pw.append(s["prior_work_ordinal"]); dp.append(s["depth_ordinal"])
        agg[system] = {
            "n_judgments": len(js),
            "judgment_similarity": _mean(js),
            "frac_core_found": _mean(cf),
            "conclusion_agreement_pct": (round(100 * _mean(ca), 1) if ca else None),
            "positive_shift_pct": (round(100 * _mean(ps), 1) if ps else None),
            "negative_shift_pct": (round(100 * _mean(ns), 1) if ns else None),
            "prior_work_engagement_mean": _mean(pw),
            "depth_of_analysis_mean": _mean(dp),
        }
    return agg


_ROWS = [
    ("Judgment similarity (0-1)", "judgment_similarity", False, None, True),
    ("Core judgments found (0-1)", "frac_core_found", False, None, True),
    ("Conclusion agreement", "conclusion_agreement_pct", True, None, True),
    ("Positive shift (over-claims) ↓", "positive_shift_pct", True, None, False),
    ("Negative shift (under-claims) ↓", "negative_shift_pct", True, None, False),
    ("Prior-work engagement (0-2)", "prior_work_engagement_mean", False, 2, True),
    ("Depth of analysis (0-2)", "depth_of_analysis_mean", False, 2, True),
]


def _fmt(v, pct=False, scale=None):
    if v is None:
        return "-"
    if pct:
        return f"{v}%"
    return f"{v}/{scale}" if scale else f"{v}"


def write_report(results, agg, judge_cost, dataset, old_mine):
    ok = [r for r in results if not r.get("error")]
    conc_usd = sum((r.get("conclusion_meta", {}) or {}).get("cost_usd", 0.0) for r in results)

    L = [f"# Conclusion Re-scoring Experiment (v2)\n",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')} · dataset: {dataset}_\n",
         "**What changed:** only the final conclusion paragraph was rebuilt from each paper's "
         "existing Artifact A, using a *critical reviewer* prompt that faithfully carries the "
         "agent's per-claim verdicts. The pipeline / Artifact A was NOT re-run. Afzal's baseline "
         "and the human references are unchanged and re-judged with the identical Fig 13/14 judge.\n",
         f"- Papers: **{len(results)}** (succeeded: {len(ok)}) · conclusion model: "
         f"`{args.conclusion_model}` · judge model: `{args.judge_model}`",
         f"- Cost — new conclusions: ${conc_usd:.4f} · judge: ${judge_cost['usd']:.4f} · "
         f"total: ${conc_usd + judge_cost['usd']:.4f}\n"]

    # main scores: Afzal vs NEW mine
    a, m = agg["afzal"], agg["mine"]
    L.append("## Alignment scores vs. human assessments — NEW conclusion\n")
    L.append("Higher is better except the two Shift rows (lower = better calibration).\n")
    L.append("| Dimension | Afzal (baseline) | Mine v2 (critical conclusion) |")
    L.append("|---|---|---|")
    for label, key, pct, scale, _ in _ROWS:
        L.append(f"| {label} | {_fmt(a.get(key), pct, scale)} | {_fmt(m.get(key), pct, scale)} |")
    L.append(f"\n_Judgments: Afzal {a['n_judgments']}, Mine {m['n_judgments']} (paper×human-ref pairs)._\n")

    # OLD vs NEW mine
    if old_mine:
        L.append("## Did it improve? OLD vs NEW conclusion (mine only)\n")
        L.append("| Dimension | Mine v1 (original) | Mine v2 (critical) | Δ |")
        L.append("|---|---|---|---|")
        for label, key, pct, scale, higher_better in _ROWS:
            ov, nv = old_mine.get(key), m.get(key)
            delta = "-" if (ov is None or nv is None) else f"{round(nv - ov, 3):+}"
            arrow = ""
            if ov is not None and nv is not None and nv != ov:
                improved = (nv > ov) if higher_better else (nv < ov)
                arrow = " ✅" if improved else " ⚠️"
            L.append(f"| {label} | {_fmt(ov, pct, scale)} | {_fmt(nv, pct, scale)} | {delta}{arrow} |")
        L.append("")

    # per-paper verdict flips
    L.append("## Per-paper novelty verdicts (human vs Afzal vs mine v1 vs mine v2)\n")
    L.append("| forum_id | human ref | human | Afzal | mine v1 | mine v2 |")
    L.append("|---|---|---|---|---|---|")
    for r in results:
        old_by = {pr["human_file"]: pr for pr in
                  ((r.get("old_judge") or {}).get("per_ref") or [])}
        for pr in (r.get("judge", {}).get("per_ref", []) or []):
            mn, af = pr.get("mine") or {}, pr.get("afzal") or {}
            oldc = ((old_by.get(pr["human_file"], {}) or {}).get("mine") or {}).get("reviewer_conclusion", "-")
            L.append(f"| {r['sid']} | {pr['human_file']} | {af.get('reference_conclusion','-')} | "
                     f"{af.get('reviewer_conclusion','-')} | {oldc} | {mn.get('reviewer_conclusion','-')} |")

    L.append("\n> Same GPT-4.1 judge for all systems. `mine v1` = the original pipeline "
             "conclusion (from eval/out); `mine v2` = this experiment's critical, "
             "Artifact-A-grounded conclusion. Prior-work/depth judged on prose only.\n")
    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")


def write_scores_csv(results):
    rows = []
    for r in results:
        for pr in (r.get("judge", {}).get("per_ref", []) or []):
            for system in ("afzal", "mine"):
                s = pr.get(system)
                if not s:
                    continue
                rows.append({
                    "forum_id": r["sid"], "human_ref": pr["human_file"], "system": system,
                    "judgment_similarity": s["judgment_similarity"], "frac_found": s["frac_found"],
                    "conclusion_aligned": s["conclusion_aligned"],
                    "reference_conclusion": s["reference_conclusion"],
                    "reviewer_conclusion": s["reviewer_conclusion"],
                    "positive_shift": s["positive_shift"], "negative_shift": s["negative_shift"],
                    "prior_work_engagement": s["prior_work_engagement"],
                    "depth_of_analysis": s["depth_of_analysis"],
                })
    if not rows:
        return
    with (OUT / "scores.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def flush_outputs(results, judge_cost, dataset, old_mine):
    agg = aggregate(results)
    write_report(results, agg, judge_cost, dataset, old_mine)
    write_scores_csv(results)
    (OUT / "aggregate.json").write_text(json.dumps(
        {"aggregate": agg, "judge_cost": judge_cost, "n_papers": len(results)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return agg


# ----------------------------------------------------------------------------- #
# Main
# ----------------------------------------------------------------------------- #
def main():
    dataset = Path(args.dataset)
    if not dataset.exists():
        log.error(f"dataset not found: {dataset}"); sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY not set (.env)"); sys.exit(1)

    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    else:
        ids = [Path(p).stem for p in sorted(glob.glob(str(SRC_RESULTS / "*.json")))]
    if args.n:
        ids = ids[: args.n]
    if not ids:
        log.error(f"no papers found in {SRC_RESULTS} — run the main eval first."); sys.exit(1)

    old_mine = ((_read(SRC / "aggregate.json", {}) or {}).get("aggregate", {}) or {}).get("mine")

    log.info("=" * 78)
    log.info(f"CONCLUSION RE-SCORING | {len(ids)} papers | conclusion={args.conclusion_model} "
             f"judge={args.judge_model}")
    log.info(f"reading Artifact A from: {SRC_DATA}")
    log.info(f"writing NEW outputs to : {OUT}  (originals untouched)")
    if old_mine:
        log.info(f"baseline to beat (mine v1): conclusion_agreement={old_mine.get('conclusion_agreement_pct')}%  "
                 f"positive_shift={old_mine.get('positive_shift_pct')}%  "
                 f"judgment_sim={old_mine.get('judgment_similarity')}")
    log.info("=" * 78)

    concl_llm = make_conclusion_llm(args.conclusion_model)
    judge_llm = _judge_llm(args.judge_model)

    results, judge_cost = [], {"usd": 0.0, "tokens": 0}
    for i, sid in enumerate(ids, 1):
        rp = RESULTS / f"{sid}.json"
        prev = _read(rp)
        if prev and prev.get("judge", {}).get("per_ref") and not args.force:
            log.info(f"[{i}/{len(ids)}] {sid}: already re-scored in out_v2, skipping (use --force)")
            results.append(prev)
            jc = prev.get("judge", {}).get("cost", {})
            judge_cost["usd"] += jc.get("usd", 0.0); judge_cost["tokens"] += jc.get("tokens", 0)
            flush_outputs(results, judge_cost, dataset, old_mine)
            continue

        src_rec = _read(SRC_RESULTS / f"{sid}.json", {}) or {}
        rec = {"sid": sid, "steps": src_rec.get("steps", {}), "cost": src_rec.get("cost", {}),
               "old_judge": src_rec.get("judge", {}), "error": None}
        try:
            log.info(f"[{i}/{len(ids)}] {sid}: rebuilding conclusion from Artifact A ...")
            text, cmeta = generate_conclusion(sid, concl_llm)
            if not text:
                raise RuntimeError("no Artifact A / no claims to ground the conclusion on")
            rec["conclusion"] = text
            rec["conclusion_meta"] = cmeta
            # save the new conclusion separately (never overwrites the original)
            (CONCL_DIR / f"{sid}.json").write_text(
                json.dumps(cmeta, ensure_ascii=False, indent=2), encoding="utf-8")
            (CONCL_DIR / f"{sid}.txt").write_text(text, encoding="utf-8")
            log.info(f"[{i}/{len(ids)}] {sid}: new conclusion written "
                     f"({len(text.split())} words, {cmeta['n_challenged']}/{cmeta['n_claims']} claims "
                     f"challenged) -> out_v2/conclusions/{sid}.txt")

            log.info(f"[{i}/{len(ids)}] {sid}: judging (Afzal + mine v2) vs human assessment(s) ...")
            jr = judge_paper(sid, dataset, text, judge_llm)
            jr["cost"] = {
                "usd": round(sum(pr[s]["cost_usd"] for pr in jr["per_ref"]
                                 for s in ("afzal", "mine") if pr.get(s)), 4),
                "tokens": sum(pr[s]["tokens"] for pr in jr["per_ref"]
                              for s in ("afzal", "mine") if pr.get(s)),
            }
            rec["judge"] = jr
            judge_cost["usd"] += jr["cost"]["usd"]; judge_cost["tokens"] += jr["cost"]["tokens"]

            # concise per-paper progress line: the flip that matters
            for pr in jr["per_ref"]:
                mn, af = pr["mine"], pr["afzal"]
                oldc = "?"
                for opr in (src_rec.get("judge", {}).get("per_ref") or []):
                    if opr["human_file"] == pr["human_file"] and opr.get("mine"):
                        oldc = opr["mine"]["reviewer_conclusion"]
                log.info(
                    f"[{i}/{len(ids)}] {sid} {pr['human_file']}: "
                    f"human={mn['reference_conclusion']} | mine v1={oldc} -> v2={mn['reviewer_conclusion']} "
                    f"(sim {mn['judgment_similarity']}, "
                    f"shift={'+' if mn['positive_shift'] else ('-' if mn['negative_shift'] else '0')}) "
                    f"| Afzal={af['reviewer_conclusion']}")
        except Exception as e:
            log.error(f"[{i}/{len(ids)}] {sid}: FAILED — {e}\n{traceback.format_exc()}")
            rec["error"] = repr(e)[:200]

        rp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(rec)
        flush_outputs(results, judge_cost, dataset, old_mine)

    agg = flush_outputs(results, judge_cost, dataset, old_mine)

    # ---- terminal summary: the whole point of the experiment ----
    a, m = agg["afzal"], agg["mine"]
    log.info("=" * 78)
    log.info("RESULT — NEW conclusion (mine v2) vs Afzal, and vs the OLD conclusion (mine v1)")
    log.info(f"{'dimension':32} {'Afzal':>10} {'mine v1':>10} {'mine v2':>10}")
    for label, key, pct, scale, higher in _ROWS:
        ov = (old_mine or {}).get(key)
        log.info(f"{label:32} {str(a.get(key)):>10} {str(ov):>10} {str(m.get(key)):>10}")
    log.info("=" * 78)
    log.info(f"Report:  {OUT / 'report.md'}")
    log.info(f"Scores:  {OUT / 'scores.csv'}")
    log.info(f"New conclusions: {CONCL_DIR}")
    log.info(f"Judge cost: ${judge_cost['usd']:.4f} · "
             f"conclusions: ${sum((r.get('conclusion_meta',{}) or {}).get('cost_usd',0.0) for r in results):.4f}")


if __name__ == "__main__":
    main()

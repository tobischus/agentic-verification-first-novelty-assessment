#!/usr/bin/env python3
"""Grading re-derivation experiment (Step 1): does fixing the per-claim CHALLENGED rule fix
the A2 grading misses -- WITHOUT re-running the expensive agent?

Artifact A has two layers: (1) an EVIDENCE layer (the comparisons: overlap_degree,
what_is_shared, submission_delta -- gathered by the agent) and (2) a VERDICT layer
(challenged/not_challenged, DERIVED from the evidence by the rule `challenged = ∃ can_refute`).
The diagnosis found the evidence layer is sound but the verdict rule is too strict (a
substantial overlap with any differentiator -> cannot_refute -> not_challenged), and it does
not aggregate the union of partial overlaps the way human reviewers do.

This script RE-DERIVES the verdict from the EXISTING evidence (no agent re-run), then builds
the conclusion with the SAME critical central-contribution prompt used in out_v2, and re-runs
the identical Fig 13/14 judge. Baseline for the comparison = out_v2 (weighted conclusion +
OLD grading), so the delta isolates the GRADING fix alone.

  --fix A : mechanical rule -- challenged = (∃ can_refute) OR (∃ overlap_degree in {substantial, same}).
            Zero extra LLM calls. Safe, small.
  --fix B : one LLM "collective coverage" call per claim -- do these prior works TOGETHER cover
            the claim's core contribution? Captures the union-of-partial-overlaps reasoning.

If the scores jump -> the evidence was good, only the rule was bad (no re-run needed).
If they don't -> the evidence itself is insufficient (then a real agent re-run is warranted).

Writes to a SEPARATE eval/out_v3/ (A) or eval/out_v3b/ (B); never touches out/ or out_v2/.
Run:  python eval/rescore_with_grading.py --fix A     (or via run-rescore-grading.ps1)
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
from typing import List

from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_DATASET = (_REPO.parent.parent / "Afzal Dataset" / "data_for_release")

ap = argparse.ArgumentParser(description="Re-derive per-claim verdicts and re-judge")
ap.add_argument("--dataset", default=str(_DEFAULT_DATASET))
ap.add_argument("--src-out", default=str(_REPO / "eval" / "out"), help="ORIGINAL run: Artifact A source")
ap.add_argument("--baseline-out", default=str(_REPO / "eval" / "out_v2"),
                help="weighted-conclusion + OLD-grading run to compare against")
ap.add_argument("--out", default=None, help="NEW output dir (default eval/out_v3[b])")
ap.add_argument("--fix", choices=["A", "B"], default="A")
ap.add_argument("--ids", default=None)
ap.add_argument("--n", type=int, default=0)
ap.add_argument("--conclusion-model", default=os.getenv("NOVELTY_CONCLUSION_MODEL", "gpt-4.1"))
ap.add_argument("--judge-model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
ap.add_argument("--grading-model", default=os.getenv("NOVELTY_GRADING_MODEL", "gpt-4.1"),
                help="model for the --fix B collective-coverage call")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

SRC = Path(args.src_out)
SRC_DATA = SRC / "data"
BASE = Path(args.baseline_out)
OUT = Path(args.out) if args.out else (_REPO / "eval" / ("out_v3b" if args.fix == "B" else "out_v3"))
CONCL_DIR = OUT / "conclusions"
RESULTS = OUT / "results"
for d in (OUT, CONCL_DIR, RESULTS):
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(_REPO / "eval"))
from dotenv import load_dotenv
load_dotenv(_REPO / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(OUT / "run.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)], force=True)
log = logging.getLogger("grading")
for noisy in ("httpx", "urllib3", "openai", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:
    from langchain.callbacks import get_openai_callback


# ----------------------------------------------------------------------------- #
# helpers (copied so this script stands alone)
# ----------------------------------------------------------------------------- #
def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _author_year(authors, year) -> str:
    s = authors if isinstance(authors, str) else ", ".join(authors or [])
    names = [a.strip() for a in (s or "").split(",") if a.strip()]
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
_STRONG = ("substantial", "same")


# ----------------------------------------------------------------------------- #
# THE FIX: re-derive the per-claim CHALLENGED verdict from EXISTING evidence
# ----------------------------------------------------------------------------- #
def verdict_A(e, _llm=None):
    """Fix A -- mechanical. challenged = ∃ can_refute OR ∃ substantial/same overlap."""
    comps = e.get("comparisons") or []
    can_refute = (e.get("can_refute_count") or 0) > 0
    strong = [c for c in comps if (c.get("overlap_degree") or "").lower() in _STRONG]
    if can_refute:
        return True, "verified refuter (can_refute)"
    if strong:
        return True, f"{len(strong)} substantial/same overlap(s)"
    return False, "no substantial/same overlap"


class CoverageJudgment(BaseModel):
    core_contribution: str = Field(description="the claim's central/core contribution in one phrase")
    collective_coverage: str = Field(description="FULLY, PARTIALLY, or NOT -- how much of the CORE "
                                                  "contribution the prior work below COLLECTIVELY covers")
    residual_novelty: str = Field(description="what, if anything, remains genuinely novel after all prior work")
    verdict: str = Field(description="challenged (core is collectively covered / not novel enough) "
                                     "or not_challenged (a substantive part of the core stays novel)")


FIXB_PROMPT = """You are judging whether a paper's claimed contribution is novel ENOUGH, given the prior work an evidence-grounded agent already found.

A claim is CHALLENGED if prior work — either a single paper OR the UNION of several papers together — already covers the CORE of the claimed contribution, such that a critical reviewer would call it incremental / not novel enough. It is NOT_CHALLENGED only if a substantive part of the core contribution stays genuinely new after accounting for ALL the prior work below.

Rules:
- Judge the CENTRAL/core contribution, not peripheral additions (extra experiments, framing, added scope, evaluation protocol).
- Several PARTIAL overlaps that TOGETHER cover the core DO challenge the claim — this is how reviewers reason ("X does the decomposition, Y does the selection, so the combination is incremental").
- Do NOT invent overlap beyond what is stated. If the prior work genuinely leaves the core contribution novel, answer not_challenged.

CLAIM: {claim}
What the submission does: {realization}

PRIOR WORK FOUND (overlap degree; what it shares; what the submission adds beyond it):
{comparisons}
"""


def make_verdict_B(llm):
    def verdict_B(e, _llm=llm):
        comps = [c for c in (e.get("comparisons") or [])
                 if (c.get("overlap_degree") or "").lower() in _OVERLAP_DEGREES]
        if (e.get("can_refute_count") or 0) > 0:
            return True, "verified refuter (can_refute)"
        if not comps:
            return False, "no partial+ overlap to aggregate"
        comps.sort(key=lambda c: _DEG_RANK.get((c.get("overlap_degree") or "").lower(), 0), reverse=True)
        lines = []
        for c in comps[:8]:
            lines.append(f"- \"{(c.get('title') or '')[:80]}\" [overlap: {(c.get('overlap_degree') or '?').lower()}]"
                         f"; shares: {(c.get('what_is_shared') or '')[:250]}"
                         f"; submission adds: {(c.get('submission_delta') or '')[:250]}")
        prompt = FIXB_PROMPT.format(
            claim=e.get("claim_text") or e.get("claim_name", ""),
            realization=_segments_text(e.get("claim_realization"))[:700] or "(not recorded)",
            comparisons="\n".join(lines))
        try:
            res = _llm.with_structured_output(CoverageJudgment).invoke(prompt)
            ch = (res.verdict or "").lower().strip() == "challenged"
            return ch, f"{(res.collective_coverage or '?').lower()} coverage"
        except Exception as ex:
            log.warning(f"  fix-B call failed ({repr(ex)[:80]}); falling back to Fix A")
            return verdict_A(e)
    return verdict_B


# ----------------------------------------------------------------------------- #
# conclusion (SAME critical central-contribution prompt as out_v2)
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


def build_grounded_input(sid: str, verdict_fn):
    """Same evidence blocks as out_v2, but the per-claim CHALLENGED label is RE-DERIVED
    by verdict_fn (Fix A or B) instead of read from the agent's stored verdict."""
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
    if not order:
        order = [e.get("claim_id") for e in a.get("claims", [])]

    blocks, flips = [], []
    n_claims = n_challenged = 0
    deg_counts = {"same": 0, "substantial": 0, "partial": 0, "superficial": 0}
    for cid in order:
        e = a_by.get(cid)
        if e is None:
            continue
        n_claims += 1
        old_ch = (e.get("agent_verdict") or "").lower() == "challenged" or (e.get("can_refute_count") or 0) > 0
        challenged, reason = verdict_fn(e)
        if challenged:
            n_challenged += 1
        if challenged != old_ch:
            flips.append((cid, old_ch, challenged, reason))
        lines = [f"CLAIM: {e.get('claim_text') or e.get('claim_name', '')}",
                 f"  AGENT VERDICT: {'CHALLENGED' if challenged else 'NOT CHALLENGED'} ({reason})"]
        real = _segments_text(e.get("claim_realization"))
        if real:
            lines.append(f"  What the submission does: {real[:800]}")
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
            lines.append("  Overlapping prior work: none of substance found among the papers examined.")
        blocks.append("\n".join(lines))

    verdict_summary = (
        f"{n_challenged} of {n_claims} claim(s) CHALLENGED by prior work (re-derived, fix {args.fix}). "
        f"Overlap degrees across claims: same x{deg_counts['same']}, substantial x{deg_counts['substantial']}, "
        f"partial x{deg_counts['partial']}, superficial x{deg_counts['superficial']}.")
    return {"title": submeta.get("title", ""), "abstract": (submeta.get("abstract", "") or "")[:2500],
            "verdict_summary": verdict_summary, "evidence": "\n\n".join(blocks),
            "n_claims": n_claims, "n_challenged": n_challenged, "flips": flips}


def make_conclusion_llm(model):
    from langchain_openai import ChatOpenAI
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.2}
    return ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                      max_retries=4, timeout=180, **kw)


def generate_conclusion(sid, verdict_fn, llm):
    data = build_grounded_input(sid, verdict_fn)
    if data is None:
        return None, None
    prompt = CRITICAL_CONCLUSION_PROMPT.format(
        title=data["title"], abstract=data["abstract"],
        verdict_summary=data["verdict_summary"], evidence=data["evidence"])
    with get_openai_callback() as cb:
        text = (llm.invoke(prompt).content or "").strip()
    meta = {"text": text, "model": args.conclusion_model, "fix": args.fix,
            "n_claims": data["n_claims"], "n_challenged": data["n_challenged"],
            "verdict_summary": data["verdict_summary"],
            "flips": [{"claim": f[0], "old": f[1], "new": f[2], "reason": f[3]} for f in data["flips"]],
            "cost_usd": round(cb.total_cost, 4), "tokens": cb.prompt_tokens + cb.completion_tokens}
    return text, meta


# ----------------------------------------------------------------------------- #
# LLM-as-Judge (identical to run_eval.py / rescore_conclusions.py)
# ----------------------------------------------------------------------------- #
_ENGAGE = {"NONE": 0, "LIMITED": 1, "EXTENSIVE": 2}
_DEPTH = {"SURFACE": 0, "MODERATE": 1, "DEEP": 2}
_CONCL = {"INSUFFICIENT": 0, "MIXED": 1, "SUFFICIENT": 2}


def _judge_llm(model):
    from langchain_openai import ChatOpenAI
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    return ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                      max_retries=4, timeout=180, **kw)


def judge_pair(llm, reference, assessment):
    from prompts import (FIG13_CORE_JUDGMENT_EXTRACTION, Fig13Output,
                         FIG14_NOVELTY_EVALUATION, Fig14Output)
    with get_openai_callback() as cb:
        core = llm.with_structured_output(Fig13Output).invoke(
            FIG13_CORE_JUDGMENT_EXTRACTION.format(reference_assessment=reference))
        core_text = "\n".join(f"- {c.judgment}" for c in core.core_judgments)
        ev = llm.with_structured_output(Fig14Output).invoke(
            FIG14_NOVELTY_EVALUATION.format(extracted_core_judgments=core_text,
                                            reference_assessment=reference, reviewer_assessment=assessment))
    sims = ev.judgment_similarities or []
    found = [s for s in sims if s.found_in_reviewer and s.similarity.upper() != "NOT_SIMILAR"]
    ref_c = _CONCL.get((ev.reference_conclusion or "").upper().strip(), None)
    rev_c = _CONCL.get((ev.reviewer_conclusion or "").upper().strip(), None)
    shift = (rev_c - ref_c) if (ref_c is not None and rev_c is not None) else 0
    return {
        "n_core": len(sims),
        "judgment_similarity": round(sum(s.confidence for s in found) / len(sims), 3) if sims else 0.0,
        "frac_found": round(len(found) / len(sims), 3) if sims else 0.0,
        "conclusion_aligned": bool(ev.conclusion_aligned),
        "reference_conclusion": ev.reference_conclusion, "reviewer_conclusion": ev.reviewer_conclusion,
        "positive_shift": shift > 0, "negative_shift": shift < 0,
        "prior_work_engagement": ev.prior_work_engagement,
        "prior_work_ordinal": _ENGAGE.get((ev.prior_work_engagement or "").upper().strip(), None),
        "depth_of_analysis": ev.depth_of_analysis,
        "depth_ordinal": _DEPTH.get((ev.depth_of_analysis or "").upper().strip(), None),
        "cost_usd": round(cb.total_cost, 4), "tokens": cb.prompt_tokens + cb.completion_tokens,
        "core_judgments": [c.judgment for c in core.core_judgments]}


def judge_paper(sid, dataset, my_conclusion, llm):
    p = dataset / sid
    afzal = (p / "ours" / "summary.txt").read_text(encoding="utf-8").strip()
    humans = sorted(glob.glob(str(p / "human_novelty_assessments" / "*.txt")))
    per_ref = []
    for hp in humans:
        ref = Path(hp).read_text(encoding="utf-8").strip()
        per_ref.append({"human_file": Path(hp).name,
                        "afzal": judge_pair(llm, ref, afzal),
                        "mine": judge_pair(llm, ref, my_conclusion) if my_conclusion else None})
    return {"n_human_refs": len(humans), "per_ref": per_ref}


# ----------------------------------------------------------------------------- #
# aggregate + report (baseline = out_v2 mine, i.e. weighted conclusion + OLD grading)
# ----------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def aggregate(results):
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
                ps.append(1.0 if s["positive_shift"] else 0.0); ns.append(1.0 if s["negative_shift"] else 0.0)
                pw.append(s["prior_work_ordinal"]); dp.append(s["depth_ordinal"])
        agg[system] = {"n_judgments": len(js), "judgment_similarity": _mean(js), "frac_core_found": _mean(cf),
                       "conclusion_agreement_pct": (round(100 * _mean(ca), 1) if ca else None),
                       "positive_shift_pct": (round(100 * _mean(ps), 1) if ps else None),
                       "negative_shift_pct": (round(100 * _mean(ns), 1) if ns else None),
                       "prior_work_engagement_mean": _mean(pw), "depth_of_analysis_mean": _mean(dp)}
    return agg


_ROWS = [("Judgment similarity (0-1)", "judgment_similarity", False, None, True),
         ("Core judgments found (0-1)", "frac_core_found", False, None, True),
         ("Conclusion agreement", "conclusion_agreement_pct", True, None, True),
         ("Positive shift (over-claims) ↓", "positive_shift_pct", True, None, False),
         ("Negative shift (under-claims) ↓", "negative_shift_pct", True, None, False),
         ("Prior-work engagement (0-2)", "prior_work_engagement_mean", False, 2, True),
         ("Depth of analysis (0-2)", "depth_of_analysis_mean", False, 2, True)]


def _fmt(v, pct=False, scale=None):
    if v is None:
        return "-"
    return f"{v}%" if pct else (f"{v}/{scale}" if scale else f"{v}")


def _base_verdicts():
    """out_v2 mine reviewer_conclusion per (sid, ref) = the weighted+OLD-grading baseline."""
    out = {}
    for f in glob.glob(str(BASE / "results" / "*.json")):
        r = _read(f, {}) or {}
        for pr in (r.get("judge", {}).get("per_ref") or []):
            if pr.get("mine"):
                out[(r.get("sid"), pr["human_file"])] = pr["mine"].get("reviewer_conclusion", "-")
    return out


def write_report(results, agg, judge_cost, dataset, base_mine):
    m, a = agg["mine"], agg["afzal"]
    conc_usd = sum((r.get("conclusion_meta", {}) or {}).get("cost_usd", 0.0) for r in results)
    base_v = _base_verdicts()
    L = [f"# Grading Re-derivation Experiment — Fix {args.fix} (v3)\n",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')} · dataset: {dataset}_\n",
         f"**What changed vs out_v2:** ONLY the per-claim CHALLENGED verdict, re-derived from the "
         f"EXISTING Artifact-A evidence (Fix {args.fix}). The agent was NOT re-run; the conclusion "
         f"prompt (central-contribution weighting) and models are identical to out_v2, so the delta "
         f"below isolates the GRADING fix.\n",
         f"- Fix: **{args.fix}** ({'mechanical: substantial/same overlap counts as challenged' if args.fix=='A' else 'LLM collective-coverage aggregation per claim'})",
         f"- conclusion model: `{args.conclusion_model}` · judge: `{args.judge_model}`"
         + (f" · grading model: `{args.grading_model}`" if args.fix == "B" else ""),
         f"- cost — conclusions ${conc_usd:.4f} · judge ${judge_cost['usd']:.4f}\n"]

    L += ["## Scores vs. human assessments\n",
          "| Dimension | Afzal | Mine v2 (old grading) | Mine v3 (Fix %s) | Δ v2→v3 |" % args.fix,
          "|---|---|---|---|---|"]
    for label, key, pct, scale, hb in _ROWS:
        bv, nv = base_mine.get(key) if base_mine else None, m.get(key)
        d = "-" if (bv is None or nv is None) else f"{round(nv - bv, 3):+}"
        arrow = ""
        if bv is not None and nv is not None and nv != bv:
            arrow = " ✅" if ((nv > bv) if hb else (nv < bv)) else " ⚠️"
        L.append(f"| {label} | {_fmt(a.get(key), pct, scale)} | {_fmt(bv, pct, scale)} | "
                 f"{_fmt(nv, pct, scale)} | {d}{arrow} |")
    L.append(f"\n_Judgments: {m['n_judgments']} (paper×human-ref). Baseline = out_v2._\n")

    L += ["## Per-paper verdicts (human vs v2 old-grading vs v3 new-grading)\n",
          "| forum_id | ref | human | Afzal | mine v2 | mine v3 | claims re-challenged |",
          "|---|---|---|---|---|---|---|"]
    for r in results:
        nflips = len((r.get("conclusion_meta", {}) or {}).get("flips", []))
        for pr in (r.get("judge", {}).get("per_ref", []) or []):
            mn, af = pr.get("mine") or {}, pr.get("afzal") or {}
            bv = base_v.get((r["sid"], pr["human_file"]), "-")
            L.append(f"| {r['sid']} | {pr['human_file']} | {mn.get('reference_conclusion','-')} | "
                     f"{af.get('reviewer_conclusion','-')} | {bv} | {mn.get('reviewer_conclusion','-')} | {nflips} |")
    L.append("\n> `claims re-challenged` = how many claims Fix %s flipped not_challenged→challenged "
             "(or back) vs the agent's stored verdict. If the scores jump, the evidence was sound and "
             "only the rule was wrong (no agent re-run needed).\n" % args.fix)
    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")


def write_scores_csv(results):
    rows = []
    for r in results:
        for pr in (r.get("judge", {}).get("per_ref", []) or []):
            for system in ("afzal", "mine"):
                s = pr.get(system)
                if not s:
                    continue
                rows.append({"forum_id": r["sid"], "human_ref": pr["human_file"], "system": system,
                             "judgment_similarity": s["judgment_similarity"], "frac_found": s["frac_found"],
                             "conclusion_aligned": s["conclusion_aligned"],
                             "reference_conclusion": s["reference_conclusion"],
                             "reviewer_conclusion": s["reviewer_conclusion"],
                             "positive_shift": s["positive_shift"], "negative_shift": s["negative_shift"],
                             "prior_work_engagement": s["prior_work_engagement"],
                             "depth_of_analysis": s["depth_of_analysis"]})
    if rows:
        with (OUT / "scores.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)


def flush_outputs(results, judge_cost, dataset, base_mine):
    agg = aggregate(results)
    write_report(results, agg, judge_cost, dataset, base_mine)
    write_scores_csv(results)
    (OUT / "aggregate.json").write_text(json.dumps(
        {"aggregate": agg, "judge_cost": judge_cost, "fix": args.fix, "n_papers": len(results)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return agg


# ----------------------------------------------------------------------------- #
# main
# ----------------------------------------------------------------------------- #
def main():
    dataset = Path(args.dataset)
    if not dataset.exists():
        log.error(f"dataset not found: {dataset}"); sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY not set"); sys.exit(1)

    ids = ([x.strip() for x in args.ids.split(",") if x.strip()] if args.ids
           else [Path(p).stem for p in sorted(glob.glob(str(SRC / "results" / "*.json")))])
    if args.n:
        ids = ids[: args.n]
    if not ids:
        log.error(f"no papers in {SRC/'results'} — run the main eval first."); sys.exit(1)

    base_mine = ((_read(BASE / "aggregate.json", {}) or {}).get("aggregate", {}) or {}).get("mine")

    log.info("=" * 82)
    log.info(f"GRADING RE-DERIVATION | Fix {args.fix} | {len(ids)} papers | "
             f"conclusion={args.conclusion_model} judge={args.judge_model}"
             + (f" grading={args.grading_model}" if args.fix == "B" else ""))
    log.info(f"reading Artifact A from : {SRC_DATA}   (agent NOT re-run)")
    log.info(f"baseline (out_v2)       : {BASE}")
    log.info(f"writing NEW outputs to  : {OUT}")
    if base_mine:
        log.info(f"baseline to beat (mine v2, weighted conclusion + OLD grading): "
                 f"agreement={base_mine.get('conclusion_agreement_pct')}%  "
                 f"pos_shift={base_mine.get('positive_shift_pct')}%  neg_shift={base_mine.get('negative_shift_pct')}%")
    log.info("=" * 82)

    concl_llm = make_conclusion_llm(args.conclusion_model)
    judge_llm = _judge_llm(args.judge_model)
    verdict_fn = verdict_A if args.fix == "A" else make_verdict_B(_judge_llm(args.grading_model))

    results, judge_cost = [], {"usd": 0.0, "tokens": 0}
    for i, sid in enumerate(ids, 1):
        rp = RESULTS / f"{sid}.json"
        prev = _read(rp)
        if prev and prev.get("judge", {}).get("per_ref") and not args.force:
            log.info(f"[{i}/{len(ids)}] {sid}: already done, skipping (--force to redo)")
            results.append(prev)
            jc = prev.get("judge", {}).get("cost", {})
            judge_cost["usd"] += jc.get("usd", 0.0); judge_cost["tokens"] += jc.get("tokens", 0)
            flush_outputs(results, judge_cost, dataset, base_mine)
            continue

        src_rec = _read(SRC / "results" / f"{sid}.json", {}) or {}
        rec = {"sid": sid, "steps": src_rec.get("steps", {}), "cost": src_rec.get("cost", {}), "error": None}
        try:
            log.info(f"[{i}/{len(ids)}] {sid}: re-deriving verdicts (Fix {args.fix}) + conclusion ...")
            text, cmeta = generate_conclusion(sid, verdict_fn, concl_llm)
            if not text:
                raise RuntimeError("no Artifact A to ground on")
            rec["conclusion"] = text
            rec["conclusion_meta"] = cmeta
            (CONCL_DIR / f"{sid}.txt").write_text(text, encoding="utf-8")
            (CONCL_DIR / f"{sid}.json").write_text(json.dumps(cmeta, ensure_ascii=False, indent=2), encoding="utf-8")
            fl = cmeta["flips"]
            log.info(f"[{i}/{len(ids)}] {sid}: {cmeta['n_challenged']}/{cmeta['n_claims']} claims challenged "
                     f"(re-derived); {len(fl)} flip(s)"
                     + (": " + ", ".join(f"{f['claim']} {f['old']}→{f['new']} [{f['reason']}]" for f in fl) if fl else ""))

            jr = judge_paper(sid, dataset, text, judge_llm)
            jr["cost"] = {"usd": round(sum(pr[s]["cost_usd"] for pr in jr["per_ref"]
                                           for s in ("afzal", "mine") if pr.get(s)), 4),
                          "tokens": sum(pr[s]["tokens"] for pr in jr["per_ref"]
                                        for s in ("afzal", "mine") if pr.get(s))}
            rec["judge"] = jr
            judge_cost["usd"] += jr["cost"]["usd"]; judge_cost["tokens"] += jr["cost"]["tokens"]
            for pr in jr["per_ref"]:
                mn = pr["mine"]
                bv = _base_verdicts().get((sid, pr["human_file"]), "?")
                log.info(f"[{i}/{len(ids)}] {sid} {pr['human_file']}: human={mn['reference_conclusion']} | "
                         f"v2={bv} → v3={mn['reviewer_conclusion']} "
                         f"(shift={'+' if mn['positive_shift'] else ('-' if mn['negative_shift'] else '0')}, "
                         f"sim {mn['judgment_similarity']})")
        except Exception as ex:
            log.error(f"[{i}/{len(ids)}] {sid}: FAILED — {ex}\n{traceback.format_exc()}")
            rec["error"] = repr(ex)[:200]

        rp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(rec)
        flush_outputs(results, judge_cost, dataset, base_mine)

    agg = flush_outputs(results, judge_cost, dataset, base_mine)
    m = agg["mine"]
    log.info("=" * 82)
    log.info(f"RESULT — Fix {args.fix}: mine v3 (new grading) vs mine v2 (old grading) vs Afzal")
    log.info(f"{'dimension':32} {'Afzal':>9} {'v2 (old)':>10} {'v3 (Fix '+args.fix+')':>12}")
    for label, key, pct, scale, hb in _ROWS:
        bv = (base_mine or {}).get(key)
        log.info(f"{label:32} {str(agg['afzal'].get(key)):>9} {str(bv):>10} {str(m.get(key)):>12}")
    total_flips = sum(len((r.get("conclusion_meta", {}) or {}).get("flips", [])) for r in results)
    log.info("-" * 82)
    log.info(f"claims re-challenged by Fix {args.fix}: {total_flips} across {len(results)} papers")
    log.info(f"Report: {OUT / 'report.md'}  ·  conclusions: {CONCL_DIR}")
    log.info("=" * 82)


if __name__ == "__main__":
    main()

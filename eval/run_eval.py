#!/usr/bin/env python3
"""First evaluation run: my agentic pipeline vs. Afzal's baseline, judged against the
human novelty assessments (Afzal et al. 2026 dataset).

For each eligible dataset paper (has a local PDF + a human_novelty_assessment + Afzal's
ours/summary.txt) it:
  1. runs MY full pipeline autonomously (GROBID doc processing -> claim extraction ->
     retrieval -> PDF download -> per-claim agentic review -> overall conclusion),
     logging every step (did GROBID parse the submission? were PDFs found? how many
     claims / comparisons? etc.) and tracking token cost;
  2. runs the LLM-as-Judge (Fig 13 + Fig 14, GPT-4.1) TWICE against each human
     assessment: once for Afzal's summary, once for MY conclusion;
  3. aggregates the four alignment dimensions and writes a human-readable report,
     a per-paper JSON, and a scores CSV.

Resumable: papers with a completed result JSON are skipped, so re-running continues.
Robust: a failure on one paper is logged and the run moves on.

Run it via run-eval.ps1 (sets env + checks GROBID), or directly:
  python eval/run_eval.py --n 18
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

# harmless: langchain's with_structured_output triggers a pydantic serializer warning
# ("Expected `none` but got `Fig13Output`") even though parsing succeeds.
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# ----------------------------------------------------------------------------- #
# Paths / args first, because api.py reads NOVELTY_DATA_DIR at import time.
# ----------------------------------------------------------------------------- #
_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_DATASET = (_REPO.parent.parent / "Afzal Dataset" / "data_for_release")

ap = argparse.ArgumentParser(description="First novelty-assessment evaluation run")
ap.add_argument("--dataset", default=str(_DEFAULT_DATASET), help="path to data_for_release")
ap.add_argument("--out", default=str(_REPO / "eval" / "out"), help="output/working dir")
ap.add_argument("--n", type=int, default=18, help="number of papers to evaluate")
ap.add_argument("--ids", default=None, help="comma-separated forum_ids (overrides --n selection)")
ap.add_argument("--judge-model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
ap.add_argument("--model", default=os.getenv("NOVELTY_MODEL", "gpt-4.1-mini"), help="pipeline LLM")
ap.add_argument("--grobid-server", default=os.getenv("GROBID_SERVER", "http://localhost:8070"))
ap.add_argument("--skip-judge", action="store_true", help="run the pipeline only, no LLM judge")
args = ap.parse_args()

OUT = Path(args.out)
DATA_DIR = OUT / "data"          # NOVELTY_DATA_DIR: flat per-paper pipeline outputs
RESULTS = OUT / "results"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)
os.environ["NOVELTY_DATA_DIR"] = str(DATA_DIR)
os.environ.setdefault("NOVELTY_MODEL", args.model)

sys.path.insert(0, str(_REPO / "src" / "novelty_assessment"))
sys.path.insert(0, str(_REPO / "eval"))

from dotenv import load_dotenv
load_dotenv(_REPO / ".env")

# ----------------------------------------------------------------------------- #
# Logging: console + run.log (pipeline modules log via the root logger too).
# ----------------------------------------------------------------------------- #
LOG_PATH = OUT / "run.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("eval")
# quieten noisy http libs
for noisy in ("httpx", "urllib3", "openai", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


try:
    from langchain_community.callbacks import get_openai_callback
except ImportError:  # older langchain
    from langchain.callbacks import get_openai_callback


# ----------------------------------------------------------------------------- #
# Paper selection
# ----------------------------------------------------------------------------- #
def eligible_papers(dataset: Path):
    """forum_ids that have a local PDF + >=1 human assessment + Afzal's summary."""
    out = []
    for d in sorted(os.listdir(dataset)):
        p = dataset / d
        if not p.is_dir() or d.startswith("."):
            continue
        pdf = p / f"{d}.pdf"
        humans = sorted(glob.glob(str(p / "human_novelty_assessments" / "*.txt")))
        summ = p / "ours" / "summary.txt"
        if pdf.exists() and humans and summ.exists():
            out.append(d)
    return out


# ----------------------------------------------------------------------------- #
# My pipeline (autonomous)
# ----------------------------------------------------------------------------- #
def _read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_my_pipeline(sid: str, pdf: Path, embedder) -> dict:
    """Run stages 1-4 + per-claim agent + conclusion. Returns a step/cost record."""
    from orchestrator import NoveltyPipeline
    from agent.claim_agent import ClaimNoveltyAgent
    import api

    sub = DATA_DIR / sid
    rec = {"sid": sid, "steps": {}, "cost": {}, "error": None}

    # ---- stages 1-4 (autonomous, resumable) ----
    t0 = time.time()
    pipe = NoveltyPipeline(
        str(DATA_DIR), sid, pdf_path=str(pdf), model=args.model,
        grobid_server=args.grobid_server, hitl=False,
    )
    state = pipe.run()
    rec["steps"]["pipeline_status"] = state.get("status")
    if state.get("status") != "completed":
        rec["error"] = f"pipeline stopped at {state.get('status')}: {state.get('last_error')}"
        rec["steps"]["stages_done"] = state.get("stages_done", [])
        return rec

    # ---- collect what happened in stages 1-4 ----
    quality = _read(sub / f"{sid}_quality.json", {})
    submeta = _read(sub / f"{sid}.json", {})
    claims_doc = _read(sub / f"{sid}_claims.json", {"claims": []})
    ranked = _read(sub / "related_work_data" / "ranked_papers.json", [])
    pdf_status = _read(sub / f"{sid}_pdf_status.json", {})
    claims = [c for c in claims_doc.get("claims", []) if c.get("status") != "rejected"]

    rec["steps"].update({
        "grobid_ok": bool(submeta.get("title")),
        "title": (submeta.get("title") or "")[:120],
        "title_source": submeta.get("title_source"),
        "abstract_chars": len(submeta.get("abstract") or ""),
        "publication_date": submeta.get("publication_date"),
        "date_source": submeta.get("date_source"),
        "quality": quality,
        "n_claims": len(claims),
        "n_ranked_papers": len(ranked),
        "n_pdfs_with": pdf_status.get("n_with_pdf"),
        "n_pdfs_total": pdf_status.get("n_total"),
    })

    # ---- per-claim agentic review (own loop: artifact_a only, no B/Judge/report) ----
    budgets = {
        "max_retrievals": int(os.getenv("NOVELTY_AGENT_MAX_RETRIEVALS", "1")),
        "closest_n": int(os.getenv("NOVELTY_AGENT_CLOSEST_N", "10")),
    }
    agent = ClaimNoveltyAgent(
        str(DATA_DIR), sid, embedder=embedder, model_name=args.model,
        grobid_server=args.grobid_server, **budgets,
    )
    # RESUMABLE: reuse a complete artifact_a from a prior (interrupted) run instead of
    # re-running the (expensive) agent -- only the missing pieces are recomputed.
    a_path = sub / f"{sid}_artifact_a.json"
    claim_ids = {c["id"] for c in claims}
    cached = _read(a_path)
    if cached and claim_ids and {e.get("claim_id") for e in cached.get("claims", [])} >= claim_ids:
        entries = [e for e in cached.get("claims", []) if e.get("claim_id") in claim_ids]
        rec["steps"]["agent_reused_cache"] = True
        log.info(f"[{sid}] reusing cached artifact_a ({len(entries)} claims) -- agent skipped")
    else:
        entries = []
        n_cl = len(claims)
        for j, c in enumerate(claims, 1):
            log.info(f"[{sid}] claim {j}/{n_cl} '{c.get('name','')[:60]}' -> agent running ...")
            t_cl = time.time()
            e = agent.run(c)
            entries.append(e)
            log.info(
                f"[{sid}] claim {j}/{n_cl} done in {time.time()-t_cl:.0f}s "
                f"(verdict={e.get('agent_verdict','?')}, "
                f"examined={e.get('candidates_examined','?')}, "
                f"comparisons={len(e.get('comparisons',[]))}, "
                f"can_refute={e.get('can_refute_count','?')}, "
                f"evidence_sufficient={e.get('evidence_sufficient','?')}, "
                f"stop={e.get('stop_reason','?')})"
            )
        artifact_a = {
            "submission_id": sid, "agentic": True, "closest_n": budgets["closest_n"],
            "n_related_pool": max((sum(e.get("pool_sources", {}).values()) for e in entries), default=0),
            "claims": entries,
        }
        a_path.write_text(json.dumps(artifact_a, ensure_ascii=False, indent=2), encoding="utf-8")

    agent_pt = agent_ct = 0
    agent_usd = 0.0
    per_claim = []
    for e in entries:
        cost = e.get("cost", {})
        agent_pt += cost.get("prompt_tokens", 0)
        agent_ct += cost.get("completion_tokens", 0)
        agent_usd += cost.get("usd", 0.0)
        comps = e.get("comparisons", []) or []
        overlaps = [x for x in comps if x.get("refutation_status") == "can_refute"
                    or (x.get("overlap_degree") or "").lower() in ("same", "substantial", "partial")]
        per_claim.append({
            "claim_id": e.get("claim_id"), "verdict": e.get("agent_verdict"),
            "evidence_sufficient": e.get("evidence_sufficient"),
            "n_comparisons": len(comps), "n_overlap": len(overlaps),
            "deep_dives": len((e.get("timings") or {}).get("deep_dive_papers", [])),
        })
    rec["steps"]["per_claim"] = per_claim

    # ---- overall novelty conclusion (my comparable assessment artifact) ----
    # RESUMABLE: reuse the cached conclusion if it was already generated.
    conc_usd = conc_pt = conc_ct = 0
    conclusion = None
    try:
        cached_c = api.get_conclusion(sid)
        if cached_c and cached_c.get("text"):
            conclusion = cached_c["text"]
            log.info(f"[{sid}] reusing cached conclusion")
        else:
            with get_openai_callback() as cb:
                out = api.generate_conclusion(sid)
            conclusion = out.get("text")
            conc_usd, conc_pt, conc_ct = cb.total_cost, cb.prompt_tokens, cb.completion_tokens
    except Exception as e:
        log.warning(f"[{sid}] conclusion failed: {repr(e)[:160]}")
    rec["steps"]["conclusion_ok"] = bool(conclusion)
    rec["conclusion"] = conclusion or ""

    # ---- cost roll-up ----
    metrics = (_read(sub / f"{sid}_pipeline_state.json", {}) or {}).get("metrics", {})
    stage_usd = sum((metrics.get(n, {}) or {}).get("usd", 0.0)
                    for n in ("document_processing", "claim_extraction", "retrieval", "fetch_pdfs"))
    stage_pt = sum((metrics.get(n, {}) or {}).get("prompt_tokens", 0)
                   for n in ("document_processing", "claim_extraction", "retrieval", "fetch_pdfs"))
    stage_ct = sum((metrics.get(n, {}) or {}).get("completion_tokens", 0)
                   for n in ("document_processing", "claim_extraction", "retrieval", "fetch_pdfs"))
    rw_meta = _read(sub / "related_work_data" / "metadata.json", {}) or {}
    retr_extra = float(rw_meta.get("total_cost") or 0.0)  # keyword+RankGPT (litellm), additive

    rec["cost"] = {
        "stages_usd": round(stage_usd + retr_extra, 4),
        "stages_prompt_tokens": stage_pt, "stages_completion_tokens": stage_ct,
        "agent_usd": round(agent_usd, 4), "agent_prompt_tokens": agent_pt, "agent_completion_tokens": agent_ct,
        "conclusion_usd": round(conc_usd, 4), "conclusion_prompt_tokens": conc_pt, "conclusion_completion_tokens": conc_ct,
        "total_usd": round(stage_usd + retr_extra + agent_usd + conc_usd, 4),
        "total_tokens": stage_pt + stage_ct + agent_pt + agent_ct + conc_pt + conc_ct,
        "model": args.model,
    }
    rec["steps"]["elapsed_s"] = round(time.time() - t0, 1)
    return rec


# ----------------------------------------------------------------------------- #
# LLM-as-Judge (Fig 13 + Fig 14)
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
    """Two-stage judge of `assessment` against `reference`. Returns parsed scores + cost."""
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
        shift = rev_c - ref_c  # >0 over-claims novelty (positive), <0 under-claims (negative)
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
    """Judge Afzal's summary AND my conclusion against every human assessment of the paper."""
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
# Aggregation
# ----------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def aggregate(results: list) -> dict:
    """Mean per-system scores over all (paper, human-ref) judgments."""
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


# ----------------------------------------------------------------------------- #
# Report writing
# ----------------------------------------------------------------------------- #
def write_report(results, agg, judge_cost, dataset):
    ok = [r for r in results if not r.get("error")]
    failed = [r for r in results if r.get("error")]
    pipe_usd = sum((r.get("cost", {}) or {}).get("total_usd", 0.0) for r in results)
    pipe_tok = sum((r.get("cost", {}) or {}).get("total_tokens", 0) for r in results)

    L = []
    L.append(f"# First Evaluation Run\n")
    L.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')} · dataset: {dataset}_\n")
    L.append(f"- Papers attempted: **{len(results)}** · succeeded: **{len(ok)}** · failed: **{len(failed)}**")
    L.append(f"- Pipeline model: `{args.model}` · Judge model: `{args.judge_model}`\n")

    # cost
    L.append("## Cost\n")
    L.append(f"- **My pipeline (all papers):** ${pipe_usd:.4f} · {pipe_tok:,} tokens")
    L.append(f"- **LLM-as-Judge (Afzal + mine, all refs):** ${judge_cost['usd']:.4f} · {judge_cost['tokens']:,} tokens")
    L.append(f"- **Grand total:** ${pipe_usd + judge_cost['usd']:.4f}\n")

    # per-paper pipeline health
    L.append("## Pipeline run (what worked)\n")
    L.append("| forum_id | status | GROBID | claims | ranked | PDFs | conclusion | $ | time |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        s = r.get("steps", {})
        c = r.get("cost", {})
        stat = "✅" if not r.get("error") else "❌"
        grob = "✓" if s.get("grobid_ok") else "✗"
        conc = "✓" if s.get("conclusion_ok") else "✗"
        pdfs = f"{s.get('n_pdfs_with','?')}/{s.get('n_pdfs_total','?')}"
        L.append(f"| {r['sid']} | {stat} {s.get('pipeline_status','-')} | {grob} | "
                 f"{s.get('n_claims','-')} | {s.get('n_ranked_papers','-')} | {pdfs} | {conc} | "
                 f"${c.get('total_usd',0):.3f} | {s.get('elapsed_s','-')}s |")
    if failed:
        L.append("\n### Failures\n")
        for r in failed:
            L.append(f"- **{r['sid']}**: {r['error']}")

    # scores
    L.append("\n## Alignment scores vs. human assessments (LLM-as-Judge)\n")
    L.append("Higher is better except the two Shift rows (lower = better calibration).\n")
    a, m = agg["afzal"], agg["mine"]
    L.append("| Dimension | Afzal (baseline) | Mine (agentic) |")
    L.append("|---|---|---|")
    def row(label, key, pct=False, scale=None):
        av, mv = a.get(key), m.get(key)
        fmt = lambda v: ("-" if v is None else (f"{v}%" if pct else (f"{v}/{scale}" if scale else f"{v}")))
        L.append(f"| {label} | {fmt(av)} | {fmt(mv)} |")
    row("Judgment similarity (0-1)", "judgment_similarity")
    row("Core judgments found (0-1)", "frac_core_found")
    row("Conclusion agreement", "conclusion_agreement_pct", pct=True)
    row("Positive shift (over-claims) ↓", "positive_shift_pct", pct=True)
    row("Negative shift (under-claims) ↓", "negative_shift_pct", pct=True)
    row("Prior-work engagement (0-2)", "prior_work_engagement_mean", scale=2)
    row("Depth of analysis (0-2)", "depth_of_analysis_mean", scale=2)
    L.append(f"\n_Judgments: Afzal {a['n_judgments']}, Mine {m['n_judgments']} (paper×human-ref pairs)._\n")
    L.append("> Note: my assessment = the pipeline's overall **conclusion** paragraph; "
             "Afzal's = `ours/summary.txt`; reference = `human_novelty_assessments/*.txt`. "
             "Same GPT-4.1 judge for both. Prior-work engagement / depth are judged on the "
             "prose only — the pipeline's richer per-claim verified evidence is not shown to "
             "the judge here, to keep the comparison prose-to-prose.\n")

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
                    "reference_conclusion": s["reference_conclusion"], "reviewer_conclusion": s["reviewer_conclusion"],
                    "positive_shift": s["positive_shift"], "negative_shift": s["negative_shift"],
                    "prior_work_engagement": s["prior_work_engagement"], "depth_of_analysis": s["depth_of_analysis"],
                })
    if not rows:
        return
    with (OUT / "scores.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def flush_outputs(results, judge_cost, dataset):
    """(Re)write report.md + scores.csv + aggregate.json from all results so far, so the
    CSV/report always reflect live progress and survive an interruption."""
    agg = aggregate(results)
    write_report(results, agg, judge_cost, dataset)
    write_scores_csv(results)
    (OUT / "aggregate.json").write_text(json.dumps(
        {"aggregate": agg, "judge_cost": judge_cost,
         "pipeline_cost_usd": round(sum((r.get('cost', {}) or {}).get('total_usd', 0.0) for r in results), 4),
         "n_papers": len(results)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return agg


# ----------------------------------------------------------------------------- #
# Main
# ----------------------------------------------------------------------------- #
def main():
    dataset = Path(args.dataset)
    if not dataset.exists():
        log.error(f"dataset not found: {dataset}"); sys.exit(1)

    # prerequisites
    if not os.getenv("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY not set (.env)"); sys.exit(1)
    try:
        import requests
        alive = requests.get(f"{args.grobid_server}/api/isalive", timeout=5).text.strip()
        log.info(f"GROBID {args.grobid_server} isalive={alive}")
        if alive.lower() != "true":
            raise RuntimeError(f"isalive returned {alive!r}")
    except Exception as e:
        log.error(f"GROBID not reachable at {args.grobid_server}: {repr(e)[:120]} "
                  f"-- start it (see Start.txt) before the eval."); sys.exit(1)

    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    else:
        ids = eligible_papers(dataset)[: args.n]
    log.info(f"selected {len(ids)} papers: {ids}")

    from agent.claim_agent import _get_embedder
    embedder = _get_embedder()
    llm = _judge_llm(args.judge_model) if not args.skip_judge else None

    def is_scored(rec):
        # "done" = the final score comparison exists (unless the judge is disabled, in
        # which case a completed pipeline with a conclusion is enough).
        if not rec:
            return False
        if args.skip_judge:
            return bool(rec.get("conclusion")) and not rec.get("error")
        return bool(rec.get("judge", {}).get("per_ref"))

    results, judge_cost = [], {"usd": 0.0, "tokens": 0}
    for i, sid in enumerate(ids, 1):
        rp = RESULTS / f"{sid}.json"
        prev = _read(rp) if rp.exists() else None
        if is_scored(prev):
            log.info(f"[{i}/{len(ids)}] {sid}: already scored, skipping")
            results.append(prev)
            jc = prev.get("judge", {}).get("cost", {})
            judge_cost["usd"] += jc.get("usd", 0.0); judge_cost["tokens"] += jc.get("tokens", 0)
            flush_outputs(results, judge_cost, dataset)
            continue

        log.info(f"===== [{i}/{len(ids)}] {sid} : running my pipeline =====")
        try:
            rec = run_my_pipeline(sid, dataset / sid / f"{sid}.pdf", embedder)
        except Exception as e:
            log.error(f"[{sid}] pipeline crashed: {e}\n{traceback.format_exc()}")
            rec = {"sid": sid, "steps": {}, "cost": {}, "error": f"crash: {repr(e)[:200]}"}

        # judge IMMEDIATELY after the paper's output is ready, and persist -> the CSV shows
        # this paper's Afzal-vs-mine scores right away.
        if not args.skip_judge and not rec.get("error") and rec.get("conclusion"):
            log.info(f"[{sid}] judging Afzal + mine against {sid} human assessment(s)")
            try:
                jr = judge_paper(sid, dataset, rec.get("conclusion", ""), llm)
                jcost = sum(pr[s]["cost_usd"] for pr in jr["per_ref"] for s in ("afzal", "mine") if pr.get(s))
                jtok = sum(pr[s]["tokens"] for pr in jr["per_ref"] for s in ("afzal", "mine") if pr.get(s))
                jr["cost"] = {"usd": round(jcost, 4), "tokens": jtok}
                rec["judge"] = jr
                judge_cost["usd"] += jcost; judge_cost["tokens"] += jtok
            except Exception as e:
                log.error(f"[{sid}] judge failed: {e}")
                rec["judge_error"] = repr(e)[:200]

        rp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(rec)
        # write CSV + report + aggregate NOW so progress is visible after every paper
        flush_outputs(results, judge_cost, dataset)
        c = rec.get("cost", {})
        j = rec.get("judge", {}).get("per_ref")
        log.info(f"[{i}/{len(ids)}] {sid} DONE: status={rec.get('steps',{}).get('pipeline_status')} "
                 f"claims={rec.get('steps',{}).get('n_claims')} "
                 f"cost=${c.get('total_usd',0):.3f} judged={'yes' if j else 'no'} error={rec.get('error')} "
                 f"-> scores.csv updated")

    agg = flush_outputs(results, judge_cost, dataset)
    log.info("=" * 70)
    log.info(f"DONE. {len([r for r in results if not r.get('error')])}/{len(results)} papers succeeded.")
    log.info(f"Report:  {OUT / 'report.md'}")
    log.info(f"Scores:  {OUT / 'scores.csv'}")
    log.info(f"Pipeline cost: ${sum((r.get('cost',{}) or {}).get('total_usd',0.0) for r in results):.4f} | "
             f"Judge cost: ${judge_cost['usd']:.4f}")
    if agg.get("mine", {}).get("n_judgments"):
        m, a = agg["mine"], agg["afzal"]
        log.info(f"Conclusion agreement -- Mine: {m['conclusion_agreement_pct']}%  Afzal: {a['conclusion_agreement_pct']}%")


if __name__ == "__main__":
    main()

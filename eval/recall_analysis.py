#!/usr/bin/env python3
"""Recall analysis: when a human reviewer judged a paper 'not novel enough', did my
retrieval pool actually contain the prior work they based that on -- and if so, did my
agent grade the overlap high enough?

This quantifies the real bottleneck found by the conclusion re-scoring experiment: the
pipeline over-claims novelty exactly on papers where Artifact A found 0 challenged claims.
That can have THREE distinct causes, which this script separates:

  (B) NOT-A-RETRIEVAL-PROBLEM : the human's novelty objection is not overlap with a specific
      paper at all -- it's "this is obvious / common knowledge", "just a marginal variant",
      or "lacks theoretical/empirical justification". No paper exists to retrieve; my
      overlap paradigm structurally cannot (and arguably should not) challenge these.
  (A1) RETRIEVAL MISS        : the human names a specific prior work, and it is ABSENT from
      my pool -> a recall problem in retrieval.
  (A2) GRADING MISS          : the named prior work IS in my pool, yet the agent still found
      0 challenged claims -> the agent saw the paper but graded the overlap too leniently.

For each paper x human-assessment it uses an LLM to (1) classify the objection + extract the
specific prior works the human names, then (2) match those against my retrieved pool
(ranked_papers.json). It cross-tabulates with the agent's per-claim challenge outcome
(artifact_a) and writes a report to eval/out_v2/.

Run:  python eval/recall_analysis.py            (or via run-rescore.ps1's sibling)
Reads the SAME papers the main eval ran (eval/out/results/*.json). Read-only on eval/out/.
"""
import argparse
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

# harmless langchain/pydantic serializer warning on with_structured_output
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_DATASET = (_REPO.parent.parent / "Afzal Dataset" / "data_for_release")

ap = argparse.ArgumentParser(description="Retrieval recall vs human-cited prior work")
ap.add_argument("--dataset", default=str(_DEFAULT_DATASET))
ap.add_argument("--src-out", default=str(_REPO / "eval" / "out"))
ap.add_argument("--out", default=str(_REPO / "eval" / "out_v2"))
ap.add_argument("--ids", default=None)
ap.add_argument("--n", type=int, default=0)
ap.add_argument("--model", default=os.getenv("NOVELTY_JUDGE_MODEL", "gpt-4.1"))
args = ap.parse_args()

SRC = Path(args.src_out)
SRC_DATA = SRC / "data"
SRC_RESULTS = SRC / "results"
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(_REPO / "eval"))
from dotenv import load_dotenv
load_dotenv(_REPO / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(OUT / "recall.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)], force=True)
log = logging.getLogger("recall")
for noisy in ("httpx", "urllib3", "openai", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


# ----------------------------------------------------------------------------- #
# structured-output schemas
# ----------------------------------------------------------------------------- #
class NamedWork(BaseModel):
    name: str = Field(description="short identifier: method name or author reference, "
                                  "e.g. 'SNIP (Lee et al.)', 'RESTA', 'TOOLDEC'")
    description: str = Field(description="what this prior work is / does, in a few words")


class ObjectionAnalysis(BaseModel):
    primary_basis: str = Field(description=(
        "the PRIMARY basis of the reviewer's novelty judgment, EXACTLY one of: "
        "OVERLAP_SPECIFIC (overlaps with / borrows from specific prior work the reviewer "
        "names or clearly points to); OBVIOUSNESS (contribution called intuitive / common "
        "knowledge / a well-known result, no specific paper); MARGINAL_DELTA (a small "
        "incremental variant of a general approach, e.g. 'just another X variant', no "
        "specific refuting paper); INSUFFICIENT_RIGOR (novelty questioned for lack of "
        "theoretical/empirical justification, not overlap); POSITIVE (novelty considered "
        "sufficient/genuine); OTHER"))
    named_prior_works: List[NamedWork] = Field(
        default_factory=list,
        description="EVERY specific prior work the reviewer names or clearly identifies as "
                    "something the paper overlaps with / should be compared to. Empty if none.")


class PoolMatch(BaseModel):
    named_work: str
    status: str = Field(description="PRESENT (the pool contains this paper/method), ABSENT, "
                                    "or UNCLEAR")
    best_match_title: str = Field(default="", description="closest pool title, if any")


class PoolMatchList(BaseModel):
    matches: List[PoolMatch]


EXTRACT_PROMPT = """You are analyzing a human reviewer's novelty assessment of a scientific paper. Determine WHY the reviewer judges the paper's novelty as they do, and whether they ground it in specific prior work.

Follow the schema. For `primary_basis` pick the single best-fitting category. For `named_prior_works`, extract only prior works the reviewer ACTUALLY names or clearly points to as overlapping / to-be-compared (method names like "SNIP", "RESTA", "TOOLDEC", "Domino", or author references like "Lee et al."). Do NOT invent references; if the reviewer speaks only in general terms ("common sense", "a LoRA variant", "well-known"), return an empty list.

ASSESSMENT:
{assessment}
"""

MATCH_PROMPT = """A retrieval system gathered these candidate prior-work papers for a submission (one per line, "title — first author, year"):

{pool}

A human reviewer pointed to these specific prior works as relevant to the submission's novelty:
{named}

For EACH named prior work decide whether it is PRESENT in the retrieved pool (same paper or same specific method/system), ABSENT, or UNCLEAR. Match on method/topic/system name and authors — NOT exact string equality. Give the best-matching pool title if there is any plausible one.
"""


def _llm(model):
    from langchain_openai import ChatOpenAI
    kw = {} if model.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    return ChatOpenAI(model_name=model, api_key=os.getenv("OPENAI_API_KEY"),
                      max_retries=4, timeout=180, **kw)


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _first_author(authors) -> str:
    s = (authors or "") if isinstance(authors, str) else ", ".join(authors or [])
    names = [a.strip() for a in s.split(",") if a.strip()]
    return names[0] if names else ""


def pool_lines(sid: str):
    ranked = _read(SRC_DATA / sid / "related_work_data" / "ranked_papers.json", []) or []
    agent = _read(SRC_DATA / sid / "related_work_data" / "agent_retrieved_papers.json", []) or []
    lines, n = [], 0
    for p in ranked + agent:
        t = (p.get("title") or "").strip()
        if not t:
            continue
        lines.append(f"- {t[:140]} — {_first_author(p.get('authors'))}, {p.get('year', '')}")
        n += 1
    return "\n".join(lines), n


def agent_challenge(sid: str):
    """(n_claims, n_challenged) from Artifact A."""
    d = _read(SRC_DATA / sid / f"{sid}_artifact_a.json")
    if not d:
        return 0, 0
    ncl = len(d.get("claims", []))
    nch = 0
    for e in d.get("claims", []):
        v = (e.get("agent_verdict") or "").lower()
        if v == "challenged" or (e.get("can_refute_count") or 0) > 0:
            nch += 1
    return ncl, nch


def v2_verdict(sid: str, ref: str):
    """The mine v2 reviewer_conclusion + human reference conclusion for this ref."""
    r = _read(OUT / "results" / f"{sid}.json", {}) or {}
    for pr in (r.get("judge", {}).get("per_ref") or []):
        if pr["human_file"] == ref and pr.get("mine"):
            return pr["mine"].get("reference_conclusion"), pr["mine"].get("reviewer_conclusion")
    return None, None


def main():
    dataset = Path(args.dataset)
    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    else:
        ids = [Path(p).stem for p in sorted(glob.glob(str(SRC_RESULTS / "*.json")))]
    if args.n:
        ids = ids[: args.n]
    if not ids:
        log.error(f"no papers in {SRC_RESULTS} — run the main eval first."); sys.exit(1)

    llm = _llm(args.model)
    extract = llm.with_structured_output(ObjectionAnalysis)
    match = llm.with_structured_output(PoolMatchList)

    log.info("=" * 80)
    log.info(f"RECALL ANALYSIS | {len(ids)} papers | model={args.model}")
    log.info("Does my pool contain the prior work the human based 'not novel' on?")
    log.info("=" * 80)

    rows = []          # one per (sid, ref)
    for i, sid in enumerate(ids, 1):
        p = dataset / sid
        humans = sorted(glob.glob(str(p / "human_novelty_assessments" / "*.txt")))
        pool_txt, pool_n = pool_lines(sid)
        ncl, nch = agent_challenge(sid)
        for hp in humans:
            ref = Path(hp).name
            assessment = Path(hp).read_text(encoding="utf-8").strip()
            hum_c, _ = v2_verdict(sid, ref)
            try:
                oa = extract.invoke(EXTRACT_PROMPT.format(assessment=assessment))
                named = oa.named_prior_works or []
                matches = []
                if named:
                    named_txt = "\n".join(f"- {w.name}: {w.description}" for w in named)
                    ml = match.invoke(MATCH_PROMPT.format(pool=pool_txt or "(empty)", named=named_txt))
                    matches = ml.matches or []
                present = sum(1 for m in matches if m.status.upper().strip() == "PRESENT")
                absent = sum(1 for m in matches if m.status.upper().strip() == "ABSENT")

                # classify by the AGENT'S OUTCOME first, then by cause of any miss.
                # An over-claim only happens when the agent challenged nothing (nch == 0);
                # if nch > 0 the agent flagged the overlap (possibly via a sibling paper, even
                # when the human's exact named work was not retrieved) -> not a failure.
                basis = (oa.primary_basis or "OTHER").upper().strip()
                if nch > 0:
                    situation = "agent_challenged"       # agent found overlap to challenge
                elif basis != "OVERLAP_SPECIFIC" or not named:
                    situation = "B_not_retrieval"        # obviousness / marginal / rigor: no paper exists
                elif present == 0:
                    situation = "A1_retrieval_miss"      # named prior work absent from pool
                else:
                    situation = "A2_grading_miss"        # named + in pool, agent still didn't challenge

                rows.append({
                    "sid": sid, "ref": ref, "human_conclusion": hum_c,
                    "primary_basis": basis, "n_named": len(named),
                    "named": [w.name for w in named],
                    "present": present, "absent": absent,
                    "matches": [{"named": m.named_work, "status": m.status,
                                 "best_match": m.best_match_title} for m in matches],
                    "pool_n": pool_n, "agent_challenged": nch, "agent_claims": ncl,
                    "situation": situation,
                })
                log.info(f"[{i}/{len(ids)}] {sid} {ref}: human={hum_c} basis={basis} "
                         f"named={len(named)} in-pool={present}/{len(named)} "
                         f"agent_challenged={nch}/{ncl} -> {situation}")
            except Exception as e:
                log.error(f"[{i}/{len(ids)}] {sid} {ref}: FAILED {e}\n{traceback.format_exc()}")

    write_report(rows)
    (OUT / "recall_analysis.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # terminal summary
    from collections import Counter
    sit = Counter(r["situation"] for r in rows)
    named_rows = [r for r in rows if r["primary_basis"] == "OVERLAP_SPECIFIC" and r["n_named"]]
    tot_named = sum(r["n_named"] for r in named_rows)
    tot_present = sum(r["present"] for r in named_rows)
    log.info("=" * 80)
    log.info(f"SITUATION BREAKDOWN over {len(rows)} (paper x human-ref) pairs:")
    log.info(f"  agent_challenged (agent DID flag overlap, no over-claim): {sit.get('agent_challenged',0)}")
    log.info(f"  --- of the OVER-CLAIMING pairs (agent challenged 0): ---")
    log.info(f"  B  not-a-retrieval-problem (obviousness/marginal/rigor): {sit.get('B_not_retrieval',0)}")
    log.info(f"  A1 retrieval MISS (named prior work absent from pool)   : {sit.get('A1_retrieval_miss',0)}")
    log.info(f"  A2 grading MISS (in pool but agent didn't challenge)    : {sit.get('A2_grading_miss',0)}")
    if tot_named:
        log.info(f"POOL RECALL on human-named prior work: {tot_present}/{tot_named} "
                 f"= {round(100*tot_present/tot_named,1)}%")
    log.info(f"Report: {OUT / 'recall_analysis.md'}")


def write_report(rows):
    from collections import Counter
    sit = Counter(r["situation"] for r in rows)
    named_rows = [r for r in rows if r["primary_basis"] == "OVERLAP_SPECIFIC" and r["n_named"]]
    tot_named = sum(r["n_named"] for r in named_rows)
    tot_present = sum(r["present"] for r in named_rows)
    basis_c = Counter(r["primary_basis"] for r in rows)

    L = ["# Retrieval Recall vs. Human-Cited Prior Work\n",
         f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')} · model: `{args.model}`_\n",
         "Answers: when a human judged a paper 'not novel enough', did my pool contain the "
         "prior work they based it on — and did the agent grade the overlap?\n",
         "## Why each paper over/under-claims — the causes\n",
         f"Over **{len(rows)}** (paper × human-ref) pairs:\n",
         f"| Situation | Count | Meaning |",
         f"|---|---|---|",
         f"| **agent_challenged** | {sit.get('agent_challenged',0)} | the agent DID flag overlap "
         f"(challenged ≥1 claim) — no over-claim on the overlap axis, even if the human's exact "
         f"named paper was not the one it used |",
         f"| **B — not a retrieval problem** | {sit.get('B_not_retrieval',0)} | agent challenged 0; "
         f"human objection is obviousness / marginal delta / lack of rigor — no specific paper to retrieve |",
         f"| **A1 — retrieval miss** | {sit.get('A1_retrieval_miss',0)} | agent challenged 0; human "
         f"names a prior work, ABSENT from my pool (recall problem) |",
         f"| **A2 — grading miss** | {sit.get('A2_grading_miss',0)} | agent challenged 0; named prior "
         f"work IS in my pool, but agent graded the overlap too leniently |\n"]
    if tot_named:
        L.append(f"**Pool recall on human-named prior work: {tot_present}/{tot_named} = "
                 f"{round(100*tot_present/tot_named,1)}%** "
                 f"(of the specific prior works humans cite, this fraction was in my pool).\n")

    L.append("## Objection type distribution\n")
    L.append("| Primary basis of the human's novelty judgment | Count |")
    L.append("|---|---|")
    for k, v in basis_c.most_common():
        L.append(f"| {k} | {v} |")

    L.append("\n## Per paper × human-ref\n")
    L.append("| forum_id | ref | human | basis | named | in pool | agent chal | situation |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["situation"], r["sid"])):
        L.append(f"| {r['sid']} | {r['ref']} | {r['human_conclusion']} | {r['primary_basis']} | "
                 f"{r['n_named']} | {r['present']}/{r['n_named']} | "
                 f"{r['agent_challenged']}/{r['agent_claims']} | {r['situation']} |")

    # detail: the named works and their match status, for the A rows
    L.append("\n## Named prior works & pool match (papers where the human cited specifics)\n")
    for r in named_rows:
        L.append(f"**{r['sid']} / {r['ref']}** (human={r['human_conclusion']}, "
                 f"agent challenged {r['agent_challenged']}/{r['agent_claims']}):")
        for m in r["matches"]:
            mark = {"PRESENT": "✅", "ABSENT": "❌"}.get(m["status"].upper().strip(), "❓")
            bm = f" → pool: \"{m['best_match'][:80]}\"" if m["best_match"] else ""
            L.append(f"- {mark} {m['named']} [{m['status']}]{bm}")
        L.append("")

    L.append("> Situations: **B** = my overlap paradigm structurally cannot address the objection "
             "(and staying honest ≠ over-claiming); **A1** = fix retrieval recall; **A2** = fix the "
             "agent's overlap-degree / can_refute threshold. Pipeline pool = ranked_papers.json "
             "(+ agent_retrieved if any).\n")
    (OUT / "recall_analysis.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

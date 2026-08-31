#!/usr/bin/env python3
"""
Which way should the per-claim REALIZATION be produced?

The realization is the "what the submission itself does for this claim" reading: prose with
verbatim, machine-verified quotes. It is not decoration -- it is handed to EVERY prior-work
comparison as context, and shown to the reviewer.

Two candidates:
  sections  section menu -> model picks sections -> read those in full  (2 calls/claim)
            Inherited from DeepClaimExtractor, i.e. from the design that LOST the Stage-A
            comparison; carried over untested when the pipeline switched extractors.
  fulltext  the whole paper in ONE call, model picks the relevant parts itself
            (1 call/claim). Consistent with how the claims themselves are extracted.

FAIRNESS: both variants realize the SAME claims of the SAME papers, produced by one prior
extraction run. Only the realization method differs.

Measured per variant: calls, tokens, USD, segments, verified quotes, and the quote
verification rate (deterministic -- an unverifiable quote is demoted to prose, so a low
rate means the method points at text it cannot actually support).

Then a BLIND pairwise judgement per claim, in BOTH orientations (a win counts only if it
survives the swap), on: faithfulness to the paper, coverage of what the claim needs, and
whether the quotes carry the load-bearing specifics.

Usage
-----
  python eval/eval_realization.py --data-dir eval/out/data --ids A,B,C --run
  python eval/eval_realization.py --data-dir eval/out/data --ids A,B,C --judge
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

_SRC = Path(__file__).resolve().parents[1] / "src" / "novelty_assessment"
sys.path.insert(0, str(_SRC))
from claim_extraction import (  # noqa: E402
    FullTextClaimExtractor,
    build_realization,
    build_realization_fulltext,
    load_paper_for_extraction,
    DeepClaimExtractor,
    _usd,
)
from agent.passages import PassageIndex, chunks_from_sections  # noqa: E402

load_dotenv()

VARIANTS = ("sections", "fulltext")


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def out_path(data_dir: Path, sid: str, variant: str) -> Path:
    return data_dir / sid / f"{sid}_realization_{variant}.json"


def claims_of(data_dir: Path, sid: str) -> List[dict]:
    """The claim set both variants must realize (one prior extraction, shared)."""
    for name in (f"{sid}_claims_fulltext_luna.json", f"{sid}_claims.json"):
        doc = _load(data_dir / sid / name)
        if doc and doc.get("claims"):
            return [c for c in doc["claims"] if c.get("status") != "rejected"]
    return []


def run_variant(data_dir: Path, sid: str, variant: str, model: str, effort: str) -> dict:
    claims = claims_of(data_dir, sid)
    if not claims:
        return {"error": "no claims"}
    meta, title, content, source_text = load_paper_for_extraction(str(data_dir), sid)
    _, sections = DeepClaimExtractor._load(str(data_dir), sid)
    index = PassageIndex(chunks_from_sections(sections, "submission"), embedder=None)

    ex = FullTextClaimExtractor(model_name=model, reasoning_effort=effort)
    ex._pt = ex._ct = ex._calls = 0
    items, t0 = [], time.time()
    for c in claims:
        ct = c.get("claim_text") or c.get("name", "")
        if variant == "sections":
            segs = build_realization(ex, ct, index, source_text)
        else:
            segs = build_realization_fulltext(ex, ct, content, source_text)
        items.append({"claim_id": c["id"], "claim_text": ct, "segments": segs})
    doc = {
        "submission_id": sid, "variant": variant, "model": model,
        "n_claims": len(items), "seconds": round(time.time() - t0, 1),
        "cost": {"model": model, "prompt_tokens": ex._pt, "completion_tokens": ex._ct,
                 "n_calls": ex._calls, "usd": _usd(model, ex._pt, ex._ct)},
        "claims": items,
    }
    out_path(data_dir, sid, variant).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


# --------------------------------------------------------------------------- #
# Blind pairwise judgement
# --------------------------------------------------------------------------- #


class _Verdict(BaseModel):
    winner: str = Field(description='"A", "B", or "tie"')
    reason: str = Field(default="", description="one sentence")


_PROMPT = """Two systems each wrote a short explanation of what a paper does to realize ONE of its claimed contributions. Decide which explanation is better.

Judge on, in order of importance:
1. FAITHFULNESS -- is everything stated actually what the paper does for THIS claim? Penalise anything invented, generalised, or belonging to a different contribution.
2. COVERAGE -- does it capture what someone comparing this contribution against prior work would need: what was built and how, its defining design decisions?
3. EVIDENCE -- do the quoted passages carry the load-bearing specifics, rather than generic or peripheral sentences?

Length and style do not matter. Answer "tie" only if the two are genuinely equivalent.

## Paper title
{title}

## The claim
{claim}

## Paper (abstract + beginning)
{paper}

## Explanation A
{a}

## Explanation B
{b}"""


def _fmt(segs: List[dict]) -> str:
    out = []
    for s in segs or []:
        c = (s.get("content") or "").strip()
        if not c:
            continue
        out.append(f'QUOTE: "{c}"' if s.get("kind") == "quote" else c)
    return "\n".join(out) or "(empty)"


def _paper_ctx(data_dir: Path, sid: str, limit: int = 5000) -> str:
    meta = _load(data_dir / sid / f"{sid}.json") or {}
    ft = _load(data_dir / sid / f"{sid}_fulltext.json") or {}
    parts, used = [(meta.get("abstract") or "").strip()], 0
    for s in ft.get("sections", []):
        t = (s.get("text") or "").strip()
        if not t:
            continue
        parts.append(t)
        used += len(t)
        if used >= limit:
            break
    return "\n\n".join(parts)[:limit]


def judge_once(judge, title, claim, paper, a, b) -> Optional[str]:
    try:
        r = judge.with_structured_output(_Verdict, include_raw=True).invoke(
            _PROMPT.replace("{title}", title).replace("{claim}", claim)
            .replace("{paper}", paper).replace("{a}", a).replace("{b}", b)).get("parsed")
        v = (r.winner or "").strip().upper()
        return v if v in ("A", "B", "TIE") else None
    except Exception:
        return None


def judge_pair(judge, title, claim, paper, x, y) -> dict:
    """x vs y in both orientations; a win must survive the swap."""
    v1 = judge_once(judge, title, claim, paper, x, y)
    v2 = judge_once(judge, title, claim, paper, y, x)
    if v1 is None or v2 is None:
        return {"winner": None, "consistent": False, "raw": [v1, v2]}
    if v1 == "A" and v2 == "B":
        return {"winner": "x", "consistent": True, "raw": [v1, v2]}
    if v1 == "B" and v2 == "A":
        return {"winner": "y", "consistent": True, "raw": [v1, v2]}
    return {"winner": "tie", "consistent": v1 == "TIE" == v2, "raw": [v1, v2]}


def stats(doc: dict) -> dict:
    segs = [s for c in doc.get("claims", []) for s in c.get("segments", [])]
    quotes = [s for s in segs if s.get("kind") == "quote"]
    # a quote that failed verification was demoted to kind="text" with verified=False
    demoted = [s for s in segs if s.get("kind") == "text" and s.get("verified") is False]
    total_q = len(quotes) + len(demoted)
    return {
        "n_claims": doc.get("n_claims", 0),
        "segments_per_claim": len(segs) / max(1, doc.get("n_claims", 1)),
        "verified_quotes_per_claim": len(quotes) / max(1, doc.get("n_claims", 1)),
        "quote_verification_rate": (len(quotes) / total_q) if total_q else None,
        "calls": doc.get("cost", {}).get("n_calls", 0),
        "usd": doc.get("cost", {}).get("usd"),
        "seconds": doc.get("seconds"),
    }


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def main():
    ap = argparse.ArgumentParser(description="Compare realization variants")
    ap.add_argument("--data-dir", default="eval/out/data")
    ap.add_argument("--ids", required=True)
    ap.add_argument("--model", default="gpt-5.6-luna")
    ap.add_argument("--reasoning-effort", default="high")
    ap.add_argument("--judge-model", default="gpt-4.1")
    ap.add_argument("--run", action="store_true", help="produce both variants")
    ap.add_argument("--judge", action="store_true", help="score + blind pairwise")
    ap.add_argument("--out", default="eval/out/realization_comparison.json")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    ids = [s.strip() for s in args.ids.split(",") if s.strip()]

    if args.run:
        for sid in ids:
            for variant in VARIANTS:
                if out_path(data_dir, sid, variant).exists():
                    print(f"  [{sid}] {variant}: exists, skip")
                    continue
                d = run_variant(data_dir, sid, variant, args.model, args.reasoning_effort)
                if d.get("error"):
                    print(f"  [{sid}] {variant}: {d['error']}")
                else:
                    print(f"  [{sid}] {variant}: {d['n_claims']} claims, "
                          f"{d['cost']['n_calls']} calls, ${d['cost']['usd']}, {d['seconds']}s")
        if not args.judge:
            return

    from langchain_openai import ChatOpenAI
    jm = args.judge_model
    kw = {} if jm.startswith(("gpt-5", "o1", "o3", "o4")) else {"temperature": 0.0}
    judge = ChatOpenAI(model_name=jm, api_key=os.getenv("OPENAI_API_KEY"),
                       max_retries=4, timeout=180, **kw)

    per_variant, rows, battle = {v: [] for v in VARIANTS}, [], {
        "sections_wins": 0, "fulltext_wins": 0, "ties": 0, "position_inconsistent": 0,
        "per_claim": []}

    for sid in ids:
        docs = {v: _load(out_path(data_dir, sid, v)) for v in VARIANTS}
        if not all(docs.values()):
            print(f"[{sid}] missing a variant -> skipped")
            continue
        for v in VARIANTS:
            per_variant[v].append(stats(docs[v]))
        title = (_load(data_dir / sid / f"{sid}.json") or {}).get("title", "")
        paper = _paper_ctx(data_dir, sid)
        by_id = {v: {c["claim_id"]: c for c in docs[v]["claims"]} for v in VARIANTS}
        for cid in by_id["sections"]:
            if cid not in by_id["fulltext"]:
                continue
            cs, cf = by_id["sections"][cid], by_id["fulltext"][cid]
            r = judge_pair(judge, title, cs["claim_text"], paper,
                           _fmt(cs["segments"]), _fmt(cf["segments"]))
            r.update({"submission_id": sid, "claim_id": cid})
            battle["per_claim"].append(r)
            if r["winner"] == "x":
                battle["sections_wins"] += 1
            elif r["winner"] == "y":
                battle["fulltext_wins"] += 1
            else:
                battle["ties"] += 1
                if not r["consistent"]:
                    battle["position_inconsistent"] += 1
            print(f"  [{sid}/{cid}] {r['raw']} -> "
                  + {"x": "sections", "y": "fulltext"}.get(r["winner"], "tie"))

    summary = {v: {k: _mean([s[k] for s in per_variant[v]])
                   for k in ("segments_per_claim", "verified_quotes_per_claim",
                             "quote_verification_rate", "calls", "usd", "seconds")}
               for v in VARIANTS if per_variant[v]}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "ids": ids, "judge_model": jm,
         "summary": summary, "battle": battle}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 84)
    print(f"REALIZATION VARIANTS  ({len(ids)} papers, judge={jm})")
    print("=" * 84)
    print(f"{'variant':<11}{'calls/paper':>13}{'USD/paper':>11}{'sec':>7}"
          f"{'segs/claim':>12}{'vq/claim':>10}{'quote-ver':>11}")
    print("-" * 84)
    for v, s in summary.items():
        print(f"{v:<11}{s['calls'] or 0:>13.1f}{(s['usd'] or 0):>11.4f}{(s['seconds'] or 0):>7.0f}"
              f"{(s['segments_per_claim'] or 0):>12.1f}{(s['verified_quotes_per_claim'] or 0):>10.1f}"
              f"{(s['quote_verification_rate'] or 0) * 100:>10.1f}%")
    print("-" * 84)
    print("vq/claim = verified quotes · quote-ver = share of quotes that verified verbatim")
    n = len(battle["per_claim"])
    print(f"\nBLIND PAIRWISE (both orientations)  n={n} claims")
    print(f"  sections wins: {battle['sections_wins']}")
    print(f"  fulltext wins: {battle['fulltext_wins']}")
    print(f"  tie          : {battle['ties']}"
          + (f"  ({battle['position_inconsistent']} only because the orientations disagreed)"
             if battle["position_inconsistent"] else ""))
    print(f"\nwritten: {args.out}")


if __name__ == "__main__":
    main()

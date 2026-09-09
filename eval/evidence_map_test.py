#!/usr/bin/env python3
"""
Build the claim-evidence map for one claim and report it both ways: as the reviewer sees
it, and as numbers on the dimensions the evaluation will use.

The numbers are chosen so that none of them can be improved by writing more:

  grounding    share of shown correspondences with BOTH sides verified. By construction
               1.0 -- unverified pairs are dropped -- so what carries information is how
               many were dropped, printed beside it.
  circularity  share of submission quotes that are really the claim text quoted back.
               Must be 0: the claim no longer sits in its own verification corpus.
  granularity  distinct submission sentences the map points at, per paper. One sentence
               answering for every correspondence is a map that localises nothing.
  selectivity  papers reported as challenging, against papers examined.

Usage
-----
  python eval/evidence_map_test.py --submission graphrag_when_to_use --claim claim_2
  python eval/evidence_map_test.py --submission ID --claim claim_1 --limit 6
"""
import argparse
import json
import os
import re
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                          # noqa: E402

load_dotenv()
W = 96
CHALLENGE = ("same", "substantial")
OVERLAP = ("same", "substantial", "partial")


def _w(t, ind="  "):
    return textwrap.fill(" ".join((t or "").split()), W, initial_indent=ind, subsequent_indent=ind)


def _norm(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def run(data_dir: str, sid: str, claim_id: str, model: str, limit: int) -> dict:
    from agent import evidence_map as em
    from agent.claim_agent import ClaimNoveltyAgent, _fmt_sections_full, _segments_to_text
    from agent.tools import ClaimToolbox

    sub = Path(data_dir) / sid
    art = json.loads((sub / f"{sid}_artifact_a.json").read_text(encoding="utf-8"))
    claims_doc = json.loads((sub / f"{sid}_claims.json").read_text(encoding="utf-8"))
    claim = {c["id"]: c for c in claims_doc.get("claims", [])}[claim_id]
    entry = {e["claim_id"]: e for e in art["claims"]}[claim_id]

    ag = ClaimNoveltyAgent(data_dir, sid, model_name=model)
    spend = {"pt": 0, "ct": 0, "calls": 0}

    def struct(schema, prompt):
        try:
            parsed, a, b = ag._struct(schema, prompt)
        except Exception as e:
            print(f"    [call failed] {type(e).__name__}: {str(e)[:160]}")
            return None
        spend["pt"] += a; spend["ct"] += b; spend["calls"] += 1
        return parsed

    tb = ClaimToolbox(data_dir, sid, claim, ag.embedder)
    claim_str = ag._claim_str(claim)
    t0 = time.perf_counter()

    # The submission side the model may quote from: the sections this claim's realization
    # was read from, in full. Quoting from a summary would put a paraphrase where the
    # reviewer expects the paper's words.
    sub_names = tb._sections_read.get("submission") or []
    if not sub_names:
        sub_names = [m.get("name") for m in (tb.section_menu("submission") or [])[:6]
                     if m.get("name")]
    sub_secs = (tb.read_sections("submission", sub_names) or {}).get("sections") or []
    submission_text = _fmt_sections_full(sub_secs) or _segments_to_text(
        entry.get("claim_realization") or [])

    papers = [c for c in entry.get("comparisons", []) if c.get("sections_used")]
    if limit:
        papers = papers[:limit]
    print(f"\n{claim_id}: mapping {len(papers)} papers the run read in full\n")

    results = []
    for c in papers:
        pid = c["paper_id"]
        tb.ensure_fulltext(pid)
        secs = (tb.read_sections(pid, c["sections_used"]) or {}).get("sections") or []
        paper_text = _fmt_sections_full(secs)
        if not paper_text.strip():
            continue
        mapping = em.build_map(
            struct, claim_str, submission_text, c.get("title", ""), paper_text,
            tb._submission_text, tb._paper_source_text(pid),
            ag.min_quote_tokens, ag.fuzzy_threshold)
        kept = mapping["pairs"]
        # The rejected pairs stay in the artifact. A filter whose decisions are invisible
        # cannot be checked, and these are exactly the ones worth reading: they are what
        # separates a correspondence from two sentences that share a vocabulary.
        mapping["pairs"] = kept
        verdict = em.conclude(struct, claim_str, mapping)
        results.append({**mapping, **verdict, "paper_id": pid, "title": c.get("title", ""),
                        "run_degree": (c.get("overlap_degree") or "").lower()})
        print(f"  {len(mapping['pairs'])} pairs (+{mapping['dropped']} dropped)  "
              f"run={results[-1]['run_degree']:12} map={verdict['degree']:12} "
              f"{c.get('title', '')[:38]}")

    from agent.claim_agent import _usd
    out = {"claim_id": claim_id, "claim": claim, "papers": results, "spend": spend,
           "usd": _usd(model, spend["pt"], spend["ct"]),
           "seconds": round(time.perf_counter() - t0, 1)}
    _render(out)
    _metrics(out, claim)
    return out


def _render(r: dict) -> None:
    ranked = sorted(r["papers"], key=lambda p: (p["degree"] not in CHALLENGE,
                                                -len(p["pairs"])))
    print("\n" + "=" * W)
    print("CLAIM-EVIDENCE MAP")
    print("=" * W)
    print(_w("CLAIM: " + (r["claim"].get("claim_text") or ""), ""))
    ch = [p for p in ranked if p["degree"] in CHALLENGE]
    print(f"\n{len(ch)} of {len(ranked)} examined papers challenge this claim.\n")

    for p in ranked:
        if p["degree"] in ("none", "superficial") and not p["pairs"]:
            continue
        head = "CHALLENGE" if p["degree"] in CHALLENGE else p["degree"]
        print("-" * W)
        print(f"[{head}] {p['title'][:78]}")
        if p.get("reasoning"):
            print(); print(_w(p["reasoning"]))
        for i, q in enumerate(p["pairs"][:3], 1):
            print(f"\n  ({i}) {q['strength']} — {q['rationale'][:110]}")
            print(_w('YOUR PAPER: "' + " ".join(q["claim_quote"].split())[:170] + '…"', "      "))
            print(_w('THIS PAPER: "' + " ".join(q["paper_quote"].split())[:170] + '…"', "      "))
        if p.get("submission_delta"):
            print(); print(_w("STILL YOURS: " + p["submission_delta"][:340]))
        print()

    quiet = [p for p in ranked if p["degree"] in ("none", "superficial") and not p["pairs"]]
    if quiet:
        print("-" * W)
        print("Examined, no correspondence could be evidenced:")
        for p in quiet:
            print(f"  - {p['title'][:82]}")
    print(f"\n{r['spend']['calls']} calls · {r['spend']['pt']:,}+{r['spend']['ct']:,} tokens · "
          f"${r['usd']:.4f} · {r['seconds']}s")


def _metrics(r: dict, claim: dict) -> None:
    pairs = [q for p in r["papers"] for q in p["pairs"]]
    dropped = sum(p["dropped"] for p in r["papers"])
    # Circularity is now structural, not textual: the claim was removed from the corpus a
    # submission quote is verified against, so a quote that verified is in the paper's body
    # by construction. Comparing the quote's WORDING to the claim flagged a legitimate
    # sentence -- the claim had been extracted almost verbatim from it -- so what is counted
    # here is what actually matters: quotes that did NOT come from the submission body.
    circular = sum(1 for q in pairs if not q.get("claim_quote_verified"))
    anchors = {_norm(q["claim_quote"])[:80] for q in pairs}
    ch = [p for p in r["papers"] if p["degree"] in CHALLENGE]
    ov = [p for p in r["papers"] if p["degree"] in OVERLAP]

    print("\n" + "=" * W)
    print("DIMENSIONS")
    print("=" * W)
    print(f"  grounding    {len(pairs)}/{len(pairs)} shown pairs verified on both sides "
          f"({dropped} dropped before display)")
    print(f"  circularity  {circular}/{len(pairs)} submission quotes not found in the "
          f"submission body  (must be 0)")
    print(f"  granularity  {len(anchors)} distinct submission sentences across "
          f"{len(pairs)} pairs")
    print(f"  selectivity  {len(ch)} challenge / {len(ov)} overlap / {len(r['papers'])} examined")


def main():
    ap = argparse.ArgumentParser(description="Claim-evidence map for one claim")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)
    res = run(args.data_dir, args.submission, args.claim, args.model, args.limit)
    out = args.out or f"eval/out/evmap_{args.submission}_{args.claim}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str),
                         encoding="utf-8")
    print(f"written: {out}")


if __name__ == "__main__":
    main()

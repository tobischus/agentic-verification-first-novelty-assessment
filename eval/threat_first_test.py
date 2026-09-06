#!/usr/bin/env python3
"""
Run one claim through threat-first examination and print the review a reviewer would read.

Two things are being tested at once and both have to hold, or the change is not worth
making: the assessment must be at least as good, and the page must be shorter and sharper.
The per-paper comparison is deliberately the pipeline's existing one -- two earlier
attempts at replacing it made the output worse -- so what is under test here is the order
papers are examined in, when the examination stops, and how the result is laid out.

Usage
-----
  python eval/threat_first_test.py --submission graphrag_when_to_use --claim claim_2
  python eval/threat_first_test.py --submission ID --claim claim_1 --budget 6
"""
import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src" / "novelty_assessment"))

from dotenv import load_dotenv                                          # noqa: E402

load_dotenv()

W = 96


def _w(t, ind="  "):
    return textwrap.fill(" ".join((t or "").split()), W, initial_indent=ind, subsequent_indent=ind)


def run(data_dir: str, sid: str, claim_id: str, model: str, budget: int) -> dict:
    from agent import threat as th
    from agent.claim_agent import ClaimNoveltyAgent, _segments_to_text
    from agent.tools import ClaimToolbox

    sub = Path(data_dir) / sid
    art = json.loads((sub / f"{sid}_artifact_a.json").read_text(encoding="utf-8"))
    claims_doc = json.loads((sub / f"{sid}_claims.json").read_text(encoding="utf-8"))
    claim = {c["id"]: c for c in claims_doc.get("claims", [])}[claim_id]
    entry = {e["claim_id"]: e for e in art["claims"]}[claim_id]

    ag = ClaimNoveltyAgent(data_dir, sid, model_name=model)
    spend = {"pt": 0, "ct": 0, "calls": 0}

    def struct(schema, prompt):
        parsed, a, b = ag._struct(schema, prompt)
        spend["pt"] += a; spend["ct"] += b; spend["calls"] += 1
        return parsed

    tb = ClaimToolbox(data_dir, sid, claim, ag.embedder)
    claim_ctx = _segments_to_text(entry.get("claim_realization") or [])
    t0 = time.perf_counter()

    ranked = th.rank(struct, ag._claim_str(claim), tb._ranked())
    print(f"\nThreat ranking over {len(ranked)} papers:")
    for p in ranked:
        print(f"  {p['threat']:2}  {p.get('title', '')[:56]:58} {p['threat_reason'][:60]}")

    examined, stop, miscal = [], None, 0
    for i, p in enumerate(ranked):
        if len(examined) >= budget:
            stop = "budget_exhausted"
            break
        pid = p["paper_id"]
        tb.ensure_fulltext(pid)
        # the pipeline's own comparison, unchanged: what is under test is the scheduling
        before = (spend["pt"], spend["ct"])
        comp, a, b = ag._section_compare(tb, claim, pid, claim_ctx)
        spend["pt"] += a; spend["ct"] += b; spend["calls"] += 2
        comp["_paper"] = p
        examined.append(comp)

        nxt = ranked[i + 1]["threat"] if i + 1 < len(ranked) else None
        deg = (comp.get("overlap_degree") or "").lower()
        miscal = miscal + 1 if deg in ("superficial", "none") else 0
        stop = th.settled(examined, nxt, miscal)
        print(f"    examined [{p['threat']}] {p.get('title', '')[:44]:46} "
              f"-> {comp.get('overlap_degree'):12} {'STOP: ' + stop if stop else ''}")
        if stop:
            break

    # Re-entry: a challenge the reviewer cannot check is a failed evidence check. The action
    # it triggers asks a DIFFERENT question -- re-running the same comparison produced the
    # same missing pair every time, because that prompt only asks for pairs when the answer
    # is `can_refute`. Here the demand is the pair itself, with withdrawal as a legitimate
    # answer, so a judgement that cannot be evidenced is retracted rather than shown unbacked.
    from agent.claim_agent import _fmt_sections_full
    from agent import evidence as ev
    repaired, withdrawn = [], []
    for c in th.ungrounded(examined):
        pid = c["_paper"]["paper_id"]
        secs, a, b = ag._pick_sections(tb, pid, "")
        spend["pt"] += a; spend["ct"] += b; spend["calls"] += 1
        if not secs:
            names = [m.get("name") for m in (tb.section_menu(pid) or [])[:4] if m.get("name")]
            secs = (tb.read_sections(pid, names) or {}).get("sections") or []
        got = struct(th.GroundedPair, th.GROUND_PROMPT.format(
            claim=ag._claim_str(claim)[:1200], realization=claim_ctx[:1600],
            title=c["_paper"].get("title", ""), sections=_fmt_sections_full(secs),
            assessment=(c.get("assessment") or "")[:800]))
        title = c["_paper"].get("title", "")[:40]
        if got is None:
            continue
        if got.withdraw:
            c["overlap_degree"] = "partial"
            c["withdraw_reason"] = got.withdraw_reason
            withdrawn.append(pid)
            print(f"    ground [{c['_paper']['threat']}] {title:42} -> WITHDRAWN")
            continue
        v = ev.verify_pair(got.claim_quote, got.paper_quote, tb._submission_text,
                           tb._paper_source_text(pid), ag.min_quote_tokens, ag.fuzzy_threshold)
        if v["fully_verified"]:
            c["evidence_pairs"] = [{
                "claim_quote": ev.expand_to_sentence(got.claim_quote, tb._submission_text),
                "paper_quote": ev.expand_to_sentence(got.paper_quote, tb._paper_source_text(pid)),
                "rationale": got.rationale,
                "claim_quote_verified": True, "paper_quote_verified": True}]
            repaired.append(pid)
        print(f"    ground [{c['_paper']['threat']}] {title:42} "
              f"-> {'GROUNDED' if v['fully_verified'] else 'pair did not verify'}")

    from agent.claim_agent import _usd
    usd = _usd(model, spend["pt"], spend["ct"])
    result = {"claim_id": claim_id, "ranked": ranked, "examined": examined,
              "stop_reason": stop or "loop_ended", "repaired": repaired,
              "withdrawn": withdrawn,
              "spend": spend, "usd": usd,
              "seconds": round(time.perf_counter() - t0, 1)}
    _render(claim, result)
    return result


def _render(claim: dict, r: dict) -> None:
    """The reviewer-facing page: strongest threat first, one block per paper.

    'What the paper does' and 'what that means for the claim' are one block rather than
    two: separated, the reviewer has to hold a paragraph about a stranger's paper in mind
    while reading a second paragraph about their own, for every one of eleven entries.
    """
    ex = sorted(r["examined"], key=lambda c: -c["_paper"]["threat"])
    print("\n" + "=" * W)
    print("REVIEW — threat-first")
    print("=" * W)
    print(_w("CLAIM: " + (claim.get("claim_text") or ""), ""))
    print()

    DEG = {"same": "delivers the same contribution", "substantial": "substantial overlap",
           "partial": "partial overlap", "superficial": "no overlap of contribution",
           "none": "unrelated to the claim"}
    threats = [c for c in ex if (c.get("overlap_degree") or "").lower() in ("same", "substantial")]
    print(f"{len(threats)} of {len(ex)} examined papers challenge this claim; "
          f"{len(r['ranked']) - len(ex)} lower-ranked papers were not examined.")
    print(f"Stopped because: {r['stop_reason']}")
    print()

    for c in ex:
        p = c["_paper"]
        deg = (c.get("overlap_degree") or "").lower()
        head = "CHALLENGE" if deg in ("same", "substantial") else "examined"
        print("-" * W)
        print(f"[{head}] threat {p['threat']}/10 · {DEG.get(deg, deg)}")
        print(_w(p.get("title", ""), "  "))
        note = c.get("assessment") or c.get("brief_note") or ""
        if note:
            print(); print(_w(note))
        pairs = [x for x in (c.get("evidence_pairs") or [])
                 if x.get("claim_quote_verified") and x.get("paper_quote_verified")]
        for x in pairs[:3]:
            print()
            print(_w('YOUR CLAIM: "' + " ".join(x["claim_quote"].split())[:150] + '…"', "    "))
            print(_w('THIS PAPER: "' + " ".join(x["paper_quote"].split())[:150] + '…"', "    "))
        # A comparison that produced no pair still produced verified spans of the paper;
        # leaving them out would show the reviewer an assertion where evidence exists.
        if not pairs:
            quotes = [x["content"] for x in (c.get("paper_realization") or [])
                      if x.get("kind") == "quote" and x.get("verified")]
            for q in quotes[:2]:
                print()
                print(_w('THIS PAPER: "' + " ".join(q.split())[:190] + '…"', "    "))
        if c.get("submission_delta"):
            print(); print(_w("STILL YOURS: " + c["submission_delta"][:400]))
        print()

    rest = [p for p in r["ranked"] if p["paper_id"] not in {c["_paper"]["paper_id"] for c in ex}]
    if rest:
        print("-" * W)
        print("Not examined — ranked below what was already settled:")
        for p in rest[:10]:
            print(f"  [{p['threat']}] {p.get('title', '')[:52]:54} {p['threat_reason'][:36]}")
        if len(rest) > 10:
            print(f"  … and {len(rest) - 10} more")
    print()
    print(f"{r['spend']['calls']} calls · {r['spend']['pt']:,}+{r['spend']['ct']:,} tokens · "
          f"${r['usd']:.4f} · {r['seconds']}s")


def main():
    ap = argparse.ArgumentParser(description="Threat-first examination, printed as a review")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--budget", type=int, default=6, help="most papers to examine")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)
    res = run(args.data_dir, args.submission, args.claim, args.model, args.budget)
    out = args.out or f"eval/out/threat_{args.submission}_{args.claim}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"written: {out}")


if __name__ == "__main__":
    main()

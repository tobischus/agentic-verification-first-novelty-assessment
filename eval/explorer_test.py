#!/usr/bin/env python3
"""
Run the tool-loop explorer on one claim and print what a reviewer would read.

Compared against the deep-claim-extraction pipeline on the same claim: what it found, what
it cost, and how much of it is checkable.

Usage
-----
  python eval/explorer_test.py --submission graphrag_when_to_use --claim claim_2
  python eval/explorer_test.py --submission ID --claim claim_1 --budget 12
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
    from agent import explorer as ex
    from agent import evidence as ev
    from agent import threat as th
    from agent import claim_agent as ca
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
        except Exception as e:                       # a failed turn must not end the run
            print(f"    [call failed] {type(e).__name__}: {str(e)[:200]}")
            return None
        spend["pt"] += a; spend["ct"] += b; spend["calls"] += 1
        return parsed

    tb = ClaimToolbox(data_dir, sid, claim, ag.embedder)
    claim_str = ag._claim_str(claim)
    claim_ctx = _segments_to_text(entry.get("claim_realization") or [])
    t0 = time.perf_counter()

    # ---- pass 1: every paper, retrieval only, no model call --------------- #
    scanned = ex.scan(tb, claim_str, tb._ranked())
    print(f"\nScanned {len(scanned)} papers (no model calls):")
    for p in scanned[:12]:
        print(f"  {p['scan']:.2f}  {p.get('title', '')[:70]}")

    # ---- pass 2: the tool loop -------------------------------------------- #
    state, history, stop = {}, [], None
    for turn in range(budget):
        defs = ex.deficits(scanned, state)
        act = struct(ex.Action, ex.ACT_PROMPT.format(
            claim=claim_str[:1200], realization=claim_ctx[:1400],
            pool=ex.pool_table(scanned, state, limit=20), history="\n".join(history[-12:]) or "(nothing yet)",
            gate=ex.gate_text(defs)))
        if act is None:
            stop = "no_action"; break
        tool, pid = (act.tool or "").strip().lower(), (act.paper_id or "").strip()
        st = state.setdefault(pid, {}) if pid else {}

        if tool == "finish":
            if defs:
                history.append(f"finish REFUSED by the gate: {defs[0]}")
                print(f"  [{turn}] finish -> REFUSED ({len(defs)} deficits)")
                continue
            stop = "gate_granted_finish"
            print(f"  [{turn}] finish -> granted")
            break

        if pid not in tb.pool:
            history.append(f"{tool} on unknown paper {pid} -- ignored")
            continue

        if tool == "read":
            hits = tb.read_paper(pid, query=act.query or claim_str)
            st["read"] = True
            txt = " / ".join(h["text"][:160] for h in (hits.get("passages") or [])[:2])
            history.append(f"read {pid} ({act.query[:60]}): {txt[:300]}")
            print(f"  [{turn}] read     {pid[:12]} — {act.why[:58]}")

        elif tool == "compare":
            # The SAME deep dive the pipeline runs: the sections the model asks for, the
            # comparison, then the evidence map. Comparing this loop against the pipeline
            # is only about which papers get opened; if the reading underneath differed
            # too, a difference in the output would have two possible causes.
            tb.ensure_fulltext(pid)
            pctx = ""
            if ca._AGENTIC_SECTIONS:
                pctx, _names, a, b, _ = ag._read_paper_agentic(tb, claim, pid, claim_ctx)
                spend["pt"] += a; spend["ct"] += b; spend["calls"] += 2
            comp, a, b = ag._section_compare(tb, claim, pid, claim_ctx, pctx)
            spend["pt"] += a; spend["ct"] += b; spend["calls"] += 1
            if ca._USE_EVIDENCE_MAP:
                comp, a, b = ag._map_evidence(tb, claim, pid, comp, pctx)
                spend["pt"] += a; spend["ct"] += b; spend["calls"] += 2
            ag._record(tb, pid, comp, log=False)
            stored = next((x for x in reversed(tb.ledger["comparisons"])
                           if x.get("paper_id") == pid), comp)
            deg = (stored.get("overlap_degree") or "").lower()
            st.update({"compared": True, "degree": deg, "comp": stored,
                       "grounded": any(p_.get("claim_quote_verified") and p_.get("paper_quote_verified")
                                       for p_ in (stored.get("evidence_pairs") or []))})
            history.append(f"compared {pid}: {deg} — {(stored.get('assessment') or '')[:200]}")
            print(f"  [{turn}] compare  {pid[:12]} -> {deg:12} — {act.why[:44]}")

        elif tool == "ground":
            if not st.get("compared"):
                history.append(f"ground {pid} before comparing it -- ignored")
                continue
            names = tb._sections_read.get(pid) or [
                m.get("name") for m in (tb.section_menu(pid) or [])[:4] if m.get("name")]
            secs = (tb.read_sections(pid, names) or {}).get("sections") or []
            got = struct(th.GroundedPair, th.GROUND_PROMPT.format(
                claim=claim_str[:1200], realization=claim_ctx[:1600],
                title=tb.pool[pid].get("title", ""), sections=_fmt_sections_full(secs),
                assessment=(st["comp"].get("assessment") or "")[:800]))
            if got is None:
                continue
            if got.withdraw:
                st["degree"] = "partial" if st["degree"] in ex.CHALLENGE else "superficial"
                st["comp"]["overlap_degree"] = st["degree"]
                st["comp"]["withdraw_reason"] = got.withdraw_reason
                st["grounded"] = True          # settled: the claim of overlap was retracted
                history.append(f"ground {pid}: WITHDRAWN -- {got.withdraw_reason[:160]}")
                print(f"  [{turn}] ground   {pid[:12]} -> withdrawn")
            else:
                v = ev.verify_pair(got.claim_quote, got.paper_quote, tb._submission_text,
                                   tb._paper_source_text(pid), ag.min_quote_tokens,
                                   ag.fuzzy_threshold)
                if v["fully_verified"]:
                    st["comp"]["evidence_pairs"] = [{
                        "claim_quote": ev.expand_to_sentence(got.claim_quote, tb._submission_text),
                        "paper_quote": ev.expand_to_sentence(got.paper_quote,
                                                             tb._paper_source_text(pid)),
                        "rationale": got.rationale,
                        "claim_quote_verified": True, "paper_quote_verified": True}]
                    st["grounded"] = True
                history.append(f"ground {pid}: "
                               f"{'pair verified' if v['fully_verified'] else 'pair did not verify'}")
                print(f"  [{turn}] ground   {pid[:12]} -> "
                      f"{'GROUNDED' if v['fully_verified'] else 'not verified'}")
        else:
            history.append(f"unknown tool {tool} -- ignored")
    else:
        stop = "budget_exhausted"

    from agent.claim_agent import _usd
    res = {"claim_id": claim_id, "claim": claim, "scanned": scanned, "state": state,
           "history": history, "stop_reason": stop or "loop_ended",
           "deficits_left": ex.deficits(scanned, state), "spend": spend,
           "usd": _usd(model, spend["pt"], spend["ct"]),
           "seconds": round(time.perf_counter() - t0, 1)}
    _render(res)
    return res


def _render(r: dict) -> None:
    st = r["state"]
    comps = [(pid, s) for pid, s in st.items() if s.get("comp")]
    ch = [(p, s) for p, s in comps if (s.get("degree") or "") in ("same", "substantial")]
    print("\n" + "=" * W)
    print("REVIEW — tool loop")
    print("=" * W)
    print(_w("CLAIM: " + (r["claim"].get("claim_text") or ""), ""))
    print()
    print(f"{len(r['scanned'])} papers scanned · {len(comps)} compared · {len(ch)} challenge "
          f"the claim · stopped: {r['stop_reason']}")
    if r["deficits_left"]:
        print(f"Left unresolved: {r['deficits_left'][0]}")
    print()
    for pid, s in sorted(comps, key=lambda x: -(dict((p['paper_id'], p['scan'])
                                                     for p in r["scanned"]).get(x[0], 0))):
        c = s["comp"]
        deg = (s.get("degree") or "").lower()
        head = "CHALLENGE" if deg in ("same", "substantial") else deg
        title = next((p.get("title", "") for p in r["scanned"] if p["paper_id"] == pid), pid)
        print("-" * W)
        print(f"[{head}] {title[:80]}")
        note = c.get("assessment") or c.get("brief_note") or ""
        if note:
            print(); print(_w(note))
        for x in (c.get("evidence_pairs") or [])[:2]:
            if x.get("claim_quote_verified") and x.get("paper_quote_verified"):
                print()
                print(_w('YOUR CLAIM: "' + " ".join(x["claim_quote"].split())[:150] + '…"', "    "))
                print(_w('THIS PAPER: "' + " ".join(x["paper_quote"].split())[:150] + '…"', "    "))
        if c.get("withdraw_reason"):
            print(); print(_w("Overlap claim withdrawn: " + c["withdraw_reason"][:300]))
        if c.get("submission_delta"):
            print(); print(_w("STILL YOURS: " + c["submission_delta"][:320]))
        print()
    print(f"{r['spend']['calls']} calls · {r['spend']['pt']:,}+{r['spend']['ct']:,} tokens · "
          f"${r['usd']:.4f} · {r['seconds']}s")


def main():
    ap = argparse.ArgumentParser(description="Tool-loop explorer over the whole pool")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--model", default=os.getenv("NOVELTY_AGENT_MODEL", "gpt-5-mini"))
    ap.add_argument("--budget", type=int, default=14, help="most turns the loop may take")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    os.chdir(REPO)
    res = run(args.data_dir, args.submission, args.claim, args.model, args.budget)
    out = args.out or f"eval/out/explorer_{args.submission}_{args.claim}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str),
                         encoding="utf-8")
    print(f"written: {out}")


if __name__ == "__main__":
    main()

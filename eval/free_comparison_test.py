import json, os, sys, time
sys.path.insert(0, "src/novelty_assessment")
from dotenv import load_dotenv; load_dotenv()
from agent import elements as el
from agent.claim_agent import ClaimNoveltyAgent, _fmt_sections_full
from agent.tools import ClaimToolbox

sid = sys.argv[1] if len(sys.argv) > 1 else "graphrag_when_to_use"
only = sys.argv[2] if len(sys.argv) > 2 else ""
art = json.load(open(f"data/{sid}/{sid}_artifact_a.json", encoding="utf-8"))
cd = json.load(open(f"data/{sid}/{sid}_claims.json", encoding="utf-8"))
by = {c["id"]: c for c in cd["claims"]}
ag = ClaimNoveltyAgent("data", sid, model_name="gpt-5-mini")
spend = {"pt": 0, "ct": 0, "n": 0}
def struct(schema, prompt):
    p, a, b = ag._struct(schema, prompt); spend["pt"] += a; spend["ct"] += b; spend["n"] += 1; return p

out, t0 = [], time.perf_counter()
for entry in art["claims"]:
    cid = entry["claim_id"]
    if only and cid != only: continue
    claim = by[cid]; tb = ClaimToolbox("data", sid, claim, ag.embedder)
    passages = el.sentences_of([s["content"] for s in (entry.get("claim_realization") or [])
                if s.get("kind") == "quote" and s.get("verified")])
    for c in entry.get("comparisons", []):
        if not c.get("sections_used"): continue
        tb.ensure_fulltext(c["paper_id"])
        got = tb.read_sections(c["paper_id"], c["sections_used"])
        sec = _fmt_sections_full(got.get("sections") or [])
        if not sec.strip(): continue
        r = el.compare_free(struct, ag._claim_str(claim), passages, c.get("title", ""),
                            sec, tb._paper_source_text(c["paper_id"]))
        r["claim_id"] = cid; r["title"] = c.get("title"); r["run_degree"] = (c.get("overlap_degree") or "").lower()
        out.append(r)
        g = sum(1 for x in r["contacts"] if x["grounded"])
        print(f"  {cid}  run={r['run_degree']:12} free={r['degree']:12} "
              f"contacts={len(r['contacts'])} (belegt {g})  {r['title'][:40]}")
json.dump({"spend": spend, "results": out}, open("eval/out/free_" + sid + ".json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n{spend['n']} calls, {spend['pt']:,}+{spend['ct']:,} tok, {(time.perf_counter()-t0)/60:.1f} min")

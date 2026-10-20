"""Checks for the claim-level assessment (src/novelty_assessment/claim_assessment.py).
No model call. Run from the repository root:  python eval/claim_assessment_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "src/novelty_assessment")
import battle_export as be          # noqa: E402
import claim_assessment as ca       # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def cmp(pid, degree, status, pds=None, refute=False):
    return {"paper_id": pid, "title": pid, "overlap_degree": degree,
            "refutation_status": "can_refute" if refute else "",
            "evidence_check": {"status": status, "proposed_degree_supported": pds}}


entry = {"comparisons": [cmp("a", "partial", "material", True),
                         cmp("b", "partial", "material", False),
                         cmp("c", "superficial", "material"),
                         cmp("d", "none", "")]}
refs = {"a": "R1", "b": "R2", "c": "R3", "d": "R4"}
filler = " ".join(["word"] * 70)

p = ca.consistency_problems("R9 overlaps. " + filler, entry, "not_challenged", refs)
check("an id that is not among the claim's comparisons is caught", any("R9" in x for x in p))
p = ca.consistency_problems("R2 is a confirmed partial overlap. " + filler, entry, "not_challenged", refs)
check("an unconfirmed level called confirmed is caught", any("NOT confirmed" in x for x in p))
p = ca.consistency_problems("R1 remains unsupported. " + filler, entry, "not_challenged", refs)
check("a confirmed level called unsupported is caught", any("WAS confirmed" in x for x in p))
p = ca.consistency_problems("R1 is a confirmed partial overlap; R2 is not confirmed. " + filler,
                            entry, "not_challenged", refs)
check("correct statements pass", not p, p)
p = ca.consistency_problems("The claim is anticipated by R1. " + filler, entry, "not_challenged", refs)
check("'not challenged' contradicted is caught", any("not challenged" in x for x in p))
p = ca.consistency_problems("Too short.", entry, "not_challenged", refs)
check("word budget enforced", any("words" in x for x in p))

f = ca.build_claim_findings(entry, 1, "claim", "not_challenged", refs)
check("findings give counts, not ids, for comparisons without a section",
      "R4" not in f and "other comparisons (no detailed section): 1" in f)
check("a superficial/material conflict is stated in its direction", "is LOWER than" in f)
check("an unconfirmed partial is marked NOT established", "did NOT support the proposed level" in f)

# The 20 human-study reports: every stored assessment is current and printed.
keys = sorted(p.name for p in Path("final_evaluation/inputs/main").iterdir() if p.is_dir())
n = current = printed = 0
for key in keys:
    for v in ("agent", "linear"):
        contexts, _p, b, _r = ca.contexts_for("data", key, v)
        stored = {x["claim_id"]: x.get("claim_assessment") for x in b["per_claim"]}
        md = " ".join(be.build("data", key, variant=v).split())
        for cid, _i, _e, _v, findings in contexts:
            n += 1
            s = stored.get(cid)
            current += bool(s) and not ca.is_stale(s, findings)
            printed += bool(s) and " ".join(s["text"].split()) in md
check("every stored claim assessment is current", current == n, f"{current}/{n}")
check("every stored claim assessment is printed by the export", printed == n, f"{printed}/{n}")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)

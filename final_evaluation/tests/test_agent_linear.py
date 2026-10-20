"""Agent vs linear from the run records. No server, no database, no API call.

The unit tests build their own run logs; the last two tests read the real artifacts of the
20 E1 papers (gitignored) and are skipped without them.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from final_evaluation.evaluation import agent_linear as al  # noqa: E402
from final_evaluation.evaluation.e1 import analyze as an  # noqa: E402

OVERLAP = ("same", "substantial", "partial")


def _pw(pid, state, compares, trace=()):
    rounds = []
    for t in range(compares):
        rounds += [{"turn": t, "call": "semantic_compare"}, {"turn": t, "call": "evidence_map"}]
    return {"paper_id": pid, "final_state": state, "rounds": rounds,
            "decision_trace": list(trace)}


def _artifact(*pws):
    return {"claims": [{"claim_id": "claim_1", "run_log": {"prior_work": list(pws)}}]}


def test_pair_endings_follow_the_state_model():
    art = _artifact(
        _pw("p_dismissed", "dismissed", 0),
        _pw("p_passed", "checked", 1),
        _pw("p_reentry", "checked", 2),
        _pw("p_open_agent", "budget_exhausted", 2),
        _pw("p_open_linear", "budget_exhausted", 1),
    )
    ends = al.pair_endings(art)
    assert ends[("claim_1", "p_dismissed")] == "dismissed"
    assert ends[("claim_1", "p_passed")] == "checked"
    assert ends[("claim_1", "p_reentry")] == "resolved_by_reentry"
    assert ends[("claim_1", "p_open_agent")] == "unresolved"
    assert ends[("claim_1", "p_open_linear")] == "unresolved"

    c = al.endings(art)
    assert c["dismissed"] == 1 and c["compared"] == 4
    assert c["first_check_failed"] == 3 == c["resolved_by_reentry"] + c["unresolved"]


def test_paired_counts_papers_and_leaves_ties_out_of_the_sign_test():
    per_paper = {
        "a": {"agent": {"x": 1}, "linear": {"x": 3}},
        "b": {"agent": {"x": 2}, "linear": {"x": 5}},
        "c": {"agent": {"x": 4}, "linear": {"x": 4}},
        "d": {"agent": {"x": 6}, "linear": {"x": 1}},
    }
    t = al.paired(per_paper, "x")
    assert (t["agent"], t["linear"]) == (13, 13)
    assert (t["agent_lower"], t["agent_higher"], t["equal"]) == (2, 1, 1)
    assert t["p"] == an.sign_test(2, 1)

    nested = {k: {"matched": v} for k, v in per_paper.items()}
    assert al.paired(nested, "x", "matched") == t


def test_holm_is_monotone_and_capped():
    adj = al.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert adj["a"] == pytest.approx(0.04)          # 4 * 0.01
    assert adj["c"] == pytest.approx(0.09)          # 3 * 0.03
    assert adj["b"] == pytest.approx(0.09)          # max(0.09, 2 * 0.04)
    assert adj["d"] == pytest.approx(0.5)
    assert al.holm({"a": 0.6, "b": 0.7})["b"] == 1.0


def test_reentry_outcomes_compare_the_first_and_the_last_turn():
    found = _pw("p1", "checked", 2, [
        "[0] SEMANTIC DEGREE: partial", "[0] EVIDENCE CHECK: status=insufficient",
        "[1] SEMANTIC DEGREE: partial", "[1] EVIDENCE CHECK: status=material"])
    withdrawn = _pw("p2", "checked", 2, [
        "[0] SEMANTIC DEGREE: partial", "[0] EVIDENCE CHECK: status=insufficient",
        "[1] SEMANTIC DEGREE: superficial", "[1] EVIDENCE CHECK: status=nonmaterial"])
    still_open = _pw("p3", "budget_exhausted", 2, [
        "[0] SEMANTIC DEGREE: superficial", "[0] EVIDENCE CHECK: status=material",
        "[1] SEMANTIC DEGREE: superficial", "[1] EVIDENCE CHECK: status=material"])
    once = _pw("p4", "checked", 1, ["[0] SEMANTIC DEGREE: none"])
    c = al.reentry_outcomes(_artifact(found, withdrawn, still_open, once), OVERLAP)
    assert c == {("resolved", "overlap_confirmed", "evidence"): 1,
                 ("resolved", "overlap_rejected", "both"): 1,
                 ("unresolved", "disagreement", "neither"): 1}


def test_a_changed_artifact_is_refused(tmp_path):
    f = tmp_path / "artifact.json"
    f.write_text("{}", encoding="utf-8")
    good = hashlib.sha256(f.read_bytes()).hexdigest()
    assert al._checked("artifact.json", good, tmp_path) == f
    with pytest.raises(SystemExit):
        al._checked("artifact.json", "0" * 64, tmp_path)
    with pytest.raises(SystemExit):
        al._checked("missing.json", good, tmp_path)


def _have_artifacts() -> bool:
    try:
        entries = al.paper_entries()
    except OSError:
        return False
    return all((ROOT / e["systems"][v]["provenance"]["artifact_a_path"].replace("\\", "/")).exists()
               for _, _, e in entries for v in al.VARIANTS)


@pytest.mark.skipif(not _have_artifacts(), reason="run artifacts of the E1 papers not present")
def test_real_run_records_add_up():
    res = al.analyze()
    assert res["papers"] == 20
    assert not res["unexpected_endings"]
    for paper, rec in res["per_paper"].items():
        for v in al.VARIANTS:
            x = rec[v]
            assert x["dismissed"] + x["compared"] == x["comparisons_recorded"], (paper, v)
            assert x["first_check_failed"] == x["resolved_by_reentry"] + x["unresolved"], (paper, v)
        assert rec["linear"]["dismissed"] == rec["linear"]["resolved_by_reentry"] == 0
        assert rec["matched"]["agent"]["pairs"] == rec["matched"]["linear"]["pairs"] \
            == rec["agent"]["compared"]
    outcomes = res["reentry_outcomes"]
    assert not [o for o in outcomes if o["end"] == "unparsed"]
    # In these runs every unresolved agent pair was compared twice, so every one is traced.
    assert sum(o["n"] for o in outcomes) == sum(
        res["reentry"]["agent"][k] for k in ("resolved_by_reentry", "unresolved"))
    assert sum(o["n"] for o in outcomes if o["end"] == "resolved") \
        == res["reentry"]["agent"]["resolved_by_reentry"]


@pytest.mark.skipif(not _have_artifacts(), reason="run artifacts of the E1 papers not present")
def test_adjudication_packet_keeps_part_a_free_of_readings(tmp_path):
    import json

    from final_evaluation.scripts import adjudication_packet as ap

    res = ap.build(tmp_path)
    text = (tmp_path / "divergent_claims.md").read_text(encoding="utf-8")
    part_a, part_b = text.split("# Part B — the two assessments")
    # The paper texts themselves may say "agent"; what must not appear is a reading.
    for leak in ("Overlap degree", "Assessment X", "Assessment Y", "challenging the claim",
                 "[same]", "[weaker]", "can_refute", "not_challenged", "left unresolved",
                 "evidence check passed", "linear baseline"):
        assert leak not in part_a.split("# Part A — the evidence")[1], leak
    assert part_b.count("| Overlap degree |") >= res["cases"]

    key = json.loads((tmp_path / "key.json").read_text(encoding="utf-8"))
    assert len(key) == res["cases"]
    assert all({k["X"], k["Y"]} == {"agent", "linear"} for k in key.values())

    # A second run never overwrites decisions that may already be filled in.
    (tmp_path / "decisions.csv").write_text("filled", encoding="utf-8")
    again = ap.build(tmp_path)
    assert (tmp_path / "decisions.csv").read_text(encoding="utf-8") == "filled"
    assert again["decisions"].endswith("decisions.template.csv")

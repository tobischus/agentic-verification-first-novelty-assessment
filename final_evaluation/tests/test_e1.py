"""E1 plan and the E1-vs-human comparison. No server, no database, no API call.

The plan test reads the local frozen inputs (gitignored) and is skipped without them; the
comparison tests build their own export ZIP and judge file.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from final_evaluation.evaluation.e1 import adapter  # noqa: E402
from final_evaluation.evaluation.e2 import analyze  # noqa: E402

E1_CONFIG = "final_evaluation/config/e1_main.yaml"
MAIN_CONFIG = ROOT / "final_evaluation/config/main.yaml"
HAVE_MAIN_INPUTS = (ROOT / "final_evaluation/inputs/main").is_dir()


@pytest.mark.skipif(not HAVE_MAIN_INPUTS, reason="frozen main-study inputs not present")
def test_plan_covers_every_pair_in_both_orders_and_marks_the_human_tasks():
    plan = adapter.build_plan(E1_CONFIG)
    main = yaml.safe_load(MAIN_CONFIG.read_text(encoding="utf-8"))
    human = [c for c in plan["calls"] if c["paper_set"] == "human_rated"]
    assert len(human) == 10 * 10 * 2

    ordered = Counter((c["paper_id"], c["system_a"], c["system_b"]) for c in human)
    assert set(ordered.values()) == {1}
    for paper in main["papers"]:
        for x, y in itertools.combinations(adapter.SYSTEMS, 2):
            assert ordered[(paper, x, y)] == 1 and ordered[(paper, y, x)] == 1

    marked = {(c["paper_id"], frozenset((c["system_a"], c["system_b"])))
              for c in human if c["human_task"]}
    assert marked == {(t["paper"], frozenset(t["pair"])) for t in main["tasks"]}
    assert all(c["content_version_a"] and c["content_version_b"] for c in human)
    assert plan["rubric_version"] == main["study"]["rubric_version"]
    assert [c["call_index"] for c in plan["calls"]] == list(range(1, len(plan["calls"]) + 1))


@pytest.mark.skipif(not HAVE_MAIN_INPUTS, reason="frozen main-study inputs not present")
def test_plan_filters_keep_the_full_plan_indices():
    full = adapter.build_plan(E1_CONFIG)
    part = adapter.build_plan(E1_CONFIG, papers="hubble", pairs="agent:linear")
    assert len(part["calls"]) == 2 and part["filtered"]
    idx = {(c["paper_id"], c["system_a"], c["system_b"]): c["call_index"] for c in full["calls"]}
    for c in part["calls"]:
        assert idx[(c["paper_id"], c["system_a"], c["system_b"])] == c["call_index"]


def test_resume_refuses_a_file_from_another_run(tmp_path):
    out = tmp_path / "judge_calls.jsonl"
    out.write_text(json.dumps({"e1_id": "other", "rubric_version": "novelty_report_judge_v5",
                               "paper_id": "p", "system_a": "a", "system_b": "b"}) + "\n",
                   encoding="utf-8")
    with pytest.raises(SystemExit):
        adapter._load_done(out, {"e1_id": "e1_main_v5", "rubric_version": "novelty_report_judge_v5"})


def test_e1_only_config_is_never_seeded():
    from final_evaluation.scripts import seed
    with pytest.raises(SystemExit):
        seed._study_config("final_evaluation/config/e1_extra.yaml")


# --- compare_to_e1 ----------------------------------------------------------------

CRITS = analyze.CRITERIA
RUBRIC = "novelty_report_judge_v5"
RUBRIC_TEXT = (ROOT / "final_evaluation/prompts" / f"{RUBRIC}.txt").read_text(encoding="utf-8")


def _export(tmp_path, ratings, versions, rubric_text=RUBRIC_TEXT):
    p = tmp_path / "export.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("ratings.jsonl", "\n".join(json.dumps(r) for r in ratings))
        if rubric_text is not None:
            z.writestr("rubric.txt", rubric_text)
        z.writestr("manifest.json", json.dumps({
            "study_id": "main_study_v2", "rubric_version": RUBRIC,
            "reports": [{"report_id": f"{p_}::{s}", "paper_id": p_, "system_id": s,
                         "content_version": v} for (p_, s), v in versions.items()]}))
    return str(p)


def _rating(a, b, winner, code="M01"):
    return {"status": "submitted", "paper_id": "p1", "system_a": a, "system_b": b,
            "participant_code": code, "is_test_participant": False, "is_practice": False,
            "criteria": {c: {"winner": winner} for c in CRITS}}


def _judge(a, b, winner, cv_a, cv_b, rubric=RUBRIC):
    return {"paper_id": "p1", "system_a": a, "system_b": b, "rubric_version": rubric,
            "content_version_a": cv_a, "content_version_b": cv_b,
            "parsed_result": {"criteria": {c: {"winner": winner} for c in CRITS}}}


def _write(tmp_path, calls):
    p = tmp_path / "judge_calls.jsonl"
    p.write_text("\n".join(json.dumps(c) for c in calls), encoding="utf-8")
    return str(p)


def test_compare_matches_orientation_and_content(tmp_path):
    versions = {("p1", "agent"): "v-agent", ("p1", "afzal"): "v-afzal"}
    # Rater saw agent as A and chose A (agent). Judge, same orientation, chose A (agent);
    # the other orientation also picks agent -> stable.
    zip_path = _export(tmp_path, [_rating("agent", "afzal", "A")], versions)
    e1 = _write(tmp_path, [_judge("agent", "afzal", "A", "v-agent", "v-afzal"),
                           _judge("afzal", "agent", "B", "v-afzal", "v-agent")])
    r = analyze.compare_to_e1(zip_path, e1)
    assert r["comparable_responses"] == 1 and not r["not_comparable"]
    d = r["by_criterion"]["submission_fidelity"]
    assert (d["compared"], d["agree"], d["stable_compared"], d["stable_agree"]) == (1, 1, 1, 1)


def test_compare_refuses_other_content_other_rubric_and_other_orientation(tmp_path):
    versions = {("p1", "agent"): "v-agent", ("p1", "afzal"): "v-afzal"}
    zip_path = _export(tmp_path, [_rating("agent", "afzal", "A")], versions)

    stale = _write(tmp_path, [_judge("agent", "afzal", "A", "OLD", "v-afzal")])
    r = analyze.compare_to_e1(zip_path, stale)
    assert r["comparable_responses"] == 0 and sum(r["not_comparable"].values()) == 1

    other_rubric = _write(tmp_path, [_judge("agent", "afzal", "A", "v-agent", "v-afzal",
                                            rubric="novelty_report_judge_v3")])
    assert analyze.compare_to_e1(zip_path, other_rubric)["comparable_responses"] == 0

    # Only the swapped orientation exists: never used in place of the rater's own.
    swapped = _write(tmp_path, [_judge("afzal", "agent", "B", "v-afzal", "v-agent")])
    assert analyze.compare_to_e1(zip_path, swapped)["comparable_responses"] == 0


def test_compare_treats_unclear_as_missing_and_skips_test_raters(tmp_path):
    versions = {("p1", "agent"): "v-agent", ("p1", "afzal"): "v-afzal"}
    test_rating = dict(_rating("agent", "afzal", "B", code="PV01"), is_test_participant=True)
    zip_path = _export(tmp_path, [_rating("agent", "afzal", "unclear"), test_rating], versions)
    e1 = _write(tmp_path, [_judge("agent", "afzal", "A", "v-agent", "v-afzal")])
    r = analyze.compare_to_e1(zip_path, e1)
    assert r["human_responses"] == 1
    d = r["by_criterion"]["conclusion_warrant"]
    assert d["compared"] == 0 and d["human_unclear"] == 1 and d["agreement"] is None


def test_cache_parts_are_the_same_text_as_the_single_string():
    """Billing change only: the three parts concatenate to exactly the pilot's user string,
    with breakpoints after the submission and after report A -- never after report B."""
    import importlib
    pj = adapter._judge()
    importlib.reload(pj)
    sub, a, b = "S0001 x\nS0002 {y}", "A0001 report a", "B0001 report b\nB0002 end"
    parts = pj.user_parts(sub, a, b)
    assert "".join(p["text"] for p in parts) == pj.USER_TEMPLATE.format(
        submission=sub, report_a=a, report_b=b)
    assert [("prompt_cache_breakpoint" in p) for p in parts] == [True, True, False]
    assert parts[0]["text"].endswith(sub) and parts[1]["text"].endswith(a)


def test_cache_order_groups_by_paper_then_report_a_without_new_randomness():
    calls = [{"paper_id": p, "system_a": s, "system_b": t, "i": i} for i, (p, s, t) in enumerate([
        ("p2", "agent", "linear"), ("p1", "linear", "agent"), ("p2", "afzal", "agent"),
        ("p1", "agent", "afzal"), ("p2", "agent", "afzal"), ("p1", "linear", "afzal")])]
    out = adapter.cache_order(calls)
    assert sorted(c["i"] for c in out) == list(range(6))
    assert [c["paper_id"] for c in out] == ["p2"] * 3 + ["p1"] * 3      # first-seen paper first
    assert [(c["paper_id"], c["system_a"]) for c in out] == [
        ("p2", "agent"), ("p2", "agent"), ("p2", "afzal"),
        ("p1", "linear"), ("p1", "linear"), ("p1", "agent")]
    assert [c["i"] for c in out][:2] == [0, 4]                          # shuffle order kept inside


def test_billed_usd_prices_writes_reads_flex_and_long_context():
    base = {"output_tokens": 1000, "service_tier": "default"}
    r = {**base, "input_tokens": 100_000, "cache_tokens": 20_000, "cache_write_tokens": 50_000}
    # 30k plain x2 + 50k write x2.5 + 20k read x0.2 + 1k out x12  (per 1M)
    assert abs(adapter.billed_usd(r) - (0.06 + 0.125 + 0.004 + 0.012)) < 1e-9
    assert abs(adapter.billed_usd({**r, "service_tier": "flex"}) - (0.06 + 0.125 + 0.004 + 0.012) / 2) < 1e-9
    long = {**base, "input_tokens": 275_989, "cache_tokens": 0, "cache_write_tokens": 275_989}
    assert abs(adapter.billed_usd(long) - (275_989 * 2.5 * 2 + 1000 * 18) / 1e6) < 1e-9
    assert adapter.billed_usd({**base, "input_tokens": 5, "cache_tokens": 0}) is None


def test_usage_counts_reads_cache_from_the_raw_usage_on_every_tier():
    """langchain files flex reads under `flex_cache_read`; the raw usage is authoritative."""
    from types import SimpleNamespace
    pj = adapter._judge()
    raw = {"prompt_tokens_details": {"cached_tokens": 54909, "cache_write_tokens": 0}}
    msg = SimpleNamespace(
        usage_metadata={"input_tokens": 114894, "output_tokens": 900,
                        "input_token_details": {"flex_cache_read": 54909, "flex": 59985},
                        "output_token_details": {"flex_reasoning": 300}},
        response_metadata={"token_usage": raw, "service_tier": "flex"})
    u = pj.usage_counts(msg)
    assert (u["cache_tokens"], u["cache_write_tokens"], u["reasoning_tokens"]) == (54909, 0, 300)
    # no raw usage: fall back to whichever *cache_read key langchain used
    msg.response_metadata = {}
    assert pj.usage_counts(msg)["cache_tokens"] == 54909


def _rec(paper, a, b, winners, chars=(100, 200), **kw):
    return {"paper_id": paper, "system_a": a, "system_b": b, "paper_set": "main", "call_index": kw.get("i", 0),
            "context_chars": {"report_a": chars[0], "report_b": chars[1]},
            "parsed_result": {"criteria": {c: {"winner": w} for c, w in zip(E1_CRITERIA, winners)}}}


E1_CRITERIA = ("submission_fidelity", "comparison_specificity", "presented_evidence",
               "conclusion_warrant", "reviewer_usefulness")


def test_stable_verdict_needs_both_orders_to_agree():
    from final_evaluation.evaluation.e1 import analyze as an
    # criterion order: stable agent | tie both | agent then tie | unclear once | A both (position)
    xy = _rec("p", "agent", "linear", ["A", "tie", "A", "unclear", "A"])
    yx = _rec("p", "linear", "agent", ["B", "tie", "tie", "A", "A"])
    u = an.units([xy, yx])[("p", ("agent", "linear"))]
    assert [an.stable_verdict(u, c) for c in E1_CRITERIA] == [
        "agent", "tie", "inconsistent", "unclear", "inconsistent"]
    assert an.stable_verdict(an.units([xy])[("p", ("agent", "linear"))], E1_CRITERIA[0]) == "incomplete"


def test_sign_test_and_pair_table():
    from final_evaluation.evaluation.e1 import analyze as an
    assert an.sign_test(5, 0) == 0.0625 and an.sign_test(0, 0) == 1.0 and an.sign_test(3, 3) == 1.0
    recs = []
    for i, p in enumerate(("p1", "p2", "p3")):
        recs += [_rec(p, "agent", "afzal", ["A"] * 5), _rec(p, "afzal", "agent", ["B"] * 5)]
    t = an.pair_table(an.units(recs), E1_CRITERIA[0], ("agent", "afzal"))
    assert (t["papers"], t["agent_wins"], t["afzal_wins"], t["net_preference"]) == (3, 3, 0, 1.0)
    assert t["ci95"] == [1.0, 1.0]


def test_bradley_terry_orders_a_dominance_chain():
    from final_evaluation.evaluation.e1 import analyze as an
    recs = []
    for p in ("p1", "p2", "p3", "p4"):
        for x, y in (("agent", "linear"), ("linear", "afzal"), ("agent", "afzal")):
            recs += [_rec(p, x, y, ["A"] * 5), _rec(p, y, x, ["B"] * 5)]
    bt = an.bradley_terry(an.units(recs), E1_CRITERIA[0])
    assert list(bt) == ["agent", "linear", "afzal"]


def test_elo_is_bradley_terry_on_the_elo_scale():
    from final_evaluation.evaluation.e1 import analyze as an
    # agent beats linear on p1-p3, loses on p4: 3:1, plus 0.5 pseudo-wins each way -> odds 3.5:1.5
    recs = []
    for p, w in (("p1", "A"), ("p2", "A"), ("p3", "A"), ("p4", "B")):
        recs += [_rec(p, "agent", "linear", [w] * 5), _rec(p, "linear", "agent", ["B" if w == "A" else "A"] * 5)]
    us = an.units(recs)
    e = an.elo(us, (E1_CRITERIA[0],))
    r = e["ratings"]
    assert list(r) == ["agent", "linear"] and e["games"] == 4 and e["papers"] == 4
    assert abs((r["agent"]["elo"] - r["linear"]["elo"]) - 400 * math.log10(3.5 / 1.5)) < 0.2
    assert abs((r["agent"]["elo"] + r["linear"]["elo"]) / 2 - 1000) < 0.1
    assert r["agent"]["ci95"][0] <= r["agent"]["elo"] <= r["agent"]["ci95"][1]
    assert 0.5 < e["bootstrap_share_higher"]["agent>linear"] <= 1.0
    on = an.online_elo(us, (E1_CRITERIA[0],), orders=50)
    assert list(on) == ["agent", "linear"] and abs(sum(on.values()) - 2000) < 0.1


def test_shared_rank_follows_the_arena_rule():
    from final_evaluation.evaluation.e1 import analyze as an
    ratings = {"a": {"ci95": [1400, 1600]}, "b": {"ci95": [1350, 1550]},
               "c": {"ci95": [700, 860]}, "d": {"ci95": [600, 740]}, "e": {"ci95": [480, 690]}}
    ranks = {s: an.shared_rank(ratings, s) for s in ratings}
    # overlapping CIs share a rank; a system is behind only those whose CI lies wholly above
    assert ranks == {"a": 1, "b": 1, "c": 3, "d": 3, "e": 4}


def test_sensitivity_fit_without_covariate_is_the_plain_bradley_terry():
    from final_evaluation.evaluation.e1 import analyze as an, sensitivity as se
    games = [("agent", "linear", "agent"), ("agent", "linear", "linear"), ("agent", "afzal", "agent"),
             ("linear", "afzal", "tie"), ("linear", "afzal", "linear"), ("agent", "afzal", "agent")]
    plain = an._bt_fit(games)
    th, beta = se.fit([(x, y, 1.0 if v == x else 0.5 if v == "tie" else 0.0, ()) for x, y, v in games])
    assert beta == [] and all(abs(th[s] - plain[s]) < 1e-9 for s in plain)
    # with an all-zero covariate the slope stays 0 and the strengths do not move
    th0, beta0 = se.fit([(x, y, 1.0 if v == x else 0.5 if v == "tie" else 0.0, (0.0,)) for x, y, v in games])
    assert abs(beta0[0]) < 1e-9 and all(abs(th0[s] - plain[s]) < 1e-9 for s in plain)


def test_sensitivity_fit_separates_a_planted_length_effect():
    from final_evaluation.evaluation.e1 import sensitivity as se
    # equal systems; the longer report (dz=+1) wins 9 of 10 -> positive slope, strengths ~equal
    obs = [("agent", "linear", 1.0, (1.0,))] * 9 + [("agent", "linear", 0.0, (1.0,))]
    obs += [("agent", "linear", 0.0, (-1.0,))] * 9 + [("agent", "linear", 1.0, (-1.0,))]
    th, beta = se.fit(obs)
    assert beta[0] > 1.0 and abs(th["agent"] - th["linear"]) < 1e-6


def test_detailed_comparisons_counts_only_claim_review_blocks():
    from final_evaluation.evaluation.e1 import sensitivity as se
    text = ("# Report\n\n### R9 — not in a claim review\n"
            "\n# Claim 1 — Review\n\n## Detailed comparisons\n\n### R17 — A\n\ntext\n\n### R1 — B\n"
            "\n# Claim 2 — Review\n\n## Evidence limits\n")
    assert se.detailed_comparisons(text) == 2


def test_length_effect_counts_the_longer_report():
    from final_evaluation.evaluation.e1 import analyze as an
    # agent's report is the longer one (200 vs 100 when agent is B in the first call)
    recs = [_rec("p", "linear", "agent", ["B"] * 5, chars=(100, 200)),
            _rec("p", "agent", "linear", ["A"] * 5, chars=(200, 100))]
    le = an.length_effect(an.units(recs), E1_CRITERIA[0])
    assert (le["stable_preferences"], le["longer_won"]) == (1, 1)


# --- the E1 judge config and rubric v5 ----------------------------------------------

@pytest.mark.skipif(not HAVE_MAIN_INPUTS, reason="frozen main-study inputs not present")
def test_main_plan_uses_its_own_judge_and_directory():
    plan = adapter.build_plan(E1_CONFIG)
    assert not plan["problems"]
    assert (plan["model"], plan["effort"], plan["rubric_version"], plan["inventory"]) == (
        "gpt-6.1-sol", "medium", "novelty_report_judge_v5", True)
    assert plan["default_out_dir"] == "final_evaluation/results/main/e1"


def test_rubric_criteria_section_is_found():
    crit = analyze.criteria_text(RUBRIC_TEXT)
    assert crit and all(c in crit for c in CRITS)


def _v5_response(**inv_overrides):
    report = {"contributions_examined": "most", "off_point_material": "low",
              "repetition": "medium", "unsupported_or_contradicted": "low"}
    inv = {"central_contributions": ["c1", "c2"], "A": dict(report), "B": dict(report)}
    inv.update(inv_overrides)
    return {"inventory": inv,
            "criteria": {c: {"winner": "tie", "reason": "r", "locators": []} for c in E1_CRITERIA}}


def test_validate_requires_the_inventory_only_when_asked():
    pj = adapter._judge()
    no_inv = {"criteria": _v5_response()["criteria"]}
    assert pj.validate(no_inv, set()) == []                     # without inventory unchanged
    assert pj.validate(no_inv, set(), inventory=True) == ["no 'inventory' object"]
    assert pj.validate(_v5_response(), set(), inventory=True) == []
    bad = _v5_response(A={"contributions_examined": "many"})
    probs = pj.validate(bad, set(), inventory=True)
    assert any("A.contributions_examined" in p for p in probs) and any("A.repetition" in p for p in probs)
    assert pj.validate(_v5_response(central_contributions=[]), set(), inventory=True)


def test_run_call_records_the_configured_model_and_checks_the_inventory():
    from types import SimpleNamespace
    pj = adapter._judge()

    class FakeLLM:
        def __init__(self, body):
            self.body = body

        def invoke(self, messages, **kw):
            return SimpleNamespace(content=json.dumps(self.body),
                                   usage_metadata={"input_tokens": 10, "output_tokens": 5},
                                   response_metadata={"model_name": "gpt-6.1-sol"})

    call = {"paper_id": "p", "system_a": "agent", "system_b": "linear", "call_index": 1}
    docs = {"p": {"submission": "S0001 s", "reports": {"agent": "A0001 a", "linear": "B0001 b"}}}
    rec = pj.run_call(FakeLLM(_v5_response()), "rubric", call, docs,
                      model="gpt-6.1-sol", effort="medium", inventory=True)
    assert not rec.get("failed") and rec["parsed_result"]["inventory"]["A"]["repetition"] == "medium"
    assert (rec["requested_model"], rec["effort"]) == ("gpt-6.1-sol", "medium")
    # a v5 response without inventory is a technical error, retried and finally failed
    rec = pj.run_call(FakeLLM({"criteria": _v5_response()["criteria"]}), "rubric", call, docs,
                      inventory=True)
    assert rec["failed"] and rec["n_attempts"] == pj.MAX_ATTEMPTS
    assert rec["requested_model"] == pj.JUDGE_MODEL               # default unchanged


def test_compare_matches_the_criteria_by_content(tmp_path):
    versions = {("p1", "agent"): "v-agent", ("p1", "afzal"): "v-afzal"}
    e1 = _write(tmp_path, [_judge("agent", "afzal", "A", "v-agent", "v-afzal")])
    crit = analyze.criteria_text(RUBRIC_TEXT)
    # the raters' file may lack the judge-only sections: only the CRITERIA section counts
    raters_only = f"CRITERIA\n{crit}PROCEDURE\n"
    r = analyze.compare_to_e1(_export(tmp_path, [_rating("agent", "afzal", "A")], versions,
                                      rubric_text=raters_only), e1)
    assert r["comparable_responses"] == 1 and r["judge_rubric_versions"] == [RUBRIC]
    other = f"CRITERIA\n{crit}extra sentence\nPROCEDURE\n"
    assert analyze.compare_to_e1(_export(tmp_path, [_rating("agent", "afzal", "A")], versions,
                                         rubric_text=other), e1)["comparable_responses"] == 0
    assert analyze.compare_to_e1(_export(tmp_path, [_rating("agent", "afzal", "A")], versions,
                                         rubric_text=None), e1)["comparable_responses"] == 0


def test_billed_usd_gpt61_sol_reads_at_005x():
    base = {"output_tokens": 1000, "service_tier": "default"}
    r = {**base, "input_tokens": 100_000, "cache_tokens": 20_000, "cache_write_tokens": 50_000}
    # 30k plain x2 + 50k write x2.5 + 20k read x0.1 + 1k out x10  (per 1M)
    assert abs(adapter.billed_usd(r, "gpt-6.1-sol") - (0.06 + 0.125 + 0.002 + 0.010)) < 1e-9
    assert abs(adapter.billed_usd({**r, "service_tier": "flex"}, "gpt-6.1-sol")
               - (0.06 + 0.125 + 0.002 + 0.010) / 2) < 1e-9

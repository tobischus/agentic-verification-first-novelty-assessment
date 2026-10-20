"""E3 automatic source audit. No server, no database, no API call.

The unit tests build their own run log and source files; the last test reads the real
artifacts of the 20 E1 papers (gitignored) and is skipped without them.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from final_evaluation.evaluation.e3 import source_audit as sa  # noqa: E402

sys.path.insert(0, str(ROOT / "src" / "novelty_assessment"))
import verdict as vd  # noqa: E402


def test_classify_separates_exact_near_and_missing_quotes():
    src = sa.norm("We propose TTI, a curriculum-based online RL approach [12] that trains "
                  "the agent with short trajectories first.")
    assert sa.classify("we propose  TTI, a curriculum-based online RL approach", src)[0] == "exact"
    # a dropped citation marker is near-verbatim, not exact
    kind, score = sa.classify("a curriculum-based online RL approach that trains the agent "
                              "with short trajectories first", src)
    assert kind == "near" and 90 <= score < 100
    assert sa.classify("an unrelated sentence about protein folding and crystal lattices", src)[0] \
        == "not_found"
    assert sa.classify("anything", None) == ("no_source", 0.0)


def _pw(pid, rel, sha, date="2024-01-01"):
    return {"paper_id": pid, "parsed_text_path": rel, "parsed_text_sha256": sha,
            "pinned_version_date": date}


def test_audit_counts_rates_and_refuses_an_unhashed_source(tmp_path):
    sub_text = "The submission introduces a progressive horizon schedule for agent training."
    paper_file = tmp_path / "related_work_data" / "grobid_fulltext" / "p1.txt"
    paper_file.parent.mkdir(parents=True)
    paper_file.write_text("Prior work trains agents with short trajectories first and then "
                          "longer ones.", encoding="utf-8")
    good = hashlib.sha256(paper_file.read_bytes()).hexdigest()
    pair = {"claim_quote": "introduces a progressive horizon schedule for agent training",
            "paper_quote": "trains agents with short trajectories first and then longer ones"}
    art = {"claims": [{
        "claim_id": "claim_1",
        "run_log": {"submission_selection": {"source_sha256": "x"},
                    "prior_work": [_pw("p1", "grobid_fulltext/p1.txt", good),
                                   _pw("p2", "grobid_fulltext/p1.txt", "0" * 64),
                                   _pw("p3", "", "")]},
        "comparisons": [
            {"paper_id": "p1", "overlap_degree": "substantial", "refutation_status": "can_refute",
             "evidence_pairs": [pair], "map_diag": {"returned": 4, "unverified": 1}},
            {"paper_id": "p2", "overlap_degree": "partial", "evidence_pairs": [pair],
             "map_diag": {"returned": 2, "unverified": 0}},
            {"paper_id": "p3", "overlap_degree": "partial", "evidence_pairs": [],
             "map_diag": {"returned": 1, "unverified": 1}},
        ]}]}
    c, misses = sa.audit_variant(art, tmp_path, "sub", "2025-01-01", vd, sa.norm(sub_text), "x")
    r = sa.rates(c)
    assert c["overlap"] == 3 and c["overlap_grounded"] == 2
    assert r["grounding_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert r["verifiability_rate"] == pytest.approx(5 / 7, abs=1e-4)
    assert r["ownership_rate"] == pytest.approx(2 / 5, abs=1e-4)
    # p2's recorded hash does not match its file: its quote is not auditable, not "found"
    assert c["prior_work_exact"] == 1 and c["prior_work_no_source"] == 1
    assert c["submission_exact"] == 2 and not misses
    assert r["quotes_shown"] == 4 and r["quotes_audited"] == 3 and r["share_exact"] == 1.0
    assert r["sources_dated_before_submission"] == 1.0 and c["submission_hash_ok"] == 1


def _have_artifacts() -> bool:
    from final_evaluation.evaluation import agent_linear as al
    try:
        entries = al.paper_entries()
    except OSError:
        return False
    return all((ROOT / e["systems"][v]["provenance"]["artifact_a_path"].replace("\\", "/")).exists()
               for _, _, e in entries for v in al.VARIANTS)


@pytest.mark.skipif(not _have_artifacts(), reason="run artifacts of the E1 papers not present")
def test_real_audit_adds_up():
    res = sa.analyze()
    assert res["papers"] == 20
    for v, r in res["variants"].items():
        c = r["counts"]
        assert c["submission_hash_ok"] == c["claims"], v
        assert r["quotes_exact"] + r["quotes_near"] + r["quotes_not_found"] \
            + r["quotes_not_auditable"] == r["quotes_shown"], v
        assert r["grounding_rate_refuting"] == 1.0, v     # the refutation invariant
        assert 0 < r["verifiability_rate"] <= 1 and 0 < r["ownership_rate"] <= 1, v

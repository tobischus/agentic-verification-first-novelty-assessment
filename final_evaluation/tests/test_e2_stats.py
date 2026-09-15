"""Unit tests for the E2 statistics. No server, no database, no network.

The Krippendorff test is the one that matters: a wrong reliability coefficient that
still *looks* plausible is worse than none, so it is checked against the published
worked example (Krippendorff 2004 / Hayes & Krippendorff 2007, the 4-coder x 12-unit
matrix with missing values reproduced in the R `irr` package's documentation), whose
nominal alpha is 0.743.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from final_evaluation.evaluation.e2.stats import (  # noqa: E402
    bootstrap_ci, exact_agreement, krippendorff_alpha_nominal)

TEXTBOOK = [
    [1, 1, None, 1],
    [2, 2, 3, 2],
    [3, 3, 3, 3],
    [3, 3, 3, 3],
    [2, 2, 2, 2],
    [1, 2, 3, 4],
    [4, 4, 4, 4],
    [1, 1, 2, 1],
    [2, 2, 2, 2],
    [None, 5, 5, 5],
    [None, None, 1, 1],
    [None, 3, None, None],
]


def _units(rows):
    return {f"u{i}": {f"c{j}": v for j, v in enumerate(row)} for i, row in enumerate(rows)}


def test_krippendorff_matches_published_example():
    r = krippendorff_alpha_nominal(_units(TEXTBOOK))
    assert r.alpha is not None
    assert abs(r.alpha - 0.743) < 0.001, f"expected ~0.743, got {r.alpha}"
    assert r.n_units_used == 11  # the single-value unit is correctly skipped


def test_perfect_agreement_is_alpha_one():
    units = {"u1": {"a": "x", "b": "x"}, "u2": {"a": "y", "b": "y"}}
    r = krippendorff_alpha_nominal(units)
    assert r.alpha == 1.0


def test_no_variation_is_not_estimable_rather_than_a_fake_number():
    """Everyone always says 'tie' -> expected disagreement is 0. Reporting alpha=1 (or 0)
    there would be an invented result; the protocol requires `not estimable`."""
    units = {"u1": {"a": "tie", "b": "tie"}, "u2": {"a": "tie", "b": "tie"}}
    r = krippendorff_alpha_nominal(units)
    assert r.alpha is None
    assert "not estimable" in r.reason


def test_unclear_is_missing_not_a_category():
    """A unit where one rater is `unclear` (None) has only one usable value and must be
    dropped from the coincidence matrix, not counted as agreement or as a category."""
    units = {"u1": {"a": "agent", "b": None}, "u2": {"a": "agent", "b": "agent"},
             "u3": {"a": "linear", "b": "linear"}}
    r = krippendorff_alpha_nominal(units)
    assert r.n_units_used == 2
    ex = exact_agreement(units)
    assert ex == {"agree": 2, "total": 2, "rate": 1.0}


def test_too_little_data_is_not_estimable():
    r = krippendorff_alpha_nominal({"u1": {"a": "x", "b": "y"}})
    assert r.alpha is None and "not estimable" in r.reason


def test_bootstrap_refuses_two_papers():
    out = bootstrap_ci([0.4, 0.6])
    assert out["ci"] is None
    assert "fewer than 3 papers" in out["reason"]


def test_bootstrap_returns_interval_with_enough_papers():
    out = bootstrap_ci([0.1, 0.4, 0.5, 0.6, 0.9], n_resamples=500)
    assert out["ci"] is not None
    lo, hi = out["ci"]
    assert lo <= hi
    assert 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0

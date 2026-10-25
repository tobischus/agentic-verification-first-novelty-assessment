"""Nominal Krippendorff's alpha with missing data, and exact-agreement, as plain functions over (unit_id -> {coder_id: category | None}) -- no pandas, no stats library, so the formula is auditable line by line against Krippendorff's own definition instead of trusted from a package."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Hashable, Optional


@dataclass
class AlphaResult:
    alpha: Optional[float]
    n_pairable_values: int
    n_units_used: int
    reason: str = ""


def krippendorff_alpha_nominal(units: Dict[str, Dict[str, Optional[Hashable]]]) -> AlphaResult:
    """`units`: {unit_id: {coder_id: category_or_None}}."""
    coincidence: Counter = Counter()
    marginal: Counter = Counter()
    n = 0.0
    n_units_used = 0

    for unit_id, ratings in units.items():
        values = [v for v in ratings.values() if v is not None]
        m = len(values)
        if m < 2:
            continue
        n_units_used += 1
        weight = 1.0 / (m - 1)
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                coincidence[(values[i], values[j])] += weight
                marginal[values[i]] += weight
                n += weight

    if n < 2 or n_units_used < 2:
        return AlphaResult(alpha=None, n_pairable_values=int(n), n_units_used=n_units_used,
                           reason="fewer than 2 pairable units -- not estimable")

    categories = list(marginal.keys())
    if len(categories) < 2:
        return AlphaResult(alpha=None, n_pairable_values=int(n), n_units_used=n_units_used,
                           reason="no variation across categories -- not estimable")

    d_o = sum(w for (c, k), w in coincidence.items() if c != k) / n
    sum_nc2 = sum(v * v for v in marginal.values())
    denom = n * (n - 1)
    if denom == 0:
        return AlphaResult(alpha=None, n_pairable_values=int(n), n_units_used=n_units_used,
                           reason="degenerate denominator -- not estimable")
    d_e = (n * n - sum_nc2) / denom
    if d_e == 0:
        return AlphaResult(alpha=None, n_pairable_values=int(n), n_units_used=n_units_used,
                           reason="expected disagreement is 0 (every rating identical) -- not estimable")

    alpha = 1 - d_o / d_e
    return AlphaResult(alpha=alpha, n_pairable_values=int(n), n_units_used=n_units_used)


def exact_agreement(units: Dict[str, Dict[str, Optional[Hashable]]]) -> dict:
    """Among units with >=2 non-missing values, the fraction where ALL non-missing values are identical. Reports numerator/denominator, not just the ratio, per the brief ("mit Nennern")."""
    agree = 0
    total = 0
    for ratings in units.values():
        values = [v for v in ratings.values() if v is not None]
        if len(values) < 2:
            continue
        total += 1
        if len(set(values)) == 1:
            agree += 1
    return {"agree": agree, "total": total,
           "rate": (agree / total) if total else None}



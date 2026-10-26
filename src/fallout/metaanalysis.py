"""Inverse-variance meta-analysis and leave-studies-out "impact diffs".

Definitions of change follow VITALITY (Xu et al., BMJ 2025;389:e082068):
a *direction* change is a change in the sign of the pooled estimate, and a
*significance* change is the two-sided p-value crossing 0.05 in either
direction. Estimates are on an additive scale (log RR, log OR, MD, SMD), so
"no effect" is 0.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

ALPHA = 0.05
Z_CRIT = 1.959963984540054  # standard normal 97.5th percentile


def normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


@dataclass
class Pooled:
    model: str
    k: int
    estimate: float
    se: float
    ci_low: float
    ci_high: float
    z: float
    p: float
    tau2: float
    q: float
    i2: float

    @property
    def significant(self) -> bool:
        return self.p < ALPHA

    @property
    def direction(self) -> int:
        return (self.estimate > 0) - (self.estimate < 0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["significant"] = self.significant
        return d


def pool(yi: list[float], vi: list[float], model: str = "random") -> Pooled:
    """Fixed-effect (``"fixed"``) or DerSimonian–Laird random-effects (``"random"``) pooling."""
    if len(yi) != len(vi) or not yi:
        raise ValueError("yi and vi must be non-empty and the same length")
    if any(v <= 0 for v in vi):
        raise ValueError("all sampling variances must be positive")
    if model not in ("fixed", "random"):
        raise ValueError("model must be 'fixed' or 'random'")
    k = len(yi)
    w = [1.0 / v for v in vi]
    sw = sum(w)
    fixed = sum(wi * y for wi, y in zip(w, yi)) / sw
    q = sum(wi * (y - fixed) ** 2 for wi, y in zip(w, yi))
    df = k - 1
    i2 = max(0.0, (q - df) / q) if q > 0 else 0.0
    tau2 = 0.0
    if model == "random" and k > 1:
        c = sw - sum(wi * wi for wi in w) / sw
        tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
    ws = [1.0 / (v + tau2) for v in vi]
    est = sum(wi * y for wi, y in zip(ws, yi)) / sum(ws)
    se = math.sqrt(1.0 / sum(ws))
    z = est / se
    return Pooled(model, k, est, se, est - Z_CRIT * se, est + Z_CRIT * se, z, normal_two_sided_p(z), tau2, q, i2)


def effect_from_2x2(ai: float, bi: float, ci: float, di: float, measure: str = "RR", cc: float = 0.5) -> tuple[float, float] | None:
    """Log RR or log OR and its variance from a 2x2 table.

    ``ai``/``bi`` are events/non-events in the treatment arm, ``ci``/``di`` in
    control. ``cc`` is added to all four cells only when a cell is zero.
    Returns None when both arms have no events, or both arms are all events
    (the study carries no information on a ratio scale).
    """
    if (ai == 0 and ci == 0) or (bi == 0 and di == 0):
        return None
    if 0 in (ai, bi, ci, di):
        ai, bi, ci, di = ai + cc, bi + cc, ci + cc, di + cc
    measure = measure.upper()
    if measure == "RR":
        n1, n2 = ai + bi, ci + di
        return math.log((ai / n1) / (ci / n2)), 1 / ai - 1 / n1 + 1 / ci - 1 / n2
    if measure == "OR":
        return math.log((ai * di) / (bi * ci)), 1 / ai + 1 / bi + 1 / ci + 1 / di
    raise ValueError("measure must be RR or OR")


def effect_from_means(m1: float, sd1: float, n1: int, m2: float, sd2: float, n2: int, measure: str = "MD") -> tuple[float, float]:
    """Mean difference, or SMD as Hedges' g with the usual large-sample variance."""
    measure = measure.upper()
    if measure == "MD":
        return m1 - m2, sd1 ** 2 / n1 + sd2 ** 2 / n2
    if measure == "SMD":
        df = n1 + n2 - 2
        sp = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / df)
        j = 1 - 3 / (4 * df - 1)
        g = j * (m1 - m2) / sp
        return g, (n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2))
    raise ValueError("measure must be MD or SMD")


@dataclass
class ImpactDiff:
    removed: list[str]
    before: Pooled
    after: Pooled | None
    direction_changed: bool | None
    significance_changed: bool | None
    note: str = ""

    @property
    def any_change(self) -> bool | None:
        if self.direction_changed is None:
            return None
        return self.direction_changed or self.significance_changed

    def to_dict(self) -> dict:
        return {
            "removed": self.removed,
            "before": self.before.to_dict(),
            "after": self.after.to_dict() if self.after else None,
            "direction_changed": self.direction_changed,
            "significance_changed": self.significance_changed,
            "any_change": self.any_change,
            "note": self.note,
        }


def impact_without(studies: list[str], yi: list[float], vi: list[float], remove: list[str], model: str = "random") -> ImpactDiff:
    """Re-pool after dropping the named studies and report what changed."""
    missing = [s for s in remove if s not in studies]
    if missing:
        raise KeyError(f"studies not in the meta-analysis: {missing}")
    before = pool(yi, vi, model)
    keep = [(y, v) for s, y, v in zip(studies, yi, vi) if s not in set(remove)]
    if not keep:
        return ImpactDiff(list(remove), before, None, None, None, "no studies remain after removal")
    after = pool([y for y, _ in keep], [v for _, v in keep], model)
    note = "single study remains; pooled result is that study" if len(keep) == 1 else ""
    return ImpactDiff(
        list(remove), before, after,
        direction_changed=before.direction != after.direction,
        significance_changed=before.significant != after.significant,
        note=note,
    )

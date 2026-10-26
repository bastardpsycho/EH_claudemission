import csv
import math
from pathlib import Path

import pytest

from fallout.metaanalysis import effect_from_2x2, effect_from_means, impact_without, pool

BCG = Path(__file__).parent.parent / "examples" / "bcg.csv"


def bcg():
    rows = list(csv.DictReader(open(BCG)))
    eff = [effect_from_2x2(*(float(r[c]) for c in ("ai", "bi", "ci", "di"))) for r in rows]
    return [r["study"] for r in rows], [e[0] for e in eff], [e[1] for e in eff]


def test_bcg_matches_metafor():
    # metafor: rma(measure="RR", ai=tpos, bi=tneg, ci=cpos, di=cneg, data=dat.bcg, method="DL")
    _, yi, vi = bcg()
    re = pool(yi, vi, "random")
    assert re.estimate == pytest.approx(-0.7141, abs=5e-5)
    assert re.se == pytest.approx(0.1787, abs=5e-5)
    assert re.tau2 == pytest.approx(0.3088, abs=5e-5)
    assert re.q == pytest.approx(152.2330, abs=5e-4)
    fe = pool(yi, vi, "fixed")
    assert fe.estimate == pytest.approx(-0.4303, abs=5e-5)
    assert fe.se == pytest.approx(0.0405, abs=5e-5)


def test_pool_by_hand_two_studies():
    # Weights 1/0.1=10 and 1/0.4=2.5 -> (10*0.5 + 2.5*(-0.5))/12.5 = 0.3
    fe = pool([0.5, -0.5], [0.1, 0.4], "fixed")
    assert fe.estimate == pytest.approx(0.3)
    assert fe.se == pytest.approx(math.sqrt(1 / 12.5))
    # Q = 10*0.04 + 2.5*0.64 = 2.0; C = 12.5 - (100+6.25)/12.5 = 4.0; tau2 = (2-1)/4 = 0.25
    re = pool([0.5, -0.5], [0.1, 0.4], "random")
    assert re.q == pytest.approx(2.0)
    assert re.tau2 == pytest.approx(0.25)
    w1, w2 = 1 / 0.35, 1 / 0.65
    assert re.estimate == pytest.approx((w1 * 0.5 - w2 * 0.5) / (w1 + w2))


def test_2x2_continuity_and_double_zero():
    assert effect_from_2x2(0, 10, 0, 10) is None
    y, v = effect_from_2x2(0, 10, 2, 8, "OR")
    assert y == pytest.approx(math.log((0.5 * 8.5) / (10.5 * 2.5)))
    assert v == pytest.approx(1 / 0.5 + 1 / 10.5 + 1 / 2.5 + 1 / 8.5)


def test_means():
    md, v = effect_from_means(10, 2, 20, 8, 2, 20, "MD")
    assert md == 2 and v == pytest.approx(0.4)
    g, _ = effect_from_means(10, 2, 20, 8, 2, 20, "SMD")
    assert g == pytest.approx((1 - 3 / (4 * 38 - 1)) * 1.0)


def test_impact_direction_and_significance_flags():
    studies = ["fake", "a", "b"]
    yi, vi = [-1.5, 0.1, 0.05], [0.02, 0.05, 0.05]
    diff = impact_without(studies, yi, vi, ["fake"], "fixed")
    assert diff.before.estimate < 0 and diff.before.significant
    assert diff.after.estimate > 0 and not diff.after.significant
    assert diff.direction_changed and diff.significance_changed and diff.any_change


def test_impact_no_change_and_edge_cases():
    names, yi, vi = bcg()
    diff = impact_without(names, yi, vi, ["TPT Madras 1980"])
    assert diff.direction_changed is False and diff.significance_changed is False
    with pytest.raises(KeyError):
        impact_without(names, yi, vi, ["nope"])
    gone = impact_without(["x"], [0.1], [0.1], ["x"])
    assert gone.after is None and gone.any_change is None

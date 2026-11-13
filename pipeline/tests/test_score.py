import math

import numpy as np
import pytest

from pipeline.lsh import score
from pipeline.lsh.config import load_site
from pipeline.lsh.score import ScoreParams

P = ScoreParams()  # SPEC defaults: 0.6/0.3/0.1, t_full 5, t_no 50, motion_full 30


@pytest.mark.parametrize(
    "years, expected",
    [(5.0, 1.0), (50.0, 0.0), (5 * math.sqrt(10), 0.5), (1.0, 1.0), (500.0, 0.0), (math.inf, 0.0)],
)
def test_hazard_erosion_anchor_points(years, expected):
    assert float(score.hazard_erosion(years, 5, 50)) == pytest.approx(expected, abs=1e-9)


def test_hazard_erosion_example_from_spec():
    assert float(score.hazard_erosion(15.8, 5, 50)) == pytest.approx(0.5, abs=0.001)


@pytest.mark.parametrize("rate", [0.0, -12.0, float("nan")])
def test_not_retreating_means_infinite_years_and_no_erosion_hazard(rate):
    t, lo, hi = score.years_until_river(400, rate, 5)
    assert np.isinf(t) and np.isinf(lo) and np.isinf(hi)
    res = score.compute(400, rate, 5, 0.0, np.nan, P)
    assert float(res["H_E"]) == 0.0
    assert float(res["score"]) == 0


def test_spec_point_fixture_scores_53():
    """SPEC §9 example: D=410, R=38, sigma=7.5, F=0.42, motion masked -> 53."""
    res = score.compute(410, 38.0, 7.5, 0.42, np.nan, P)
    assert float(res["score"]) == 53
    assert float(res["H_E"]) == pytest.approx(0.666, abs=0.001)
    assert float(res["H_F"]) == pytest.approx(0.42)
    assert float(res["H_G"]) == 0.0
    assert float(res["years"]) == pytest.approx(10.8, abs=0.05)
    assert float(res["years_low"]) == pytest.approx(9.0, abs=0.05)
    assert float(res["years_high"]) == pytest.approx(13.4, abs=0.05)
    assert score.score_class(float(res["score"])) == "high"


def test_high_bound_infinite_when_sigma_exceeds_rate():
    t, lo, hi = score.years_until_river(300, 10, 12)
    assert float(t) == pytest.approx(30) and float(lo) == pytest.approx(300 / 22) and np.isinf(hi)


def test_motion_not_usable_rescales_weights():
    w = score.effective_weights({"erosion": 0.6, "flood": 0.3, "motion": 0.1}, motion_usable=False)
    assert w["motion"] == 0
    assert w["erosion"] == pytest.approx(0.667, abs=0.001)
    assert w["flood"] == pytest.approx(0.333, abs=0.001)
    assert sum(w.values()) == pytest.approx(1.0)
    # and motion then has no effect on the score
    p = ScoreParams(motion_usable=False)
    a = score.compute(410, 38, 7.5, 0.42, 0.0, p)["score"]
    b = score.compute(410, 38, 7.5, 0.42, 30.0, p)["score"]
    assert float(a) == float(b)


def test_motion_hazard():
    assert float(score.hazard_motion(15, 30)) == 0.5
    assert float(score.hazard_motion(-45, 30)) == 1.0
    assert float(score.hazard_motion(np.nan, 30)) == 0.0


def test_flood_nan_is_zero():
    assert float(score.hazard_flood(np.nan)) == 0.0


def test_full_risk_everywhere_is_100():
    assert float(score.compute(0.0, 50, 1, 1.0, 30.0, P)["score"]) == 100


def test_river_distance_nan_gives_nan_score():
    res = score.compute(np.nan, 40, 5, 0.5, 1.0, P)
    assert np.isnan(res["score"]) and score.score_class(float(res["score"])) is None


def test_vectorised_matches_scalar():
    rng = np.random.default_rng(0)
    d = rng.uniform(0, 3000, 500)
    r = rng.uniform(-30, 80, 500)
    s = rng.uniform(0, 10, 500)
    f = rng.uniform(0, 1, 500)
    m = np.where(rng.random(500) < 0.3, np.nan, rng.normal(0, 20, 500))
    vec = score.compute(d, r, s, f, m, P)["score"]
    scal = [float(score.compute(*args, P)["score"]) for args in zip(d, r, s, f, m, strict=True)]
    assert np.array_equal(vec, np.array(scal))


@pytest.mark.parametrize(
    "value, key",
    [(0, "low"), (24, "low"), (25, "moderate"), (49, "moderate"), (50, "high"), (74, "high"),
     (75, "severe"), (100, "severe")],
)
def test_class_boundaries(value, key):
    assert score.score_class(value) == key
    assert score.CLASS_KEYS[int(score.class_index(value))] == key


def test_class_colours_match_spec():
    assert score.CLASS_COLOURS == {"low": "#1a9850", "moderate": "#fee08b", "high": "#f46d43",
                                   "severe": "#a50026"}


def test_params_from_site_config():
    p = ScoreParams.from_config(load_site("manpura").score, motion_usable=True)
    assert p.weights == {"erosion": 0.6, "flood": 0.3, "motion": 0.1}
    assert (p.t_full_risk_yr, p.t_no_risk_yr, p.motion_full_mm) == (5, 50, 30)


def test_round_half_up():
    assert list(score.round_half_up([0.5, 1.5, 2.5, 52.49])) == [1, 2, 3, 52]

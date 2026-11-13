import numpy as np
import pytest
from shapely.geometry import LineString, box

from pipeline.lsh.transects import (
    baseline_from_land,
    cast_transects,
    decimal_year,
    first_intersection_distance,
    landsat_decimal_year,
    retreat_rate,
    trim_transect,
)

YEARS = [1988, 1993, 1998, 2003, 2008, 2013, 2018, 2023, 2026]


def _run(rate_m_yr: float, noise_m: float = 0.0):
    """Land = x > bank(t); the bank moves +rate m/yr toward the land (positive = erosion)."""
    rng = np.random.default_rng(1)
    bank_x = {y: 10_000 + rate_m_yr * (y - YEARS[0]) + rng.normal(0, noise_m) for y in YEARS}
    land0 = box(bank_x[YEARS[0]], 0, 30_000, 10_000)
    edge = box(bank_x[YEARS[0]] - 1, 0, 30_000, 10_000).exterior.difference(
        LineString([(bank_x[YEARS[0]], -1), (bank_x[YEARS[0]], 10_001)]).buffer(1))
    bases = baseline_from_land(land0, 3000, exclude=edge.buffer(3001))
    assert bases, "baseline missing"
    trs = cast_transects(bases, land0, 100, 6000)
    assert trs
    rates = []
    for tr in trs:
        d = [first_intersection_distance(tr.line, LineString([(bank_x[y], -50_000), (bank_x[y], 50_000)]))
             for y in YEARS]
        rates.append(retreat_rate([y + 0.125 for y in YEARS], d))
    return trs, rates


def test_eroding_bank_rate_is_positive_40():
    trs, rates = _run(40.0)
    vals = np.array([r.rate_m_yr for r in rates])
    assert np.all(np.abs(vals - 40) <= 1)
    # transects point outward: from land toward the river (west, -x)
    for tr in trs:
        (x0, _), (x1, _) = tr.line.coords
        assert x1 < x0


def test_accreting_bank_rate_is_negative():
    _, rates = _run(-25.0)
    assert all(r.rate_m_yr == pytest.approx(25.0 * -1, abs=1) for r in rates)


def test_noisy_rate_has_sigma_and_r2():
    _, rates = _run(40.0, noise_m=30.0)
    r = rates[0]
    assert 38 <= r.rate_m_yr <= 42 and r.sigma_m_yr > 0 and 0.9 < r.r2 <= 1 and r.n_obs == 9


def test_rate_needs_four_observations():
    r = retreat_rate([2000, 2010, 2020], [100, 80, 60])
    assert r.rate_m_yr is None and r.n_obs == 3
    r = retreat_rate([2000, 2010, 2020, 2025, 2030], [100, np.nan, 60, 50, np.nan])
    assert r.rate_m_yr is None and r.n_obs == 3


def test_first_intersection_and_trim():
    t = LineString([(0, 0), (1000, 0)])
    bank = LineString([(300, -5), (300, 5)]).union(LineString([(700, -5), (700, 5)]))
    assert first_intersection_distance(t, bank) == pytest.approx(300)
    assert np.isnan(first_intersection_distance(t, LineString([(0, 10), (1000, 10)])))
    assert trim_transect(t, [300, 450, np.nan]).length == pytest.approx(550)


def test_decimal_years():
    assert decimal_year("2026-01-01") == pytest.approx(2026.0014, abs=1e-4)
    assert 2026.49 < decimal_year("2026-07-01") < 2026.51
    assert landsat_decimal_year(2026, [1, 2, 3]) == pytest.approx(2026.125)

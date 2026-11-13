"""Phase-6 analysis on small synthetic inputs: SAR water, bank lines, signed transect distances, motion."""

import math

import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from pipeline.lsh import banklines, motion, transects, water


def test_otsu_bimodal_and_ratio():
    rng = np.random.default_rng(0)
    v = np.concatenate([rng.normal(-20, 1, 5000), rng.normal(-8, 2, 5000)])
    t, ratio = water.otsu(v)
    assert -17 < t < -11 and ratio > 0.8
    _, uni = water.otsu(rng.normal(-10, 1, 5000))
    # a single Gaussian gives 2/π ≈ 0.64 — above the spec's 0.5 cut-off (docs/DECISIONS.md)
    assert abs(uni - 2 / math.pi) < 0.03 and uni < ratio
    assert water.otsu(np.full(500, -10.0)) == (float("nan"), 0.0) or np.isnan(
        water.otsu(np.full(500, -10.0))[0]
    )


def test_clean_removes_specks_and_fills_holes():
    a = np.zeros((30, 30), bool)
    a[1:3, 1:3] = True  # 4 px speck
    a[10:25, 10:25] = True
    a[15, 15] = False  # 1 px hole
    out = water.clean(a, 10)
    assert not out[1:3, 1:3].any() and out[15, 15] and out[10:25, 10:25].all()


def test_river_components_keep_edge_and_large_only():
    aoi = np.ones((100, 100), bool)
    w = np.zeros_like(aoi)
    w[:, :10] = True  # touches the edge → river
    w[50:55, 50:55] = True  # small inland pond → dropped
    w[20:80, 30:40] = True  # 600 px × 1e-2 km² = 6 km² → river by size
    r = banklines.river_components(w, aoi, px_km2=1e-2)
    assert r[:, :10].all() and not r[50:55, 50:55].any() and r[20:80, 30:40].all()
    # river_min_km2: null → only edge-connected water is river (large enclosed ponds dropped)
    r = banklines.river_components(w, aoi, px_km2=1e-2, min_km2=None)
    assert r[:, :10].all() and not r[20:80, 30:40].any()


def test_land_polygon_and_bank_excludes_aoi_edge():
    res = 10.0
    t = from_origin(0, 1000, res, res)
    aoi = np.ones((100, 100), bool)
    river = np.zeros_like(aoi)
    river[:, 60:] = True  # land on the west 600 m, river east
    land = banklines.land_polygon(river, aoi, t, res)
    assert abs(land.area - 600 * 1000) < 0.02 * 600 * 1000
    bank = banklines.bank_line(land, box(0, 0, 1000, 1000), res)
    xs = np.array(bank.coords)[:, 0] if bank.geom_type == "LineString" else None
    assert bank.length > 900 and xs is not None and np.allclose(xs, 600, atol=15)  # only the x=600 shore


def test_landsat_gap_fill_uses_nearest_year():
    aoi = np.ones((2, 2), bool)
    m = {
        1988: np.array([[1, 255], [0, 0]], np.uint8),
        1993: np.array([[1, 1], [0, 255]], np.uint8),
        2026: np.array([[0, 0], [0, 0]], np.uint8),
    }
    f = banklines.fill_landsat_gaps(m, aoi)
    assert f[1988][0, 1] == 1 and f[1993][1, 1] == 0 and (f[2026] != 255).all()


def test_median3_majority():
    a, b, c = (np.array([1, 0, 1, 0], bool), np.array([1, 1, 0, 0], bool), np.array([0, 1, 1, 0], bool))
    assert banklines.median3([a, b, c]).tolist() == [True, True, True, False]


def test_signed_distance_behind_baseline():
    bank = transects.CrossingIndex(LineString([(0, -500), (0, 500)]))  # bank at x = 0
    d = np.array([1.0, 0.0])
    # start on land 300 m west of the bank, looking east → +300
    assert transects.signed_bank_distance(np.array([-300.0, 0]), d, 2000, bank, True) == 300
    # the river ate past the baseline: start at x = +200 (in water) → bank is 200 m behind → −200
    assert transects.signed_bank_distance(np.array([200.0, 0]), d, 2000, bank, False) == -200
    assert math.isnan(transects.signed_bank_distance(np.array([-3000.0, 0]), d, 1000, bank, True))


def test_baseline_land_closes_creeks():
    from shapely.geometry import MultiPolygon

    two = MultiPolygon([box(0, 0, 1000, 5000), box(1100, 0, 2100, 5000)])  # split by a 100 m creek
    merged = transects.baseline_land(two)
    assert merged.geom_type == "Polygon" and merged.area > two.area


def test_motion_sign_convention():
    # spec §11: φ = −4π/λ · 0.01 m → +10 mm (toward the satellite)
    phi = -4 * math.pi / motion.WAVELENGTH_M * 0.01
    assert abs(float(motion.phase_to_mm(np.array([phi]))[0]) - 10.0) < 1e-9


def test_gunw_mask_decoding():
    # 111 = water flag 1, ref subswath 1, sec subswath 1 → valid; 101 = ref 0 → invalid; anomaly bit → invalid
    m = np.array([11, 111, 101, 110, 11 | (1 << 9), 0], np.uint32)
    assert motion.mask_valid(m).tolist() == [True, True, False, False, False, False]

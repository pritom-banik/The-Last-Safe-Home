"""End-to-end: `python -m pipeline.cli all --site demo` writes every SPEC §5 file and a valid layers.json."""

import json

import numpy as np
import pytest
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import shape

from pipeline import cli
from pipeline.lsh import demo, io, publish, score
from pipeline.lsh.config import load_site


@pytest.fixture(scope="module")
def demo_dir(demo_data_dir):
    return demo_data_dir / "processed" / "demo"


def test_every_spec_file_exists(demo_dir):
    site = load_site("demo")
    expected = demo.expected_outputs(site, demo_dir) + [demo_dir / "layers.json"]
    assert [str(p) for p in expected if not p.is_file()] == []
    dates = demo.nisar_dates(site)
    assert len(dates) == 10 and len(site.landsat.years) == 9
    # no date falls inside the instrument gap
    assert not any("2026-07-27" <= d.isoformat() <= "2026-08-10" for d in dates)


def test_layers_json_valid_and_synthetic(demo_dir):
    manifest = io.read_json(demo_dir / "layers.json")
    assert publish.validate_manifest(manifest, demo_dir) == []
    assert manifest["synthetic"] is True
    assert manifest["site"] == "demo" and len(manifest["nisar_dates"]) == 10
    assert manifest["landsat_years"][0] == 1988
    for layer in ("sar_hh", "water", "floodfreq", "motion", "score", "landwater"):
        assert layer in manifest["rasters"]
    assert set(manifest["vectors"]) == {"banklines", "transects", "buildings", "unions"}
    assert manifest["score_weights"] == {"erosion": 0.6, "flood": 0.3, "motion": 0.1}


def test_stats_and_validation(demo_dir):
    stats = io.read_json(demo_dir / "stats.json")
    assert stats["synthetic"] is True
    assert stats["nisar_passes"] == 10
    assert 30 <= stats["mean_retreat_m_yr"] <= 50  # river migrates ~40 m/yr
    assert stats["transects_with_rate"] >= 0.8 * stats["transects_total"]
    assert sum(1 for v in stats["area_by_class_km2"].values() if v > 0) == 4  # not all one class
    assert stats["buildings_total"] == 500
    assert io.read_json(demo_dir / "validation.json")["status"] == "not_validated"


def test_river_pixels_have_no_score(demo_dir):
    sc, _ = io.read_raster(demo_dir / "cog" / "demo_score_static.tif")
    dist, _ = io.read_raster(demo_dir / "cog" / "demo_distance_static.tif")
    assert np.array_equal(np.isnan(sc), np.isnan(dist))
    assert np.isnan(sc).mean() > 0.1  # the river + outside AOI
    assert np.nanmin(sc) >= 0 and np.nanmax(sc) <= 100


def test_vectors_are_wgs84_with_required_props(demo_dir):
    site = load_site("demo")
    w, s, e, n = site.bounds
    for name, props in [("banklines", {"date", "year", "source"}),
                        ("transects", {"id", "rate_m_yr", "sigma_m_yr", "n_obs", "r2", "nisar_change_m"}),
                        ("buildings", {"id", "kind"}), ("unions", {"name_en", "name_bn", "mean_score"})]:
        fc = io.read_json(io.vector_path(demo_dir, "demo", name))
        assert fc["type"] == "FeatureCollection" and fc["features"]
        for f in fc["features"]:
            assert props <= set(f["properties"])
            gw, gs, ge, gn = shape(f["geometry"]).bounds
            assert w - 1e-6 <= gw and ge <= e + 1e-6 and s - 1e-6 <= gs and gn <= n + 1e-6, name
    sources = {f["properties"]["source"] for f in io.read_json(
        io.vector_path(demo_dir, "demo", "banklines"))["features"]}
    assert sources == {"landsat", "nisar", "nisar-median3"}


def test_score_raster_agrees_with_shared_formula(demo_dir):
    """Recompute the score at land pixels from the published layers + transects, the way the API will."""
    site = load_site("demo")
    cogd = demo_dir / "cog"
    dist, prof = io.read_raster(cogd / "demo_distance_static.tif")
    sc, _ = io.read_raster(cogd / "demo_score_static.tif")
    ff, _ = io.read_raster(cogd / "demo_floodfreq_2026.tif")
    mo, _ = io.read_raster(cogd / "demo_motion_2026.tif")
    stats = io.read_json(demo_dir / "stats.json")
    tr = [f["properties"] for f in io.read_json(io.vector_path(demo_dir, "demo", "transects"))["features"]
          if f["properties"]["rate_m_yr"] is not None and f["properties"]["bank_lon"] is not None]
    to_utm = Transformer.from_crs(4326, site.utm_epsg, always_xy=True)
    bx, by = to_utm.transform([p["bank_lon"] for p in tr], [p["bank_lat"] for p in tr])
    tree = cKDTree(np.column_stack([bx, by]))

    rows, cols = np.nonzero(np.isfinite(sc))
    pick = np.random.default_rng(3).choice(rows.size, 300, replace=False)
    t = prof["transform"]
    xs = t.c + (cols[pick] + 0.5) * t.a
    ys = t.f + (rows[pick] + 0.5) * t.e
    _, idx = tree.query(np.column_stack([xs, ys]))
    params = score.ScoreParams.from_config(site.score, stats["motion_usable"])
    res = score.compute(dist[rows[pick], cols[pick]], np.array([tr[i]["rate_m_yr"] for i in idx]),
                        np.array([tr[i]["sigma_m_yr"] for i in idx]), ff[rows[pick], cols[pick]],
                        mo[rows[pick], cols[pick]], params)
    diff = np.abs(res["score"] - sc[rows[pick], cols[pick]])
    # transect props are rounded to 0.01 m/yr; allow a 1-point rounding flip on a few pixels
    assert diff.max() <= 1 and (diff == 0).mean() >= 0.95


def test_demo_refuses_real_site(tmp_path):
    with pytest.raises(ValueError):
        demo.generate(load_site("manpura"), tmp_path)
    assert cli.main(["demo", "--site", "manpura"]) == 2


def test_rerun_skips_existing(demo_dir, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(demo_dir.parent.parent))
    assert cli.main(["demo", "--site", "demo"]) == 0
    summary = json.loads((demo_dir / "summaries" / "demo.json").read_text(encoding="utf-8"))
    assert summary["skipped"] is True

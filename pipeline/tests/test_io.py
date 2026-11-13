import datetime as dt

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pipeline.lsh import io


@pytest.mark.parametrize(
    "product, key, name",
    [
        ("gcov-hh-db", dt.date(2026, 6, 21), "manpura_gcov-hh-db_20260621.tif"),
        ("water", "2026-07-03", "manpura_water_20260703.tif"),
        ("mndwi", 1988, "manpura_mndwi_1988.tif"),
        ("score", "static", "manpura_score_static.tif"),
        ("banklines", None, "manpura_banklines.geojson"),
    ],
)
def test_build_and_parse_round_trip(product, key, name):
    assert io.build_name("manpura", product, key) == name
    info = io.parse_name(name)
    assert info["site"] == "manpura" and info["product"] == product
    expected_key = io.to_date(key) if isinstance(key, str) and key != "static" else key
    assert info["key"] == expected_key
    assert io.build_name(info["site"], info["product"], info["key"], info["ext"]) == name


@pytest.mark.parametrize("bad", ["manpura_water.txt", "Manpura_water_2026.tif", "manpura_water_2026.tiff",
                                 "manpura_water_202607.tif", "manpura.tif"])
def test_parse_rejects_bad_names(bad):
    with pytest.raises(ValueError):
        io.parse_name(bad)


@pytest.mark.parametrize("site, product, key", [("Man_pura", "water", 2026), ("demo", "wat er", 2026),
                                                ("demo", "water", "yesterday"), ("demo", "water", 1066)])
def test_build_rejects_bad_parts(site, product, key):
    with pytest.raises(ValueError):
        io.build_name(site, product, key)


def test_write_cog_float_and_mask(tmp_path):
    t = from_origin(500000, 2500000, 30, 30)
    a = np.random.default_rng(0).random((300, 300))
    a[0, 0] = np.nan
    p = io.write_cog(tmp_path / "cog" / "demo_score_static.tif", a, t, "EPSG:32646")
    with rasterio.open(p) as src:
        assert src.dtypes[0] == "float32" and np.isnan(src.nodata)
        assert src.crs.to_epsg() == 32646
        assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
        assert src.overviews(1)
    back, _ = io.read_raster(p)
    assert np.isnan(back[0, 0]) and back[1, 1] == pytest.approx(a[1, 1], rel=1e-6)

    m = np.zeros((300, 300), dtype="uint8")
    m[:10] = 1
    m[-1] = 255
    p = io.write_cog(tmp_path / "cog" / "demo_water_20260621.tif", m, t, "EPSG:32646", mask=True)
    with rasterio.open(p) as src:
        assert src.dtypes[0] == "uint8" and src.nodata == 255
    back, _ = io.read_raster(p)
    assert back[0, 0] == 1 and np.isnan(back[-1, 0])
    assert io.list_keys(tmp_path, "demo", "water") == [dt.date(2026, 6, 21)]
    assert not list((tmp_path / "cog").glob("*.tmp.tif"))


def test_json_writes_nan_as_null(tmp_path):
    p = io.write_json(tmp_path / "x.json", {"a": float("nan"), "b": [np.float32("inf"), 1], "c": "মনপুরা"})
    assert io.read_json(p) == {"a": None, "b": [None, 1], "c": "মনপুরা"}

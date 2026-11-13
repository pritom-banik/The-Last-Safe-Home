"""Landsat helpers and context conversions, offline (cached raw files stand in for the services)."""

import json
from types import SimpleNamespace

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from pipeline.lsh import context, io, landsat
from pipeline.lsh.config import load_site


def test_qa_bits_mask_fill_cloud_shadow():
    qa = np.array([0, 1 << 0, 1 << 1, 1 << 2, 1 << 3, 1 << 4, 1 << 6, 21824], dtype=np.uint16)
    # 21824 = clear-land code (bits 6,8,10,12,14) → valid; bit 2 (cirrus... unused here) stays valid
    assert landsat.qa_valid(qa).tolist() == [True, False, False, True, False, False, True, True]


def test_reflectance_and_mndwi():
    dn = np.array([0, 7273, 10909], dtype=np.uint16)
    r = landsat.reflectance(dn)
    assert np.isnan(r[0]) and abs(r[1] - 0.0) < 1e-3 and abs(r[2] - 0.1) < 1e-3
    m = landsat.mndwi(np.array([0.1, 0.05, np.nan], "float32"), np.array([0.02, 0.2, 0.1], "float32"))
    assert m[0] > 0.5 and m[1] < -0.5 and np.isnan(m[2])


def test_water_threshold_otsu_and_clamp():
    rng = np.random.default_rng(1)
    v = np.concatenate([rng.normal(-0.4, 0.05, 5000), rng.normal(0.5, 0.05, 5000)])
    t = landsat.water_threshold(v)
    assert -0.1 <= t <= 0.3
    assert landsat.water_threshold(np.concatenate([v - 2, v[:10]])) == -0.1  # clamped
    assert landsat.water_threshold(np.array([np.nan] * 10)) == 0.0


def test_platform_preference():
    items = [
        SimpleNamespace(properties={"platform": p, "eo:cloud_cover": c})
        for p, c in [("landsat-7", 1), ("landsat-5", 30), ("landsat-8", 20), ("landsat-9", 10)]
    ]
    picked, plat = landsat.pick_items(items, 2008)
    assert plat == "landsat-5" and len(picked) == 1
    picked, plat = landsat.pick_items(items, 2023)
    assert plat == "landsat-8+landsat-9" and [i.properties["eo:cloud_cover"] for i in picked] == [10, 20]
    assert landsat.pick_items([items[0]], 2013)[1] == "landsat-7"
    assert landsat.pick_items([], 2013) == ([], "")


def test_context_from_cached_raw(tmp_path):
    site = load_site("manpura")
    w, s, e, n = site.bounds
    raw = tmp_path / "raw" / "context"
    raw.mkdir(parents=True)
    cx, cy = site.center
    (raw / "overpass_buildings.json").write_text(
        json.dumps(
            {
                "elements": [
                    {"type": "way", "id": 1, "center": {"lon": cx, "lat": cy}, "tags": {"building": "yes"}},
                    {"type": "node", "id": 2, "lon": cx + 0.01, "lat": cy, "tags": {"amenity": "school"}},
                    {
                        "type": "way",
                        "id": 1,
                        "center": {"lon": cx, "lat": cy},
                        "tags": {"building": "yes"},
                    },  # duplicate
                    {
                        "type": "way",
                        "id": 3,
                        "center": {"lon": w - 1, "lat": cy},
                        "tags": {"building": "yes"},
                    },  # outside
                ]
            }
        ),
        encoding="utf-8",
    )
    (raw / "overpass_roads.json").write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "way",
                        "id": 9,
                        "tags": {"highway": "track"},
                        "geometry": [{"lon": w - 0.1, "lat": cy}, {"lon": cx, "lat": cy}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    # WorldPop clip: 100 m-ish grid in EPSG:4326, 2 people per cell
    res = 0.001
    arr = np.full((int((n - s) / res) + 20, int((e - w) / res) + 20), 2.0, dtype="float32")
    with rasterio.open(
        raw / "worldpop.tif",
        "w",
        driver="GTiff",
        width=arr.shape[1],
        height=arr.shape[0],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        nodata=-99999,
        transform=from_origin(w - 10 * res, n + 10 * res, res, res),
    ) as dst:
        dst.write(arr, 1)
        dst.update_tags(lsh_source="test")
    inner = box(w + 0.02, s + 0.02, e - 0.02, n - 0.02)
    (raw / "geoboundaries_ADM4.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"shapeName": "Manpura", "shapeID": "U1"},
                        "geometry": mapping(inner),
                    },
                    {
                        "type": "Feature",
                        "properties": {"shapeName": "Far", "shapeID": "U2"},
                        "geometry": mapping(box(0, 0, 1, 1)),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "processed"
    s_ = context.run(site, out, tmp_path / "raw")
    assert s_["osm"]["by_kind"] == {"building": 1, "school": 1} and s_["osm"]["roads"] == 1
    b = io.read_json(io.vector_path(out, site.id, "buildings"))["features"]
    assert [f["properties"]["kind"] for f in b] == ["building", "school"]
    pop = s_["population"]
    assert abs(pop["sum_ratio"] - 1) < 0.02  # sum-preserving resample
    u = io.read_json(io.vector_path(out, site.id, "unions"))["features"]
    assert [f["properties"]["name_en"] for f in u] == ["Manpura"] and s_["unions"]["level"] == "ADM4"
    assert {"id", "name_en", "name_bn"} <= set(u[0]["properties"])

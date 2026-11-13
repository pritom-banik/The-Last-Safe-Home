"""API tests against the synthetic demo site (SPEC §11)."""

import time

import morecantile
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pyproj import Transformer
from rasterio.io import MemoryFile

from api.app.main import create_app
from pipeline.lsh import io

API = "/api/v1"
TMS = morecantile.tms.get("WebMercatorQuad")


@pytest.fixture(scope="module")
def client(demo_settings):
    return TestClient(create_app(demo_settings))


@pytest.fixture(scope="module")
def demo_dir(demo_data_dir):
    return demo_data_dir / "processed" / "demo"


def _pixel_lonlat(demo_dir, rows, cols):
    _, prof = io.read_raster(demo_dir / "cog" / "demo_score_static.tif")
    t = prof["transform"]
    x = t.c + (np.asarray(cols) + 0.5) * t.a
    y = t.f + (np.asarray(rows) + 0.5) * t.e
    return Transformer.from_crs(32646, 4326, always_xy=True).transform(x, y)


@pytest.fixture(scope="module")
def land_points(demo_dir):
    """(lon, lat, raster score) for land pixels well inside the AOI, mixed classes."""
    sc, _ = io.read_raster(demo_dir / "cog" / "demo_score_static.tif")
    sc[:5], sc[-5:], sc[:, :5], sc[:, -5:] = np.nan, np.nan, np.nan, np.nan
    out = []
    for lo, hi in [(0, 25), (25, 50), (50, 75), (75, 101)]:
        rows, cols = np.nonzero((sc >= lo) & (sc < hi))
        pick = np.random.default_rng(lo).choice(rows.size, 5, replace=False)
        lon, lat = _pixel_lonlat(demo_dir, rows[pick], cols[pick])
        out += list(zip(lon, lat, sc[rows[pick], cols[pick]], strict=True))
    return out


@pytest.fixture(scope="module")
def river_point(demo_dir):
    dist, _ = io.read_raster(demo_dir / "cog" / "demo_distance_static.tif")
    sc, _ = io.read_raster(demo_dir / "cog" / "demo_score_static.tif")
    h, w = dist.shape
    row = h // 2
    cols = [c for c in range(20, w - 20) if np.isnan(dist[row, c]) and np.isnan(dist[row, c - 3])
            and np.isnan(dist[row, c + 3])]
    lon, lat = _pixel_lonlat(demo_dir, [row], [cols[len(cols) // 2]])
    assert np.isnan(sc[row, cols[len(cols) // 2]])
    return float(lon[0]), float(lat[0])


# --------------------------------------------------------------------------- basics


def test_health_lists_loaded_sites_only(client):
    body = client.get(f"{API}/health").json()
    assert body == {"status": "ok", "sites": ["demo"]}  # manpura has no processed data in the test dir


def test_sites(client):
    sites = client.get(f"{API}/sites").json()
    assert len(sites) == 1
    s = sites[0]
    assert set(s) == {"id", "name", "synthetic", "center", "zoom", "bounds"}
    assert s["id"] == "demo" and s["synthetic"] is True and len(s["bounds"]) == 4
    assert s["name"]["bn"]


def test_layers_stats_validation(client):
    layers = client.get(f"{API}/sites/demo/layers").json()
    assert layers["synthetic"] is True and len(layers["nisar_dates"]) == 10 and "score" in layers["rasters"]
    stats = client.get(f"{API}/sites/demo/stats").json()
    assert stats["synthetic"] is True and stats["nisar_passes"] == 10
    assert client.get(f"{API}/sites/demo/validation").json()["status"] == "not_validated"


@pytest.mark.parametrize("path", ["/sites/nowhere/layers", "/sites/nowhere/point?lon=90.6&lat=22.6",
                                  "/tiles/nowhere/score/12/3079/1780.png"])
def test_unknown_site(client, path):
    r = client.get(API + path)
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_site"


@pytest.mark.parametrize("name", ["banklines", "transects", "buildings", "unions"])
def test_vectors(client, name):
    r = client.get(f"{API}/sites/demo/vectors/{name}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert "max-age=86400" in r.headers["cache-control"]
    fc = r.json()
    assert fc["type"] == "FeatureCollection" and fc["features"]


def test_vectors_are_compact(client, demo_dir):
    r = client.get(f"{API}/sites/demo/vectors/banklines")
    assert b" " not in r.content[:2000]
    coords = r.json()["features"][0]["geometry"]["coordinates"]
    flat = coords[0][0] if isinstance(coords[0][0], list) else coords[0]
    assert all(len(str(v).split(".")[-1]) <= 5 for v in flat)
    assert len(r.content) < (demo_dir / "vector" / "demo_banklines.geojson").stat().st_size


def test_banklines_by_source(client):
    feats = client.get(f"{API}/sites/demo/vectors/banklines").json()["features"]
    every = {f["properties"]["source"] for f in feats}
    assert "nisar-median3" in every
    r = client.get(f"{API}/sites/demo/vectors/banklines?source=landsat,nisar")
    assert r.status_code == 200
    assert {f["properties"]["source"] for f in r.json()["features"]} == {"landsat", "nisar"}
    m3 = client.get(f"{API}/sites/demo/vectors/banklines?source=nisar-median3").json()["features"]
    assert m3 and {f["properties"]["source"] for f in m3} == {"nisar-median3"}
    for bad in ("banklines?source=evil", "banklines?source=", "buildings?source=landsat"):
        r = client.get(f"{API}/sites/demo/vectors/{bad}")
        assert r.status_code == 422, bad


def test_unknown_vector(client):
    r = client.get(f"{API}/sites/demo/vectors/secrets")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_vector"


# --------------------------------------------------------------------------- point


POINT_KEYS = {"site", "in_aoi", "in_river", "score", "class", "years_until_river", "distance_to_bank_m",
              "retreat_rate_m_yr", "retreat_sigma_m_yr", "transect_id", "flood_frequency", "motion_mm",
              "motion_status", "components", "weights", "data"}


def test_point_inside_matches_raster(client, land_points):
    classes = set()
    for lon, lat, raster_score in land_points:
        r = client.get(f"{API}/sites/demo/point", params={"lon": lon, "lat": lat})
        assert r.status_code == 200, r.text
        b = r.json()
        assert set(b) == POINT_KEYS
        assert b["in_aoi"] and not b["in_river"]
        assert abs(b["score"] - raster_score) <= 1  # transect rates are rounded to 0.01 in the GeoJSON
        assert b["class"] in {"low", "moderate", "high", "severe"}
        classes.add(b["class"])
        y = b["years_until_river"]
        if y["central"] is not None:
            assert y["low"] <= y["central"] and (y["high"] is None or y["central"] <= y["high"])
            assert y["over_50"] == (y["central"] > 50)
        else:
            assert y["over_50"] is True
        assert b["motion_status"] in {"ok", "masked"}
        assert b["data"]["synthetic"] is True and b["data"]["nisar_passes"] == 10
        w = b["weights"]
        assert w == {"erosion": 0.6, "flood": 0.3, "motion": 0.1}
        c = b["components"]
        expected = round(100 * (w["erosion"] * c["H_E"] + w["flood"] * c["H_F"] + w["motion"] * c["H_G"]))
        assert abs(expected - b["score"]) <= 1
    assert classes == {"low", "moderate", "high", "severe"}


def test_point_is_fast(client, land_points):
    lon, lat, _ = land_points[-1]
    start = time.perf_counter()
    for _ in range(5):
        client.get(f"{API}/sites/demo/point", params={"lon": lon, "lat": lat})
    assert (time.perf_counter() - start) / 5 < 0.5


def test_point_in_river(client, river_point):
    lon, lat = river_point
    b = client.get(f"{API}/sites/demo/point", params={"lon": lon, "lat": lat}).json()
    assert b["in_aoi"] is True and b["in_river"] is True
    assert b["score"] is None and b["class"] is None and b["years_until_river"] is None


@pytest.mark.parametrize("lon, lat", [(90.0, 22.65), (90.65, 23.5), (90.59999, 22.65)])
def test_point_outside(client, lon, lat):
    r = client.get(f"{API}/sites/demo/point", params={"lon": lon, "lat": lat})
    assert r.status_code == 404 and r.json()["error"]["code"] == "outside_aoi"


@pytest.mark.parametrize("params", [{"lon": 90.65}, {"lon": 200, "lat": 22.6}, {"lon": "x", "lat": 22.6}])
def test_point_bad_params(client, params):
    r = client.get(f"{API}/sites/demo/point", params=params)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


# --------------------------------------------------------------------------- polygon


def _box(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def test_polygon_small_ok(client):
    poly = _box(90.655, 22.63, 90.675, 22.66)
    r = client.post(f"{API}/sites/demo/polygon-stats", json={"type": "Feature", "properties": {},
                                                             "geometry": poly})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["in_aoi"] is True and b["synthetic"] is True
    assert 0 < b["land_area_km2"] <= b["area_km2"]
    assert b["transects"] > 0 and b["max_retreat_m_yr"] > 0
    assert 0 <= b["buildings_within_100m"] <= b["buildings_within_500m"] <= b["buildings_total"]
    assert set(b["people_by_class"]) == {"low", "moderate", "high", "severe"}
    assert 0 <= b["mean_score"] <= 100
    assert b["area_lost_km2_per_yr"] > 0  # this box covers the eroding east bank


def test_polygon_whole_site_matches_stats(client):
    b = client.post(f"{API}/sites/demo/polygon-stats", json=_box(90.59, 22.59, 90.71, 22.71)).json()
    stats = client.get(f"{API}/sites/demo/stats").json()
    assert b["buildings_total"] == stats["buildings_total"]
    assert b["buildings_within_500m"] == stats["buildings_within_500m"]
    assert sum(b["people_by_class"].values()) == pytest.approx(stats["people_total"], abs=5)
    assert b["transects"] == stats["transects_total"]


def test_polygon_too_large(client):
    r = client.post(f"{API}/sites/demo/polygon-stats", json=_box(90.0, 22.0, 91.0, 23.0))
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_large"


def test_polygon_no_overlap(client):
    r = client.post(f"{API}/sites/demo/polygon-stats", json=_box(90.80, 22.80, 90.82, 22.82))
    assert r.status_code == 200 and r.json()["in_aoi"] is False


@pytest.mark.parametrize("body", [{"type": "Point", "coordinates": [90.6, 22.6]}, {"type": "Polygon"},
                                  {"type": "Polygon", "coordinates": [[[500, 22], [501, 22], [500, 23]]]},
                                  [1, 2]])
def test_polygon_invalid(client, body):
    r = client.post(f"{API}/sites/demo/polygon-stats", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] in {"invalid_geometry", "invalid_request"}


def test_polygon_is_fast(client):
    start = time.perf_counter()
    client.post(f"{API}/sites/demo/polygon-stats", json=_box(90.62, 22.62, 90.68, 22.68))
    assert time.perf_counter() - start < 0.5


# --------------------------------------------------------------------------- tiles


def _tile(lon=90.665, lat=22.65, z=13):
    t = TMS.tile(lon, lat, z)
    return f"{t.z}/{t.x}/{t.y}"


def _png(content):
    with MemoryFile(content) as m, m.open() as d:
        return d.read()


@pytest.mark.parametrize("layer, query", [("score", ""), ("water", "?date=2026-09-09"), ("water", ""),
                                          ("sar_hh", "?date=2026-06-17"), ("floodfreq", ""), ("motion", ""),
                                          ("landwater", "?date=1988"), ("landwater", "?year=2026")])
def test_tile_png(client, layer, query):
    r = client.get(f"{API}/tiles/demo/{layer}/{_tile()}.png{query}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert "max-age=86400" in r.headers["cache-control"]
    a = _png(r.content)
    assert a.shape == (4, 256, 256)


def test_score_tile_uses_class_colours(client):
    a = _png(client.get(f"{API}/tiles/demo/score/{_tile()}.png").content)
    opaque = a[3] > 0
    colours = {tuple(int(v) for v in px) for px in a[:3, opaque].T}
    assert colours <= {(0x1a, 0x98, 0x50), (0xfe, 0xe0, 0x8b), (0xf4, 0x6d, 0x43), (0xa5, 0x00, 0x26)}
    assert set(np.unique(a[3])) <= {0, 200}
    assert (a[3] == 0).any()  # the river is transparent


def test_tile_outside_returns_204(client):
    r = client.get(f"{API}/tiles/demo/score/{_tile(10.0, 50.0, 12)}.png")
    assert r.status_code == 204 and not r.content


def test_unknown_layer(client):
    r = client.get(f"{API}/tiles/demo/nothing/{_tile()}.png")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_layer"


@pytest.mark.parametrize("url", [
    "/tiles/demo/water/{t}.png?date=2026-01-01",
    "/tiles/demo/water/{t}.png?date=../../stats",
    "/tiles/demo/water/{t}.png?date=..%2F..%2Fstats",
    "/tiles/demo/cog%2Fdemo_score_static.tif/{t}.png",
    "/tiles/demo/..%2F..%2Flayers.json/{t}.png",
    "/tiles/demo/stats.json/{t}.png",
    "/tiles/demo/landwater/{t}.png?year=1987",
    "/tiles/demo/score/40/1/1.png",
])
def test_tile_path_attempts_are_404(client, url):
    r = client.get(API + url.replace("{t}", _tile()))
    assert r.status_code in (404, 422)  # 422: over-long `date` rejected before any lookup
    assert "error" in r.json()


def test_static_layer_ignores_date(client):
    """A static layer has no date: a hostile `date` cannot change which file is read."""
    r = client.get(f"{API}/tiles/demo/score/{_tile()}.png?date=../../x")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


# --------------------------------------------------------------------------- scenes


class _FakeResult:
    """Just enough of an asf_search result for `granule_from_result`."""

    def __init__(self, name, product, start, track="69", direction="ASCENDING"):
        self.properties = {
            "sceneName": name,
            "processingLevel": product,
            "startTime": start,
            "flightDirection": direction,
            "bytes": {f"{name}.h5": {"bytes": 6.2e9}},
        }
        self.umm = {"AdditionalAttributes": [{"Name": "TRACK_NUMBER", "Values": [track]}]}
        self.geometry = _box(90.0, 22.0, 91.5, 23.0)

    def find_urls(self, **_):
        return [f"https://nisar.asf.earthdatacloud.nasa.gov/{self.properties['sceneName']}.h5"]


@pytest.fixture
def fake_asf(monkeypatch):
    import asf_search

    from api.app import routes_scenes

    routes_scenes._cache.clear()
    calls = []

    def search(**kw):
        calls.append(kw)
        level = kw["processingLevel"][0]
        return [
            _FakeResult(f"NISAR_{level}_{d}", level, f"2026-{d}T23:21:00Z")
            for d in ("07-12", "10-16", "08-29")
        ]

    monkeypatch.setattr(asf_search, "search", search)
    return calls


def test_scenes(client, fake_asf):
    body = {"geometry": _box(90.6, 22.6, 90.7, 22.7), "products": ["GCOV", "GUNW"],
            "start": "2026-06-17", "end": None}
    r = client.post(f"{API}/scenes", json=body)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 6
    assert [x["datetime"] for x in rows] == sorted((x["datetime"] for x in rows), reverse=True)
    first = rows[0]
    assert set(first) == {"granule", "product", "datetime", "direction", "track", "url_asf", "size_mb"}
    assert first["track"] == "69" and first["direction"] == "ASCENDING" and first["size_mb"] == 6200.0
    assert first["url_asf"].startswith("https://search.asf.alaska.edu/")
    assert first["granule"] in first["url_asf"]
    assert {c["productionConfiguration"][0] for c in fake_asf} == {"PR"}
    assert {c["processingLevel"][0] for c in fake_asf} == {"GCOV", "GUNW"}
    # cached for an hour: a second identical request does not search again
    n = len(fake_asf)
    assert client.post(f"{API}/scenes", json=body).json() == rows
    assert len(fake_asf) == n


def test_scenes_feature_and_one_product(client, fake_asf):
    feat = {"type": "Feature", "properties": {}, "geometry": _box(90.6, 22.6, 90.7, 22.7)}
    r = client.post(f"{API}/scenes", json={"geometry": feat, "products": ["GUNW"]})
    assert r.status_code == 200 and {x["product"] for x in r.json()} == {"GUNW"}


def test_scenes_capped_at_100(client, monkeypatch):
    import asf_search

    from api.app import routes_scenes

    routes_scenes._cache.clear()
    monkeypatch.setattr(
        asf_search,
        "search",
        lambda **kw: [
            _FakeResult(f"G{kw['processingLevel'][0]}{i:03d}", "GCOV", f"2026-07-01T00:{i:02d}Z")
            for i in range(80)
        ],
    )
    r = client.post(f"{API}/scenes", json={"geometry": _box(90.6, 22.6, 90.7, 22.7)})
    assert r.status_code == 200 and len(r.json()) == 100


_SMALL = {"type": "Polygon", "coordinates": [[[90.6, 22.6], [90.7, 22.6], [90.7, 22.7], [90.6, 22.6]]]}


@pytest.mark.parametrize(
    "body",
    [
        {"geometry": {"type": "Point", "coordinates": [90.6, 22.6]}},
        {"geometry": {"type": "Polygon", "coordinates": [[[500, 22], [501, 22], [500, 23], [500, 22]]]}},
        {"geometry": {"type": "Polygon", "coordinates": "x"}},
        {"geometry": _SMALL, "products": ["SLC"]},
        {"geometry": _SMALL, "start": "yesterday"},
    ],
)
def test_scenes_bad_requests(client, fake_asf, body):
    r = client.post(f"{API}/scenes", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] in {"invalid_geometry", "invalid_request"}
    assert not fake_asf


def test_scenes_asf_down(client, monkeypatch):
    import asf_search

    from api.app import routes_scenes

    routes_scenes._cache.clear()

    def boom(**_):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(asf_search, "search", boom)
    r = client.post(f"{API}/scenes", json={"geometry": _box(90.6, 22.6, 90.7, 22.7)})
    assert r.status_code == 502 and r.json()["error"]["code"] == "search_failed"

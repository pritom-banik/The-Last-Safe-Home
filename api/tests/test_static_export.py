"""Static fallback export (api/static_export.py) on the demo site: same answers as the API."""

import json

import pytest
from fastapi.testclient import TestClient

from api import static_export
from api.app.main import create_app

API = "/api/v1"


@pytest.fixture(scope="module")
def exported(demo_settings, demo_data_dir, tmp_path_factory, monkeypatch_module):
    out = tmp_path_factory.mktemp("static")
    monkeypatch_module.setenv("DATA_DIR", str(demo_data_dir))
    assert static_export.main(["--sites", "demo", "--out", str(out), "--grid-m", "250"]) == 0
    return out


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_files(exported):
    sites = json.loads((exported / "sites.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in sites] == ["demo"]
    layers = json.loads((exported / "sites/demo/layers.json").read_text(encoding="utf-8"))
    assert layers["static"]["maxzoom"] == 14 and "sar_hh" not in layers["rasters"]
    for name in ("banklines", "banklines.landsat+nisar", "banklines.nisar-median3", "unions", "buildings"):
        assert (exported / f"sites/demo/vectors/{name}.geojson").exists(), name
    assert any((exported / "tiles/demo/score/static").rglob("*.png"))
    last = layers["nisar_dates"][-1]
    assert any((exported / f"tiles/demo/water/{last}").rglob("*.png"))
    first_year = layers["landsat_years"][0]
    assert any((exported / f"tiles/demo/landwater/{first_year}").rglob("*.png"))


def test_point_grid_matches_api(exported, demo_settings):
    g = json.loads((exported / "sites/demo/points.json").read_text(encoding="utf-8"))
    client = TestClient(create_app(demo_settings))
    cols = g["columns"]
    land = [k for k, r in enumerate(g["river"]) if not r]
    assert land and len(g["idx"]) == len(g["river"])
    for k in land[:: max(1, len(land) // 25)]:
        r, c = divmod(g["idx"][k], g["cols"])
        lon = g["west"] + (c + 0.5) * g["dlon"]
        lat = g["north"] - (r + 0.5) * g["dlat"]
        p = client.get(f"{API}/sites/demo/point", params={"lon": lon, "lat": lat}).json()
        row = {name: g["values"][i][k] for i, name in enumerate(cols)}
        assert row["score"] == p["score"]
        assert row["d"] == p["distance_to_bank_m"]
        assert row["yc"] == p["years_until_river"]["central"]
        assert row["tid"] == p["transect_id"]
        assert row["f"] == p["flood_frequency"]

"""Deploy pack (pipeline.lsh.pack): only served files, HV left out, HH rounded, manifest consistent."""

import json

import numpy as np
import rasterio

from pipeline.lsh import pack


def test_pack_demo(demo_data_dir, tmp_path):
    src = demo_data_dir / "processed" / "demo"
    r = pack.pack_site(src, tmp_path / "demo")
    out = tmp_path / "demo"
    layers = json.loads((out / "layers.json").read_text(encoding="utf-8"))
    assert "sar_hv" not in layers["rasters"] and r["dropped_layers"] == ["sar_hv"]
    # every file the manifest points at exists, nothing else was copied
    expected = {rel for n, e in layers["rasters"].items() for rel in pack.raster_files(layers, n, e)}
    expected |= set(layers["vectors"].values())
    copied = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert copied == expected | {"layers.json", "stats.json", "validation.json"}
    assert not any("gcov-hv" in c for c in copied)
    # HH rounded to 0.1 dB, still float32 + NaN nodata; other rasters byte-identical
    hh = layers["rasters"]["sar_hh"]["pattern"].replace("{date}", layers["nisar_dates"][-1].replace("-", ""))
    with rasterio.open(src / hh) as a, rasterio.open(out / hh) as b:
        x, y = a.read(1), b.read(1)
        assert b.dtypes[0] == "float32" and np.isnan(b.nodata)
        ok = np.isfinite(x)
        assert np.array_equal(ok, np.isfinite(y))
        assert np.nanmax(np.abs(x[ok] - y[ok])) <= 0.05 + 1e-5
    score = layers["rasters"]["score"]["path"]
    assert (src / score).read_bytes() == (out / score).read_bytes()


def test_pack_size_limit(demo_data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(demo_data_dir))
    monkeypatch.setattr(pack, "MAX_BYTES", 1000)
    assert pack.main(["--sites", "demo", "--out", str(tmp_path)]) == 1
    monkeypatch.setattr(pack, "MAX_BYTES", 10**12)
    tar = tmp_path / "data.tar.gz"
    assert pack.main(["--sites", "demo", "--out", str(tmp_path), "--tar", str(tar)]) == 0
    assert tar.stat().st_size > 0

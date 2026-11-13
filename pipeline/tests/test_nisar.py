"""NISAR inventory, track choice, AOI subsetting over range reads, and GCOV → dB COGs, on synthetic files."""

import dataclasses
import io as pyio
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
from pyproj import Transformer
from shapely.geometry import box, mapping

from pipeline.lsh import io, nisar
from pipeline.lsh.config import get_settings, load_site

GRID = nisar.GCOV_GRID


def make_gcov(
    path_or_buf, site, *, res=100.0, epsg=32646, pols=("HHHH", "HVHV"), water_x=None, flip_y=False, pad=5000
):
    """GCOV-like HDF5 covering the site AOI + `pad` metres; water (low γ⁰) east of `water_x` (UTM metres)."""
    w, s, e, n = site.bounds
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform([w, e, e, w], [s, s, n, n])
    x = np.arange(min(xs) - pad, max(xs) + pad, res) + res / 2
    y = np.arange(max(ys) + pad, min(ys) - pad, -res) - res / 2
    if flip_y:
        y = y[::-1]
    X, _ = np.meshgrid(x, y)
    rng = np.random.default_rng(0)
    hh = np.where(X > (water_x if water_x is not None else x.mean()), 10 ** (-2.2), 10 ** (-0.8))
    hh = (hh * rng.gamma(4, 0.25, hh.shape)).astype("float32")
    hh[:3, :] = 0  # border fill → NaN
    with h5py.File(path_or_buf, "w") as f:
        g = f.require_group(GRID)
        g["xCoordinates"] = x
        g["yCoordinates"] = y
        p = g.create_dataset("projection", data=np.uint32(epsg))
        p.attrs["epsg_code"] = epsg
        g["xCoordinateSpacing"] = res
        g["yCoordinateSpacing"] = -res
        for pol in pols:
            g.create_dataset(pol, data=hh if pol == "HHHH" else hh * 0.2, chunks=(64, 64))
        mask = np.ones(hh.shape, np.uint8)
        mask[:3, :] = 255
        g["mask"] = mask
        f.require_group("/science/LSAR/identification")["trackNumber"] = 69
    return x, y


class FakeSession:
    """requests-like session serving one in-memory file with Range support."""

    def __init__(self, data: bytes):
        self.data = data
        self.calls = 0

    def get(self, url, headers=None, **_):
        self.calls += 1
        rng = (headers or {}).get("Range")
        if not rng:
            return SimpleNamespace(
                status_code=200, content=self.data, headers={}, url=url, raise_for_status=lambda: None
            )
        a, b = (int(v) for v in rng.removeprefix("bytes=").split("-"))
        body = self.data[a : b + 1]
        return SimpleNamespace(
            status_code=206,
            content=body,
            url=url,
            raise_for_status=lambda: None,
            headers={"Content-Range": f"bytes {a}-{a + len(body) - 1}/{len(self.data)}"},
        )


def row(track, direction, date, pols="HH+HV", cover=1.0, full="TRUE", size=6000.0, product="GCOV", name=None):
    return nisar.Granule(
        granule=name or f"NISAR_L2_PR_{product}_{track}_{date.replace('-', '')}T000000_x",
        product=product,
        datetime_utc=f"{date}T23:21:00Z",
        track=str(track),
        frame="13",
        direction=direction,
        polarizations=pols,
        url=f"https://x/{date}_{track}.h5",
        size_mb=size,
        full_frame=full,
        aoi_cover=cover,
    )


DATES = [f"2026-{m:02d}-{d:02d}" for m, d in [(6, 18), (6, 30), (7, 12), (7, 24), (8, 17), (8, 29), (9, 10)]]


def test_track_choice_asks_when_two_tracks_qualify():
    rows = [row(69, "ASCENDING", d) for d in DATES] + [row(91, "DESCENDING", d) for d in DATES]
    chosen, needs, cands = nisar.choose_track(rows, None)
    assert needs is True and len(cands) == 2
    chosen, needs, _ = nisar.choose_track(rows, 91)
    assert chosen["track"] == "91" and needs is False
    with pytest.raises(ValueError):
        nisar.choose_track(rows, 12)


def test_track_choice_counts_usable_hh_passes():
    rows = [row(69, "ASCENDING", d) for d in DATES]
    rows += [row(91, "DESCENDING", d, pols="VH+VV") for d in DATES[:4]] + [
        row(91, "DESCENDING", d) for d in DATES[4:]
    ]
    chosen, needs, cands = nisar.choose_track(rows, None)
    assert chosen["track"] == "69" and needs is False  # track 91 has only 3 HH passes
    assert {c["track"]: c["hh_passes"] for c in cands} == {"69": 7, "91": 3}


def test_one_granule_per_date_prefers_hh_full_cover():
    same = "2026-07-02"
    rows = [
        row(91, "D", same, pols="HH+HV+VH+VV", cover=0.5, full="FALSE", size=3500, name="partial"),
        row(91, "D", same, pols="HH+HV", cover=1.0, full="TRUE", size=1800, name="full"),
        row(91, "D", "2026-07-14", pols="VH+VV", name="vvonly"),
        row(91, "D", same, product="GUNW", pols="HH", name="ifg"),
    ]
    sel = nisar.select(rows, "91", "D")
    assert [g.granule for g in sel] == ["full", "ifg"]
    assert {g.granule: g.selected for g in rows} == {"partial": "", "full": "yes", "vvonly": "", "ifg": "yes"}


def test_inventory_round_trip(tmp_path):
    rows = [row(69, "ASCENDING", d) for d in DATES[:2]]
    p = tmp_path / "inventory.csv"
    nisar.write_inventory(rows, p)
    head = p.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head[:9] == [
        "granule",
        "product",
        "datetime_utc",
        "track",
        "frame",
        "direction",
        "polarizations",
        "url",
        "size_mb",
    ]
    assert nisar.read_inventory(p) == rows


def test_granule_from_asf_result():
    site = load_site("manpura")
    w, s, e, n = site.bounds
    res = SimpleNamespace(
        properties={
            "sceneName": "G1",
            "processingLevel": "GCOV",
            "startTime": "2026-06-18T23:21:02Z",
            "flightDirection": "ASCENDING",
            "url": "https://x/G1.h5",
            "bytes": {"G1.h5": {"bytes": 6_136_000_000}, "G1_QA_STATS.h5": {"bytes": 70_000}},
        },
        umm={
            "AdditionalAttributes": [
                {"Name": "TRACK_NUMBER", "Values": ["69"]},
                {"Name": "FRAME_NUMBER", "Values": ["13"]},
                {"Name": "FREQUENCY_A_POLARIZATION", "Values": ["HV", "HH"]},
                {"Name": "FULL_FRAME", "Values": ["TRUE"]},
            ]
        },
        geometry=mapping(box(w - 1, s, (w + e) / 2, n + 1)),
        find_urls=lambda **_: ["https://x/G1.h5"],
    )
    g = nisar.granule_from_result(res, site.aoi)
    assert (g.track, g.frame, g.direction, g.polarizations, g.size_mb) == (
        "69",
        "13",
        "ASCENDING",
        "HH+HV",
        6136.0,
    )
    assert g.aoi_cover == pytest.approx(0.5, abs=0.01)


def test_subset_over_range_reads_matches_source(tmp_path):
    site = load_site("manpura")
    buf = pyio.BytesIO()
    make_gcov(buf, site, res=250, pad=60_000)  # frame much larger than the AOI, as in reality
    sess = FakeSession(buf.getvalue())
    rf = nisar.RangeFile("https://x/f.h5", sess, block_size=64 * 1024)
    dst = tmp_path / "G_20260618T232102_aoi.h5"
    with h5py.File(rf, "r") as f:
        info = nisar.subset_gcov(f, dst, site.bounds, source_url="https://x/f.h5")
    assert info["epsg"] == 32646 and {"HHHH", "HVHV", "mask"} <= set(info["layers"])
    assert rf.bytes_fetched < 0.5 * len(sess.data)  # read the AOI window, not the whole file
    full = nisar.read_gcov(_write(tmp_path / "full.h5", buf), site.bounds)
    sub = nisar.read_gcov(dst, site.bounds)
    np.testing.assert_array_equal(np.isnan(full.hh), np.isnan(sub.hh))
    np.testing.assert_allclose(full.hh, sub.hh, equal_nan=True)
    assert sub.mask_applied


def _write(path, buf):
    path.write_bytes(buf.getvalue())
    return path


def test_read_gcov_orients_north_up_and_masks(tmp_path):
    site = load_site("manpura")
    p = tmp_path / "x_20260618T232102_.h5"
    make_gcov(p, site, flip_y=True)
    d = nisar.read_gcov(p)
    assert d.y[0] > d.y[-1]  # north → south
    assert np.isnan(d.hh[-3:]).all()  # the fill rows (south after the flip) are masked
    assert nisar.to_db(np.array([1.0, 0.01, 0.0, np.nan])).tolist()[:2] == [0.0, -20.0]
    assert np.isnan(nisar.to_db(np.array([0.0, -1.0, np.nan]))).all()


def test_process_gcov_writes_db_cogs_on_one_grid(tmp_path):
    site = load_site("manpura")
    settings = dataclasses.replace(get_settings(), data_dir=tmp_path)
    gdir = nisar.nisar_dir(site, settings) / "gcov"
    gdir.mkdir(parents=True)
    tr = Transformer.from_crs(4326, 32646, always_xy=True)
    cx, _ = tr.transform(site.center[0], site.center[1])
    make_gcov(gdir / "NISAR_L2_PR_GCOV_A_20260618T232102_20260618T232136_aoi.h5", site, water_x=cx)
    make_gcov(
        gdir / "NISAR_L2_PR_GCOV_B_20260630T232101_20260630T232136_aoi.h5",
        site,
        water_x=cx + 2000,
        pols=("HHHH",),
    )
    make_gcov(gdir / "NISAR_L2_PR_GCOV_C_20260714T123456_20260714T123530_aoi.h5", site, pols=("VVVV",))
    out = settings.data_dir / "processed" / site.id
    s = nisar.process_gcov(site, out, settings)
    assert s["written"] == ["2026-06-18", "2026-06-30"] and "2026-07-14" in s["per_date"]  # VV-only skipped
    assert s["res_m"] == 100
    a, pa = io.read_raster(io.cog_path(out, site.id, "gcov-hh-db", "2026-06-18"))
    b, pb = io.read_raster(io.cog_path(out, site.id, "gcov-hh-db", "2026-06-30"))
    assert pa["transform"] == pb["transform"] and a.shape == b.shape and pa["crs"].to_epsg() == 32646
    assert io.cog_path(out, site.id, "gcov-hv-db", "2026-06-18").exists()
    assert not io.cog_path(out, site.id, "gcov-hv-db", "2026-06-30").exists()
    land, water = np.nanmedian(a[:, : a.shape[1] // 4]), np.nanmedian(a[:, -a.shape[1] // 4 :])
    assert -10 < land < -6 and -24 < water < -20  # dB of the synthetic land / water levels
    assert nisar.process_gcov(site, out, settings)["skipped_existing"] == ["2026-06-18", "2026-06-30"]


def test_date_of_granule():
    assert (
        nisar.date_of(
            "NISAR_L2_PR_GCOV_023_069_A_013_4005_DHDH_A_20260618T232102_20260618T232136_P05023_N_F_J_001"
        ).isoformat()
        == "2026-06-18"
    )


def test_gunw_latest_version_per_pair():
    from pipeline.lsh.nisar import Granule, latest_versions, pair_key

    base = ("NISAR_L2_PR_GUNW_028_170_A_013_029_4000_SH_20260824T232918_20260824T232952_"
            "20260905T232918_20260905T232952_P05023_N_F_J")
    other = ("NISAR_L2_PR_GUNW_027_170_A_013_028_4000_SH_20260812T232918_20260812T232953_"
             "20260824T232918_20260824T232952_P05023_N_F_J")
    assert pair_key(base + "_001") == pair_key(base + "_002_aoi.h5") == base

    def g(name):
        return Granule(name, "GUNW", "", "170", "13", "ASCENDING", "HH", "", None)

    kept = latest_versions([g(base + "_002"), g(other + "_001"), g(base + "_001")])
    assert [k.granule for k in kept] == [other + "_001", base + "_002"]

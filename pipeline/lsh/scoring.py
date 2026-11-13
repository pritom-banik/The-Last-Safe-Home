"""`score` pipeline step for real sites (SPEC §7.10): distance, years, score rasters, union stats, stats.json.

Formulas live in `score.py` (shared with the API); this module only assembles the inputs on the 30 m grid.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from shapely.geometry import shape

from pipeline.lsh import banklines, io, score
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.grid import site_grid

log = logging.getLogger("lsh.scoring")

MOTION_USABLE_PCT = 30.0


def _r(x, nd: int = 2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _nanmean(a: np.ndarray):
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else None


def _read_on_grid(path: Path, grid) -> np.ndarray:
    arr, prof = io.read_raster(path)
    if arr.shape != grid.shape or prof["transform"] != grid.transform:
        raise ValueError(f"{path.name} is not on the site's {grid.res:g} m analysis grid")
    return arr


def run(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    sid, epsg = site.id, site.utm_epsg
    out_dir = Path(out_dir)
    if (
        io.cog_path(out_dir, sid, "score", "static").exists()
        and (out_dir / "stats.json").exists()
        and not force
    ):
        return {"skipped": True}
    grid = site_grid(site, site.analysis.grid_res_m)
    shape_, res, aoi = grid.shape, grid.res, grid.aoi
    px_km2 = res * res / 1e6

    def raster_of(geom) -> np.ndarray:
        if geom.is_empty:
            return np.zeros(shape_, bool)
        return rasterize([geom], out_shape=shape_, transform=grid.transform, fill=0, default_value=1).astype(
            bool
        )

    land = banklines.read_land(out_dir)
    today_key = banklines.today_key(land)
    land_today = aoi & raster_of(land[today_key])

    # distance to today's bank (outside the AOI counts as land: the box edge is not a bank)
    dist = np.clip(distance_transform_edt(land_today | ~aoi) * res - res / 2, 0, None)
    dist = np.where(land_today, dist, np.nan).astype("float32")

    # nearest transect with a rate (KD-tree on today's bank crossing) → R, σR
    tr = [f["properties"] for f in io.read_json(io.vector_path(out_dir, sid, "transects"))["features"]]
    tr = [p for p in tr if p["rate_m_yr"] is not None and p["bank_lon"] is not None]
    if not tr:
        raise RuntimeError("no transects with a rate and a bank point: check banklines/transects")
    from pyproj import Transformer

    bx, by = Transformer.from_crs(4326, epsg, always_xy=True).transform(
        [p["bank_lon"] for p in tr], [p["bank_lat"] for p in tr]
    )
    tree = cKDTree(np.column_stack([bx, by]))
    rows, cols = np.nonzero(land_today)
    t = grid.transform
    xs, ys = t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e
    _, idx = tree.query(np.column_stack([xs, ys]))
    R = np.full(shape_, np.nan)
    S = np.full(shape_, np.nan)
    R[rows, cols] = np.array([tr[i]["rate_m_yr"] for i in idx])
    S[rows, cols] = np.array([tr[i]["sigma_m_yr"] for i in idx])

    floodfreq = _read_on_grid(io.cog_path(out_dir, sid, "floodfreq", 2026), grid)
    motion = _read_on_grid(io.cog_path(out_dir, sid, "motion", 2026), grid)
    coherent_land_pct = float(100.0 * np.isfinite(motion[land_today]).mean()) if land_today.any() else 0.0
    motion_usable = coherent_land_pct >= MOTION_USABLE_PCT
    params = score.ScoreParams.from_config(site.score, motion_usable)
    res_ = score.compute(dist, R, S, floodfreq, motion, params)
    sc = np.where(land_today, res_["score"], np.nan).astype("float32")
    yrs = np.where(land_today, np.clip(res_["years"], 0, 1000), np.nan).astype("float32")
    for product, arr in (("distance", dist), ("years", yrs), ("score", sc)):
        io.write_cog(io.cog_path(out_dir, sid, product, "static"), arr, grid.transform, grid.crs)

    # ---- people + buildings
    pop_path = io.cog_path(out_dir, sid, "population", "static")
    pop = np.nan_to_num(_read_on_grid(pop_path, grid)) if pop_path.exists() else np.zeros(shape_)
    cls_idx = score.class_index(sc)
    b_feats = (
        io.read_json(io.vector_path(out_dir, sid, "buildings"))["features"]
        if io.vector_path(out_dir, sid, "buildings").exists()
        else []
    )
    if b_feats:
        blon = np.array([f["geometry"]["coordinates"][0] for f in b_feats])
        blat = np.array([f["geometry"]["coordinates"][1] for f in b_feats])
        bxx, byy = Transformer.from_crs(4326, epsg, always_xy=True).transform(blon, blat)
        br = np.clip(np.floor((byy - t.f) / t.e).astype(int), 0, shape_[0] - 1)
        bc = np.clip(np.floor((bxx - t.c) / t.a).astype(int), 0, shape_[1] - 1)
        # a building standing in today's river counts as distance 0 (it is at, or past, the bank)
        b_dist = np.where(land_today[br, bc], dist[br, bc], np.where(aoi[br, bc], 0.0, np.nan))
        b_class = score.class_index(sc[br, bc])
    else:
        br = bc = np.empty(0, int)
        b_dist = b_class = np.empty(0)

    # ---- Landsat land per year (same polygons as the bank lines)
    years = sorted(int(k) for s_, k in land if s_ == "landsat")
    land_by_year = {y: aoi & raster_of(land[("landsat", str(y))]) for y in years}
    from pipeline.lsh.transects import landsat_decimal_year

    t_years = {y: landsat_decimal_year(y, site.landsat.months) for y in years}

    def area_loss_rate(inside: np.ndarray) -> float | None:
        if len(years) < 2:
            return None
        tt = np.array([t_years[y] for y in years])
        area = np.array([(land_by_year[y] & inside).sum() * px_km2 for y in years])
        return float(-np.polyfit(tt, area, 1)[0])

    # ---- unions
    u_path = io.vector_path(out_dir, sid, "unions")
    u_out = []
    if u_path.exists():
        for f in io.read_json(u_path)["features"]:
            g_utm = io.from_wgs84(shape(f["geometry"]), epsg)
            inside = aoi & raster_of(g_utm)
            in_b = inside[br, bc] if len(br) else np.empty(0, bool)
            props = {
                k: v
                for k, v in f["properties"].items()
                if not k.startswith(("buildings_", "people_", "mean_score", "land_area", "area_lost"))
            }
            props.update(
                {
                    "synthetic": False,
                    "land_area_km2": round(float((inside & land_today).sum() * px_km2), 3),
                    "mean_score": _r(_nanmean(sc[inside]), 1),
                    "area_lost_km2_per_yr": _r(area_loss_rate(inside), 4),
                    "buildings_total": int(in_b.sum()),
                    "people_total": int(round(pop[inside].sum())),
                }
            )
            for ci, key in enumerate(score.CLASS_KEYS):
                props[f"buildings_{key}"] = int((in_b & (b_class == ci)).sum()) if len(br) else 0
                props[f"people_{key}"] = int(round(pop[inside & (cls_idx == ci)].sum()))
            u_out.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
        io.write_geojson(u_path, u_out)

    # ---- stats.json
    rates = np.array([p["rate_m_yr"] for p in tr])
    eroding = rates[rates > 0]
    l0, l1 = land_by_year[years[0]], land_by_year[years[-1]]
    nisar_dates = [d.isoformat() for d in io.list_keys(out_dir, sid, "water")]
    all_tr = io.read_json(io.vector_path(out_dir, sid, "transects"))["features"]
    stats = {
        "site": sid,
        "synthetic": bool(site.synthetic),
        "site_area_km2": round(float(aoi.sum() * px_km2), 2),
        "land_area_km2": round(float(land_today.sum() * px_km2), 2),
        "land_lost_km2": {
            "from_year": years[0],
            "to_year": years[-1],
            "net": round(float((l0.sum() - l1.sum()) * px_km2), 2),
            "eroded": round(float((l0 & ~l1).sum() * px_km2), 2),
            "accreted": round(float((~l0 & l1 & aoi).sum() * px_km2), 2),
        },
        "transects_total": len(all_tr),
        "transects_with_rate": int(rates.size),
        "transects_eroding": int(eroding.size),
        "mean_retreat_m_yr": _r(float(eroding.mean()) if eroding.size else None, 1),
        "max_retreat_m_yr": _r(float(eroding.max()) if eroding.size else None, 1),
        "buildings_total": len(b_feats),
        "buildings_within_100m": int((b_dist <= 100).sum()),
        "buildings_within_500m": int((b_dist <= 500).sum()),
        "people_total": int(round(pop[aoi].sum())),
        "people_by_class": {k: int(round(pop[cls_idx == i].sum())) for i, k in enumerate(score.CLASS_KEYS)},
        "buildings_by_class": {k: int((b_class == i).sum()) for i, k in enumerate(score.CLASS_KEYS)},
        "area_by_class_km2": {
            k: round(float((cls_idx == i).sum() * px_km2), 2) for i, k in enumerate(score.CLASS_KEYS)
        },
        "mean_score": _r(_nanmean(sc), 1),
        "nisar_passes": len(nisar_dates),
        "nisar_first": nisar_dates[0] if nisar_dates else None,
        "nisar_last": nisar_dates[-1] if nisar_dates else None,
        "bank_date": today_key[1] if today_key[0] == "nisar-median3" else None,
        "bank_source": f"{today_key[0]}:{today_key[1]}",
        "landsat_years": years,
        "coherent_land_pct": round(coherent_land_pct, 1),
        "motion_usable": motion_usable,
        "score_weights_effective": {k: round(v, 3) for k, v in params.effective_weights.items()},
    }
    io.write_json(out_dir / "stats.json", stats)
    hist = {k: stats["area_by_class_km2"][k] for k in score.CLASS_KEYS}
    return {
        "area_by_class_km2": hist,
        "motion_usable": motion_usable,
        "coherent_land_pct": stats["coherent_land_pct"],
        "river_pixels_nan": bool(np.isnan(sc[aoi & ~land_today]).all()),
        "mean_score": stats["mean_score"],
        "unions": len(u_out),
        "buildings_within_500m": stats["buildings_within_500m"],
    }

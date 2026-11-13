"""`validate` step (SPEC §7.11) + the phase-6 water-mask check against Sentinel-2.

1. Area check: Landsat land area of the island vs published values. The island = the land piece (narrow creeks
   closed) overlapping the site's `validation.island_unions` the most. Published values are compared with the
   closest Landsat year and with the published decline interpolated to each Landsat year.
2. Sentinel-2 check: a clear Sentinel-2 L2A scene within ±7 days of a post-monsoon NISAR pass; NDWI water vs
   the NISAR water mask on the 10 m grid: agreement, water IoU, and the distance between the two *river
   outlines* (river = the bank-line extraction: dry-season corridor + connected components) for the pass and
   for the median-of-3 map used as today's bank.
3. Accuracy: `--make-points` writes 200 stratified points to label; labelled points → confusion matrix, kappa.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

from pipeline.lsh import banklines, io
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.transects import CREEK_CLOSE_M

log = logging.getLogger("lsh.validate")
S2_MAX_CLOUD = 20
S2_WINDOW_DAYS = 7
S2_MIN_CLEAR = 0.8


# --------------------------------------------------------------------------- area check


def island_area_by_year(site: SiteConfig, site_dir: Path) -> dict[int, float]:
    names = set(site.validation.get("island_unions") or [])
    land = banklines.read_land(site_dir)
    unions = io.read_json(io.vector_path(site_dir, site.id, "unions"))["features"]
    sel = [shape(f["geometry"]) for f in unions if f["properties"].get("name_en") in names]
    if not sel:
        return {}
    target = io.from_wgs84(unary_union(sel), site.utm_epsg)
    out = {}
    for s, k in land:
        if s != "landsat":
            continue
        g = land[(s, k)]
        closed = g.buffer(CREEK_CLOSE_M).buffer(-CREEK_CLOSE_M)
        parts = [Polygon(p.exterior) for p in getattr(closed, "geoms", [closed]) if p.geom_type == "Polygon"]
        if not parts:
            continue
        island = max(parts, key=lambda p: p.intersection(target).area)
        out[int(k)] = round(g.intersection(island).area / 1e6, 2)
    return dict(sorted(out.items()))


def area_check(site: SiteConfig, site_dir: Path) -> dict | None:
    pub = {int(k): float(v) for k, v in (site.validation.get("published_area_km2") or {}).items()}
    if not pub:
        return None
    ours = island_area_by_year(site, site_dir)
    if not ours:
        return {"status": "no_island", "published_km2": pub}
    years = sorted(ours)
    rows = []
    for y, v in sorted(pub.items()):
        near = min(years, key=lambda o: abs(o - y))
        rows.append(
            {
                "published_year": y,
                "published_km2": v,
                "landsat_year": near,
                "landsat_km2": ours[near],
                "diff_km2": round(ours[near] - v, 2),
                "diff_pct": round(100 * (ours[near] - v) / v, 1),
            }
        )
    interp = []
    if len(pub) >= 2:
        py = sorted(pub)
        slope = (pub[py[-1]] - pub[py[0]]) / (py[-1] - py[0])
        for y in years:
            if py[0] - 20 <= y <= py[-1] + 5:  # stay near the published span
                ref = pub[py[0]] + slope * (y - py[0])
                interp.append(
                    {
                        "year": y,
                        "published_trend_km2": round(ref, 1),
                        "landsat_km2": ours[y],
                        "diff_pct": round(100 * (ours[y] - ref) / ref, 1),
                    }
                )
    within = [abs(r["diff_pct"]) <= 15 for r in interp] or [abs(r["diff_pct"]) <= 15 for r in rows]
    return {
        "island_unions": site.validation.get("island_unions"),
        "landsat_island_km2": ours,
        "closest_year": rows,
        "vs_published_trend": interp,
        "within_15pct": all(within),
        "declining": ours[years[-1]] < max(ours.values()),
    }


# --------------------------------------------------------------------------- Sentinel-2 check


def sentinel2_check(site: SiteConfig, site_dir: Path, work_png: Path | None = None) -> dict:
    import planetary_computer
    import pystac_client
    from odc.geo.geobox import GeoBox
    from odc.stac import load

    sid = site.id
    dates = io.list_keys(site_dir, sid, "water")
    post = [d for d in dates if d.month >= 10] or dates[-1:]
    # Planetary Computer first; Element84 Earth Search (public AWS COGs) if it is unreachable
    providers = [
        (
            "planetary-computer",
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            planetary_computer.sign_inplace,
            {"green": "B03", "swir": "B11", "scl": "SCL"},
        ),
        (
            "earth-search",
            "https://earth-search.aws.element84.com/v1",
            None,
            {"green": "green", "swir": "swir16", "scl": "scl"},
        ),
    ]
    best, errors = None, {}
    for name, url, modifier, bands in providers:
        try:
            cat = pystac_client.Client.open(url, modifier=modifier, timeout=30)
            for d in reversed(post):
                a, b = d - dt.timedelta(days=S2_WINDOW_DAYS), d + dt.timedelta(days=S2_WINDOW_DAYS)
                items = list(
                    cat.search(
                        collections=["sentinel-2-l2a"],
                        bbox=list(site.bounds),
                        datetime=f"{a.isoformat()}/{b.isoformat()}",
                        query={"eo:cloud_cover": {"lt": S2_MAX_CLOUD}},
                    ).items()
                )
                if items:
                    best = (d, items, name, bands)
                    break
        except Exception as e:  # noqa: BLE001 - try the next catalogue
            errors[name] = str(e)[:200]
            log.warning("Sentinel-2 catalogue %s failed: %s", name, e)
        if best:
            break
    if best is None:
        return {"status": "no_scene", "searched_dates": [d.isoformat() for d in post], "errors": errors}
    d, items, provider, bands = best
    dates_sorted = sorted(dates)
    wmask, prof = io.read_mask(io.cog_path(site_dir, sid, "water", d))
    # today's bank map is the median of three passes; compare that too
    i_d = dates_sorted.index(d)
    win = dates_sorted[max(0, i_d - 2) : i_d + 1]
    nis_m3 = banklines.median3([io.read_mask(io.cog_path(site_dir, sid, "water", x))[0] == 1 for x in win])
    h, w = wmask.shape
    gbox = GeoBox((h, w), prof["transform"], prof["crs"])
    ds = load(
        items,
        bands=[bands["green"], bands["swir"], bands["scl"]],
        geobox=gbox,
        groupby="solar_day",
        resampling={bands["scl"]: "nearest", "*": "bilinear"},
        fail_on_error=False,
    )
    scl = ds[bands["scl"]].values
    clear = np.isin(scl, [4, 5, 6, 7])  # vegetation, bare, water, unclassified (not cloud/shadow/dark)
    aoi = wmask != 255
    clear_frac = [float((clear[k] & aoi).sum() / aoi.sum()) for k in range(scl.shape[0])]
    days = [dt.date.fromisoformat(str(t)[:10]) for t in ds.time.values]
    # the S2 day nearest the NISAR pass with ≥ 80 % clear AOI (river stage changes daily); else the clearest
    cand = [k for k in range(len(days)) if clear_frac[k] >= S2_MIN_CLEAR]
    i = (
        min(cand, key=lambda k: (abs((days[k] - d).days), -clear_frac[k]))
        if cand
        else int(np.argmax(clear_frac))
    )
    g = ds[bands["green"]].values[i].astype("float32")
    sw = ds[bands["swir"]].values[i].astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = (g - sw) / (g + sw)
    ok = aoi & clear[i] & np.isfinite(mndwi) & (g > 0)
    ok &= distance_transform_edt(ok) > 3  # keep away from cloud edges
    s2_water = mndwi > 0.0
    nis_water = wmask == 1
    agree = float((s2_water[ok] == nis_water[ok]).mean())
    inter = (s2_water & nis_water & ok).sum()
    union = ((s2_water | nis_water) & ok).sum()

    # river outline: the same river extraction as the bank lines (dry-season corridor, connected components)
    min_km2 = site.analysis.river_min_km2
    river_l, lprof = banklines.landsat_river(site_dir, sid, min_km2)
    corr = banklines.corridor_mask(river_l, lprof, prof)
    res = abs(prof["transform"].a)
    px_km2 = res * res / 1e6
    edge = aoi & ~binary_erosion(aoi, iterations=3, border_value=0)

    def outline(river):
        return river & ~binary_erosion(river) & ok & ~edge

    r_s2 = banklines.river_components(s2_water & corr, aoi, px_km2, min_km2)
    out = {
        "status": "ok",
        "provider": provider,
        "index": "MNDWI > 0 (green, SWIR 1.6 um)",
        "nisar_date": d.isoformat(),
        "nisar_median3_window": [win[0].isoformat(), win[-1].isoformat()],
        "sentinel2_date": days[i].isoformat(),
        "sentinel2_days": {days[k].isoformat(): round(clear_frac[k], 3) for k in range(len(days))},
        "sentinel2_items": [it.id for it in items][:6],
        "clear_aoi_frac": round(float(ok.sum() / aoi.sum()), 3),
        "agreement": round(agree, 3),
        "water_iou": round(float(inter / union), 3) if union else None,
        "pixel_m": res,
    }
    for name, nw in (("pass", nis_water), ("median3", nis_m3)):
        r_ni = banklines.river_components(nw & corr, aoi, px_km2, min_km2)
        s_s2, s_ni = outline(r_s2), outline(r_ni)
        dists = np.concatenate(
            [distance_transform_edt(~s_ni)[s_s2], distance_transform_edt(~s_s2)[s_ni]]
        )
        both = ok & (r_s2 | r_ni)
        out[f"river_{name}"] = {
            "river_iou": round(float((r_s2 & r_ni & ok).sum() / both.sum()), 3) if both.any() else None,
            "outline_dist_px_median": round(float(np.median(dists)), 1) if dists.size else None,
            "outline_dist_px_p75": round(float(np.percentile(dists, 75)), 1) if dists.size else None,
            "outline_within_2px_frac": round(float((dists <= 2).mean()), 3) if dists.size else None,
            # of the disagreeing river pixels, the share where NISAR says river and S2 says land
            "nisar_wetter_frac": round(
                float((r_ni & ~r_s2 & ok).sum() / max(1, ((r_ni ^ r_s2) & ok).sum())), 3
            ),
        }
    m3 = out["river_median3"]
    out["shoreline_dist_px_median"] = m3["outline_dist_px_median"]
    out["within_2px"] = bool(m3["outline_dist_px_median"] is not None and m3["outline_dist_px_median"] <= 2)
    if work_png is not None:
        from PIL import Image

        s = 3
        rgb = np.zeros(wmask.shape + (3,), np.uint8) + 230
        rgb[nis_water & s2_water] = (40, 110, 200)
        rgb[nis_water & ~s2_water & ok] = (230, 60, 60)  # NISAR water, S2 land
        rgb[~nis_water & s2_water & ok] = (240, 200, 40)  # S2 water, NISAR land
        rgb[~ok] = (0, 0, 0)
        work_png.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgb[::s, ::s]).save(work_png)
        out["quicklook"] = str(work_png)
    return out


# --------------------------------------------------------------------------- labelled points


def make_points(site: SiteConfig, site_dir: Path, raw_dir: Path, n_each: int = 100, seed: int = 7) -> Path:
    dates = io.list_keys(site_dir, site.id, "water")
    d = dates[-1]
    w, prof = io.read_mask(io.cog_path(site_dir, site.id, "water", d))
    rng = np.random.default_rng(seed)
    t = prof["transform"]
    rows_out = []
    for cls in (1, 0):
        r, c = np.nonzero(w == cls)
        pick = rng.choice(r.size, min(n_each, r.size), replace=False)
        for k in pick:
            x, y = t.c + (c[k] + 0.5) * t.a, t.f + (r[k] + 0.5) * t.e
            from shapely.geometry import Point

            lon, lat = io.to_wgs84(Point(x, y), site.utm_epsg).coords[0]
            rows_out.append(
                {
                    "id": len(rows_out) + 1,
                    "lon": round(lon, 6),
                    "lat": round(lat, 6),
                    "nisar_date": d.isoformat(),
                    "nisar_class": "water" if cls else "land",
                    "label": "",
                }
            )
    path = Path(raw_dir) / "validation" / "points.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        wr.writeheader()
        wr.writerows(rows_out)
    return path


def accuracy(points_csv: Path) -> dict | None:
    if not points_csv.exists():
        return None
    with points_csv.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("label", "").strip().lower() in ("water", "land")]
    if len(rows) < 20:
        return None
    pred = np.array([r["nisar_class"] == "water" for r in rows])
    true = np.array([r["label"].strip().lower() == "water" for r in rows])
    tp, tn = int((pred & true).sum()), int((~pred & ~true).sum())
    fp, fn = int((pred & ~true).sum()), int((~pred & true).sum())
    n = len(rows)
    oa = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / n**2
    return {
        "n": n,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "overall_accuracy": round(oa, 3),
        "kappa": round((oa - pe) / (1 - pe), 3) if pe < 1 else None,
    }


def run(site: SiteConfig, site_dir: Path, raw_dir: Path, make_pts: bool = False) -> dict:
    site_dir = Path(site_dir)
    summary: dict = {}
    if make_pts:
        summary["points_csv"] = str(make_points(site, site_dir, raw_dir))
    area = area_check(site, site_dir)
    try:
        s2 = sentinel2_check(site, site_dir, site_dir / "work" / "s2_check.png")
    except Exception as e:  # noqa: BLE001 - the network check must not block publishing
        log.warning("Sentinel-2 check failed: %s", e)
        s2 = {"status": "error", "message": str(e)}
    acc = accuracy(Path(raw_dir) / "validation" / "points.csv")
    out = {"status": "validated" if acc else "not_validated"}
    if acc:
        out["accuracy"] = acc
    else:
        out["reason"] = (
            "no hand-labelled points yet (validate --make-points, then label them from Sentinel-2)"
        )
    if area:
        out["area_check"] = area
    out["sentinel2_check"] = s2
    io.write_json(site_dir / "validation.json", out)
    summary.update(
        {
            "status": out["status"],
            "area_within_15pct": area and area.get("within_15pct"),
            "s2": {
                k: s2.get(k)
                for k in ("status", "agreement", "water_iou", "shoreline_dist_px_median", "within_2px")
            },
        }
    )
    return summary

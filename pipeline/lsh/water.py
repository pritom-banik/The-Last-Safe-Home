"""SAR water masks and flooded-vegetation flags from NISAR HH dB (SPEC §7.3)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig

log = logging.getLogger("lsh.water")

BIMODAL_MIN = 0.5  # Otsu between-class variance / total variance below this → histogram not bimodal
FLOODVEG_DB = 3.0  # HH brighter than the season median by this much → possible flooded vegetation


def smooth_db(db: np.ndarray, size: int) -> np.ndarray:
    """NaN → median of finite pixels, then a median filter (speckle)."""
    fill = float(np.nanmedian(db)) if np.isfinite(db).any() else -15.0
    return median_filter(np.where(np.isfinite(db), db, fill).astype("float32"), size=size)


def otsu(values: np.ndarray, bins: int = 256) -> tuple[float, float]:
    """(threshold, between-class variance / total variance) on finite values."""
    v = values[np.isfinite(values)]
    if v.size < 100 or np.ptp(v) == 0:
        return float("nan"), 0.0
    hist, edges = np.histogram(v, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    w = hist.astype("float64") / hist.sum()
    w0 = np.cumsum(w)
    w1 = 1 - w0
    m = np.cumsum(w * centres)
    mt = m[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mt * w0 - m) ** 2 / (w0 * w1)
    between[~np.isfinite(between)] = 0
    k = int(np.argmax(between))
    total = float(np.var(v))
    return float(edges[k + 1]), float(between[k] / total) if total > 0 else 0.0


def clean(water: np.ndarray, min_px: int) -> np.ndarray:
    from skimage.morphology import remove_small_holes, remove_small_objects

    # objects/holes smaller than min_px pixels are removed (skimage ≥ 0.26: `max_size` = largest removed size)
    out = remove_small_objects(water, max_size=min_px - 1)
    return remove_small_holes(out, max_size=min_px - 1)


def run(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    sid = site.id
    dates = io.list_keys(out_dir, sid, "gcov-hh-db")
    if not dates:
        raise FileNotFoundError("no gcov-hh-db COGs: run the gcov step first")
    todo = [
        d
        for d in dates
        if force
        or not (
            io.cog_path(out_dir, sid, "water", d).exists()
            and io.cog_path(out_dir, sid, "floodveg", d).exists()
        )
    ]
    if not todo:
        return {"skipped_existing": [d.isoformat() for d in dates]}
    a = site.analysis
    smooth, prof = {}, None
    aoi = None
    for d in dates:
        db, prof = io.read_raster(io.cog_path(out_dir, sid, "gcov-hh-db", d))
        if aoi is None:
            aoi = np.isfinite(db)
        smooth[d] = smooth_db(db, a.speckle_filter_px)

    thr = {d: otsu(smooth[d][aoi]) for d in dates}
    good = [t for t, r in thr.values() if np.isfinite(t) and r >= BIMODAL_MIN]
    fallback = float(np.median(good)) if good else float("nan")
    # season reference for flooded vegetation: per-pixel median HH over all passes (all are Jun–Oct)
    ref = np.median(np.stack([smooth[d] for d in dates]), axis=0)

    per_date = {}
    for d in todo:
        t, ratio = thr[d]
        used = t
        if not np.isfinite(t) or ratio < BIMODAL_MIN:
            log.warning(
                "water %s: histogram not bimodal (ratio %.2f); using the median threshold %.2f dB",
                d,
                ratio,
                fallback,
            )
            used = fallback
        water = clean((smooth[d] < used) & aoi, a.min_water_blob_px)
        floodveg = (smooth[d] > ref + FLOODVEG_DB) & ~water & aoi
        w8 = np.where(aoi, water, 255).astype(np.uint8)
        f8 = np.where(aoi, floodveg, 255).astype(np.uint8)
        io.write_cog(io.cog_path(out_dir, sid, "water", d), w8, prof["transform"], prof["crs"], mask=True)
        io.write_cog(io.cog_path(out_dir, sid, "floodveg", d), f8, prof["transform"], prof["crs"], mask=True)
        per_date[d.isoformat()] = {
            "otsu_db": round(t, 2),
            "bimodal_ratio": round(ratio, 3),
            "threshold_db": round(used, 2),
            "water_frac": round(float(water[aoi].mean()), 3),
            "floodveg_frac": round(float(floodveg[aoi].mean()), 4),
        }
        log.info("water %s: %s", d, per_date[d.isoformat()])
    return {"per_date": per_date, "fallback_threshold_db": round(fallback, 2) if good else None}

"""Flood frequency from the 2026 NISAR water masks (SPEC §7.7)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio.enums import Resampling
from rasterio.warp import reproject

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.grid import site_grid

PERMANENT_FRAC = 0.9


def run(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    sid = site.id
    out = io.cog_path(out_dir, sid, "floodfreq", 2026)
    if out.exists() and not force:
        return {"skipped": True}
    dates = io.list_keys(out_dir, sid, "water")
    if not dates:
        raise FileNotFoundError("no NISAR water masks: run water-sar first")
    count = valid = None
    prof = None
    for d in dates:
        w, prof = io.read_mask(io.cog_path(out_dir, sid, "water", d))
        ok = w != 255
        if count is None:
            count = np.zeros(w.shape, np.int16)
            valid = np.zeros(w.shape, np.int16)
        count += (w == 1) & ok
        valid += ok
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(valid > 0, count / valid, np.nan).astype("float32")

    # permanent water: Landsat (latest year) water AND water in ≥ 90 % of NISAR passes
    years = io.list_keys(out_dir, sid, "landwater")
    lw, lprof = io.read_mask(io.cog_path(out_dir, sid, "landwater", years[-1]))
    lw10 = np.full(frac.shape, 255, np.uint8)
    reproject(
        lw,
        lw10,
        src_transform=lprof["transform"],
        src_crs=lprof["crs"],
        src_nodata=255,
        dst_transform=prof["transform"],
        dst_crs=prof["crs"],
        dst_nodata=255,
        resampling=Resampling.nearest,
    )
    permanent = (lw10 == 1) & (frac >= PERMANENT_FRAC)
    frac[permanent] = np.nan

    grid = site_grid(site, site.analysis.grid_res_m)
    ff = np.full(grid.shape, np.nan, np.float32)
    reproject(
        frac,
        ff,
        src_transform=prof["transform"],
        src_crs=prof["crs"],
        src_nodata=np.nan,
        dst_transform=grid.transform,
        dst_crs=grid.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    ff[~grid.aoi] = np.nan
    io.write_cog(out, ff, grid.transform, grid.crs)
    land = np.isfinite(ff)
    return {
        "passes": len(dates),
        "permanent_water_frac": round(float(permanent[valid > 0].mean()), 3),
        "floodfreq_mean_nonpermanent": round(float(np.nanmean(ff)), 3),
        "floodfreq_pctl_50_90": [round(float(v), 2) for v in np.nanpercentile(ff[land], [50, 90])],
    }

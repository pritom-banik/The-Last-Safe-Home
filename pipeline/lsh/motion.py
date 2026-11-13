"""Season ground movement from NISAR GUNW (SPEC §7.8) — a low-confidence layer.

Sign convention: NISAR/ISCE3 interferograms are reference × conj(secondary) with the signal model
exp(−j·4π·R/λ), so positive unwrapped phase = range increase (ground moving away from the satellite).
`d = −λ/(4π)·φ` therefore gives positive = toward the satellite (≈ uplift) — the spec's formula, unchanged.
The product's ionosphere phase screen is subtracted from the unwrapped phase (docs/DECISIONS.md).
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rasterio.enums import Resampling
from rasterio.warp import reproject

from pipeline.lsh import io, nisar
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.grid import site_grid

log = logging.getLogger("lsh.motion")

WAVELENGTH_M = 0.2384  # L-band, 1.2575 GHz
MIN_PAIR_FRAC = 0.5  # pixel valid only if coherent in ≥ 50 % of pairs
USABLE_PCT = 30.0


def phase_to_mm(phi: np.ndarray) -> np.ndarray:
    """LOS displacement in mm, positive toward the satellite."""
    return -(WAVELENGTH_M / (4 * math.pi)) * phi * 1000.0


@dataclass
class Pair:
    ref: dt.date
    sec: dt.date
    disp_mm: np.ndarray  # NaN where incoherent / invalid
    coh: np.ndarray
    transform: object
    epsg: int


def _time(v) -> dt.date:
    s = (
        v.decode()
        if isinstance(v, bytes)
        else str(np.asarray(v).ravel()[0], "utf-8")
        if isinstance(np.asarray(v).ravel()[0], bytes)
        else str(v)
    )
    return dt.date.fromisoformat(s[:10])


def mask_valid(mask: np.ndarray) -> np.ndarray:
    """GUNW `mask`: bits 0–7 hold a 3-digit code (water, ref subswath, sec subswath); 0 in either subswath
    digit = invalid; bits 8–23 = RSLC anomaly flags (any set = invalid)."""
    m = mask.astype(np.uint32)
    code = m & 0xFF
    ref_sw, sec_sw = (code // 10) % 10, code % 10
    anomalies = (m >> 8) & 0xFFFF
    return (ref_sw > 0) & (sec_sw > 0) & (anomalies == 0)


def read_pair(path: Path, coherence_min: float) -> Pair:
    import h5py

    with h5py.File(path, "r") as f:
        g = nisar.grid_group(f, "GUNW")
        phi = g["unwrappedPhase"][()].astype("float64")
        if "ionospherePhaseScreen" in g:
            iono = g["ionospherePhaseScreen"][()]
            phi = phi - np.where(np.isfinite(iono), iono, 0.0)
        coh = g["coherenceMagnitude"][()].astype("float32")
        cc = g["connectedComponents"][()] if "connectedComponents" in g else None
        mask = g.parent["mask"][()] if "mask" in g.parent else None
        x, y = g["xCoordinates"][()], g["yCoordinates"][()]
        epsg = nisar._epsg(g["projection"])
        ident = f["/science/LSAR/identification"]
        ref = _time(ident["referenceZeroDopplerStartTime"][()])
        sec = _time(ident["secondaryZeroDopplerStartTime"][()])
    ok = np.isfinite(phi) & (coh >= coherence_min)
    if cc is not None:
        ok &= cc > 0
    if mask is not None:
        ok &= mask_valid(mask)
    disp = np.where(ok, phase_to_mm(phi), np.nan)
    if np.isfinite(disp).any():
        disp -= np.nanmedian(disp)  # reference: median of coherent pixels (reference_area_wkt not set)
    from rasterio.transform import from_origin

    dx, dy = abs(x[1] - x[0]), abs(y[1] - y[0])
    if y[0] < y[-1]:
        disp, coh = disp[::-1], coh[::-1]
    t = from_origin(x.min() - dx / 2, y.max() + dy / 2, dx, dy)
    return Pair(ref, sec, disp.astype("float32"), coh, t, epsg)


def run(site: SiteConfig, out_dir: Path, raw_dir: Path, force: bool = False) -> dict:
    sid = site.id
    m_out = io.cog_path(out_dir, sid, "motion", 2026)
    c_out = io.cog_path(out_dir, sid, "coherence", 2026)
    if m_out.exists() and c_out.exists() and not force:
        return {"skipped": True}
    files = sorted((Path(raw_dir) / "nisar" / "gunw").glob("*.h5"))
    # a pair downloaded in two product versions counts once: the newest (highest counter) wins
    latest: dict[str, Path] = {}
    for f in files:
        latest[nisar.pair_key(f.name)] = f
    if len(latest) < len(files):
        log.info("GUNW: %d older product versions ignored", len(files) - len(latest))
    files = sorted(latest.values())
    grid = site_grid(site, site.analysis.grid_res_m)
    if not files:
        log.warning("no GUNW files: motion not usable")
        return _write_empty(site, out_dir, grid, "no GUNW pairs")
    pairs = sorted((read_pair(p, site.analysis.coherence_min) for p in files), key=lambda p: p.ref)

    def to_grid(arr, p, resampling):
        out = np.full(grid.shape, np.nan, np.float32)
        reproject(
            arr,
            out,
            src_transform=p.transform,
            src_crs=f"EPSG:{p.epsg}",
            src_nodata=np.nan,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=resampling,
        )
        return out

    disp = np.stack([to_grid(p.disp_mm, p, Resampling.bilinear) for p in pairs])
    coh = np.stack([to_grid(p.coh, p, Resampling.bilinear) for p in pairs])
    days = np.array([(p.sec - p.ref).days for p in pairs], dtype="float64")
    chain = all(pairs[i].sec == pairs[i + 1].ref for i in range(len(pairs) - 1))
    season_days = float((pairs[-1].sec - pairs[0].ref).days) if chain else float(days.sum())
    ok = np.isfinite(disp)
    n_ok = ok.sum(axis=0)
    enough = n_ok >= MIN_PAIR_FRAC * len(pairs)
    # chain: cumulative sum; pixels missing pairs are scaled up by covered time (= mean velocity × season)
    covered = (ok * days[:, None, None]).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        motion = np.nansum(disp, axis=0) * np.where(covered > 0, season_days / covered, np.nan)
    motion = np.where(enough & grid.aoi, motion, np.nan).astype("float32")
    mean_coh = np.where(grid.aoi, np.nanmean(coh, axis=0), np.nan).astype("float32")

    # land = not today's river (latest NISAR water mask, majority on the 30 m grid)
    land = _land_today(site, out_dir, grid)
    coherent_land_pct = float(100.0 * np.isfinite(motion[land]).mean()) if land.any() else 0.0
    io.write_cog(m_out, motion, grid.transform, grid.crs)
    io.write_cog(c_out, mean_coh, grid.transform, grid.crs)
    return {
        "pairs": [f"{p.ref}→{p.sec}" for p in pairs],
        "chain": chain,
        "season_days": season_days,
        "coherent_land_pct": round(coherent_land_pct, 1),
        "motion_usable": coherent_land_pct >= USABLE_PCT,
        "motion_mm_pctl_5_50_95": [round(float(v), 1) for v in np.nanpercentile(motion, [5, 50, 95])]
        if np.isfinite(motion).any()
        else None,
        "mean_coherence_land": round(float(np.nanmean(mean_coh[land])), 3) if land.any() else None,
        "ionosphere_subtracted": True,
        "reference": "median of coherent pixels per pair",
    }


def _land_today(site: SiteConfig, out_dir: Path, grid) -> np.ndarray:
    dates = io.list_keys(out_dir, site.id, "water")
    w, prof = io.read_mask(io.cog_path(out_dir, site.id, "water", dates[-1]))
    wf = np.where(w == 255, np.nan, w).astype("float32")
    out = np.full(grid.shape, np.nan, np.float32)
    reproject(
        wf,
        out,
        src_transform=prof["transform"],
        src_crs=prof["crs"],
        src_nodata=np.nan,
        dst_transform=grid.transform,
        dst_crs=grid.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    return grid.aoi & (out < 0.5)


def _write_empty(site, out_dir, grid, reason: str) -> dict:
    nan = np.full(grid.shape, np.nan, np.float32)
    io.write_cog(io.cog_path(out_dir, site.id, "motion", 2026), nan, grid.transform, grid.crs)
    io.write_cog(io.cog_path(out_dir, site.id, "coherence", 2026), nan, grid.transform, grid.crs)
    return {"coherent_land_pct": 0.0, "motion_usable": False, "reason": reason}

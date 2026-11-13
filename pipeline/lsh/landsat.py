"""Landsat dry-season composites, MNDWI and water masks from Planetary Computer (SPEC §7.4). No login."""

from __future__ import annotations

import calendar
import logging
from pathlib import Path

import numpy as np

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.grid import SiteGrid, site_grid

log = logging.getLogger("lsh.landsat")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
RES_M = 30
SCALE, OFFSET = 0.0000275, -0.2
# qa_pixel bits that make a pixel unusable: fill 0, dilated cloud 1, cloud 3, cloud shadow 4
QA_BAD_BITS = (0, 1, 3, 4)
THRESHOLD_CLAMP = (-0.1, 0.3)
MAX_ITEMS = 12  # least cloudy scenes per composite


def platform_groups(year: int) -> list[set[str]]:
    """Preference (SPEC §7.4): Landsat 5 first for 2003/2008 (Landsat 7 SLC-off stripes), else newest."""
    if year in (2003, 2008):
        return [{"landsat-5"}, {"landsat-7"}]
    return [{"landsat-8", "landsat-9"}, {"landsat-7"}, {"landsat-5", "landsat-4"}]


def pick_items(items: list, year: int) -> tuple[list, str]:
    for group in platform_groups(year):
        chosen = [i for i in items if i.properties.get("platform") in group]
        if chosen:
            chosen.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
            return chosen[:MAX_ITEMS], "+".join(sorted(group & {i.properties["platform"] for i in chosen}))
    return [], ""


def search(site: SiteConfig, year: int) -> list:
    import planetary_computer
    import pystac_client

    months = site.landsat.months
    start = f"{year}-{min(months):02d}-01"
    last = max(months)
    end = f"{year}-{last:02d}-{calendar.monthrange(year, last)[1]:02d}"
    cat = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    items = cat.search(
        collections=[COLLECTION],
        bbox=list(site.bounds),
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": site.landsat.max_cloud}},
    ).items()
    return [i for i in items if i.datetime and i.datetime.month in months]


def qa_valid(qa: np.ndarray) -> np.ndarray:
    bad = np.zeros(qa.shape, dtype=bool)
    q = qa.astype(np.uint16)
    for bit in QA_BAD_BITS:
        bad |= (q >> bit) & 1 == 1
    return ~bad


def reflectance(dn: np.ndarray) -> np.ndarray:
    out = dn.astype("float32") * SCALE + OFFSET
    out[dn == 0] = np.nan
    return out


def mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        m = (green - swir) / (green + swir)
    m[~np.isfinite(m)] = np.nan
    return np.clip(m, -1, 1).astype("float32")


def water_threshold(values: np.ndarray) -> float:
    """Otsu on finite MNDWI values, clamped to [−0.1, 0.3] (SPEC §7.4 step 4)."""
    from skimage.filters import threshold_otsu

    v = values[np.isfinite(values)]
    if v.size < 100:
        return 0.0
    return float(np.clip(threshold_otsu(v), *THRESHOLD_CLAMP))


def load_composite(items: list, grid: SiteGrid) -> tuple[np.ndarray, np.ndarray, int]:
    """Median green and SWIR1 reflectance over cloud-free observations, on the site grid."""
    from odc.geo.geobox import GeoBox
    from odc.stac import load

    gbox = GeoBox(grid.shape, grid.transform, grid.crs)
    ds = load(
        items,
        bands=["green", "swir16", "qa_pixel"],
        geobox=gbox,
        groupby="solar_day",
        resampling={"qa_pixel": "nearest", "*": "bilinear"},
        fail_on_error=False,
    )
    ok = qa_valid(ds["qa_pixel"].values)
    green = reflectance(ds["green"].values)
    swir = reflectance(ds["swir16"].values)
    green[~ok] = np.nan
    swir[~ok] = np.nan
    with np.errstate(all="ignore"), _quiet_nanmedian():
        g = np.nanmedian(green, axis=0).astype("float32")
        s = np.nanmedian(swir, axis=0).astype("float32")
    return g, s, int(ds.sizes.get("time", 0))


class _quiet_nanmedian:
    """Silence 'All-NaN slice' warnings from nanmedian (expected where every scene is cloudy)."""

    def __enter__(self):
        import warnings

        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *exc):
        self._w.__exit__(*exc)


def run(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    grid = site_grid(site, RES_M)
    per_year, skipped, missing = {}, [], []
    for year in site.landsat.years:
        m_out = io.cog_path(out_dir, site.id, "mndwi", year)
        w_out = io.cog_path(out_dir, site.id, "landwater", year)
        if m_out.exists() and w_out.exists() and not force:
            skipped.append(year)
            continue
        items, platform = pick_items(search(site, year), year)
        if not items:
            log.warning("landsat %d: no usable scene (cloud < %s%%), skipped", year, site.landsat.max_cloud)
            missing.append(year)
            continue
        g, s, n_days = load_composite(items, grid)
        m = mndwi(g, s)
        m[~grid.aoi] = np.nan
        valid = np.isfinite(m) & grid.aoi
        if valid.sum() < 0.5 * grid.aoi.sum():
            log.warning("landsat %d: only %.0f%% of the AOI has clear pixels", year, 100 * valid.mean())
        t = water_threshold(m[valid])
        water = np.full(grid.shape, 255, dtype=np.uint8)
        water[valid] = (m[valid] > t).astype(np.uint8)
        io.write_cog(m_out, m, grid.transform, grid.crs)
        io.write_cog(w_out, water, grid.transform, grid.crs, mask=True)
        land_km2 = float(((water == 0) & grid.aoi).sum() * RES_M * RES_M / 1e6)
        per_year[year] = {
            "platform": platform,
            "scenes": len(items),
            "days": n_days,
            "scene_ids": [i.id for i in items],
            "clear_aoi_frac": round(float(valid.sum() / grid.aoi.sum()), 3),
            "threshold": round(t, 3),
            "water_frac": round(float(water[valid].mean()), 3) if valid.any() else None,
            "land_km2": round(land_km2, 2),
        }
        log.info("landsat %d: %s", year, {k: v for k, v in per_year[year].items() if k != "scene_ids"})
    return {
        "years": per_year,
        "skipped_existing": skipped,
        "missing": missing,
        "grid_shape": list(grid.shape),
        "res_m": RES_M,
    }

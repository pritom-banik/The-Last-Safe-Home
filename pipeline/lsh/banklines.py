"""Bank lines from water masks (SPEC §7.5): river components → land polygon → bank line (AOI edge excluded).

NISAR monsoon masks also contain floodplain water (flooded paddy, wet mudflats are as dark as the river at
L-band). For bank lines, NISAR water only counts as *river* inside a corridor around the latest dry-season
Landsat river (`CORRIDOR_M`); floodplain water outside it is flooding, not river (docs/DECISIONS.md).

Land polygons (site UTM) are also written to `work/land_utm.geojson` for the transects and score steps.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

import numpy as np
import shapely
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.warp import reproject
from scipy.ndimage import binary_erosion, distance_transform_edt, label
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig

log = logging.getLogger("lsh.banklines")

MIN_RIVER_KM2 = 1.0
MIN_LAND_KM2 = 0.02  # land specks smaller than this are noise, not banks
SIMPLIFY_M = 15.0
CORRIDOR_M = 300.0
LAND_FILE = "work/land_utm.geojson"


def river_components(
    water: np.ndarray, aoi: np.ndarray, px_km2: float, min_km2: float | None = MIN_RIVER_KM2
) -> np.ndarray:
    """Water components touching the AOI boundary or larger than `min_km2` (inland ponds are dropped);
    `min_km2=None`: edge-connected water only."""
    lab, n = label(water & aoi)
    if n == 0:
        return np.zeros_like(water, dtype=bool)
    edge = aoi & ~binary_erosion(aoi, border_value=0)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sizes * px_km2 >= min_km2 if min_km2 is not None else np.zeros(n + 1, dtype=bool)
    keep[np.unique(lab[edge & water])] = True
    keep[0] = False
    return keep[lab]


def land_polygon(river: np.ndarray, aoi: np.ndarray, transform, res: float) -> BaseGeometry:
    """AOI minus river, vectorised, opened by one pixel (spurs), simplified 15 m, specks dropped."""
    land = aoi & ~river
    polys = [shape(g) for g, v in shapes(land.astype(np.uint8), mask=land, transform=transform) if v == 1]
    if not polys:
        return shapely.Polygon()
    g = unary_union(polys).buffer(-res / 2).buffer(res / 2).simplify(SIMPLIFY_M, preserve_topology=True)
    g = shapely.make_valid(g)
    parts = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area >= MIN_LAND_KM2 * 1e6]
    return unary_union(parts) if parts else shapely.Polygon()


def bank_line(land: BaseGeometry, aoi_utm: BaseGeometry, res: float) -> BaseGeometry:
    """Boundary of the land minus the AOI edge (the box edge is not a bank)."""
    if land.is_empty:
        return shapely.MultiLineString()
    b = land.boundary.difference(aoi_utm.boundary.buffer(res * 1.5))
    lines = [g for g in getattr(b, "geoms", [b]) if g.geom_type == "LineString" and not g.is_empty]
    merged = linemerge(lines) if lines else shapely.MultiLineString()
    return merged


def fill_landsat_gaps(masks: dict[int, np.ndarray], aoi: np.ndarray) -> dict[int, np.ndarray]:
    """Nodata (255) pixels take the value from the nearest year with data there (else land)."""
    years = sorted(masks)
    out = {}
    for y in years:
        m = masks[y].copy()
        for other in sorted(years, key=lambda o: abs(o - y)):
            gap = (m == 255) & aoi
            if not gap.any():
                break
            src = masks[other]
            m[gap] = np.where(src[gap] != 255, src[gap], 255)
        m[(m == 255) & aoi] = 0
        out[y] = m
    return out


def median3(stack: list[np.ndarray]) -> np.ndarray:
    """Majority of three water masks (= per-pixel median of 0/1)."""
    return np.sum([s.astype(np.uint8) for s in stack], axis=0) >= 2


def _to_grid(arr: np.ndarray, src_prof: dict, dst_prof: dict) -> np.ndarray:
    out = np.zeros((dst_prof["height"], dst_prof["width"]), dtype=np.uint8)
    reproject(
        arr.astype(np.uint8),
        out,
        src_transform=src_prof["transform"],
        src_crs=src_prof["crs"],
        dst_transform=dst_prof["transform"],
        dst_crs=dst_prof["crs"],
        resampling=Resampling.nearest,
    )
    return out.astype(bool)


def landsat_river(out_dir: Path, sid: str, min_km2: float | None = MIN_RIVER_KM2) -> tuple[np.ndarray, dict]:
    """River of the latest Landsat year (cloud gaps filled from other years) and its raster profile."""
    years = io.list_keys(out_dir, sid, "landwater")
    raw, lprof = {}, None
    for y in years:
        raw[y], lprof = io.read_mask(io.cog_path(out_dir, sid, "landwater", y))
    l_aoi = np.any([raw[y] != 255 for y in years], axis=0)
    filled = fill_landsat_gaps(raw, l_aoi)
    res = abs(lprof["transform"].a)
    return river_components(filled[years[-1]] == 1, l_aoi, res * res / 1e6, min_km2), lprof


def corridor_mask(latest_river: np.ndarray, lprof: dict, dst_prof: dict) -> np.ndarray:
    """Pixels of `dst_prof`'s grid within CORRIDOR_M of the latest dry-season Landsat river."""
    seed = _to_grid(latest_river, lprof, dst_prof)
    return distance_transform_edt(~seed) * abs(dst_prof["transform"].a) <= CORRIDOR_M


def write_land(path: Path, items: list[tuple[str, str, BaseGeometry]], epsg: int) -> None:
    feats = [
        {"type": "Feature", "properties": {"source": s, "key": k}, "geometry": mapping(g)}
        for s, k, g in items
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "crs_epsg": epsg, "features": feats}), encoding="utf-8"
    )


def read_land(site_dir: Path) -> dict[tuple[str, str], BaseGeometry]:
    fc = json.loads((Path(site_dir) / LAND_FILE).read_text(encoding="utf-8"))
    return {(f["properties"]["source"], f["properties"]["key"]): shape(f["geometry"]) for f in fc["features"]}


def run(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    sid, epsg = site.id, site.utm_epsg
    min_km2 = site.analysis.river_min_km2
    out_dir = Path(out_dir)
    bank_path = io.vector_path(out_dir, sid, "banklines")
    if bank_path.exists() and (out_dir / LAND_FILE).exists() and not force:
        return {"skipped": True}
    aoi_utm = io.from_wgs84(site.aoi, epsg)
    feats, land_items, summary = [], [], {"landsat": {}, "nisar": {}, "nisar-median3": {}}

    # ---- Landsat years (dry season, 30 m)
    years = io.list_keys(out_dir, sid, "landwater")
    raw, lprof = {}, None
    for y in years:
        raw[y], lprof = io.read_mask(io.cog_path(out_dir, sid, "landwater", y))
    l_aoi = np.any([raw[y] != 255 for y in years], axis=0)
    filled = fill_landsat_gaps(raw, l_aoi)
    lres = abs(lprof["transform"].a)
    l_px_km2 = lres * lres / 1e6
    latest_river = None
    for y in years:
        river = river_components(filled[y] == 1, l_aoi, l_px_km2, min_km2)
        land = land_polygon(river, l_aoi, lprof["transform"], lres)
        bank = bank_line(land, aoi_utm, lres)
        land_items.append(("landsat", str(y), land))
        feats.append(io.feature(io.to_wgs84(bank, epsg), {"date": None, "year": y, "source": "landsat"}))
        summary["landsat"][y] = {
            "land_km2": round(land.area / 1e6, 2),
            "bank_km": round(bank.length / 1e3, 1),
        }
        latest_river = river

    # ---- NISAR dates (10 m), river constrained to the dry-season corridor
    dates = io.list_keys(out_dir, sid, "water")
    water, nprof = {}, None
    for d in dates:
        w, nprof = io.read_mask(io.cog_path(out_dir, sid, "water", d))
        water[d] = w
    n_aoi = water[dates[0]] != 255
    nres = abs(nprof["transform"].a)
    n_px_km2 = nres * nres / 1e6
    corridor = corridor_mask(latest_river, lprof, nprof)

    def nisar_land(w01: np.ndarray) -> BaseGeometry:
        river = river_components(w01 & corridor, n_aoi, n_px_km2, min_km2)
        return land_polygon(river, n_aoi, nprof["transform"], nres)

    for d in dates:
        land = nisar_land(water[d] == 1)
        bank = bank_line(land, aoi_utm, nres)
        feats.append(
            io.feature(io.to_wgs84(bank, epsg), {"date": d.isoformat(), "year": d.year, "source": "nisar"})
        )
        summary["nisar"][d.isoformat()] = {
            "land_km2": round(land.area / 1e6, 2),
            "bank_km": round(bank.length / 1e3, 1),
        }
    for i in range(2, len(dates)):
        win = dates[i - 2 : i + 1]
        land = nisar_land(median3([water[x] == 1 for x in win]))
        bank = bank_line(land, aoi_utm, nres)
        d = dates[i]
        land_items.append(("nisar-median3", d.isoformat(), land))
        feats.append(
            io.feature(
                io.to_wgs84(bank, epsg),
                {
                    "date": d.isoformat(),
                    "year": d.year,
                    "source": "nisar-median3",
                    "window": [win[0].isoformat(), d.isoformat()],
                },
            )
        )
        summary["nisar-median3"][d.isoformat()] = {
            "land_km2": round(land.area / 1e6, 2),
            "bank_km": round(bank.length / 1e3, 1),
        }

    io.write_geojson(bank_path, feats)
    write_land(out_dir / LAND_FILE, land_items, epsg)
    summary["bank_date"] = dates[-1].isoformat() if len(dates) >= 3 else None
    summary["corridor_m"] = CORRIDOR_M
    return summary


def today_key(land: dict[tuple[str, str], BaseGeometry]) -> tuple[str, str]:
    """Latest NISAR median3 land polygon = today's bank map (falls back to the latest Landsat year)."""
    m3 = sorted(k for s, k in land if s == "nisar-median3")
    if m3:
        return "nisar-median3", m3[-1]
    return "landsat", str(max(int(k) for s, k in land if s == "landsat"))


def decimal_time(source: str, key: str, months: list[int]) -> float:
    from pipeline.lsh.transects import decimal_year, landsat_decimal_year

    return (
        landsat_decimal_year(int(key), months)
        if source == "landsat"
        else decimal_year(dt.date.fromisoformat(key))
    )

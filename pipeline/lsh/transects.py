"""Baseline, transects, bank intersections and retreat rates (SPEC §7.6) — geometry core.

All geometry here is in the site's projected (metre) CRS. The synthetic demo uses the core functions; `run`
is the real-data `transects` step (reads the land polygons written by `banklines`).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import shapely
import shapely.ops
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge


def decimal_year(d: dt.date | str) -> float:
    d = dt.date.fromisoformat(d) if isinstance(d, str) else d
    start = dt.date(d.year, 1, 1)
    days = (dt.date(d.year + 1, 1, 1) - start).days
    return d.year + ((d - start).days + 0.5) / days


def landsat_decimal_year(year: int, months: list[int]) -> float:
    """Time stamp of a composite over `months` of `year` (middle of the months)."""
    return year + (float(np.mean(months)) - 0.5) / 12.0


def _lines(geom: BaseGeometry) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    if hasattr(geom, "geoms"):
        return [g for part in geom.geoms for g in _lines(part)]
    return []


def baseline_from_land(
    land: BaseGeometry, inset_m: float, min_length_m: float = 1000.0, exclude: BaseGeometry | None = None
) -> list[LineString]:
    """Land polygon buffered inland by `inset_m`, exterior ring(s), minus `exclude`, parts >= min length."""
    inner = land.buffer(-inset_m)
    polys = [inner] if inner.geom_type == "Polygon" else list(getattr(inner, "geoms", []))
    out: list[LineString] = []
    for poly in polys:
        if poly.is_empty:
            continue
        ring: BaseGeometry = LineString(poly.exterior.coords)
        if exclude is not None:
            ring = ring.difference(exclude)
        merged = linemerge(_lines(ring)) if not ring.is_empty else ring
        out.extend(p for p in _lines(merged) if p.length >= min_length_m)
    return out


@dataclass
class Transect:
    id: int
    line: LineString  # start = on the baseline, pointing outward

    @property
    def start(self) -> Point:
        return Point(self.line.coords[0])


def _first_exit(start: np.ndarray, direction: np.ndarray, length: float, boundary: BaseGeometry) -> float:
    ray = LineString([start, start + direction * length])
    return first_intersection_distance(ray, boundary)


def cast_transects(
    baselines: list[LineString],
    land: BaseGeometry,
    spacing_m: float,
    length_m: float,
    start_id: int = 0,
    smoothing_m: float = 2000.0,
) -> list[Transect]:
    """Perpendicular transects every `spacing_m` along each baseline, pointing away from the land interior.

    Direction = normal of the baseline tangent measured over a chord of `smoothing_m` (±half each side).
    An inland buffer turns every small bulge of the bank into a circular arc whose exact normals all meet
    at one bank point; the smoothed tangent keeps neighbouring transects near-parallel (DSAS-style).
    "Outward" = the side whose ray leaves the land polygon sooner (the baseline sits `inset` inside the bank,
    the other way crosses the whole land mass).
    """
    half = smoothing_m / 2.0
    boundary = land.boundary
    out: list[Transect] = []
    tid = start_id
    for base in baselines:
        for s in np.arange(0.0, base.length + 1e-9, spacing_m):
            p = np.array(base.interpolate(s).coords[0])
            a = np.array(base.interpolate(max(s - half, 0.0)).coords[0])
            b = np.array(base.interpolate(min(s + half, base.length)).coords[0])
            tangent = b - a
            norm = math.hypot(*tangent)
            if norm == 0:
                continue
            normal = np.array([-tangent[1], tangent[0]]) / norm
            d_pos = _first_exit(p, normal, length_m, boundary)
            d_neg = _first_exit(p, -normal, length_m, boundary)
            if np.isnan(d_pos) and np.isnan(d_neg):
                continue  # neither side reaches the bank within length: no useful transect
            if np.isnan(d_pos) or (not np.isnan(d_neg) and d_neg < d_pos):
                normal = -normal
            out.append(Transect(tid, LineString([p, p + normal * length_m])))
            tid += 1
    return out


def first_intersection_distance(transect: LineString, bank: BaseGeometry) -> float:
    """Distance (m) from the transect start to its first crossing of `bank`; NaN if none."""
    if bank is None or bank.is_empty:
        return float("nan")
    hit = transect.intersection(bank)
    if hit.is_empty:
        return float("nan")
    pts = shapely.get_coordinates(hit)
    x0, y0 = transect.coords[0]
    return float(np.min(np.hypot(pts[:, 0] - x0, pts[:, 1] - y0)))


def trim_transect(line: LineString, distances_m, margin_m: float = 100.0) -> LineString:
    """Shorten a transect for display: from its start to the farthest bank crossing + margin."""
    d = np.asarray(distances_m, dtype="float64")
    d = d[np.isfinite(d)]
    if d.size == 0:
        return line
    return shapely.ops.substring(line, 0.0, min(float(d.max()) + margin_m, line.length))


@dataclass
class Rate:
    rate_m_yr: float | None  # positive = bank retreating toward land (erosion)
    sigma_m_yr: float | None
    n_obs: int
    r2: float | None


def retreat_rate(years, distances_m, min_obs: int = 4) -> Rate:
    """OLS of baseline->bank distance vs decimal year. rate = −slope; sigma = standard error of the slope."""
    t = np.asarray(years, dtype="float64")
    d = np.asarray(distances_m, dtype="float64")
    ok = np.isfinite(t) & np.isfinite(d)
    t, d = t[ok], d[ok]
    n = int(t.size)
    if n < max(min_obs, 3) or np.ptp(t) == 0:
        return Rate(None, None, n, None)
    tm = t - t.mean()
    sxx = float(np.sum(tm**2))
    slope = float(np.sum(tm * (d - d.mean())) / sxx)
    resid = d - (d.mean() + slope * tm)
    sse = float(np.sum(resid**2))
    sst = float(np.sum((d - d.mean()) ** 2))
    sigma = math.sqrt(sse / (n - 2) / sxx)
    r2 = 1.0 - sse / sst if sst > 0 else 1.0
    return Rate(-slope, sigma, n, r2)


# --------------------------------------------------------------------------- real-data step (phase 6)


class CrossingIndex:
    """All segments of a (multi)line in an STRtree: fast crossings of many transects with one bank."""

    def __init__(self, lines: BaseGeometry):
        coords = [np.asarray(ln.coords) for ln in _lines(lines) if len(ln.coords) >= 2]
        segs = [LineString(c[i : i + 2]) for c in coords for i in range(len(c) - 1)]
        self.segs = np.array(segs, dtype=object)
        self.tree = shapely.STRtree(self.segs) if segs else None

    def crossings(self, line: LineString) -> np.ndarray:
        """Distances along `line` (from its start) of every crossing."""
        if self.tree is None:
            return np.empty(0)
        idx = self.tree.query(line, predicate="intersects")
        if not idx.size:
            return np.empty(0)
        pts = shapely.get_coordinates(shapely.intersection(line, self.segs[idx]))
        if not pts.size:
            return np.empty(0)
        return shapely.line_locate_point(line, shapely.points(pts))


def signed_bank_distance(
    start: np.ndarray, direction: np.ndarray, length: float, bank: CrossingIndex, start_on_land: bool
) -> float:
    """Distance from the baseline point to the bank along the transect; negative when the bank has moved
    behind the start (the start is already in the river). NaN when no crossing within ±length."""
    if start_on_land:
        d = bank.crossings(LineString([start, start + direction * length]))
        return float(d.min()) if d.size else float("nan")
    d = bank.crossings(LineString([start, start - direction * length]))
    return float(-d.min()) if d.size else float("nan")


def run(site, out_dir, force: bool = False) -> dict:
    """SPEC §7.6 on the land polygons written by `banklines`: baseline (earliest Landsat land, inset),
    transects, signed bank distances per epoch, OLS rates; writes vector/<site>_transects.geojson."""
    from pathlib import Path

    from pipeline.lsh import banklines, io

    out_dir = Path(out_dir)
    path = io.vector_path(out_dir, site.id, "transects")
    if path.exists() and not force:
        return {"skipped": True}
    a, epsg = site.analysis, site.utm_epsg
    land = banklines.read_land(out_dir)
    aoi_utm = io.from_wgs84(site.aoi, epsg)
    years = sorted(int(k) for s, k in land if s == "landsat")
    m3 = sorted(k for s, k in land if s == "nisar-median3")
    if not years:
        raise FileNotFoundError("no Landsat land polygons: run landsat + banklines first")
    epochs = [("landsat", str(y)) for y in years] + [("nisar-median3", d) for d in m3]
    t_of = {e: banklines.decimal_time(*e, site.landsat.months) for e in epochs}

    land0 = baseline_land(land[("landsat", str(years[0]))])
    # baseline parts running along the AOI box edge would cast transects at the box, not at a bank
    edge_zone = aoi_utm.boundary.buffer(a.baseline_inset_m + 300)
    baselines = baseline_from_land(land0, a.baseline_inset_m, exclude=edge_zone)
    transects = _cast_indexed(
        baselines, CrossingIndex(land0.boundary), a.transect_spacing_m, a.transect_length_m
    )

    banks = {e: CrossingIndex(banklines.bank_line(land[e], aoi_utm, 10.0)) for e in epochs}
    starts = np.array([tr.line.coords[0] for tr in transects]) if transects else np.empty((0, 2))
    for e in epochs:
        shapely.prepare(land[e])
    on_land = {
        e: shapely.contains_xy(land[e], starts[:, 0], starts[:, 1]) if len(starts) else np.empty(0, bool)
        for e in epochs
    }

    rate_epochs = [("landsat", str(y)) for y in years] + ([("nisar-median3", m3[-1])] if m3 else [])
    today_e = ("nisar-median3", m3[-1]) if m3 else ("landsat", str(years[-1]))
    feats, n_rate = [], 0
    for i, tr in enumerate(transects):
        p0 = np.asarray(tr.line.coords[0])
        direction = (np.asarray(tr.line.coords[1]) - p0) / a.transect_length_m
        dist = {
            e: signed_bank_distance(p0, direction, a.transect_length_m, banks[e], bool(on_land[e][i]))
            for e in epochs
        }
        finite = [v for v in dist.values() if np.isfinite(v)]
        if not finite:
            continue
        rate = retreat_rate([t_of[e] for e in rate_epochs], [dist[e] for e in rate_epochs])
        lo = min(0.0, min(finite)) - 100.0
        hi = min(max(finite) + 100.0, a.transect_length_m)
        shown = LineString([p0 + direction * lo, p0 + direction * hi]).intersection(aoi_utm)
        if shown.is_empty:
            continue
        today = dist[today_e]
        first_m3 = dist[("nisar-median3", m3[0])] if m3 else float("nan")
        change = first_m3 - today if np.isfinite(first_m3) and np.isfinite(today) else None
        props = {
            "id": tr.id,
            "rate_m_yr": _rnd(rate.rate_m_yr),
            "sigma_m_yr": _rnd(rate.sigma_m_yr),
            "n_obs": rate.n_obs,
            "r2": _rnd(rate.r2, 3),
            "nisar_change_m": _rnd(change),
            "dist_today_m": _rnd(today),
            "bank_lon": None,
            "bank_lat": None,
        }
        if np.isfinite(today):
            lon, lat = io.to_wgs84(Point(p0 + direction * today), epsg).coords[0]
            props["bank_lon"], props["bank_lat"] = round(lon, 6), round(lat, 6)
        n_rate += rate.rate_m_yr is not None
        feats.append(io.feature(io.to_wgs84(shown, epsg), props))
    io.write_geojson(path, feats)
    rates = np.array(
        [f["properties"]["rate_m_yr"] for f in feats if f["properties"]["rate_m_yr"] is not None]
    )
    return {
        "baseline_km": round(sum(b.length for b in baselines) / 1e3, 1),
        "transects_cast": len(transects),
        "transects_written": len(feats),
        "with_rate": n_rate,
        "with_rate_frac": round(n_rate / len(feats), 3) if feats else 0,
        "rate_m_yr_pctl_1_10_50_90_99": [
            round(float(v), 1) for v in np.percentile(rates, [1, 10, 50, 90, 99])
        ]
        if rates.size
        else None,
        "rate_epochs": [f"{s}:{k}" for s, k in rate_epochs],
    }


CREEK_CLOSE_M = 200.0  # channels narrower than 2 × this are closed before the baseline is drawn


def baseline_land(land: BaseGeometry) -> BaseGeometry:
    """Land for the baseline: close narrow creeks (a creek through an island would get its own baseline and
    fans of transects across the island) and drop holes."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    closed = shapely.make_valid(land.buffer(CREEK_CLOSE_M).buffer(-CREEK_CLOSE_M))
    parts = [Polygon(p.exterior) for p in getattr(closed, "geoms", [closed]) if p.geom_type == "Polygon"]
    return unary_union(parts)


def _rnd(x, nd: int = 2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _cast_indexed(
    baselines: list[LineString],
    boundary: CrossingIndex,
    spacing_m: float,
    length_m: float,
    smoothing_m: float = 2000.0,
) -> list[Transect]:
    """`cast_transects` with an indexed land boundary (real coastlines have tens of thousands of vertices)."""
    half = smoothing_m / 2.0
    out: list[Transect] = []
    tid = 1
    for base in baselines:
        for s in np.arange(0.0, base.length + 1e-9, spacing_m):
            p = np.array(base.interpolate(s).coords[0])
            a = np.array(base.interpolate(max(s - half, 0.0)).coords[0])
            b = np.array(base.interpolate(min(s + half, base.length)).coords[0])
            tangent = b - a
            norm = math.hypot(*tangent)
            if norm == 0:
                continue
            normal = np.array([-tangent[1], tangent[0]]) / norm
            dp = boundary.crossings(LineString([p, p + normal * length_m]))
            dn = boundary.crossings(LineString([p, p - normal * length_m]))
            d_pos = dp.min() if dp.size else np.nan
            d_neg = dn.min() if dn.size else np.nan
            if np.isnan(d_pos) and np.isnan(d_neg):
                continue
            if np.isnan(d_pos) or (not np.isnan(d_neg) and d_neg < d_pos):
                normal = -normal
            out.append(Transect(tid, LineString([p, p + normal * length_m])))
            tid += 1
    return out

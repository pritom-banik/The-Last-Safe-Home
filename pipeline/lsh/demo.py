"""Synthetic demo site (SPEC §7.13). NOT real measurements — every file is flagged synthetic.

A sine-shaped river channel migrates east: the east bank erodes at ~40 m/yr (30–50 along the bank), the
west bank accretes at ~25 m/yr. From that analytic river the generator writes every product in SPEC §5:
9 Landsat-year masks, 10 NISAR dates (HH/HV backscatter, water, flooded vegetation), flood frequency, a
small motion field with coherence, buildings, three unions, and the score layers. Bank lines, transects,
rates and the score go through the same `transects.py` / `score.py` code the real pipeline uses, so the
demo exercises the real formulas.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import distance_transform_edt, gaussian_filter
from scipy.spatial import cKDTree
from scipy.special import ndtr
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box

from pipeline.lsh import io, score
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.transects import (
    baseline_from_land,
    cast_transects,
    decimal_year,
    first_intersection_distance,
    landsat_decimal_year,
    retreat_rate,
    trim_transect,
)

log = logging.getLogger("lsh.demo")

SEED = 2026
N_NISAR_DATES = 10
NISAR_REPEAT_DAYS = 12
N_BUILDINGS = 500
PEOPLE_PER_BUILDING = 4.4  # rough Bangladesh rural household size; demo only
UNION_NAMES = [
    ("Demo Union North", "ডেমো ইউনিয়ন উত্তর"),
    ("Demo Union Middle", "ডেমো ইউনিয়ন মধ্য"),
    ("Demo Union South", "ডেমো ইউনিয়ন দক্ষিণ"),
]

BankFn = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]  # v -> (west_u, east_u)


# --------------------------------------------------------------------------- river model


@dataclass(frozen=True)
class River:
    """Channel in local metres (u east, v north, origin = AOI centre).

    t = years since the latest Landsat composite.
    """
    c0: float = 300.0
    half_width: float = 700.0
    amp: float = 400.0
    wavelength: float = 8000.0
    phase: float = 0.6
    east_rate: float = 40.0      # m/yr, east bank moves east (erosion of east land)
    east_rate_amp: float = 10.0
    west_rate: float = 25.0      # m/yr, west bank moves east (accretion of west land)
    west_rate_amp: float = 8.0

    def centre(self, v):
        return self.c0 + self.amp * np.sin(2 * np.pi * v / self.wavelength + self.phase)

    def rates(self, v):
        e = self.east_rate + self.east_rate_amp * np.sin(2 * np.pi * v / 9000.0 + 1.0)
        w = self.west_rate + self.west_rate_amp * np.cos(2 * np.pi * v / 11000.0)
        return w, e

    def banks(self, v, t):
        c = self.centre(v)
        w_rate, e_rate = self.rates(v)
        return c - self.half_width + w_rate * t, c + self.half_width + e_rate * t


def _wiggle(rng: np.random.Generator, rms: float, k: int = 3) -> Callable[[np.ndarray], np.ndarray]:
    """Smooth along-bank noise: sum of k sinusoids, RMS ≈ rms metres."""
    wl = rng.uniform(1500, 6000, k)
    ph = rng.uniform(0, 2 * np.pi, k)
    a = rng.normal(size=k)
    a *= rms * math.sqrt(2) / np.linalg.norm(a)
    return lambda v: sum(a[i] * np.sin(2 * np.pi * np.asarray(v) / wl[i] + ph[i]) for i in range(k))


def _state(river: River, t: float, offset: float = 0.0, west_noise=None, east_noise=None) -> BankFn:
    def fn(v):
        w, e = river.banks(v, t)
        w = w + offset + (west_noise(v) if west_noise else 0.0)
        e = e + offset + (east_noise(v) if east_noise else 0.0)
        return w, e
    return fn


def _median_state(states: list[BankFn]) -> BankFn:
    def fn(v):
        ws, es = zip(*(s(v) for s in states), strict=True)
        return np.median(np.stack(ws), axis=0), np.median(np.stack(es), axis=0)
    return fn


# --------------------------------------------------------------------------- grid


@dataclass
class Grid:
    transform: object
    crs: str
    res: float
    shape: tuple[int, int]
    xc: float
    yc: float
    U: np.ndarray
    V: np.ndarray
    X: np.ndarray
    Y: np.ndarray
    aoi: np.ndarray       # bool, pixel centre inside AOI
    aoi_utm: Polygon
    aoi_wgs84: Polygon

    @property
    def pixel_km2(self) -> float:
        return self.res * self.res / 1e6


def make_grid(site: SiteConfig) -> Grid:
    res = float(site.analysis.grid_res_m)
    aoi_utm = io.from_wgs84(site.aoi, site.utm_epsg)
    minx, miny, maxx, maxy = aoi_utm.bounds
    x0, y1 = math.floor(minx / res) * res, math.ceil(maxy / res) * res
    x1, y0 = math.ceil(maxx / res) * res, math.floor(miny / res) * res
    w, h = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    transform = from_origin(x0, y1, res, res)
    xs = x0 + (np.arange(w) + 0.5) * res
    ys = y1 - (np.arange(h) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    c = aoi_utm.centroid
    aoi = rasterize([aoi_utm], out_shape=(h, w), transform=transform, fill=0, default_value=1).astype(bool)
    return Grid(transform, f"EPSG:{site.utm_epsg}", res, (h, w), c.x, c.y, X - c.x, Y - c.y, X, Y,
                aoi, aoi_utm, site.aoi)


def _river_mask(grid: Grid, state: BankFn) -> np.ndarray:
    v = grid.V[:, 0]
    w, e = state(v)
    return (grid.U > w[:, None]) & (grid.U < e[:, None])


def _smooth(rng: np.random.Generator, shape, sigma_px: float) -> np.ndarray:
    g = gaussian_filter(rng.standard_normal(shape), sigma_px)
    return g / g.std()


# --------------------------------------------------------------------------- dates


def nisar_dates(site: SiteConfig, n: int = N_NISAR_DATES) -> list[dt.date]:
    """12-day repeat from nisar.start, skipping known gaps, up to nisar.end, first n."""
    start = dt.date.fromisoformat(site.nisar.start)
    end = dt.date.fromisoformat(site.nisar.end_or_today)
    gaps = [(dt.date.fromisoformat(a), dt.date.fromisoformat(b)) for a, b in site.nisar.known_gaps]
    out, d = [], start
    while d <= end and len(out) < n:
        if not any(a <= d <= b for a, b in gaps):
            out.append(d)
        d += dt.timedelta(days=NISAR_REPEAT_DAYS)
    return out


# --------------------------------------------------------------------------- outputs


def expected_outputs(site: SiteConfig, out_dir: Path) -> list[Path]:
    sid = site.id
    paths: list[Path] = []
    for d in nisar_dates(site):
        for product in ("gcov-hh-db", "gcov-hv-db", "water", "floodveg"):
            paths.append(io.cog_path(out_dir, sid, product, d))
    for y in site.landsat.years:
        for product in ("mndwi", "landwater"):
            paths.append(io.cog_path(out_dir, sid, product, y))
    for product in ("floodfreq", "motion", "coherence"):
        paths.append(io.cog_path(out_dir, sid, product, 2026))
    for product in ("distance", "years", "score", "population"):
        paths.append(io.cog_path(out_dir, sid, product, "static"))
    for name in ("banklines", "transects", "buildings", "unions"):
        paths.append(io.vector_path(out_dir, sid, name))
    paths += [out_dir / "stats.json", out_dir / "validation.json"]
    return paths


def _lines_wgs84(grid: Grid, state: BankFn, epsg: int):
    """Both banks of one state as a MultiLineString clipped to the AOI: (utm, wgs84)."""
    v = np.arange(grid.V.min() - 2 * grid.res, grid.V.max() + 2 * grid.res, grid.res)
    w, e = state(v)
    lines = MultiLineString([
        list(zip(grid.xc + w, grid.yc + v, strict=True)),
        list(zip(grid.xc + e, grid.yc + v, strict=True)),
    ])
    utm = lines.intersection(grid.aoi_utm)
    # clip again in lon/lat: the AOI's straight lon/lat edges are slightly curved in UTM (~1 m)
    return utm, io.to_wgs84(utm, epsg).intersection(grid.aoi_wgs84)


def _land_polygon(grid: Grid, state: BankFn) -> Polygon:
    """Land on both sides of the river for one state, extended 4 km past the AOI (so the baseline buffer
    does not shrink away from the AOI edges); clipped back to the AOI afterwards."""
    pad = 4000.0
    v = np.arange(grid.V.min() - pad, grid.V.max() + pad, grid.res)
    w, e = state(v)
    u_lo, u_hi = grid.U.min() - pad, grid.U.max() + pad
    west = Polygon([(u_lo, v[0]), *zip(w, v, strict=True), (u_lo, v[-1])])
    east = Polygon([(u_hi, v[0]), *zip(e, v, strict=True), (u_hi, v[-1])])
    return affinity.translate(west.union(east), grid.xc, grid.yc)


def generate(site: SiteConfig, out_dir: Path, force: bool = False) -> dict:
    if not site.synthetic:
        raise ValueError(f"site '{site.id}' is not synthetic; refusing to write demo data into it")
    out_dir = Path(out_dir)
    expected = expected_outputs(site, out_dir)
    if not force and all(p.exists() for p in expected):
        log.info("demo outputs exist; skipping (use --force to regenerate)")
        return {"skipped": True, "files": len(expected)}

    rng = np.random.default_rng(SEED)
    sid, epsg, a = site.id, site.utm_epsg, site.analysis
    grid = make_grid(site)
    river = River()
    shape, aoi = grid.shape, grid.aoi

    def cog(product, key, arr, mask=False):
        if mask:
            arr = np.where(aoi, arr, 255)
        else:
            arr = np.where(aoi, arr, np.nan)
        io.write_cog(io.cog_path(out_dir, sid, product, key), arr, grid.transform, grid.crs, mask=mask)

    # ---- time axis: t = 0 at the latest Landsat composite
    years = sorted(site.landsat.years)
    t_ref = landsat_decimal_year(years[-1], site.landsat.months)
    t_years = {y: landsat_decimal_year(y, site.landsat.months) - t_ref for y in years}
    dates = nisar_dates(site)
    t_dates = {d: decimal_year(d) - t_ref for d in dates}

    # ---- bank states
    landsat_states = {y: _state(river, t_years[y], 0.0, _wiggle(rng, 40), _wiggle(rng, 40)) for y in years}
    nisar_states = {  # per-pass tide/noise offset ~15 m plus a small along-bank wiggle
        d: _state(river, t_dates[d], float(rng.normal(0, 15)), _wiggle(rng, 8), _wiggle(rng, 8))
        for d in dates
    }
    median3 = {dates[i]: _median_state([nisar_states[dates[j]] for j in (i - 2, i - 1, i)])
               for i in range(2, len(dates))}
    today = dates[-1]
    today_state = median3[today]

    # ---- Landsat products
    river_latest_landsat = None
    land_area_by_year: dict[int, np.ndarray] = {}
    mndwi_tex = 0.06 * _smooth(rng, shape, 6)
    for y in years:
        r = _river_mask(grid, landsat_states[y])
        mndwi = np.where(r, 0.35, -0.28) + mndwi_tex + 0.03 * rng.standard_normal(shape)
        cog("mndwi", y, mndwi)
        cog("landwater", y, r.astype("uint8"), mask=True)
        land_area_by_year[y] = aoi & ~r
        river_latest_landsat = r

    # ---- seasonal flooding model (distance to the latest dry-season river)
    d0 = distance_transform_edt(~river_latest_landsat) * grid.res
    east_side = grid.U > river.centre(grid.V)
    p_flood = np.where(east_side, 0.85 * np.exp(-d0 / 700.0), 0.5 * np.exp(-d0 / 500.0))
    flood_field = _smooth(rng, shape, 3)
    veg = ndtr(_smooth(rng, shape, 4))
    hh_tex, hv_tex = 1.2 * _smooth(rng, shape, 5), 1.0 * _smooth(rng, shape, 5)

    water_stack = []
    for d in dates:
        r = _river_mask(grid, nisar_states[d])
        doy = d.timetuple().tm_yday
        season = 0.3 + 0.7 * math.exp(-(((doy - 245) / 30.0) ** 2))  # peaks early September
        u = ndtr(flood_field + 0.25 * rng.standard_normal(shape))
        flooded = aoi & ~r & (u < p_flood * season)
        floodveg = flooded & (veg > 0.7)
        water = r | (flooded & ~floodveg)
        water_stack.append(water)

        speckle = lambda: 10 * np.log10(rng.gamma(4.0, 0.25, shape))  # noqa: E731  (4-look speckle)
        hh = np.select([water, floodveg], [-22.0, -3.5], -8.0 + hh_tex) + speckle()
        hv = np.select([water, floodveg], [-29.0, -12.0], -15.0 + hv_tex) + speckle()
        cog("gcov-hh-db", d, hh)
        cog("gcov-hv-db", d, hv)
        cog("water", d, water.astype("uint8"), mask=True)
        cog("floodveg", d, floodveg.astype("uint8"), mask=True)

    # ---- flood frequency (permanent water -> NaN)
    stack = np.stack(water_stack)
    frac = stack.mean(axis=0)
    permanent = river_latest_landsat & (frac >= 0.9)
    cog("floodfreq", 2026, np.where(permanent, np.nan, frac))

    # ---- today's bank, land and distance
    river_today = _river_mask(grid, today_state)
    land_today = aoi & ~river_today
    dist = np.clip(distance_transform_edt(~river_today) * grid.res - grid.res / 2, 0, None)
    dist = np.where(land_today, dist, np.nan)
    cog("distance", "static", dist)

    # ---- motion + coherence (low confidence layer)
    coh = np.where(land_today, 0.62 + 0.13 * _smooth(rng, shape, 5), 0.12 + 0.05 * _smooth(rng, shape, 2))
    coh = np.clip(coh, 0, 1)
    bowl = -22.0 * np.exp(-((grid.U - 3000) ** 2 + (grid.V - 2500) ** 2) / (2 * 900.0**2))
    motion = 5.0 * _smooth(rng, shape, 8) + bowl
    motion = np.where(land_today & (coh >= a.coherence_min), motion, np.nan)
    coherent_land_pct = 100.0 * np.isfinite(motion[land_today]).mean()
    motion_usable = bool(coherent_land_pct >= 30)
    cog("motion", 2026, motion)
    cog("coherence", 2026, coh)

    # ---- bank lines (EPSG:4326)
    bank_feats, bank_utm = [], {}
    for y in years:
        utm, wgs = _lines_wgs84(grid, landsat_states[y], epsg)
        bank_utm[("landsat", y)] = utm
        bank_feats.append(io.feature(wgs, {"date": None, "year": y, "source": "landsat"}))
    for d in dates:
        _, wgs = _lines_wgs84(grid, nisar_states[d], epsg)
        bank_feats.append(io.feature(wgs, {"date": d.isoformat(), "year": d.year, "source": "nisar"}))
    for i, d in enumerate(dates[2:], start=2):
        utm, wgs = _lines_wgs84(grid, median3[d], epsg)
        bank_utm[("nisar-median3", d)] = utm
        bank_feats.append(io.feature(wgs, {
            "date": d.isoformat(), "year": d.year, "source": "nisar-median3",
            "window": [dates[i - 2].isoformat(), d.isoformat()],
        }))
    io.write_geojson(io.vector_path(out_dir, sid, "banklines"), bank_feats)

    # ---- baseline + transects + rates (shared transect code)
    land0 = _land_polygon(grid, landsat_states[years[0]])
    baselines = [ln for b in baseline_from_land(land0, a.baseline_inset_m)
                 for ln in _as_lines(b.intersection(grid.aoi_utm)) if ln.length >= 1000]
    transects = cast_transects(baselines, land0, a.transect_spacing_m, a.transect_length_m, start_id=1)
    m3_dates = dates[2:]
    tr_feats, bank_pts, bank_rate = [], [], []
    inner_aoi = grid.aoi_utm.buffer(-grid.res)
    for tr in transects:
        if not inner_aoi.contains(tr.start):  # stubs starting on the AOI edge
            continue
        d_land = [first_intersection_distance(tr.line, bank_utm[("landsat", y)]) for y in years]
        d_m3 = [first_intersection_distance(tr.line, bank_utm[("nisar-median3", d)]) for d in m3_dates]
        shown = io.to_wgs84(trim_transect(tr.line, d_land + d_m3), epsg).intersection(grid.aoi_wgs84)
        if shown.is_empty:
            continue
        rate = retreat_rate([t_years[y] for y in years] + [t_dates[today]], d_land + [d_m3[-1]])
        change = d_m3[0] - d_m3[-1] if np.isfinite(d_m3[0]) and np.isfinite(d_m3[-1]) else None
        props = {
            "id": tr.id,
            "rate_m_yr": _r(rate.rate_m_yr), "sigma_m_yr": _r(rate.sigma_m_yr),
            "n_obs": rate.n_obs, "r2": _r(rate.r2, 3),
            "nisar_change_m": _r(change), "dist_today_m": _r(d_m3[-1]),
            "bank_lon": None, "bank_lat": None,
        }
        if np.isfinite(d_m3[-1]):
            bp = tr.line.interpolate(d_m3[-1])
            lon, lat = io.to_wgs84(bp, epsg).coords[0]
            props["bank_lon"], props["bank_lat"] = round(lon, 6), round(lat, 6)
            if rate.rate_m_yr is not None:
                bank_pts.append(bp.coords[0])
                bank_rate.append((rate.rate_m_yr, rate.sigma_m_yr))
        tr_feats.append(io.feature(shown, props))
    io.write_geojson(io.vector_path(out_dir, sid, "transects"), tr_feats)
    if not bank_pts:
        raise RuntimeError("demo produced no transects with a rate; check the river model")

    # ---- score (shared score code): nearest transect bank point -> R, sigma
    tree = cKDTree(np.asarray(bank_pts))
    rs = np.asarray(bank_rate)
    _, idx = tree.query(np.column_stack([grid.X[land_today], grid.Y[land_today]]))
    R = np.full(shape, np.nan)
    S = np.full(shape, np.nan)
    R[land_today], S[land_today] = rs[idx, 0], rs[idx, 1]
    floodfreq = np.where(permanent, np.nan, frac)
    params = score.ScoreParams.from_config(site.score, motion_usable)
    res = score.compute(dist, R, S, floodfreq, motion, params)
    sc = np.where(land_today, res["score"], np.nan)
    yrs = np.where(land_today, np.clip(res["years"], 0, 1000), np.nan)
    cog("years", "static", yrs)
    cog("score", "static", sc)

    # ---- buildings + population
    near_east_bank = land_today & east_side & (dist >= 150) & (dist <= 700)
    bx, by, kinds = _buildings(rng, grid, land_today, near_east_bank)
    rows, cols = _pixel_index(grid, bx, by)
    pop = np.zeros(shape)
    np.add.at(pop, (rows, cols), PEOPLE_PER_BUILDING)
    cog("population", "static", pop)
    b_feats = []
    for i, (x, y, k) in enumerate(zip(bx, by, kinds, strict=True), start=1):
        lon, lat = io.to_wgs84(Point(x, y), epsg).coords[0]
        b_feats.append(io.feature(Point(lon, lat), {"id": i, "kind": k}))
    io.write_geojson(io.vector_path(out_dir, sid, "buildings"), b_feats)
    b_score = sc[rows, cols]
    b_dist = dist[rows, cols]
    b_class = score.class_index(b_score)

    # ---- unions (three latitude bands) with per-union stats
    w, s, e, n = site.bounds
    edges = np.linspace(s, n, len(UNION_NAMES) + 1)
    u_feats = []
    cls_idx = score.class_index(sc)
    for j, (name_en, name_bn) in enumerate(UNION_NAMES):
        band = box(w, edges[-2 - j], e, edges[-1 - j])  # north first
        band_utm = io.from_wgs84(band, epsg)
        inside = aoi & rasterize([band_utm], out_shape=shape, transform=grid.transform, fill=0,
                                 default_value=1).astype(bool)
        in_b = inside[rows, cols]
        props = {
            "id": f"{sid}-u{j + 1}", "name_en": name_en, "name_bn": name_bn, "synthetic": True,
            "land_area_km2": round(float((inside & land_today).sum() * grid.pixel_km2), 3),
            "mean_score": _r(_nanmean(sc[inside]), 1),
            "area_lost_km2_per_yr": _r(_area_loss_rate(land_area_by_year, inside, t_years, grid), 4),
            "buildings_total": int(in_b.sum()),
            "people_total": int(round(pop[inside].sum())),
        }
        for ci, key in enumerate(score.CLASS_KEYS):
            props[f"buildings_{key}"] = int((in_b & (b_class == ci)).sum())
            props[f"people_{key}"] = int(round(pop[inside & (cls_idx == ci)].sum()))
        u_feats.append(io.feature(band, props))
    io.write_geojson(io.vector_path(out_dir, sid, "unions"), u_feats)

    # ---- stats.json + validation.json
    rates = np.array([f["properties"]["rate_m_yr"] for f in tr_feats
                      if f["properties"]["rate_m_yr"] is not None])
    eroding = rates[rates > 0]
    cls_all = cls_idx
    area0 = land_area_by_year[years[0]].sum() * grid.pixel_km2
    area1 = land_area_by_year[years[-1]].sum() * grid.pixel_km2
    river0 = ~land_area_by_year[years[0]] & aoi
    stats = {
        "site": sid, "synthetic": True,
        "site_area_km2": round(grid.aoi_utm.area / 1e6, 2),
        "land_area_km2": round(float(land_today.sum() * grid.pixel_km2), 2),
        "land_lost_km2": {"from_year": years[0], "to_year": years[-1], "net": round(float(area0 - area1), 2),
                          "eroded": round(float((land_area_by_year[years[0]] & ~land_area_by_year[years[-1]])
                                                .sum() * grid.pixel_km2), 2),
                          "accreted": round(float((river0 & land_area_by_year[years[-1]]).sum()
                                                  * grid.pixel_km2), 2)},
        "transects_total": len(tr_feats),
        "transects_with_rate": int(rates.size),
        "transects_eroding": int(eroding.size),
        "mean_retreat_m_yr": _r(float(eroding.mean()) if eroding.size else None, 1),
        "max_retreat_m_yr": _r(float(eroding.max()) if eroding.size else None, 1),
        "buildings_total": len(bx),
        "buildings_within_100m": int((b_dist <= 100).sum()),
        "buildings_within_500m": int((b_dist <= 500).sum()),
        "people_total": int(round(pop.sum())),
        "people_by_class": {k: int(round(pop[cls_all == i].sum())) for i, k in enumerate(score.CLASS_KEYS)},
        "buildings_by_class": {k: int((b_class == i).sum()) for i, k in enumerate(score.CLASS_KEYS)},
        "area_by_class_km2": {k: round(float((cls_all == i).sum() * grid.pixel_km2), 2)
                              for i, k in enumerate(score.CLASS_KEYS)},
        "mean_score": _r(_nanmean(sc), 1),
        "nisar_passes": len(dates),
        "nisar_first": dates[0].isoformat(), "nisar_last": dates[-1].isoformat(),
        "bank_date": today.isoformat(),
        "landsat_years": years,
        "coherent_land_pct": round(float(coherent_land_pct), 1),
        "motion_usable": motion_usable,
        "score_weights_effective": {k: round(v, 3) for k, v in params.effective_weights.items()},
    }
    io.write_json(out_dir / "stats.json", stats)
    io.write_json(out_dir / "validation.json",
                  {"status": "not_validated", "reason": "synthetic demo site: nothing to validate against"})

    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        raise RuntimeError(f"demo did not write: {missing}")
    return {
        "files": len(expected), "nisar_dates": len(dates), "landsat_years": len(years),
        "transects": len(tr_feats), "buildings": len(bx), "coherent_land_pct": stats["coherent_land_pct"],
        "motion_usable": motion_usable, "area_by_class_km2": stats["area_by_class_km2"],
    }


# --------------------------------------------------------------------------- helpers


def _as_lines(geom) -> list[LineString]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, LineString)]


def _r(x, nd: int = 2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _nanmean(a: np.ndarray):
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else None


def _pixel_index(grid: Grid, x: np.ndarray, y: np.ndarray):
    t = grid.transform
    cols = np.floor((x - t.c) / t.a).astype(int)
    rows = np.floor((y - t.f) / t.e).astype(int)
    return np.clip(rows, 0, grid.shape[0] - 1), np.clip(cols, 0, grid.shape[1] - 1)


def _buildings(rng: np.random.Generator, grid: Grid, land: np.ndarray, near_bank: np.ndarray):
    """500 points on today's land: 80% in 10 villages (3 near the eroding bank), 20% scattered."""
    centres = []
    for mask, k in ((near_bank, 3), (land, 7)):
        ys, xs = np.nonzero(mask)
        pick = rng.choice(xs.size, k, replace=False)
        centres.append(np.column_stack([grid.X[ys[pick], xs[pick]], grid.Y[ys[pick], xs[pick]]]))
    villages = np.vstack(centres)
    x0, y1 = grid.transform.c, grid.transform.f
    x1, y0 = x0 + grid.shape[1] * grid.res, y1 - grid.shape[0] * grid.res
    pts: list[tuple[float, float]] = []
    while len(pts) < N_BUILDINGS:
        if rng.random() < 0.8:
            cx, cy = villages[rng.integers(len(villages))]
            x, y = rng.normal(cx, 350), rng.normal(cy, 350)
        else:
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r, c = _pixel_index(grid, np.array([x]), np.array([y]))
        if 0 <= x - x0 < x1 - x0 and 0 <= y1 - y < y1 - y0 and land[r[0], c[0]]:
            pts.append((x, y))
    kinds = np.array(["building"] * N_BUILDINGS, dtype=object)
    special = rng.choice(N_BUILDINGS, 15, replace=False)
    kinds[special[:8]], kinds[special[8:11]], kinds[special[11:]] = "school", "hospital", "place_of_worship"
    arr = np.asarray(pts)
    return arr[:, 0], arr[:, 1], list(kinds)


def _area_loss_rate(land_by_year: dict[int, np.ndarray], inside: np.ndarray, t_years: dict[int, float],
                    grid: Grid) -> float | None:
    """km²/yr of land lost (positive = losing), OLS of Landsat land area vs time."""
    ys = sorted(land_by_year)
    if len(ys) < 2:
        return None
    t = np.array([t_years[y] for y in ys])
    area = np.array([(land_by_year[y] & inside).sum() * grid.pixel_km2 for y in ys])
    return float(-np.polyfit(t, area, 1)[0])

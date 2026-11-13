"""Loads processed site data into memory at startup (SPEC §9).

Per site: layers.json, stats.json, validation.json, the GeoJSON vectors (raw bytes for serving, plus
projected geometries + STRtree / KD-tree indexes for queries), and the small static analysis rasters
(distance, flood frequency, motion, population, score, Landsat land/water) as numpy arrays. Tiles are
rendered from the COGs on disk by rio-tiler, so the large per-date rasters are never held in memory.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from scipy.spatial import cKDTree
from shapely import STRtree
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from pipeline.lsh import io, score
from pipeline.lsh.config import ConfigError, Settings, SiteConfig, load_site
from pipeline.lsh.transects import landsat_decimal_year

log = logging.getLogger("lsh.api.store")


@dataclass
class Raster:
    """One band in memory (float32, nodata -> NaN) with its grid."""
    data: np.ndarray
    transform: rasterio.Affine
    epsg: int

    @classmethod
    def load(cls, path: Path) -> Raster:
        with rasterio.open(path) as src:
            a = src.read(1).astype("float32")
            nd = src.nodata
            if nd is not None and not np.isnan(nd):
                a[a == nd] = np.nan
            return cls(a, src.transform, src.crs.to_epsg())

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    @property
    def pixel_km2(self) -> float:
        return abs(self.transform.a * self.transform.e) / 1e6

    def rowcol(self, x, y):
        inv = ~self.transform
        c, r = inv * (np.asarray(x, dtype="float64"), np.asarray(y, dtype="float64"))
        return np.floor(r).astype(int), np.floor(c).astype(int)

    def sample(self, x, y) -> np.ndarray:
        """Values at projected coordinates; NaN outside the grid."""
        r, c = self.rowcol(x, y)
        h, w = self.shape
        ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        out = np.full(np.shape(r), np.nan, dtype="float64")
        out[ok] = self.data[r[ok], c[ok]]
        return out

    def mask(self, geom_utm: BaseGeometry) -> np.ndarray:
        """Pixels whose centre is inside the geometry; if none, the pixel under its representative point."""
        m = rasterize([geom_utm], out_shape=self.shape, transform=self.transform, fill=0,
                      default_value=1).astype(bool)
        if not m.any():
            p = geom_utm.representative_point()
            r, c = self.rowcol(p.x, p.y)
            if 0 <= r < self.shape[0] and 0 <= c < self.shape[1]:
                m[int(r), int(c)] = True
        return m

    def centres(self, m: np.ndarray):
        rows, cols = np.nonzero(m)
        t = self.transform
        return t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e


@dataclass
class SiteData:
    id: str
    cfg: SiteConfig
    dir: Path
    layers: dict
    stats: dict
    validation: dict
    params: score.ScoreParams
    vectors: dict[str, bytes]
    rasters: dict[str, Raster]
    landwater: dict[int, Raster]
    water_today: Raster | None
    to_utm: Transformer
    to_wgs: Transformer
    # transects with a rate: KD-tree on today's bank crossing (same rule the score raster uses)
    rate_tree: cKDTree | None = None
    rate_props: list[dict] = field(default_factory=list)
    # all transects, projected, for polygon queries
    transect_tree: STRtree | None = None
    transect_props: list[dict] = field(default_factory=list)
    # buildings, projected
    building_tree: STRtree | None = None
    building_dist: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def synthetic(self) -> bool:
        return bool(self.layers.get("synthetic", False))

    @property
    def summary(self) -> dict:
        return {k: self.layers[k] for k in ("site", "name", "synthetic", "center", "zoom", "bounds")} | {
            "id": self.id}

    def project(self, geom: BaseGeometry) -> BaseGeometry:
        return io.from_wgs84(geom, self.cfg.utm_epsg)

    def raster_path(self, layer: str, key: str | None) -> Path | None:
        """File for a manifest raster layer + date/year, or None if not allowed. Never takes a path."""
        entry = self.layers.get("rasters", {}).get(layer)
        if entry is None:
            return None
        if "path" in entry:
            rel = entry["path"]
        else:
            pattern = entry["pattern"]
            if "{date}" in pattern:
                if key not in self.layers.get("nisar_dates", []):
                    return None
                rel = pattern.replace("{date}", key.replace("-", ""))
            else:
                years = [str(y) for y in self.layers.get("landsat_years", [])]
                if key not in years:
                    return None
                rel = pattern.replace("{year}", key)
        path = (self.dir / rel).resolve()
        if self.dir.resolve() not in path.parents or not path.is_file():
            return None
        return path

    def default_key(self, layer: str) -> str | None:
        entry = self.layers.get("rasters", {}).get(layer, {})
        pat = entry.get("pattern", "")
        if "{date}" in pat and self.layers.get("nisar_dates"):
            return self.layers["nisar_dates"][-1]
        if "{year}" in pat and self.layers.get("landsat_years"):
            return str(self.layers["landsat_years"][-1])
        return None

    @property
    def landsat_times(self) -> dict[int, float]:
        return {y: landsat_decimal_year(y, self.cfg.landsat.months) for y in self.landwater}


def _read_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


STATIC_RASTERS = ("distance", "floodfreq", "motion", "population", "score", "years")


def load_site_data(site_id: str, data_dir: Path) -> SiteData | None:
    try:
        cfg = load_site(site_id)
    except ConfigError as e:
        log.warning("site %s: %s", site_id, e)
        return None
    site_dir = data_dir / "processed" / site_id
    layers = _read_json(site_dir / "layers.json")
    if layers is None:
        log.warning("site %s: no layers.json in %s (run the pipeline); skipped", site_id, site_dir)
        return None

    rasters: dict[str, Raster] = {}
    for name in STATIC_RASTERS:
        entry = layers.get("rasters", {}).get(name)
        if entry and "path" in entry:
            rasters[name] = Raster.load(site_dir / entry["path"])
            if rasters[name].epsg != cfg.utm_epsg:
                raise ValueError(f"{site_id}/{name}: CRS EPSG:{rasters[name].epsg} != site {cfg.utm_epsg}")
    landwater = {}
    if "landwater" in layers.get("rasters", {}):
        for y in layers.get("landsat_years", []):
            landwater[int(y)] = Raster.load(site_dir / layers["rasters"]["landwater"]["pattern"]
                                            .replace("{year}", str(y)))
    water_today = None
    if layers.get("nisar_dates") and "water" in layers.get("rasters", {}):
        last = layers["nisar_dates"][-1].replace("-", "")
        water_today = Raster.load(site_dir / layers["rasters"]["water"]["pattern"].replace("{date}", last))

    stats = _read_json(site_dir / "stats.json", {})
    sd = SiteData(
        id=site_id, cfg=cfg, dir=site_dir, layers=layers, stats=stats,
        validation=_read_json(site_dir / "validation.json", {"status": "not_validated"}),
        params=score.ScoreParams.from_config(cfg.score, bool(layers.get("motion_usable", False))),
        vectors={n: (site_dir / rel).read_bytes() for n, rel in layers.get("vectors", {}).items()},
        rasters=rasters, landwater=landwater, water_today=water_today,
        to_utm=Transformer.from_crs(4326, cfg.utm_epsg, always_xy=True),
        to_wgs=Transformer.from_crs(cfg.utm_epsg, 4326, always_xy=True),
    )
    _index_vectors(sd)  # queries use the full-precision features
    sd.vectors = {n: compact_geojson(raw) for n, raw in sd.vectors.items()}  # what the map downloads
    log.info("site %s loaded: %d rasters, %d vectors, %d transects with rate", site_id, len(rasters),
             len(sd.vectors), len(sd.rate_props))
    return sd


def _round(o, nd: int):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, list):
        return [_round(x, nd) for x in o]
    return o


def compact_geojson(raw: bytes, nd: int = 5) -> bytes:
    """Served GeoJSON: coordinates rounded to `nd` decimals (1e-5° ≈ 1 m, finer than the 10–30 m data) and no
    whitespace. Properties are untouched."""
    fc = json.loads(raw)
    for f in fc.get("features", []):
        g = f.get("geometry")
        if g and "coordinates" in g:
            g["coordinates"] = _round(g["coordinates"], nd)
    return json.dumps(fc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def filter_by_source(raw: bytes, sources: frozenset[str]) -> bytes:
    """Only the features whose `source` property is in `sources` (bank lines: landsat/nisar/nisar-median3)."""
    fc = json.loads(raw)
    fc["features"] = [
        f for f in fc.get("features", []) if (f.get("properties") or {}).get("source") in sources
    ]
    return json.dumps(fc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _features(sd: SiteData, name: str) -> list[dict]:
    raw = sd.vectors.get(name)
    return json.loads(raw)["features"] if raw else []


def _index_vectors(sd: SiteData) -> None:
    trs = _features(sd, "transects")
    if trs:
        geoms = [sd.project(shape(f["geometry"])) for f in trs]
        sd.transect_tree = STRtree(geoms)
        sd.transect_props = [f["properties"] for f in trs]
        with_rate = [p for p in sd.transect_props
                     if p.get("rate_m_yr") is not None and p.get("bank_lon") is not None]
        if with_rate:
            x, y = sd.to_utm.transform([p["bank_lon"] for p in with_rate], [p["bank_lat"] for p in with_rate])
            sd.rate_tree = cKDTree(np.column_stack([x, y]))
            sd.rate_props = with_rate

    blds = _features(sd, "buildings")
    if blds:
        pts = [sd.project(shape(f["geometry"]).centroid) for f in blds]
        sd.building_tree = STRtree(pts)
        dist = sd.rasters.get("distance")
        xs = np.array([p.x for p in pts])
        ys = np.array([p.y for p in pts])
        sd.building_dist = dist.sample(xs, ys) if dist else np.full(len(pts), np.nan)


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sites: dict[str, SiteData] = {}
        for sid in settings.sites:
            sd = load_site_data(sid, settings.data_dir)
            if sd is not None:
                self.sites[sid] = sd
        self.loaded_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")

    def get(self, site_id: str) -> SiteData | None:
        return self.sites.get(site_id)

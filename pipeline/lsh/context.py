"""Context layers (SPEC §7.9): OSM buildings/roads/facilities, WorldPop population, geoBoundaries unions.

Raw downloads are cached under data/raw/<site>/context/ and reused on reruns.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import requests
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig
from pipeline.lsh.grid import site_grid

log = logging.getLogger("lsh.context")

USER_AGENT = "last-safe-home-pipeline/0.1 (+https://github.com/AriyaArKa/nasa)"
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
WORLDPOP_URLS = [  # newest first
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/BGD/v1/100m/constrained/"
    "bgd_pop_2025_CN_100m_R2025A_v1.tif",
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/BGD/bgd_ppp_2020_constrained.tif",
]
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/BGD/{level}/"
FACILITIES = ("school", "hospital", "place_of_worship")


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=kw.pop("timeout", 300), **kw)
    r.raise_for_status()
    return r


def _overpass(query: str) -> dict:
    last: Exception | None = None
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                r = requests.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=600)
                if r.status_code in (429, 504):
                    raise requests.HTTPError(f"{r.status_code} from {url}")
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as e:
                last = e
                log.warning("overpass %s attempt %d failed: %s", url, attempt + 1, e)
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Overpass failed on every mirror: {last}")


def _cached_json(path: Path, fetch) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def osm(site: SiteConfig, raw: Path) -> dict:
    """Buildings (as centre points) + schools/hospitals/places of worship, and roads, clipped to the AOI."""
    w, s, e, n = site.bounds
    bbox = f"{s},{w},{n},{e}"
    fac = "|".join(FACILITIES)
    q_b = (
        f'[out:json][timeout:600];(way["building"]({bbox});node["building"]({bbox});'
        f'relation["building"]({bbox});nwr["amenity"~"^({fac})$"]({bbox}););out center tags;'
    )
    q_r = f'[out:json][timeout:600];way["highway"]({bbox});out geom tags;'
    b = _cached_json(raw / "overpass_buildings.json", lambda: _overpass(q_b))
    r = _cached_json(raw / "overpass_roads.json", lambda: _overpass(q_r))
    aoi = site.aoi

    feats, seen = [], set()
    for el in b.get("elements", []):
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        if lon is None or lat is None:
            continue
        p = Point(lon, lat)
        key = (el["type"], el["id"])
        if key in seen or not aoi.contains(p):
            continue
        seen.add(key)
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        kind = amenity if amenity in FACILITIES else "building"
        feats.append(io.feature(p, {"id": len(feats) + 1, "osm": f"{el['type'][0]}{el['id']}", "kind": kind}))

    roads = []
    for el in r.get("elements", []):
        coords = [(g["lon"], g["lat"]) for g in el.get("geometry", [])]
        if len(coords) < 2:
            continue
        line = LineString(coords).intersection(aoi)
        if line.is_empty:
            continue
        roads.append(io.feature(line, {"osm": f"w{el['id']}", "highway": el.get("tags", {}).get("highway")}))
    kinds: dict[str, int] = {}
    for f in feats:
        kinds[f["properties"]["kind"]] = kinds.get(f["properties"]["kind"], 0) + 1
    return {"buildings": feats, "roads": roads, "counts": kinds, "roads_n": len(roads)}


def worldpop_window(site: SiteConfig, raw: Path) -> tuple[Path, str]:
    """Clip the national WorldPop raster to the AOI (+ 1 km); cache the clip as worldpop.tif."""
    import rasterio
    from rasterio.windows import from_bounds

    out = raw / "worldpop.tif"
    if out.exists():
        with rasterio.open(out) as src:
            return out, src.tags().get("lsh_source", "cached")
    w, s, e, n = site.bounds
    pad = 0.01
    last: Exception | None = None
    for url in WORLDPOP_URLS:
        try:
            local = raw / url.rsplit("/", 1)[-1]
            if (
                not local.exists()
            ):  # the server refuses range reads, so fetch the national file (~15–60 MB) once
                local.parent.mkdir(parents=True, exist_ok=True)
                tmp = local.with_suffix(".part")
                with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=900) as r:
                    r.raise_for_status()
                    with tmp.open("wb") as fh:
                        for chunk in r.iter_content(2**20):
                            fh.write(chunk)
                tmp.replace(local)
            with rasterio.open(local) as src:
                win = (
                    from_bounds(w - pad, s - pad, e + pad, n + pad, src.transform)
                    .round_offsets()
                    .round_lengths()
                )
                data = src.read(1, window=win)
                prof = src.profile.copy()
                prof.update(
                    width=data.shape[1],
                    height=data.shape[0],
                    transform=src.window_transform(win),
                    driver="GTiff",
                    compress="deflate",
                    tiled=False,
                )
                prof.pop("blockxsize", None)
                prof.pop("blockysize", None)
            out.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(out, "w", **prof) as dst:
                dst.write(data, 1)
                dst.update_tags(lsh_source=url)
            return out, url
        except Exception as e:  # noqa: BLE001 - try the next source
            last = e
            log.warning("WorldPop %s failed: %s", url, e)
    raise RuntimeError(
        f"WorldPop download failed ({last}). Get a Bangladesh 100 m population GeoTIFF from worldpop.org "
        f"and save it as {out}"
    )


def population(site: SiteConfig, raw: Path, out_dir: Path, res: float) -> dict:
    """People per analysis-grid pixel, resampled with `sum` so totals are preserved (SPEC §7.9 step 2)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    src_path, source = worldpop_window(site, raw)
    grid = site_grid(site, res)
    with rasterio.open(src_path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            arr[arr == nodata] = 0
        arr[~np.isfinite(arr) | (arr < 0)] = 0
        # source total inside the AOI, for the check below
        from rasterio.features import geometry_mask

        inside = ~geometry_mask([mapping(site.aoi)], arr.shape, src.transform)
        src_total = float(arr[inside].sum())
        dst = np.zeros(grid.shape, dtype="float64")
        reproject(
            arr,
            dst,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=None,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            resampling=Resampling.sum,
        )
    dst[~grid.aoi] = np.nan
    dst_total = float(np.nansum(dst))
    path = io.cog_path(out_dir, site.id, "population", "static")
    io.write_cog(path, dst.astype("float32"), grid.transform, grid.crs)
    return {
        "source": source,
        "people_aoi_source": round(src_total),
        "people_aoi_grid": round(dst_total),
        "sum_ratio": round(dst_total / src_total, 3) if src_total else None,
    }


def unions(site: SiteConfig, raw: Path) -> dict:
    """geoBoundaries ADM4 (unions), falling back to ADM3 (upazilas), clipped to the AOI."""
    aoi = site.aoi
    for level in ("ADM4", "ADM3"):
        cache = raw / f"geoboundaries_{level}.geojson"
        try:
            if not cache.exists():
                meta = _get(GEOBOUNDARIES_API.format(level=level), timeout=60).json()
                url = meta.get("simplifiedGeometryGeoJSON") or meta["gjDownloadURL"]
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(_get(url, timeout=900).content)
            fc = json.loads(cache.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 - fall back to the next level
            log.warning("geoBoundaries %s failed: %s", level, e)
            continue
        feats = []
        for f in fc.get("features", []):
            g = shape(f["geometry"])
            if not g.is_valid:
                g = g.buffer(0)
            clip = g.intersection(aoi)
            if clip.is_empty or clip.area < 1e-4 * aoi.area:  # drop slivers
                continue
            p = f.get("properties", {})
            name = p.get("shapeName") or p.get("NAME") or ""
            feats.append(
                io.feature(
                    clip,
                    {
                        "id": p.get("shapeID") or f"{level}-{len(feats)}",
                        "name_en": name,
                        "name_bn": name,  # geoBoundaries has no Bangla names; see docs/DECISIONS.md
                        "level": level,
                        "clipped": not clip.equals(g),
                    },
                )
            )
        if feats:
            return {
                "level": level,
                "features": feats,
                "count": len(feats),
                "union_cover_frac": round(
                    unary_union([shape(f["geometry"]) for f in feats]).area / aoi.area, 3
                ),
            }
    raise RuntimeError("no admin boundaries overlap the AOI (geoBoundaries ADM4 and ADM3)")


def run(site: SiteConfig, out_dir: Path, raw_dir: Path, force: bool = False) -> dict:
    raw = raw_dir / "context"
    if force:
        for p in raw.glob("*"):
            p.unlink()
    summary: dict = {}
    o = osm(site, raw)
    io.write_geojson(io.vector_path(out_dir, site.id, "buildings"), o["buildings"])
    io.write_geojson(io.vector_path(out_dir, site.id, "roads"), o["roads"])
    summary["osm"] = {"by_kind": o["counts"], "roads": o["roads_n"]}
    summary["population"] = population(site, raw, out_dir, site.analysis.grid_res_m)
    u = unions(site, raw)
    io.write_geojson(io.vector_path(out_dir, site.id, "unions"), u["features"])
    summary["unions"] = {
        "level": u["level"],
        "count": u["count"],
        "cover_frac": u["union_cover_frac"],
        "names": [f["properties"]["name_en"] for f in u["features"]],
    }
    return summary

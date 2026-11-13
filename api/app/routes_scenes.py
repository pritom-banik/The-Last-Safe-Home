"""NISAR scene search for any polygon (SPEC §9).

`asf_search` runs server-side (search needs no login). Only provisional (`PR`) products (SPEC §16).
Results: newest first, at most 100, cached for one hour per (geometry, products, start, end).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import threading
import time
from urllib.parse import quote

import shapely
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from shapely.geometry import shape

from api.app.errors import APIError
from api.app.schemas import Scene
from pipeline.lsh.nisar import granule_from_result

log = logging.getLogger("lsh.api.scenes")
router = APIRouter()

MAX_RESULTS = 100
CACHE_TTL_S = 3600
CACHE_MAX = 256
PRODUCTS = ("GCOV", "GUNW")
PRODUCTION_CONFIGURATION = "PR"
DEFAULT_START = "2026-06-17"
VERTEX = "https://search.asf.alaska.edu/#/?dataset=NISAR&searchType=List%20Search&searchList="

_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()


class SceneQuery(BaseModel):
    geometry: dict
    products: list[str] = Field(default_factory=lambda: list(PRODUCTS))
    start: str | None = DEFAULT_START
    end: str | None = None


def _date(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError as e:
        raise APIError(422, "invalid_request", f"{name}: not an ISO date") from e


def _polygon(geom: dict):
    g = geom.get("geometry") if geom.get("type") == "Feature" else geom
    try:
        poly = shape(g)
    except Exception as e:  # noqa: BLE001 - any parse failure is the client's geometry
        raise APIError(422, "invalid_geometry", "geometry is not valid GeoJSON") from e
    if poly.geom_type not in ("Polygon", "MultiPolygon"):
        raise APIError(422, "invalid_geometry", "geometry must be a Polygon")
    if not poly.is_valid:
        poly = shapely.make_valid(poly)
    minx, miny, maxx, maxy = poly.bounds
    if poly.is_empty or minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise APIError(422, "invalid_geometry", "geometry must be a polygon in longitude/latitude")
    # ASF limits the WKT size (a simplified outline is plenty for a footprint test) and wants CCW rings
    poly = shapely.set_precision(poly.simplify(1e-4), 1e-5)
    return shapely.orient_polygons(poly) if hasattr(shapely, "orient_polygons") else _orient(poly)


def _orient(poly):
    from shapely.geometry import MultiPolygon
    from shapely.geometry.polygon import orient

    if poly.geom_type == "MultiPolygon":
        return MultiPolygon([orient(p) for p in poly.geoms])
    return orient(poly)


def search_asf(wkt: str, products: list[str], start: str | None, end: str | None) -> tuple[list[dict], bool]:
    """Query ASF, one call per product level → (rows, complete). CMR sometimes returns short pages;
    asf_search then marks the result incomplete and we do not cache it."""
    import asf_search as asf

    rows: list[dict] = []
    complete = True
    for level in products:
        results = asf.search(
            dataset=["NISAR"],
            processingLevel=[level],
            productionConfiguration=[PRODUCTION_CONFIGURATION],
            intersectsWith=wkt,
            start=start,
            end=end,
            maxResults=MAX_RESULTS,
        )
        complete &= bool(getattr(results, "searchComplete", True))
        for r in results:
            g = granule_from_result(r, shapely.from_wkt(wkt))
            rows.append(
                {
                    "granule": g.granule,
                    "product": g.product or level,
                    "datetime": g.datetime_utc,
                    "direction": g.direction,
                    "track": g.track,
                    "url_asf": VERTEX + quote(g.granule),
                    "size_mb": g.size_mb,
                }
            )
    return rows, complete


@router.post("/scenes", response_model=list[Scene])
def scenes(body: SceneQuery = Body(...)):  # noqa: B008
    products = sorted({p.upper() for p in body.products})
    if not products or any(p not in PRODUCTS for p in products):
        raise APIError(422, "invalid_request", f"products must be a subset of {list(PRODUCTS)}")
    start, end = _date(body.start, "start"), _date(body.end, "end")
    poly = _polygon(body.geometry)
    wkt = poly.wkt
    key = hashlib.sha256(json.dumps([wkt, products, start, end]).encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_S:
            return hit[1]
    try:
        rows, complete = search_asf(wkt, products, start, end)
    except Exception as e:  # noqa: BLE001 - ASF down / network: answer in the standard error shape
        log.warning("ASF search failed: %s", e)
        raise APIError(502, "search_failed", "the ASF scene search did not answer; try again later") from e
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["datetime"], reverse=True):
        if r["granule"] in seen:
            continue
        seen.add(r["granule"])
        out.append(r)
        if len(out) == MAX_RESULTS:
            break
    if not complete:
        log.warning("ASF search incomplete for %s; not cached", key[:12])
        return out
    with _lock:
        if len(_cache) >= CACHE_MAX:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[key] = (now, out)
    return out

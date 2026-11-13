"""Statistics for a user-drawn polygon (SPEC §9)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Body, Request
from shapely.geometry import shape
from shapely.validation import make_valid

from api.app.errors import APIError, get_site
from api.app.schemas import PolygonStats
from pipeline.lsh import score

router = APIRouter()

MAX_AREA_KM2 = 200.0


def parse_polygon(body) -> object:
    """GeoJSON Feature or (Multi)Polygon in EPSG:4326 -> shapely geometry."""
    if not isinstance(body, dict):
        raise APIError(422, "invalid_geometry", "body must be a GeoJSON Feature or Polygon")
    geom = body.get("geometry") if body.get("type") == "Feature" else body
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise APIError(422, "invalid_geometry", "geometry must be a Polygon or MultiPolygon")
    try:
        g = shape(geom)
    except Exception as e:  # shapely raises several types for malformed coordinates
        raise APIError(422, "invalid_geometry", f"could not read polygon: {e}") from e
    if g.is_empty:
        raise APIError(422, "invalid_geometry", "polygon is empty")
    w, s, e, n = g.bounds
    if not (-180 <= w <= e <= 180 and -90 <= s <= n <= 90):
        raise APIError(422, "invalid_geometry", "coordinates must be lon/lat (EPSG:4326)")
    if not g.is_valid:
        g = make_valid(g)
    return g


def polygon_stats(sd, geom) -> dict:
    geom_utm = sd.project(geom)
    area = geom_utm.area / 1e6
    if area > MAX_AREA_KM2:
        raise APIError(422, "too_large", f"polygon is {area:.0f} km²; the limit is {MAX_AREA_KM2:.0f} km²")
    clipped = geom.intersection(sd.cfg.aoi)
    if clipped.is_empty or clipped.area == 0:
        return {"in_aoi": False, "synthetic": sd.synthetic}
    clip_utm = sd.project(clipped)

    out: dict = {"in_aoi": True, "synthetic": sd.synthetic, "area_km2": round(clip_utm.area / 1e6, 3)}

    sc = sd.rasters.get("score")
    dist = sd.rasters.get("distance")
    pop = sd.rasters.get("population")
    if dist is not None:
        m = dist.mask(clip_utm)
        out["land_area_km2"] = round(float(np.isfinite(dist.data[m]).sum() * dist.pixel_km2), 3)
    if sc is not None:
        m = sc.mask(clip_utm)
        vals = sc.data[m]
        vals = vals[np.isfinite(vals)]
        out["mean_score"] = int(score.round_half_up(vals.mean())) if vals.size else None
        if pop is not None:
            xs, ys = sc.centres(m)
            people = np.nan_to_num(pop.sample(xs, ys))
            cls = score.class_index(sc.data[m])
            out["people_by_class"] = {k: int(round(people[cls == i].sum()))
                                      for i, k in enumerate(score.CLASS_KEYS)}

    out["area_lost_km2_per_yr"] = _area_loss_rate(sd, clip_utm)

    if sd.transect_tree is not None:
        idx = sd.transect_tree.query(clip_utm, predicate="intersects")
        rates = [sd.transect_props[i]["rate_m_yr"] for i in idx]
        rates = [r for r in rates if r is not None and r > 0]
        out["transects"] = int(len(idx))
        out["max_retreat_m_yr"] = round(max(rates), 1) if rates else None
    if sd.building_tree is not None:
        idx = sd.building_tree.query(clip_utm, predicate="intersects")
        bd = sd.building_dist[idx]
        out["buildings_total"] = int(len(idx))
        out["buildings_within_100m"] = int((bd <= 100).sum())
        out["buildings_within_500m"] = int((bd <= 500).sum())
    return out


def _area_loss_rate(sd, clip_utm) -> float | None:
    """km²/yr of land lost inside the polygon (positive = losing): OLS of Landsat land area vs time."""
    if len(sd.landwater) < 2:
        return None
    times = sd.landsat_times
    t, area = [], []
    for year, r in sorted(sd.landwater.items()):
        m = r.mask(clip_utm)
        t.append(times[year])
        area.append(float((r.data[m] == 0).sum() * r.pixel_km2))
    return round(float(-np.polyfit(t, area, 1)[0]), 4)


@router.post("/sites/{site}/polygon-stats", response_model=PolygonStats)
def polygon_stats_route(request: Request, site: str, body: dict = Body(...)):  # noqa: B008
    sd = get_site(request, site)
    return polygon_stats(sd, parse_polygon(body))

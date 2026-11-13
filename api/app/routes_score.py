"""Point query: Home Risk Score for one clicked location (SPEC §9).

Uses the same `pipeline.lsh.score.compute` as the score raster, with the same inputs: distance to today's
bank, rate of the transect whose crossing with today's bank is nearest, flood frequency and motion.
"""

from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, Query, Request
from shapely.geometry import Point

from api.app.errors import APIError, get_site
from api.app.schemas import PointResponse
from pipeline.lsh import score

router = APIRouter()


def _r(x, nd: int = 1):
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def point_query(sd, lon: float, lat: float) -> dict:
    if not sd.cfg.aoi.contains(Point(lon, lat)):
        raise APIError(404, "outside_aoi", "No data here: this point is outside the study area.")
    x, y = sd.to_utm.transform(lon, lat)
    if sd.water_today is not None and np.isnan(sd.water_today.sample(x, y)):
        raise APIError(404, "outside_aoi", "No data here: this point is outside the study area.")

    stats = sd.stats
    weights = sd.params.effective_weights
    base = {
        "site": sd.id, "in_aoi": True,
        "weights": {k: round(v, 3) for k, v in weights.items()},
        "data": {
            "nisar_passes": stats.get("nisar_passes", len(sd.layers.get("nisar_dates", []))),
            "last_pass": (sd.layers.get("nisar_dates") or [None])[-1],
            "bank_date": sd.layers.get("bank_date"),
            "synthetic": sd.synthetic,
        },
    }

    def sample(name):
        r = sd.rasters.get(name)
        return float(r.sample(x, y)) if r is not None else float("nan")

    d = sample("distance")
    f = sample("floodfreq")
    m = sample("motion")
    if not sd.params.motion_usable:
        motion_status = "not_usable"
    elif math.isnan(m):
        motion_status = "masked"
    else:
        motion_status = "ok"

    if math.isnan(d):  # inside the study area but no land distance -> today's river
        return base | {
            "in_river": True, "score": None, "class": None, "years_until_river": None,
            "distance_to_bank_m": None, "retreat_rate_m_yr": None, "retreat_sigma_m_yr": None,
            "transect_id": None, "flood_frequency": _r(f, 2), "motion_mm": None,
            "motion_status": motion_status, "components": None,
        }

    tr = None
    if sd.rate_tree is not None:
        _, i = sd.rate_tree.query([x, y])
        tr = sd.rate_props[int(i)]
    rate = tr["rate_m_yr"] if tr else float("nan")
    sigma = tr["sigma_m_yr"] if tr else float("nan")

    res = score.compute(d, rate, sigma, f, m, sd.params)
    s = float(res["score"])
    t, t_lo, t_hi = (float(res[k]) for k in ("years", "years_low", "years_high"))
    return base | {
        "in_river": False,
        "score": int(s),
        "class": score.score_class(s),
        "years_until_river": {
            "central": _r(t), "low": _r(t_lo), "high": _r(t_hi),
            "over_50": not (math.isfinite(t) and t <= 50),
        },
        "distance_to_bank_m": int(round(d)),
        "retreat_rate_m_yr": _r(rate),
        "retreat_sigma_m_yr": _r(sigma),
        "transect_id": tr["id"] if tr else None,
        "flood_frequency": _r(f, 2),
        "motion_mm": _r(m) if motion_status == "ok" else None,
        "motion_status": motion_status,
        "components": {k: round(float(res[k]), 3) for k in ("H_E", "H_F", "H_G")},
    }


@router.get("/sites/{site}/point", response_model=PointResponse, response_model_by_alias=True)
def point(request: Request, site: str, lon: float = Query(..., ge=-180, le=180),
          lat: float = Query(..., ge=-90, le=90)):
    return point_query(get_site(request, site), lon, lat)

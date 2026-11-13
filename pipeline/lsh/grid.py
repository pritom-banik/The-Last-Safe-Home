"""Site grids: the AOI in the site UTM CRS, snapped to the resolution, so all dates share one grid."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig


@dataclass(frozen=True)
class SiteGrid:
    transform: object
    shape: tuple[int, int]  # (rows, cols)
    res: float
    epsg: int
    aoi: np.ndarray  # bool: pixel centre inside the AOI polygon

    @property
    def crs(self) -> str:
        return f"EPSG:{self.epsg}"

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        t = self.transform
        return t.c, t.f + self.shape[0] * t.e, t.c + self.shape[1] * t.a, t.f


def site_grid(site: SiteConfig, res: float) -> SiteGrid:
    aoi_utm = io.from_wgs84(site.aoi, site.utm_epsg)
    minx, miny, maxx, maxy = aoi_utm.bounds
    x0, y1 = math.floor(minx / res) * res, math.ceil(maxy / res) * res
    x1, y0 = math.ceil(maxx / res) * res, math.floor(miny / res) * res
    w, h = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    transform = from_origin(x0, y1, res, res)
    aoi = rasterize([aoi_utm], out_shape=(h, w), transform=transform, fill=0, default_value=1).astype(bool)
    return SiteGrid(transform, (h, w), float(res), site.utm_epsg, aoi)

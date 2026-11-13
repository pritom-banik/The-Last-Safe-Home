"""PNG map tiles rendered from the local COGs with rio-tiler (SPEC §9).

The client never sends a file path: (site, layer, date) is mapped to a file listed in layers.json, and
anything else is a 404 (no path traversal / SSRF). Tiles outside the raster return 204.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader

from api.app.errors import APIError, get_site
from pipeline.lsh import score

router = APIRouter()

CACHE = {"Cache-Control": "public, max-age=86400"}
CATEGORICAL = {"water", "floodveg", "custom-score"}


def _hex(c: str, alpha: int) -> tuple[int, int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), alpha


CUSTOM_COLORMAPS = {
    "water": {0: (0, 0, 0, 0), 1: _hex("#2b8cbe", 180)},
    "floodveg": {0: (0, 0, 0, 0), 1: _hex("#31a354", 180)},
    # interval colormap applied to the raw 0–100 score: [low, high) -> colour
    "custom-score": [
        ((lo, hi), _hex(colour, 200))
        for (_, lo, colour), hi in zip(score.CLASSES, [c[1] for c in score.CLASSES[1:]] + [101], strict=True)
    ],
}


def render_tile(path, entry: dict, x: int, y: int, z: int) -> bytes | None:
    name = entry.get("colormap", "gray")
    categorical = name in CATEGORICAL
    with Reader(str(path)) as src:
        try:
            img = src.tile(x, y, z, resampling_method="nearest" if categorical else "bilinear")
        except TileOutsideBounds:
            return None
    if name in CUSTOM_COLORMAPS:
        colormap = CUSTOM_COLORMAPS[name]
        if name != "custom-score":
            img.array = img.array.astype("uint8")
    else:
        lo, hi = entry.get("rescale", [0, 255])
        img = img.rescale(in_range=((lo, hi),))
        colormap = cmap.get(name)
    return img.render(img_format="PNG", colormap=colormap)


@router.get("/tiles/{site}/{layer}/{z}/{x}/{y}.png")
def tile(request: Request, site: str, layer: str, z: int, x: int, y: int,
         date: str | None = Query(None, max_length=10), year: str | None = Query(None, max_length=4)):
    sd = get_site(request, site)
    entry = sd.layers.get("rasters", {}).get(layer)
    if entry is None:
        raise APIError(404, "unknown_layer", f"no raster layer '{layer}' for site '{site}'")
    if not (0 <= z <= 24 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise APIError(404, "bad_tile", "tile index out of range")
    key = None
    if "pattern" in entry:
        key = date or year or sd.default_key(layer)
    path = sd.raster_path(layer, key)
    if path is None:
        raise APIError(404, "unknown_date", f"layer '{layer}' has no data for '{key}'")
    png = render_tile(path, entry, x, y, z)
    if png is None:
        return Response(status_code=204, headers=CACHE)
    return Response(png, media_type="image/png", headers=CACHE)

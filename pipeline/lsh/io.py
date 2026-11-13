"""File naming (SPEC §5) and COG / GeoJSON read-write helpers."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

Key = dt.date | int | str | None  # date, year, "static", or None (vectors)

_NAME_RE = re.compile(
    r"^(?P<site>[a-z0-9-]+)_(?P<product>[a-z0-9-]+)(?:_(?P<key>\d{8}|\d{4}|static))?\.(?P<ext>tif|geojson)$"
)


def _check_token(value: str, what: str) -> None:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError(f"{what} '{value}' must be lowercase letters, digits or '-'")


def to_date(value: dt.date | str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value)
    return dt.date.fromisoformat(s if "-" in s else f"{s[:4]}-{s[4:6]}-{s[6:8]}")


def format_key(key: Key) -> str | None:
    if key is None:
        return None
    if isinstance(key, dt.date):
        return key.strftime("%Y%m%d")
    if isinstance(key, int):
        if not 1900 <= key <= 2100:
            raise ValueError(f"year out of range: {key}")
        return f"{key:04d}"
    if key == "static":
        return "static"
    if isinstance(key, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{8}", key):
        return to_date(key).strftime("%Y%m%d")
    raise ValueError(f"bad file key {key!r}: use a date, a year, or 'static'")


def build_name(site: str, product: str, key: Key = None, ext: str | None = None) -> str:
    """`<site>_<product>_<YYYYMMDD | YYYY | static>.<ext>`; vectors have no key."""
    _check_token(site, "site id")
    _check_token(product, "product")
    k = format_key(key)
    ext = ext or ("geojson" if k is None else "tif")
    return f"{site}_{product}.{ext}" if k is None else f"{site}_{product}_{k}.{ext}"


def parse_name(name: str) -> dict[str, Any]:
    """Inverse of build_name: {site, product, key, ext}; key is a date, int year, 'static' or None."""
    m = _NAME_RE.match(Path(name).name)
    if not m:
        raise ValueError(f"not a product file name: {name}")
    raw = m["key"]
    key: Key
    if raw is None or raw == "static":
        key = raw
    elif len(raw) == 8:
        key = to_date(raw)
    else:
        key = int(raw)
    return {"site": m["site"], "product": m["product"], "key": key, "ext": m["ext"]}


def cog_path(site_dir: Path, site: str, product: str, key: Key) -> Path:
    return Path(site_dir) / "cog" / build_name(site, product, key, "tif")


def vector_path(site_dir: Path, site: str, product: str) -> Path:
    return Path(site_dir) / "vector" / build_name(site, product, None, "geojson")


def list_keys(site_dir: Path, site: str, product: str) -> list:
    """Sorted keys of every existing COG of one product (e.g. all water_<date> dates)."""
    keys = []
    for p in (Path(site_dir) / "cog").glob(f"{site}_{product}_*.tif"):
        try:
            info = parse_name(p.name)
        except ValueError:
            continue
        if info["site"] == site and info["product"] == product:
            keys.append(info["key"])
    return sorted(keys)


# --------------------------------------------------------------------------- rasters


def write_cog(path: Path, array: np.ndarray, transform, crs, *, mask: bool = False) -> Path:
    """Write one band as a Cloud-Optimized GeoTIFF.

    Floats are stored as float32 with nodata NaN (average overviews); `mask=True` stores uint8 with
    nodata 255 (nearest overviews), per SPEC §5.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mask:
        data = np.asarray(array).astype("uint8")
        dtype, nodata, resampling = "uint8", 255, "nearest"
    else:
        data = np.asarray(array, dtype="float32")
        dtype, nodata, resampling = "float32", float("nan"), "average"
    height, width = data.shape
    profile = dict(
        driver="COG", width=width, height=height, count=1, dtype=dtype, crs=crs, transform=transform,
        nodata=nodata, compress="DEFLATE", blocksize=256, overview_resampling=resampling,
    )
    tmp = path.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **profile) as dst:
        dst.write(data, 1)
    tmp.replace(path)  # never leave a half-written COG under the final name
    return path


def read_raster(path: Path) -> tuple[np.ndarray, dict]:
    """Band 1 as float64 with nodata -> NaN (masks keep 255 -> NaN too), and the profile."""
    with rasterio.open(path) as src:
        a = src.read(1).astype("float64")
        nd = src.nodata
        if nd is not None and not np.isnan(nd):
            a[a == nd] = np.nan
        return a, src.profile


def read_mask(path: Path) -> tuple[np.ndarray, dict]:
    """A uint8 mask as stored (255 = nodata kept as 255), and the profile."""
    with rasterio.open(path) as src:
        return src.read(1), src.profile


# --------------------------------------------------------------------------- vectors


def to_wgs84(geom: BaseGeometry, epsg: int) -> BaseGeometry:
    tr = Transformer.from_crs(epsg, 4326, always_xy=True)
    return shapely.transform(geom, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))


def from_wgs84(geom: BaseGeometry, epsg: int) -> BaseGeometry:
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    return shapely.transform(geom, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))


def feature(geom: BaseGeometry, props: dict[str, Any], precision: int = 6) -> dict:
    g = shapely.set_precision(geom, 10**-precision) if precision is not None else geom
    return {"type": "Feature", "properties": props, "geometry": mapping(g)}


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    raise TypeError(f"not JSON serialisable: {type(o)}")


def clean_json(value):
    """Replace NaN/inf with None recursively (JSON has no NaN)."""
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, obj: Any, indent: int | None = 2) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean_json(obj), indent=indent, ensure_ascii=False, default=_json_default)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_geojson(path: Path, features: list[dict]) -> Path:
    return write_json(path, {"type": "FeatureCollection", "features": features}, indent=None)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))

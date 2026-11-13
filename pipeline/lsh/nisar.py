"""NISAR search, track selection, download / AOI subsetting, and HDF5 readers (SPEC §7.1, §7.2).

Two ways to get a granule onto disk:
- **subset** (default): read only the AOI window of the needed GCOV layers over HTTP range requests and
  save it as a small HDF5 file with the *same group layout* as the product (`<granule>_aoi.h5`).
  A 6 GB frame becomes tens of MB.
- **full**: download the whole `.h5` with `asf_search` (SPEC §7.1 step 6), gated at 20 GB.
Both give files that `read_gcov` opens the same way.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import re
import shutil
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape

from pipeline.lsh.config import Settings, SiteConfig

log = logging.getLogger("lsh.nisar")

GCOV_GRID = "/science/LSAR/GCOV/grids/frequencyA"
GUNW_IFG = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"
QA_PATTERN = r"^(?!.*QA_STATS).*"
MIN_AOI_COVER = 0.9  # a granule must cover ≥ 90% of the AOI to be used
MIN_PASSES = 6  # SPEC §14 phase 5: ask the user when more than one track has this many
DOWNLOAD_LIMIT_GB = 20  # SPEC §16


# --------------------------------------------------------------------------- inventory


@dataclass
class Granule:
    granule: str
    product: str
    datetime_utc: str
    track: str
    frame: str
    direction: str
    polarizations: str
    url: str
    size_mb: float | None
    # additions to the SPEC §7.1 columns (docs/DECISIONS.md)
    full_frame: str = ""
    aoi_cover: float | None = None
    selected: str = ""

    @property
    def date(self) -> str:
        return self.datetime_utc[:10]

    @property
    def pols(self) -> set[str]:
        return {p for p in self.polarizations.split("+") if p}

    @property
    def has_hh(self) -> bool:
        return "HH" in self.pols


COLUMNS = [f.name for f in fields(Granule)]
POL_ORDER = ["HH", "HV", "VH", "VV"]


def _attrs(result: Any) -> dict[str, list[str]]:
    umm = getattr(result, "umm", None) or {}
    return {a.get("Name"): a.get("Values") or [] for a in umm.get("AdditionalAttributes", [])}


def _first(values: list[str] | None) -> str:
    return str(values[0]) if values else ""


def granule_from_result(result: Any, aoi) -> Granule:
    """Inventory row from an asf_search result; blank where a property is absent (SPEC §7.1 step 4)."""
    p = result.properties
    a = _attrs(result)
    urls = result.find_urls(extension=".h5", pattern=QA_PATTERN, directAccess=False) or [p.get("url", "")]
    url = urls[0]
    name = url.rsplit("/", 1)[-1]
    size = (p.get("bytes") or {}).get(name, {}).get("bytes")
    pols = a.get("FREQUENCY_A_POLARIZATION") or []
    cover = None
    geom = getattr(result, "geometry", None)
    if geom:
        try:
            cover = round(shape(geom).intersection(aoi).area / aoi.area, 3)
        except Exception:  # noqa: BLE001 - bad footprint: leave blank
            cover = None
    return Granule(
        granule=p.get("sceneName") or p.get("fileID") or name.removesuffix(".h5"),
        product=p.get("processingLevel") or _first(a.get("PRODUCT_TYPE")),
        datetime_utc=p.get("startTime") or "",
        track=_first(a.get("TRACK_NUMBER")) or str(p.get("pathNumber") or ""),
        frame=_first(a.get("FRAME_NUMBER")) or str(p.get("frameNumber") or ""),
        direction=(p.get("flightDirection") or _first(a.get("ASCENDING_DESCENDING"))).upper(),
        polarizations="+".join(sorted(pols, key=lambda q: POL_ORDER.index(q) if q in POL_ORDER else 9)),
        url=url,
        size_mb=round(size / 1e6, 1) if size else None,
        full_frame=_first(a.get("FULL_FRAME")),
        aoi_cover=cover,
    )


def search(site: SiteConfig, products: tuple[str, ...] = ("GCOV", "GUNW")) -> list[Granule]:
    """SPEC §7.1 step 2–3. Search needs no login."""
    import asf_search as asf

    rows: list[Granule] = []
    for level in products:
        results = asf.search(
            dataset=["NISAR"],
            processingLevel=[level],
            productionConfiguration=[site.nisar.production_configuration],
            intersectsWith=site.aoi_wkt,
            start=site.nisar.start,
            end=site.nisar.end_or_today,
            maxResults=1000,
        )
        rows += [granule_from_result(r, site.aoi) for r in results]
    rows.sort(key=lambda g: (g.product, g.datetime_utc, g.granule))
    log.info("search: %s", dict(Counter(g.product for g in rows)))
    return rows


def write_inventory(rows: list[Granule], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for g in rows:
            w.writerow({k: ("" if v is None else v) for k, v in asdict(g).items()})


def read_inventory(path: Path) -> list[Granule]:
    with path.open(encoding="utf-8") as f:
        out = []
        for row in csv.DictReader(f):
            row["size_mb"] = float(row["size_mb"]) if row.get("size_mb") else None
            row["aoi_cover"] = float(row["aoi_cover"]) if row.get("aoi_cover") else None
            out.append(Granule(**{k: row.get(k, "") for k in COLUMNS}))
        return out


# --------------------------------------------------------------------------- track selection


def usable_gcov(g: Granule) -> bool:
    """A GCOV granule the water mask can use: HH present and the AOI (nearly) covered."""
    return g.product == "GCOV" and g.has_hh and (g.aoi_cover is None or g.aoi_cover >= MIN_AOI_COVER)


def track_candidates(rows: list[Granule]) -> list[dict]:
    """Per (track, direction): GCOV passes (distinct dates), passes with usable HH, GUNW count. Best first."""
    keys = sorted({(g.track, g.direction) for g in rows if g.product == "GCOV"})
    out = []
    for track, direction in keys:
        mine = [g for g in rows if g.track == track and g.direction == direction]
        gcov = [g for g in mine if g.product == "GCOV"]
        out.append(
            {
                "track": track,
                "direction": direction,
                "frames": sorted({g.frame for g in gcov}),
                "gcov_passes": len({g.date for g in gcov}),
                "hh_passes": len({g.date for g in gcov if usable_gcov(g)}),
                "gunw_hh": sum(1 for g in mine if g.product == "GUNW" and g.has_hh),
                "full_size_gb": round(sum(g.size_mb or 0 for g in pick_per_date(gcov)) / 1000, 1),
            }
        )
    out.sort(key=lambda c: (-c["hh_passes"], -c["gcov_passes"], c["track"]))
    return out


def choose_track(rows: list[Granule], configured: int | None) -> tuple[dict | None, bool, list[dict]]:
    """(chosen candidate, needs_user_choice, all candidates).

    With `track: null` the best candidate is proposed, but if more than one track has ≥ MIN_PASSES passes the
    user must choose (SPEC §14 phase 5) and nothing is downloaded until `nisar.track` is set in the site file.
    """
    cands = track_candidates(rows)
    if configured is not None:
        hit = [c for c in cands if c["track"] == str(configured)]
        if not hit:
            raise ValueError(f"configured NISAR track {configured} has no GCOV granules over the AOI")
        return hit[0], False, cands
    if not cands:
        return None, False, cands
    many = sum(1 for c in cands if c["hh_passes"] >= MIN_PASSES) > 1
    return cands[0], many, cands


def pick_per_date(gcov: list[Granule]) -> list[Granule]:
    """One GCOV granule per date: usable HH first, then best AOI cover, full frame, smaller file."""
    by_date: dict[str, list[Granule]] = {}
    for g in gcov:
        by_date.setdefault(g.date, []).append(g)
    return [
        min(
            gs,
            key=lambda g: (not usable_gcov(g), -(g.aoi_cover or 0), g.full_frame != "TRUE", g.size_mb or 0),
        )
        for _, gs in sorted(by_date.items())
    ]


def pair_key(granule: str) -> str:
    """A GUNW granule name without its trailing product counter (`_001`, `_002` = reprocessings)."""
    return re.sub(r"_\d{3}(_aoi)?(\.h5)?$", "", granule)


def latest_versions(gunw: list[Granule]) -> list[Granule]:
    """One GUNW per date pair: ASF can list a pair twice (product counter 001, 002 …); keep the newest."""
    best: dict[str, Granule] = {}
    for g in sorted(gunw, key=lambda g: g.granule):
        best[pair_key(g.granule)] = g
    return sorted(best.values(), key=lambda g: g.granule)


def select(rows: list[Granule], track: str, direction: str) -> list[Granule]:
    """GCOV (one per date, HH only) and HH GUNW of the chosen track; marks `selected` on the rows."""
    mine = [g for g in rows if g.track == track and g.direction == direction]
    gcov = [g for g in pick_per_date([g for g in mine if g.product == "GCOV"]) if usable_gcov(g)]
    gunw = latest_versions([g for g in mine if g.product == "GUNW" and g.has_hh])
    chosen = {g.granule for g in gcov + gunw}
    for g in rows:
        g.selected = "yes" if g.granule in chosen else ""
    return gcov + gunw


# --------------------------------------------------------------------------- remote reading


class RangeFile:
    """Read-only, seekable file object over HTTP range requests with a small block cache (for h5py)."""

    def __init__(self, url: str, session, block_size: int = 4 * 2**20, max_blocks: int = 64):
        self.url, self.session, self.block, self.max_blocks = url, session, block_size, max_blocks
        self.orig_url = url
        self.pos = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.bytes_fetched = 0
        r = session.get(url, headers={"Range": "bytes=0-0"}, timeout=120, allow_redirects=True)
        r.raise_for_status()
        if r.status_code != 206:
            raise OSError(f"server ignored the Range header for {url}")
        self.url = r.url  # follow the auth/cloud redirect once
        self.size = int(r.headers["Content-Range"].rsplit("/", 1)[1])

    def _get(self, i: int) -> bytes:
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        start = i * self.block
        end = min(start + self.block, self.size) - 1
        r = self.session.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=300)
        if r.status_code in (401, 403):  # signed cloud URL expired: go through the auth redirect again
            r = self.session.get(self.orig_url, headers={"Range": f"bytes={start}-{end}"}, timeout=300)
            self.url = r.url
        r.raise_for_status()
        data = r.content
        self.bytes_fetched += len(data)
        self.cache[i] = data
        if len(self.cache) > self.max_blocks:
            self.cache.popitem(last=False)
        return data

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        out = bytearray()
        while n > 0:
            i, off = divmod(self.pos, self.block)
            chunk = self._get(i)[off : off + n]
            if not chunk:
                break
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def tell(self) -> int:
        return self.pos

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def close(self) -> None:
        self.cache.clear()


def earthdata_session(settings: Settings):
    import asf_search as asf

    if not settings.has_earthdata:
        raise NeedsUserDecision("EARTHDATA_USERNAME / EARTHDATA_PASSWORD are not set (see .env.example)")
    try:
        return asf.ASFSession().auth_with_creds(settings.earthdata_username, settings.earthdata_password)
    except Exception as e:  # noqa: BLE001 - give the user the actionable part
        msg = str(e)
        if "Study%20Area" in msg or "required attributes" in msg:
            raise NeedsUserDecision(
                "Earthdata login works but ASF needs your profile completed: sign in at "
                "https://urs.earthdata.nasa.gov/profile, fill in the required 'Study Area' field, "
                "save, and retry."
            ) from e
        m = re.search(r"resolution_url=(https://urs\.earthdata\.nasa\.gov/approve_app\?client_id=[\w-]+)",
                      msg)
        if m:
            raise NeedsUserDecision(
                "Earthdata needs you to authorize the ASF data application once: open "
                f"{m.group(1)} while signed in, click Authorize, and retry."
            ) from e
        raise


# --------------------------------------------------------------------------- GCOV reading


def _epsg(proj_ds) -> int:
    for key in ("epsg_code", "epsg", "EPSG"):
        if key in proj_ds.attrs:
            return int(np.asarray(proj_ds.attrs[key]).ravel()[0])
    val = np.asarray(proj_ds[()]).ravel()
    if val.size and 1000 < int(val[0]) < 100000:
        return int(val[0])
    raise ValueError("cannot find the EPSG code in the projection dataset")


def grid_group(h5, product: str = "GCOV"):
    path = GCOV_GRID if product == "GCOV" else GUNW_IFG
    if path in h5:
        return h5[path]
    # fall back: first group holding xCoordinates (product layouts may shift; SPEC: trust the file)
    found = []
    h5.visit(lambda n: found.append(n) if n.endswith("xCoordinates") and product in n else None)
    if not found:
        raise KeyError(f"no {product} grid group with xCoordinates found")
    return h5[found[0].rsplit("/", 1)[0]]


def aoi_window(x: np.ndarray, y: np.ndarray, epsg: int, bounds_wgs84, pad_m: float = 300.0):
    """Row/col slices of the coordinate vectors that cover the AOI bounds (+ pad), or None if no overlap."""
    w, s, e, n = bounds_wgs84
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform([w, e, e, w], [s, s, n, n])
    x0, x1 = min(xs) - pad_m, max(xs) + pad_m
    y0, y1 = min(ys) - pad_m, max(ys) + pad_m
    cols = np.nonzero((x >= x0) & (x <= x1))[0]
    rows = np.nonzero((y >= y0) & (y <= y1))[0]
    if not cols.size or not rows.size:
        return None
    return slice(int(rows.min()), int(rows.max()) + 1), slice(int(cols.min()), int(cols.max()) + 1)


GCOV_LAYERS = ("HHHH", "HVHV", "mask", "numberOfLooks")
COPY_SCALARS = ("projection", "xCoordinateSpacing", "yCoordinateSpacing", "listOfPolarizations")


def subset_gcov(src, dst_path: Path, bounds_wgs84, source_url: str = "") -> dict:
    """Copy the AOI window of a GCOV file (h5py File or path) into a small HDF5 with the same layout."""
    import h5py

    own = not isinstance(src, h5py.File)
    f = h5py.File(src, "r") if own else src
    try:
        g = grid_group(f, "GCOV")
        x, y = g["xCoordinates"][()], g["yCoordinates"][()]
        epsg = _epsg(g["projection"])
        win = aoi_window(x, y, epsg, bounds_wgs84)
        if win is None:
            raise ValueError("granule does not overlap the AOI")
        rs, cs = win
        tmp = dst_path.with_suffix(".part")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(tmp, "w") as out:
            og = out.require_group(g.name)
            og["xCoordinates"] = x[cs]
            og["yCoordinates"] = y[rs]
            for name in COPY_SCALARS:
                if name in g:
                    ds = og.create_dataset(name, data=g[name][()])
                    ds.attrs.update(dict(g[name].attrs))
            for name in GCOV_LAYERS:
                if name in g and g[name].ndim == 2:
                    ds = og.create_dataset(
                        name, data=g[name][rs, cs], compression="gzip", shuffle=True, chunks=True
                    )
                    ds.attrs.update(dict(g[name].attrs))
            ident = "/science/LSAR/identification"
            if ident in f:
                oi = out.require_group(ident)
                for k, v in f[ident].items():
                    if isinstance(v, h5py.Dataset) and v.size <= 64:
                        oi[k] = v[()]
            out.attrs["lsh_subset_of"] = source_url
            out.attrs["lsh_window"] = [rs.start, rs.stop, cs.start, cs.stop]
        shutil.move(tmp, dst_path)
        return {
            "rows": rs.stop - rs.start,
            "cols": cs.stop - cs.start,
            "epsg": epsg,
            "layers": [n for n in GCOV_LAYERS if n in g],
        }
    finally:
        if own:
            f.close()


GUNW_LAYERS = ("unwrappedPhase", "coherenceMagnitude", "connectedComponents", "ionospherePhaseScreen")
GUNW_TIMES = ("referenceZeroDopplerStartTime", "secondaryZeroDopplerStartTime")


def subset_gunw(src, dst_path: Path, bounds_wgs84, source_url: str = "") -> dict:
    """AOI window of the unwrapped-interferogram layers (+ the parent `mask`) into a small HDF5."""
    import h5py

    own = not isinstance(src, h5py.File)
    f = h5py.File(src, "r") if own else src
    try:
        g = grid_group(f, "GUNW")
        parent = g.parent
        x, y = g["xCoordinates"][()], g["yCoordinates"][()]
        epsg = _epsg(g["projection"])
        win = aoi_window(x, y, epsg, bounds_wgs84, pad_m=1000.0)
        if win is None:
            raise ValueError("granule does not overlap the AOI")
        rs, cs = win
        tmp = dst_path.with_suffix(".part")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(tmp, "w") as out:
            og = out.require_group(g.name)
            og["xCoordinates"] = x[cs]
            og["yCoordinates"] = y[rs]
            for name in COPY_SCALARS:
                if name in g:
                    ds = og.create_dataset(name, data=g[name][()])
                    ds.attrs.update(dict(g[name].attrs))
            for name in GUNW_LAYERS:
                if name in g:
                    ds = og.create_dataset(name, data=g[name][rs, cs], compression="gzip", shuffle=True)
                    ds.attrs.update({k: v for k, v in g[name].attrs.items() if k != "DIMENSION_LIST"})
            if "mask" in parent:
                ds = out.require_group(parent.name).create_dataset(
                    "mask", data=parent["mask"][rs, cs], compression="gzip", shuffle=True)
                ds.attrs.update({k: v for k, v in parent["mask"].attrs.items() if k != "DIMENSION_LIST"})
            ident = "/science/LSAR/identification"
            oi = out.require_group(ident)
            for k in GUNW_TIMES:
                if f"{ident}/{k}" in f:
                    oi[k] = f[f"{ident}/{k}"][()]
            out.attrs["lsh_subset_of"] = source_url
            out.attrs["lsh_window"] = [rs.start, rs.stop, cs.start, cs.stop]
        shutil.move(tmp, dst_path)
        return {"rows": rs.stop - rs.start, "cols": cs.stop - cs.start, "epsg": epsg,
                "layers": [n for n in GUNW_LAYERS if n in g]}
    finally:
        if own:
            f.close()


@dataclass
class GcovData:
    hh: np.ndarray  # linear power, NaN invalid
    hv: np.ndarray | None
    x: np.ndarray  # pixel-centre coordinates
    y: np.ndarray
    epsg: int
    mask_applied: bool

    @property
    def transform(self):
        from rasterio.transform import from_origin

        dx = float(abs(self.x[1] - self.x[0])) if self.x.size > 1 else 1.0
        dy = float(abs(self.y[1] - self.y[0])) if self.y.size > 1 else 1.0
        return from_origin(float(self.x.min()) - dx / 2, float(self.y.max()) + dy / 2, dx, dy)


def _valid_from_mask(mask: np.ndarray, finite: np.ndarray) -> np.ndarray | None:
    """NISAR GCOV `mask`: 255 = fill, 0 = outside any subswath; other values = valid subswath codes.
    If that reading would discard almost every finite pixel, the encoding differs: ignore it (logged)."""
    valid = (mask != 255) & (mask != 0)
    if finite.sum() and (valid & finite).sum() < 0.01 * finite.sum():
        log.warning("GCOV mask would remove >99%% of finite pixels; ignoring the mask (check its encoding)")
        return None
    return valid


def read_gcov(path: Path, bounds_wgs84=None) -> GcovData:
    """Read HH (and HV) linear γ⁰ for the AOI window (whole grid if bounds is None).

    Rows are returned north → south."""
    import h5py

    with h5py.File(path, "r") as f:
        g = grid_group(f, "GCOV")
        x, y = g["xCoordinates"][()], g["yCoordinates"][()]
        epsg = _epsg(g["projection"])
        win = aoi_window(x, y, epsg, bounds_wgs84) if bounds_wgs84 is not None else (slice(None), slice(None))
        if win is None:
            raise ValueError(f"{path.name} does not overlap the AOI")
        rs, cs = win
        if "HHHH" not in g:
            raise KeyError(f"{path.name} has no HHHH layer")
        hh = g["HHHH"][rs, cs].astype("float32")
        hv = g["HVHV"][rs, cs].astype("float32") if "HVHV" in g else None
        mask = g["mask"][rs, cs] if "mask" in g else None
        x, y = x[cs], y[rs]
    for arr in (hh, hv):
        if arr is not None:
            arr[~np.isfinite(arr) | (arr <= 0)] = np.nan
    applied = False
    if mask is not None:
        valid = _valid_from_mask(mask, np.isfinite(hh))
        if valid is not None:
            hh[~valid] = np.nan
            if hv is not None:
                hv[~valid] = np.nan
            applied = True
    if y.size > 1 and y[0] < y[-1]:  # make rows run north → south
        y, hh = y[::-1], hh[::-1]
        hv = hv[::-1] if hv is not None else None
    if x.size > 1 and x[0] > x[-1]:
        x, hh = x[::-1], hh[:, ::-1]
        hv = hv[:, ::-1] if hv is not None else None
    return GcovData(hh=hh, hv=hv, x=x, y=y, epsg=epsg, mask_applied=applied)


def to_db(linear: np.ndarray) -> np.ndarray:
    """10·log10(x) for x > 0, else NaN (SPEC §7.2 step 2)."""
    out = np.full(linear.shape, np.nan, dtype="float32")
    ok = np.isfinite(linear) & (linear > 0)
    out[ok] = 10.0 * np.log10(linear[ok])
    return out


def date_of(granule: str) -> dt.date:
    """Acquisition start date from a NISAR granule name (first YYYYMMDDTHHMMSS)."""
    m = re.search(r"_(\d{8})T\d{6}_", granule)
    if not m:
        raise ValueError(f"no date in granule name {granule}")
    return dt.datetime.strptime(m.group(1), "%Y%m%d").date()


# --------------------------------------------------------------------------- pipeline steps


class NeedsUserDecision(RuntimeError):
    """A step stopped because SPEC §16 says to ask the user first (track choice, > 20 GB download)."""


def nisar_dir(site: SiteConfig, settings: Settings | None = None) -> Path:
    return site.raw_dir(settings) / "nisar"


def fetch(
    site: SiteConfig,
    settings: Settings,
    *,
    dry_run: bool = False,
    full: bool = False,
    confirm_large: bool = False,
    force: bool = False,
) -> dict:
    """SPEC §7.1. Writes inventory.csv; unless --dry-run, gets the selected GCOV granules.

    AOI subsets by default; `full=True` downloads whole products (gated at 20 GB)."""
    rows = search(site)
    chosen, needs_choice, cands = choose_track(rows, site.nisar.track)
    selected = select(rows, chosen["track"], chosen["direction"]) if chosen else []
    inv = nisar_dir(site, settings) / "inventory.csv"
    write_inventory(rows, inv)
    summary: dict[str, Any] = {
        "inventory": str(inv),
        "granules": dict(Counter(g.product for g in rows)),
        "track_candidates": cands,
        "track": chosen and {"track": chosen["track"], "direction": chosen["direction"]},
        "track_source": "config" if site.nisar.track is not None else "auto",
        "needs_track_choice": needs_choice,
        "selected_gcov_dates": [g.date for g in selected if g.product == "GCOV"],
        "selected_gunw": sum(1 for g in selected if g.product == "GUNW"),
        "dry_run": dry_run,
    }
    log.info("track candidates: %s", cands)
    if dry_run:
        return summary
    if not chosen:
        raise NeedsUserDecision("no NISAR GCOV granules found over the AOI")
    if needs_choice:
        raise NeedsUserDecision(
            f"more than one NISAR track has >= {MIN_PASSES} passes: review {inv} "
            f"and set `nisar.track` in config/sites/{site.id}.yaml"
        )

    gcov = [g for g in selected if g.product == "GCOV"]
    out_dir = nisar_dir(site, settings) / "gcov"
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched = 0
    if full:
        total_gb = sum(g.size_mb or 0 for g in gcov) / 1000
        free_gb = shutil.disk_usage(out_dir).free / 1e9
        log.info("full download: %.1f GB for %d granules (%.0f GB free)", total_gb, len(gcov), free_gb)
        if (total_gb > DOWNLOAD_LIMIT_GB or total_gb > free_gb) and not confirm_large:
            raise NeedsUserDecision(
                f"full download is {total_gb:.1f} GB (limit {DOWNLOAD_LIMIT_GB} GB, {free_gb:.0f} GB free): "
                "rerun with --confirm-large after the user agrees, or drop --full to fetch AOI subsets"
            )
        import asf_search as asf

        session = earthdata_session(settings)
        todo = [g for g in gcov if force or not (out_dir / g.url.rsplit("/", 1)[-1]).exists()]
        asf.download_urls(urls=[g.url for g in todo], path=str(out_dir), session=session, processes=4)
    else:
        import h5py

        todo = [g for g in gcov if force or not (out_dir / f"{g.granule}_aoi.h5").exists()]
        session = earthdata_session(settings) if todo else None
        for g in todo:
            rf = RangeFile(g.url, session)
            with h5py.File(rf, "r") as f:
                info = subset_gcov(f, out_dir / f"{g.granule}_aoi.h5", site.bounds, source_url=g.url)
            fetched += rf.bytes_fetched
            log.info("subset %s: %s, %.0f MB read", g.granule, info, rf.bytes_fetched / 1e6)
    # GUNW (ground movement, phase 6): always AOI subsets of the unwrapped-interferogram layers (80 m)
    import h5py

    gunw = [g for g in selected if g.product == "GUNW"]
    gdir = nisar_dir(site, settings) / "gunw"
    gtodo = [g for g in gunw if force or not (gdir / f"{g.granule}_aoi.h5").exists()]
    if gtodo and session is None:
        session = earthdata_session(settings)
    for g in gtodo:
        rf = RangeFile(g.url, session)
        with h5py.File(rf, "r") as f:
            info = subset_gunw(f, gdir / f"{g.granule}_aoi.h5", site.bounds, source_url=g.url)
        fetched += rf.bytes_fetched
        log.info("subset %s: %s, %.0f MB read", g.granule, info, rf.bytes_fetched / 1e6)
    summary["fetched_gunw"] = len(gtodo)
    summary["existing_gunw"] = len(gunw) - len(gtodo)
    summary.update(
        {
            "mode": "full" if full else "subset",
            "fetched_gcov": len(todo),
            "existing_gcov": len(gcov) - len(todo),
            "bytes_read_mb": round(fetched / 1e6, 1),
        }
    )
    return summary


def gcov_files(site: SiteConfig, settings: Settings | None = None) -> dict[str, Path]:
    """date (ISO) → GCOV file to use; a full product wins over an AOI subset of the same date."""
    out: dict[str, Path] = {}
    for p in sorted((nisar_dir(site, settings) / "gcov").glob("*.h5")):
        if "QA_STATS" in p.name:
            continue
        d = date_of(p.name).isoformat()
        if d not in out or out[d].name.endswith("_aoi.h5"):
            out[d] = p
    return dict(sorted(out.items()))


def process_gcov(
    site: SiteConfig, out_dir: Path, settings: Settings | None = None, force: bool = False
) -> dict:
    """SPEC §7.2: HH/HV γ⁰ → dB COGs on one site grid (native posting, site UTM, clipped to the AOI)."""
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    from pipeline.lsh import io
    from pipeline.lsh.grid import site_grid

    files = gcov_files(site, settings)
    if not files:
        raise NeedsUserDecision(
            f"no GCOV files in {nisar_dir(site, settings) / 'gcov'}: run fetch-nisar first"
        )
    grid = None
    written, skipped, notes = [], [], {}
    for date, path in files.items():
        hh_out = io.cog_path(out_dir, site.id, "gcov-hh-db", date)
        hv_out = io.cog_path(out_dir, site.id, "gcov-hv-db", date)
        if hh_out.exists() and not force:
            skipped.append(date)
            continue
        try:
            data = read_gcov(path, site.bounds)
        except KeyError as e:  # e.g. a VV-only acquisition
            log.warning("skip %s: %s", path.name, e)
            notes[date] = str(e)
            continue
        if grid is None:
            res = float(np.round(abs(data.x[1] - data.x[0]))) if data.x.size > 1 else 20.0
            grid = site_grid(site, res)
        for arr, dst in ((data.hh, hh_out), (data.hv, hv_out)):
            if arr is None:
                continue
            warped = np.full(grid.shape, np.nan, dtype="float32")
            # resample linear power, then convert (dB is not linear)
            reproject(
                arr,
                warped,
                src_transform=data.transform,
                src_crs=f"EPSG:{data.epsg}",
                src_nodata=np.nan,
                dst_transform=grid.transform,
                dst_crs=grid.crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            db = to_db(warped)
            db[~grid.aoi] = np.nan
            io.write_cog(dst, db, grid.transform, grid.crs)
            if dst is hh_out:
                valid = float(np.isfinite(db[grid.aoi]).mean())
        notes[date] = {
            "file": path.name,
            "valid_aoi_frac": round(valid, 3),
            "mask_applied": data.mask_applied,
            "hv": data.hv is not None,
            "src_epsg": data.epsg,
        }
        written.append(date)
    return {
        "written": written,
        "skipped_existing": skipped,
        "res_m": grid.res if grid else None,
        "grid_shape": list(grid.shape) if grid else None,
        "per_date": notes,
    }

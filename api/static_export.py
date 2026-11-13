"""Static fallback (SPEC §14 phase 10): the app without a running API.

    python -m api.static_export --sites manpura,koyra,demo --out data/static

writes files shaped like the API's answers, rendered by the API's own code so they match it exactly:

    sites.json                                   GET /sites
    sites/<site>/{layers,stats,validation}.json  GET /sites/<site>/...   (layers.json gains a "static" block)
    sites/<site>/vectors/<name>.geojson          GET /sites/<site>/vectors/<name>   (compact, as served)
    sites/<site>/vectors/banklines.<src>.geojson GET ...?source=<src>   (landsat,nisar  and  nisar-median3)
    sites/<site>/points.json                     GET /sites/<site>/point, precomputed on a lon/lat grid
    tiles/<site>/<layer>/<key>/<z>/<x>/<y>.png   GET /tiles/...  (key = ISO date, year or "static")

Tiles: zooms 8–14 for score, flood frequency, motion (if usable), water on every NISAR date and the earliest
Landsat water map (compare mode). Tiles outside the data (the API's 204) are not written; the map then shows
nothing there. The radar backscatter (`sar_hh`) is not pre-rendered (≈ 300 MB per site) and is left out of the
static manifest, so the app hides that layer.

Point grid: the API's `point_query` at every cell centre of a lon/lat grid with ≈ `--grid-m` spacing (made
coarser if a site would exceed `MAX_CELLS`), stored column by column. The web app answers a click with the
cell it falls in — the same numbers the API gives at that cell's centre. Polygon statistics and the NISAR
scene search need the live API and say so.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import shutil
import time
from pathlib import Path

import morecantile

from api.app.errors import APIError
from api.app.routes_score import point_query
from api.app.routes_tiles import render_tile
from api.app.store import Store, compact_geojson, filter_by_source
from pipeline.lsh.config import get_settings

TMS = morecantile.tms.get("WebMercatorQuad")
MIN_ZOOM, MAX_ZOOM = 8, 14
MAX_CELLS = 120_000
STATIC_LAYERS = ("score", "floodfreq", "motion", "water", "landwater")
BANK_VARIANTS = ("landsat,nisar", "nisar-median3")
# point fields stored per cell (None where the API returns null)
COLUMNS = ("score", "yc", "yl", "yh", "o50", "d", "r", "sg", "tid", "f", "m", "he", "hf", "hg")


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def layer_keys(layers: dict, name: str) -> list[str]:
    """Which files of a raster layer to pre-render: every NISAR date, the earliest Landsat year, or static."""
    entry = layers["rasters"][name]
    pat = entry.get("pattern", "")
    if "{date}" in pat:
        return list(layers.get("nisar_dates", []))
    if "{year}" in pat:
        years = layers.get("landsat_years", [])
        return [str(years[0])] if years else []
    return ["static"]


def export_tiles(sd, out: Path, log) -> dict:
    layers = sd.layers
    w, s, e, n = layers["bounds"]
    counts = {}
    for name in STATIC_LAYERS:
        if name not in layers.get("rasters", {}):
            continue
        if name == "motion" and not layers.get("motion_usable"):
            continue
        entry = layers["rasters"][name]
        for key in layer_keys(layers, name):
            path = sd.raster_path(name, None if key == "static" else key)
            if path is None:
                continue
            k = 0
            for t in TMS.tiles(w, s, e, n, list(range(MIN_ZOOM, MAX_ZOOM + 1))):
                png = render_tile(path, entry, t.x, t.y, t.z)
                if png is None:
                    continue
                f = out / "tiles" / sd.id / name / key / str(t.z) / str(t.x) / f"{t.y}.png"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(png)
                k += 1
            counts[f"{name}/{key}"] = k
        log(f"  tiles {name}: {sum(v for kk, v in counts.items() if kk.startswith(name + '/'))}")
    return counts


def grid_spec(bounds, grid_m: float) -> dict:
    w, s, e, n = bounds
    lat0 = math.radians((s + n) / 2)
    step = grid_m
    while True:
        dlat = step / 111_320
        dlon = step / (111_320 * math.cos(lat0))
        cols, rows = math.ceil((e - w) / dlon), math.ceil((n - s) / dlat)
        if cols * rows <= MAX_CELLS:
            return {"west": w, "north": n, "dlon": dlon, "dlat": dlat, "cols": cols, "rows": rows,
                    "grid_m": round(step)}
        step *= 1.1


def export_points(sd, grid_m: float) -> dict:
    """Column-wise point answers on the grid. `idx` lists the cells inside the study area (row-major index);
    `river` marks cells in today's river; the other columns hold the API's numbers for land cells."""
    g = grid_spec(sd.layers["bounds"], grid_m)
    cols = {c: [] for c in COLUMNS}
    idx, river, river_f = [], [], []
    for r in range(g["rows"]):
        lat = g["north"] - (r + 0.5) * g["dlat"]
        for c in range(g["cols"]):
            lon = g["west"] + (c + 0.5) * g["dlon"]
            try:
                p = point_query(sd, lon, lat)
            except APIError:
                continue  # outside the study area
            i = r * g["cols"] + c
            idx.append(i)
            if p["in_river"]:
                river.append(1)
                river_f.append(p["flood_frequency"])
                for col in cols.values():
                    col.append(None)
                continue
            river.append(0)
            river_f.append(None)
            y = p["years_until_river"]
            comp = p["components"]
            vals = (p["score"], y["central"], y["low"], y["high"], int(y["over_50"]), p["distance_to_bank_m"],
                    p["retreat_rate_m_yr"], p["retreat_sigma_m_yr"], p["transect_id"], p["flood_frequency"],
                    p["motion_mm"], comp["H_E"], comp["H_F"], comp["H_G"])
            for k, v in zip(COLUMNS, vals, strict=True):
                cols[k].append(v)
    base = point_query(sd, *_any_inside(sd, g, idx))
    return {
        "site": sd.id, **g,
        "weights": base["weights"], "data": base["data"],
        "motion_status": "not_usable" if not sd.params.motion_usable else None,
        "idx": idx, "river": river, "river_f": river_f, "columns": list(COLUMNS),
        "values": [cols[c] for c in COLUMNS],
    }


def _any_inside(sd, g, idx) -> tuple[float, float]:
    i = idx[0]
    r, c = divmod(i, g["cols"])
    return g["west"] + (c + 0.5) * g["dlon"], g["north"] - (r + 0.5) * g["dlat"]


def export_site(sd, out: Path, grid_m: float, tiles: bool, log) -> dict:
    t0 = time.time()
    site_dir = out / "sites" / sd.id
    layers = json.loads(json.dumps(sd.layers))
    layers["rasters"] = {k: v for k, v in layers["rasters"].items() if k in STATIC_LAYERS}
    layers["static"] = {"minzoom": MIN_ZOOM, "maxzoom": MAX_ZOOM, "grid_m": None}
    for name, raw in sd.vectors.items():
        (site_dir / "vectors").mkdir(parents=True, exist_ok=True)
        (site_dir / "vectors" / f"{name}.geojson").write_bytes(compact_geojson(raw))
    if "banklines" in sd.vectors:
        for src in BANK_VARIANTS:
            body = filter_by_source(sd.vectors["banklines"], frozenset(src.split(",")))
            (site_dir / "vectors" / f"banklines.{src.replace(',', '+')}.geojson").write_bytes(body)
    pts = export_points(sd, grid_m)
    layers["static"]["grid_m"] = pts["grid_m"]
    _json(site_dir / "points.json", pts)
    log(f"  points: {len(pts['idx'])} cells at ~{pts['grid_m']} m")
    tile_counts = export_tiles(sd, out, log) if tiles else {}
    _json(site_dir / "layers.json", layers)
    _json(site_dir / "stats.json", sd.stats)
    _json(site_dir / "validation.json", sd.validation)
    return {"site": sd.id, "cells": len(pts["idx"]), "grid_m": pts["grid_m"],
            "tiles": sum(tile_counts.values()), "seconds": round(time.time() - t0)}


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    ap = argparse.ArgumentParser(description="Static fallback export (no API needed to run the app)")
    ap.add_argument("--sites", default=",".join(settings.sites))
    ap.add_argument("--out", type=Path, default=settings.data_dir / "static")
    ap.add_argument("--grid-m", type=float, default=100.0, help="point grid spacing (made coarser if needed)")
    ap.add_argument("--no-tiles", action="store_true", help="skip tile rendering (quick test)")
    args = ap.parse_args(argv)

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    store = Store(dataclasses.replace(settings, sites=sites))
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    report = []
    for sid, sd in store.sites.items():
        print(f"{sid}:")
        report.append(export_site(sd, args.out, args.grid_m, not args.no_tiles, print))
    _json(args.out / "sites.json", [sd.summary for sd in store.sites.values()])
    _json(args.out / "export.json", {"sites": report})
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"wrote {args.out}: {size / 1e6:.0f} MB; {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

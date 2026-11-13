"""Write `layers.json`, the manifest the API and web read (SPEC §7.12).

The manifest is built from the files actually present under `data/processed/<site>/`, so it never points
at something that does not exist. `{date}` in a pattern is filled with the date as YYYYMMDD (the file
key); `nisar_dates` are ISO dates. `{year}` patterns use `landsat_years`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pipeline.lsh import io
from pipeline.lsh.config import SiteConfig

log = logging.getLogger("lsh.publish")

# layer key -> (product, key kind, rescale, colormap). Key kind: "date" | "year" | a fixed key.
RASTER_LAYERS: dict[str, tuple[str, object, list[float] | None, str]] = {
    "sar_hh": ("gcov-hh-db", "date", [-25, 0], "gray"),
    "sar_hv": ("gcov-hv-db", "date", [-32, -8], "gray"),
    "water": ("water", "date", None, "water"),
    "floodveg": ("floodveg", "date", None, "floodveg"),
    "landwater": ("landwater", "year", None, "water"),
    "mndwi": ("mndwi", "year", [-0.6, 0.6], "rdbu"),
    "floodfreq": ("floodfreq", 2026, [0, 1], "blues"),
    "motion": ("motion", 2026, [-30, 30], "rdbu"),
    "coherence": ("coherence", 2026, [0, 1], "gray"),
    "distance": ("distance", "static", [0, 3000], "viridis"),
    "years": ("years", "static", [0, 50], "magma"),
    "population": ("population", "static", [0, 20], "ylorrd"),
    "score": ("score", "static", [0, 100], "custom-score"),
}
VECTOR_LAYERS = ("banklines", "transects", "buildings", "unions")
REQUIRED_RASTERS = ("water", "score")


class PublishError(RuntimeError):
    pass


def _entry(rescale, colormap) -> dict:
    out: dict = {}
    if rescale is not None:
        out["rescale"] = rescale
    out["colormap"] = colormap
    return out


def build_manifest(site: SiteConfig, site_dir: Path) -> dict:
    sid = site.id
    site_dir = Path(site_dir)
    dates = [d.isoformat() for d in io.list_keys(site_dir, sid, "water")]
    years = io.list_keys(site_dir, sid, "landwater")

    rasters: dict[str, dict] = {}
    for layer, (product, kind, rescale, cmap) in RASTER_LAYERS.items():
        if kind in ("date", "year"):
            want = dates if kind == "date" else years
            have = io.list_keys(site_dir, sid, product)
            have = [d.isoformat() for d in have] if kind == "date" else have
            if not want or not have:
                continue
            missing = sorted(set(want) - set(have), key=str)
            if missing:
                log.warning("layer %s skipped: no file for %s", layer, missing)
                continue
            rasters[layer] = {"pattern": f"cog/{sid}_{product}_{{{kind}}}.tif", **_entry(rescale, cmap)}
        else:
            path = io.cog_path(site_dir, sid, product, kind)
            if path.exists():
                rasters[layer] = {"path": f"cog/{path.name}", **_entry(rescale, cmap)}

    vectors = {}
    for name in VECTOR_LAYERS:
        path = io.vector_path(site_dir, sid, name)
        if path.exists():
            vectors[name] = f"vector/{path.name}"

    stats_path = site_dir / "stats.json"
    stats = io.read_json(stats_path) if stats_path.exists() else {}
    if "motion_usable" not in stats:
        log.warning("stats.json has no motion_usable; publishing motion_usable=false")
    motion_usable = bool(stats.get("motion_usable", False))

    return {
        "site": sid,
        "synthetic": bool(site.synthetic),
        "name": dict(site.name),
        "center": list(site.center),
        "zoom": site.zoom,
        "bounds": [round(v, 6) for v in site.bounds],
        "nisar_dates": dates,
        "landsat_years": years,
        "known_gaps": site.nisar.known_gaps,
        "motion_usable": motion_usable,
        "bank_date": stats.get("bank_date"),
        "rasters": rasters,
        "vectors": vectors,
        "score_weights": dict(site.score.weights),
    }


def validate_manifest(manifest: dict, site_dir: Path) -> list[str]:
    """Problems with a manifest (empty list = valid): missing keys or referenced files that do not exist."""
    problems = []
    for key in ("site", "synthetic", "name", "center", "zoom", "bounds", "nisar_dates", "landsat_years",
                "known_gaps", "motion_usable", "rasters", "vectors", "score_weights"):
        if key not in manifest:
            problems.append(f"missing key '{key}'")
    site_dir = Path(site_dir)
    for layer, entry in manifest.get("rasters", {}).items():
        if "path" in entry:
            files = [entry["path"]]
        else:
            pat = entry["pattern"]
            if "{date}" in pat:
                files = [pat.replace("{date}", d.replace("-", "")) for d in manifest.get("nisar_dates", [])]
            else:
                files = [pat.replace("{year}", str(y)) for y in manifest.get("landsat_years", [])]
            if not files:
                problems.append(f"raster '{layer}' has a pattern but no dates/years")
        problems += [f"raster '{layer}': missing {f}" for f in files if not (site_dir / f).is_file()]
    for name, rel in manifest.get("vectors", {}).items():
        if not (site_dir / rel).is_file():
            problems.append(f"vector '{name}': missing {rel}")
    for layer in REQUIRED_RASTERS:
        if layer not in manifest.get("rasters", {}):
            problems.append(f"required raster '{layer}' absent")
    return problems


def publish(site: SiteConfig, site_dir: Path) -> dict:
    """Always rewrites layers.json (cheap, derived only from what is on disk)."""
    manifest = build_manifest(site, site_dir)
    problems = validate_manifest(manifest, site_dir)
    if problems:
        raise PublishError(f"{site.id}: invalid manifest: {problems}")
    io.write_json(Path(site_dir) / "layers.json", manifest)
    return {
        "layers_json": str(Path(site_dir) / "layers.json"),
        "rasters": sorted(manifest["rasters"]), "vectors": sorted(manifest["vectors"]),
        "nisar_dates": len(manifest["nisar_dates"]), "motion_usable": manifest["motion_usable"],
        "synthetic": manifest["synthetic"],
    }

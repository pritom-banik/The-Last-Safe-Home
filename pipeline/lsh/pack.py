"""Deploy copy of the processed data (SPEC §12 "Production"): `python -m pipeline.lsh.pack`.

Copies, per site, only what the API serves — layers.json, stats.json, validation.json and the COGs and
vectors the manifest references — into `data/deploy/processed/<site>/` (no work files, summaries or logs),
then checks the total size: warning over 1 GB, **error over 1.5 GB** (SPEC §12). Optionally writes a
`.tar.gz` for image builds that download the data (`DATA_URL`, see api/Dockerfile).

Display-only radar layers are made smaller for serving:
- `sar_hh` (γ⁰ dB) is rounded to 0.1 dB — finer than one grey level of the −25…0 dB display ramp — and
  stored with a floating-point predictor (about half the size). No point/polygon number reads it.
- `sar_hv` is left out by default (the app has no HV layer); `--keep-hv` keeps it.
The local `data/processed` files are never changed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
from pathlib import Path

import numpy as np
import rasterio

from pipeline.lsh.config import get_settings

WARN_BYTES = 1_000_000_000
MAX_BYTES = 1_500_000_000
ROUNDED_DB = {"sar_hh": 0.1, "sar_hv": 0.1}
DROPPED_BY_DEFAULT = {"sar_hv"}
SITE_FILES = ("layers.json", "stats.json", "validation.json")


def raster_files(layers: dict, name: str, entry: dict) -> list[str]:
    """Relative paths of a manifest raster entry (static `path`, or `pattern` over dates / years)."""
    if "path" in entry:
        return [entry["path"]]
    pat = entry["pattern"]
    if "{date}" in pat:
        return [pat.replace("{date}", d.replace("-", "")) for d in layers.get("nisar_dates", [])]
    if "{year}" in pat:
        return [pat.replace("{year}", str(y)) for y in layers.get("landsat_years", [])]
    return [pat]


def write_rounded(src: Path, dst: Path, step: float) -> None:
    """Float COG rounded to `step`, DEFLATE with the floating-point predictor."""
    with rasterio.open(src) as s:
        a = s.read(1)
        prof = s.profile
    a = np.where(np.isfinite(a), np.round(a / step) * step, np.nan).astype("float32")
    drop = ("blockxsize", "blockysize", "tiled", "interleave", "compress")
    prof = {k: v for k, v in prof.items() if k not in drop}
    prof.update(driver="COG", compress="DEFLATE", predictor=3, blocksize=256, overview_resampling="average")
    tmp = dst.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **prof) as o:
        o.write(a, 1)
    tmp.replace(dst)


def pack_site(src_dir: Path, dst_dir: Path, keep_hv: bool = False) -> dict:
    layers = json.loads((src_dir / "layers.json").read_text(encoding="utf-8"))
    dropped = set() if keep_hv else {n for n in DROPPED_BY_DEFAULT if n in layers.get("rasters", {})}
    for n in dropped:
        layers["rasters"].pop(n)
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    (dst_dir / "cog").mkdir(parents=True)
    (dst_dir / "vector").mkdir(parents=True)
    missing: list[str] = []
    for name, entry in layers.get("rasters", {}).items():
        for rel in raster_files(layers, name, entry):
            s, d = src_dir / rel, dst_dir / rel
            if not s.exists():
                missing.append(rel)
                continue
            if name in ROUNDED_DB:
                write_rounded(s, d, ROUNDED_DB[name])
            else:
                shutil.copy2(s, d)
    for rel in layers.get("vectors", {}).values():
        if (src_dir / rel).exists():
            shutil.copy2(src_dir / rel, dst_dir / rel)
        else:
            missing.append(rel)
    if missing:
        raise FileNotFoundError(f"{src_dir.name}: manifest points at missing files: {missing[:5]}")
    (dst_dir / "layers.json").write_text(json.dumps(layers, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in SITE_FILES[1:]:
        if (src_dir / f).exists():
            shutil.copy2(src_dir / f, dst_dir / f)
    size = sum(p.stat().st_size for p in dst_dir.rglob("*") if p.is_file())
    return {"site": src_dir.name, "bytes": size, "dropped_layers": sorted(dropped)}


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sites", default=",".join(settings.sites), help="comma list (default: SITES)")
    ap.add_argument("--out", type=Path, default=settings.data_dir / "deploy", help="output root")
    ap.add_argument("--tar", type=Path, help="also write this .tar.gz (contents: processed/<site>/...)")
    ap.add_argument("--keep-hv", action="store_true", help="keep the HV radar layer")
    args = ap.parse_args(argv)

    out = args.out / "processed"
    out.mkdir(parents=True, exist_ok=True)
    total, report = 0, []
    for sid in [s.strip() for s in args.sites.split(",") if s.strip()]:
        src = settings.data_dir / "processed" / sid
        if not (src / "layers.json").exists():
            print(f"skip {sid}: no layers.json (run the pipeline / `publish` first)")
            continue
        r = pack_site(src, out / sid, keep_hv=args.keep_hv)
        total += r["bytes"]
        report.append(r)
        note = f" (left out: {', '.join(r['dropped_layers'])})" if r["dropped_layers"] else ""
        print(f"{sid}: {r['bytes'] / 1e6:.0f} MB{note}")
    print(f"total: {total / 1e6:.0f} MB in {out}")
    if total > MAX_BYTES:
        print(f"ERROR: deploy data is {total / 1e9:.2f} GB, over the 1.5 GB limit (SPEC §12)",
              file=sys.stderr)
        return 1
    if total > WARN_BYTES:
        print("warning: over 1 GB; the spec expects well under 1 GB", file=sys.stderr)
    if args.tar:
        args.tar.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.tar, "w:gz") as tf:
            for r in report:
                tf.add(out / r["site"], arcname=f"processed/{r['site']}")
        print(f"wrote {args.tar} ({args.tar.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

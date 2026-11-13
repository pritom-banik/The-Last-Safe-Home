"""Pipeline entry point: `python -m pipeline.cli <step> --site <id>` (SPEC §7)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import asdict

from pipeline.lsh import banklines as banklines_mod
from pipeline.lsh import context as context_mod
from pipeline.lsh import demo as demo_mod
from pipeline.lsh import flood as flood_mod
from pipeline.lsh import io
from pipeline.lsh import landsat as landsat_mod
from pipeline.lsh import motion as motion_mod
from pipeline.lsh import nisar as nisar_mod
from pipeline.lsh import publish as publish_mod
from pipeline.lsh import scoring as scoring_mod
from pipeline.lsh import transects as transects_mod
from pipeline.lsh import validate as validate_mod
from pipeline.lsh import water as water_mod
from pipeline.lsh.config import ConfigError, SiteConfig, get_settings, list_sites, load_site

log = logging.getLogger("lsh")

# Order matters: `all` runs these in sequence (SPEC §12 "make pipeline").
PIPELINE_STEPS = [
    "fetch-nisar", "gcov", "water-sar", "landsat", "banklines", "transects",
    "flood", "motion", "context", "score", "validate", "publish",
]
# Phase in SPEC §14 that implements each step; used for the "not built yet" message.
_PLANNED_PHASE = {
    "fetch-nisar": 5, "gcov": 5, "landsat": 5, "context": 5,
    "water-sar": 6, "banklines": 6, "transects": 6, "flood": 6, "motion": 6, "score": 6, "validate": 6,
}

StepFn = Callable[[SiteConfig, argparse.Namespace], dict]
STEPS: dict[str, StepFn] = {}


def step(name: str):
    def register(fn: StepFn) -> StepFn:
        STEPS[name] = fn
        return fn
    return register


@step("show-config")
def show_config(site: SiteConfig, args: argparse.Namespace) -> dict:
    out = asdict(site)
    out["bounds"] = site.bounds
    out["processed_dir"] = str(site.processed_dir())
    return out


@step("demo")
def run_demo(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Synthetic demo site (SPEC §7.13); writes every §5 product + stats.json + validation.json."""
    return demo_mod.generate(site, site.processed_dir(), force=args.force)


@step("fetch-nisar")
def run_fetch_nisar(site: SiteConfig, args: argparse.Namespace) -> dict:
    """NISAR search → inventory.csv → track choice → GCOV AOI subsets (or full files with --full)."""
    return nisar_mod.fetch(site, get_settings(), dry_run=args.dry_run, full=args.full,
                           confirm_large=args.confirm_large, force=args.force)


@step("gcov")
def run_gcov(site: SiteConfig, args: argparse.Namespace) -> dict:
    """GCOV HH/HV → dB COGs on the site grid (SPEC §7.2)."""
    return nisar_mod.process_gcov(site, site.processed_dir(), force=args.force)


@step("water-sar")
def run_water_sar(site: SiteConfig, args: argparse.Namespace) -> dict:
    """NISAR HH → water + flooded-vegetation masks (SPEC §7.3)."""
    return water_mod.run(site, site.processed_dir(), force=args.force)


@step("banklines")
def run_banklines(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Bank lines for every Landsat year and NISAR date + median-of-3 NISAR lines (SPEC §7.5)."""
    return banklines_mod.run(site, site.processed_dir(), force=args.force)


@step("transects")
def run_transects(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Baseline, transects, bank distances and retreat rates (SPEC §7.6)."""
    return transects_mod.run(site, site.processed_dir(), force=args.force)


@step("flood")
def run_flood(site: SiteConfig, args: argparse.Namespace) -> dict:
    """2026 flood frequency (SPEC §7.7)."""
    return flood_mod.run(site, site.processed_dir(), force=args.force)


@step("motion")
def run_motion(site: SiteConfig, args: argparse.Namespace) -> dict:
    """GUNW season displacement + coherence (SPEC §7.8)."""
    return motion_mod.run(site, site.processed_dir(), site.raw_dir(), force=args.force)


@step("score")
def run_score(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Distance, years, Home Risk Score, union stats, stats.json (SPEC §7.10)."""
    return scoring_mod.run(site, site.processed_dir(), force=args.force)


@step("validate")
def run_validate(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Area check, Sentinel-2 water check, labelled-point accuracy (SPEC §7.11)."""
    return validate_mod.run(site, site.processed_dir(), site.raw_dir(), make_pts=args.make_points)


@step("landsat")
def run_landsat(site: SiteConfig, args: argparse.Namespace) -> dict:
    """Landsat dry-season MNDWI composites + water masks (SPEC §7.4)."""
    return landsat_mod.run(site, site.processed_dir(), force=args.force)


@step("context")
def run_context(site: SiteConfig, args: argparse.Namespace) -> dict:
    """OSM buildings/roads, WorldPop population, geoBoundaries unions (SPEC §7.9)."""
    return context_mod.run(site, site.processed_dir(), site.raw_dir(), force=args.force)


@step("publish")
def run_publish(site: SiteConfig, args: argparse.Namespace) -> dict:
    """layers.json manifest (SPEC §7.12)."""
    return publish_mod.publish(site, site.processed_dir())


def setup_logging(site: SiteConfig) -> None:
    out = site.processed_dir()
    out.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.FileHandler(out / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.handlers[:] = [file_handler, console]
    log.setLevel(logging.INFO)


def check_built(names: list[str]) -> None:
    for name in names:
        if name not in STEPS:
            phase = _PLANNED_PHASE.get(name, "?")
            raise NotImplementedError(f"step '{name}' is not built yet (SPEC §14 phase {phase})")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.cli", description=__doc__)
    p.add_argument("step", choices=["all", "demo", "show-config", *PIPELINE_STEPS])
    p.add_argument("--site", required=True, help=f"site id, one of {list_sites()}")
    p.add_argument("--force", action="store_true", help="recompute outputs that already exist")
    p.add_argument("--dry-run", action="store_true", help="fetch-nisar: write inventory only")
    p.add_argument("--full", action="store_true",
                   help="fetch-nisar: download whole products instead of AOI subsets")
    p.add_argument("--confirm-large", action="store_true",
                   help="fetch-nisar --full: the user agreed to a download over 20 GB")
    p.add_argument("--make-points", action="store_true", help="validate: write points to label")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Bangla names break cp1252 Windows consoles
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        site = load_site(args.site)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if args.step == "show-config":
        print(json.dumps(show_config(site, args), indent=2, ensure_ascii=False))
        return 0

    if args.step == "demo" and not site.synthetic:
        print(f"refusing: site '{site.id}' is not synthetic (demo files must not mix with real data)",
              file=sys.stderr)
        return 2

    get_settings()  # load .env before any step touches credentials
    names = PIPELINE_STEPS if args.step == "all" else [args.step]
    if site.synthetic and args.step == "all":
        names = ["demo", "publish"]
    try:
        check_built(names)
    except NotImplementedError as e:
        print(str(e), file=sys.stderr)
        return 3

    setup_logging(site)
    for name in names:
        log.info("step %s for site %s", name, site.id)
        try:
            summary = STEPS[name](site, args)
        except nisar_mod.NeedsUserDecision as e:
            log.error("step %s stopped: %s", name, e)
            print(f"STOPPED — needs a decision: {e}", file=sys.stderr)
            return 4
        io.write_json(site.processed_dir() / "summaries" / f"{name}.json", summary)
        log.info("summary %s: %s", name, json.dumps(summary, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

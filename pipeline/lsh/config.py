"""Load site YAML files and environment settings (SPEC §4)."""

from __future__ import annotations

import datetime as dt
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from shapely import wkt
from shapely.geometry.base import BaseGeometry

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config" / "sites"


class ConfigError(ValueError):
    """A site file or the environment is invalid."""


# --------------------------------------------------------------------------- env


def load_dotenv(path: Path | None = None) -> None:
    """Read KEY=VALUE lines from .env into os.environ. Existing variables win."""
    path = path or REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    earthdata_username: str
    earthdata_password: str
    data_dir: Path
    sites: list[str]
    api_url: str
    cors_origins: list[str]

    @property
    def has_earthdata(self) -> bool:
        return bool(self.earthdata_username and self.earthdata_password)


def get_settings(dotenv: bool = True) -> Settings:
    if dotenv:
        load_dotenv()
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = (REPO_ROOT / data_dir).resolve()
    return Settings(
        earthdata_username=os.environ.get("EARTHDATA_USERNAME", ""),
        earthdata_password=os.environ.get("EARTHDATA_PASSWORD", ""),
        data_dir=data_dir,
        sites=_csv(os.environ.get("SITES", "manpura,koyra,demo")),
        api_url=os.environ.get("API_URL", "http://localhost:8000"),
        cors_origins=_csv(os.environ.get("CORS_ORIGINS", "http://localhost:5173")),
    )


# --------------------------------------------------------------------------- site


@dataclass(frozen=True)
class NisarConfig:
    start: str
    end: str | None
    production_configuration: str = "PR"
    track: int | None = None
    known_gaps: list[list[str]] = field(default_factory=list)

    @property
    def end_or_today(self) -> str:
        return self.end or dt.date.today().isoformat()


@dataclass(frozen=True)
class LandsatConfig:
    years: list[int]
    months: list[int]
    max_cloud: float = 40


@dataclass(frozen=True)
class AnalysisConfig:
    grid_res_m: float = 30
    transect_spacing_m: float = 100
    transect_length_m: float = 6000
    baseline_inset_m: float = 1500
    coherence_min: float = 0.4
    min_water_blob_px: int = 10
    speckle_filter_px: int = 5
    # water bodies that do not touch the AOI edge still count as river from this size (SPEC §7.5: 1 km²);
    # null = only edge-connected water is river (sites with large enclosed ponds, e.g. Koyra's shrimp ghers)
    river_min_km2: float | None = 1.0


@dataclass(frozen=True)
class ScoreConfig:
    weights: dict[str, float]
    t_full_risk_yr: float = 5
    t_no_risk_yr: float = 50
    motion_full_mm: float = 30


@dataclass(frozen=True)
class SiteConfig:
    id: str
    name: dict[str, str]
    aoi_wkt: str
    utm_epsg: int
    center: tuple[float, float]
    zoom: float
    nisar: NisarConfig
    landsat: LandsatConfig
    analysis: AnalysisConfig
    score: ScoreConfig
    synthetic: bool = False
    reference_area_wkt: str | None = None
    validation: dict[str, Any] = field(default_factory=dict)

    @property
    def aoi(self) -> BaseGeometry:
        return wkt.loads(self.aoi_wkt)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) in EPSG:4326."""
        return tuple(self.aoi.bounds)  # type: ignore[return-value]

    def raw_dir(self, settings: Settings | None = None) -> Path:
        return (settings or get_settings()).data_dir / "raw" / self.id

    def processed_dir(self, settings: Settings | None = None) -> Path:
        return (settings or get_settings()).data_dir / "processed" / self.id


_REQUIRED = ("id", "name", "aoi_wkt", "utm_epsg", "center", "zoom", "nisar", "landsat", "analysis", "score")
_WEIGHT_KEYS = {"erosion", "flood", "motion"}


def _section(cls, data: Any, name: str, site_id: str):
    if not isinstance(data, dict):
        raise ConfigError(f"{site_id}: '{name}' must be a mapping")
    known = set(cls.__dataclass_fields__)
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"{site_id}: unknown keys in '{name}': {sorted(unknown)}")
    try:
        return cls(**data)
    except TypeError as e:
        raise ConfigError(f"{site_id}: bad '{name}' section: {e}") from e


def parse_site(data: dict[str, Any], expected_id: str | None = None) -> SiteConfig:
    if not isinstance(data, dict):
        raise ConfigError("site file must be a mapping")
    site_id = str(data.get("id", "?"))
    missing = [k for k in _REQUIRED if k not in data]
    if missing:
        raise ConfigError(f"{site_id}: missing keys {missing}")
    if expected_id is not None and site_id != expected_id:
        raise ConfigError(f"site id '{site_id}' does not match file name '{expected_id}'")

    name = data["name"]
    if not (isinstance(name, dict) and name.get("en") and name.get("bn")):
        raise ConfigError(f"{site_id}: 'name' needs both 'en' and 'bn'")

    try:
        aoi = wkt.loads(data["aoi_wkt"])
    except Exception as e:  # shapely raises several types
        raise ConfigError(f"{site_id}: invalid aoi_wkt: {e}") from e
    if aoi.geom_type not in ("Polygon", "MultiPolygon") or not aoi.is_valid or aoi.is_empty:
        raise ConfigError(f"{site_id}: aoi_wkt must be a valid polygon")
    w, s, e, n = aoi.bounds
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ConfigError(f"{site_id}: aoi_wkt must be lon/lat (EPSG:4326)")

    center = tuple(float(v) for v in data["center"])
    if len(center) != 2:
        raise ConfigError(f"{site_id}: 'center' must be [lon, lat]")

    score = _section(ScoreConfig, data["score"], "score", site_id)
    if set(score.weights) != _WEIGHT_KEYS:
        raise ConfigError(f"{site_id}: score.weights must have keys {sorted(_WEIGHT_KEYS)}")
    if not math.isclose(sum(score.weights.values()), 1.0, abs_tol=1e-6):
        raise ConfigError(f"{site_id}: score.weights must sum to 1")
    if not 0 < score.t_full_risk_yr < score.t_no_risk_yr:
        raise ConfigError(f"{site_id}: need 0 < t_full_risk_yr < t_no_risk_yr")

    nisar_raw = dict(data["nisar"])
    for key in ("start", "end"):  # YAML may parse unquoted dates into datetime.date
        if isinstance(nisar_raw.get(key), dt.date):
            nisar_raw[key] = nisar_raw[key].isoformat()
    nisar_raw["known_gaps"] = [[str(a), str(b)] for a, b in nisar_raw.get("known_gaps") or []]

    return SiteConfig(
        id=site_id,
        name={"en": name["en"], "bn": name["bn"]},
        aoi_wkt=data["aoi_wkt"],
        utm_epsg=int(data["utm_epsg"]),
        center=center,  # type: ignore[arg-type]
        zoom=float(data["zoom"]),
        nisar=_section(NisarConfig, nisar_raw, "nisar", site_id),
        landsat=_section(LandsatConfig, data["landsat"], "landsat", site_id),
        analysis=_section(AnalysisConfig, data["analysis"], "analysis", site_id),
        score=score,
        synthetic=bool(data.get("synthetic", False)),
        reference_area_wkt=data.get("reference_area_wkt"),
        validation=dict(data.get("validation") or {}),
    )


def load_site(site_id: str, config_dir: Path | None = None) -> SiteConfig:
    path = (config_dir or CONFIG_DIR) / f"{site_id}.yaml"
    if not path.is_file():
        raise ConfigError(f"no site file {path}")
    with path.open(encoding="utf-8") as f:
        return parse_site(yaml.safe_load(f), expected_id=site_id)


def list_sites(config_dir: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (config_dir or CONFIG_DIR).glob("*.yaml"))

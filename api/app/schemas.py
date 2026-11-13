"""Response models (SPEC §9)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SiteSummary(BaseModel):
    id: str
    name: dict[str, str]
    synthetic: bool
    center: list[float]
    zoom: float
    bounds: list[float]


class Health(BaseModel):
    status: str
    sites: list[str]


class YearsUntilRiver(BaseModel):
    central: float | None
    low: float | None
    high: float | None
    over_50: bool


class Components(BaseModel):
    H_E: float
    H_F: float
    H_G: float


class PointData(BaseModel):
    nisar_passes: int | None
    last_pass: str | None
    bank_date: str | None
    synthetic: bool


class PointResponse(BaseModel):
    site: str
    in_aoi: bool
    in_river: bool
    score: int | None
    # "class" is a Python keyword: stored as class_, serialised as "class"
    class_: Literal["low", "moderate", "high", "severe"] | None = Field(default=None, alias="class")
    years_until_river: YearsUntilRiver | None
    distance_to_bank_m: int | None
    retreat_rate_m_yr: float | None
    retreat_sigma_m_yr: float | None
    transect_id: int | None
    flood_frequency: float | None
    motion_mm: float | None
    motion_status: Literal["ok", "masked", "not_usable"]
    components: Components | None
    weights: dict[str, float]
    data: PointData

    model_config = ConfigDict(populate_by_name=True)


class PolygonStats(BaseModel):
    in_aoi: bool
    area_km2: float | None = None
    land_area_km2: float | None = None
    area_lost_km2_per_yr: float | None = None
    mean_score: int | None = None
    max_retreat_m_yr: float | None = None
    buildings_total: int | None = None
    buildings_within_100m: int | None = None
    buildings_within_500m: int | None = None
    people_by_class: dict[str, int] | None = None
    transects: int | None = None
    synthetic: bool


class Scene(BaseModel):
    granule: str
    product: str
    datetime: str
    direction: str
    track: str
    url_asf: str
    size_mb: float | None

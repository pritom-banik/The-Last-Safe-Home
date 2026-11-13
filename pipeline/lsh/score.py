"""Home Risk Score — the one shared implementation of SPEC §8.

The pipeline uses these functions to build `score_static.tif`; the API imports the same functions for
point queries, so the map raster and the click card can never disagree. Everything is vectorised with
numpy and also accepts plain Python scalars.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pipeline.lsh.config import ScoreConfig

# (class key, lowest score in class, colour) — SPEC §8 table. Text lives in the web i18n files.
CLASSES: list[tuple[str, int, str]] = [
    ("low", 0, "#1a9850"),
    ("moderate", 25, "#fee08b"),
    ("high", 50, "#f46d43"),
    ("severe", 75, "#a50026"),
]
CLASS_KEYS = [c[0] for c in CLASSES]
CLASS_COLOURS = {c[0]: c[2] for c in CLASSES}


@dataclass(frozen=True)
class ScoreParams:
    weights: dict[str, float] = field(default_factory=lambda: {"erosion": 0.6, "flood": 0.3, "motion": 0.1})
    t_full_risk_yr: float = 5.0
    t_no_risk_yr: float = 50.0
    motion_full_mm: float = 30.0
    motion_usable: bool = True

    @classmethod
    def from_config(cls, cfg: ScoreConfig, motion_usable: bool) -> ScoreParams:
        return cls(
            weights=dict(cfg.weights),
            t_full_risk_yr=float(cfg.t_full_risk_yr),
            t_no_risk_yr=float(cfg.t_no_risk_yr),
            motion_full_mm=float(cfg.motion_full_mm),
            motion_usable=bool(motion_usable),
        )

    @property
    def effective_weights(self) -> dict[str, float]:
        return effective_weights(self.weights, self.motion_usable)


def effective_weights(weights: dict[str, float], motion_usable: bool) -> dict[str, float]:
    """Weights actually applied: if motion is not usable, its weight is 0 and the rest rescale to sum 1."""
    w = {k: float(weights[k]) for k in ("erosion", "flood", "motion")}
    if motion_usable:
        return w
    rest = w["erosion"] + w["flood"]
    return {"erosion": w["erosion"] / rest, "flood": w["flood"] / rest, "motion": 0.0}


def years_until_river(distance_m, rate_m_yr, sigma_m_yr):
    """(T, T_low, T_high) in years. +inf where the bank is not retreating (or the rate is unknown)."""
    d = np.asarray(distance_m, dtype="float64")
    r = np.asarray(rate_m_yr, dtype="float64")
    s = np.nan_to_num(np.asarray(sigma_m_yr, dtype="float64"), nan=0.0)
    r_ok = np.isfinite(r) & (r > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(r_ok, d / np.where(r_ok, r, 1.0), np.inf)
        t_low = np.where(r_ok, d / np.where(r_ok, r + s, 1.0), np.inf)
        hi_ok = r_ok & (r - s > 0)
        t_high = np.where(hi_ok, d / np.where(hi_ok, r - s, 1.0), np.inf)
    nan = ~np.isfinite(d)  # unknown distance (e.g. in the river) -> unknown time
    t, t_low, t_high = (np.where(nan, np.nan, x) for x in (t, t_low, t_high))
    return t, t_low, t_high


def hazard_erosion(years, t_full_risk_yr: float = 5.0, t_no_risk_yr: float = 50.0):
    """H_E = clip(1 − log10(T/t_full) / log10(t_no/t_full), 0, 1). T=inf -> 0, T<=t_full -> 1."""
    t = np.asarray(years, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        h = 1.0 - np.log10(t / t_full_risk_yr) / np.log10(t_no_risk_yr / t_full_risk_yr)
    return np.clip(h, 0.0, 1.0)  # NaN stays NaN


def hazard_flood(flood_frequency):
    """H_F = F (0–1); NaN (no flood data / permanent water) -> 0 on land."""
    return np.clip(np.nan_to_num(np.asarray(flood_frequency, dtype="float64"), nan=0.0), 0.0, 1.0)


def hazard_motion(motion_mm, motion_full_mm: float = 30.0):
    """H_G = clip(|M| / motion_full_mm, 0, 1) if M is finite, else 0."""
    m = np.asarray(motion_mm, dtype="float64")
    return np.where(np.isfinite(m), np.clip(np.abs(np.nan_to_num(m)) / motion_full_mm, 0.0, 1.0), 0.0)


def round_half_up(x):
    """round() with .5 going up, identical for numpy arrays and scalars (numpy/Python round to even)."""
    return np.floor(np.asarray(x, dtype="float64") + 0.5)


def compute(distance_m, rate_m_yr, sigma_m_yr, flood_frequency, motion_mm, params: ScoreParams) -> dict:
    """Every quantity the map and the click card need. Inputs broadcast together.

    Returns arrays (0-d for scalar input): score (0–100, NaN where distance is NaN), years, years_low,
    years_high, H_E, H_F, H_G, plus the effective `weights` dict.
    """
    w = params.effective_weights
    t, t_low, t_high = years_until_river(distance_m, rate_m_yr, sigma_m_yr)
    h_e = hazard_erosion(t, params.t_full_risk_yr, params.t_no_risk_yr)
    h_f = hazard_flood(flood_frequency)
    h_g = hazard_motion(motion_mm, params.motion_full_mm)
    raw = 100.0 * (w["erosion"] * h_e + w["flood"] * h_f + w["motion"] * h_g)
    score = np.where(np.isfinite(raw), round_half_up(raw), np.nan)
    return {
        "score": score, "years": t, "years_low": t_low, "years_high": t_high,
        "H_E": h_e, "H_F": h_f, "H_G": h_g, "weights": w,
    }


def score_class(score) -> str | None:
    """Class key for one score value; None for NaN/None (river)."""
    if score is None or not np.isfinite(score):
        return None
    key = CLASS_KEYS[0]
    for name, lowest, _ in CLASSES:
        if score >= lowest:
            key = name
    return key


def class_index(score):
    """Vectorised class index 0–3 (−1 where NaN)."""
    s = np.asarray(score, dtype="float64")
    idx = np.digitize(np.nan_to_num(s, nan=-1.0), [c[1] for c in CLASSES[1:]])
    return np.where(np.isfinite(s), idx, -1)

"""Site list, manifests, stats, validation and GeoJSON vectors (SPEC §9)."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Query, Request, Response

from api.app.errors import APIError, get_site
from api.app.schemas import SiteSummary
from api.app.store import filter_by_source

router = APIRouter()

VECTOR_NAMES = ("banklines", "transects", "buildings", "unions")
ONE_DAY = "public, max-age=86400"


@router.get("/sites", response_model=list[SiteSummary])
def sites(request: Request):
    return [sd.summary for sd in request.app.state.store.sites.values()]


@router.get("/sites/{site}/layers")
def layers(request: Request, site: str):
    return get_site(request, site).layers


@router.get("/sites/{site}/stats")
def stats(request: Request, site: str):
    return get_site(request, site).stats


@router.get("/sites/{site}/validation")
def validation(request: Request, site: str):
    return get_site(request, site).validation


BANK_SOURCES = {"landsat", "nisar", "nisar-median3"}


@lru_cache(maxsize=32)
def _filtered(site: str, raw: bytes, sources: frozenset[str]) -> bytes:
    return filter_by_source(raw, sources)


@router.get("/sites/{site}/vectors/{name}")
def vector(request: Request, site: str, name: str, source: str | None = Query(None, max_length=60)):
    """GeoJSON vector; for bank lines `?source=landsat,nisar` returns only those sources (the map does not
    need the median-of-3 lines, the report needs only those)."""
    sd = get_site(request, site)
    if name not in VECTOR_NAMES or name not in sd.vectors:
        raise APIError(404, "unknown_vector", f"no vector '{name}' for site '{site}'")
    body = sd.vectors[name]
    if source is not None:
        wanted = frozenset(s.strip() for s in source.split(",") if s.strip())
        if name != "banklines" or not wanted or not wanted <= BANK_SOURCES:
            msg = f"source works for bank lines only, as a subset of {sorted(BANK_SOURCES)}"
            raise APIError(422, "invalid_request", msg)
        body = _filtered(site, body, wanted)
    return Response(body, media_type="application/geo+json", headers={"Cache-Control": ONE_DAY})

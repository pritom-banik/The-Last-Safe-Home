"""FastAPI app (SPEC §9): CORS, gzip, request timing, one error shape, routers under /api/v1."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.app import routes_layers, routes_polygon, routes_scenes, routes_score, routes_tiles
from api.app.errors import APIError, api_error_handler, error_response
from api.app.schemas import Health
from api.app.store import Store
from pipeline.lsh.config import Settings, get_settings

log = logging.getLogger("lsh.api")
PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="The Last Safe Home API", version="0.3.0")
    app.state.settings = settings
    app.state.store = Store(settings)  # loads every site in SITES that has processed data

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
        log.info("%s %s %d %.1fms", request.method, request.url.path, response.status_code, ms)
        return response

    app.add_exception_handler(APIError, api_error_handler)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        return error_response(422, "invalid_request", msg)

    @app.get(f"{PREFIX}/health", response_model=Health)
    def health(request: Request):
        return {"status": "ok", "sites": list(request.app.state.store.sites)}

    for r in (routes_layers, routes_score, routes_polygon, routes_scenes, routes_tiles):
        app.include_router(r.router, prefix=PREFIX)
    return app


app = create_app()

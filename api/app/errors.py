"""One error shape everywhere: {"error": {"code": "...", "message": "..."}} (SPEC §9)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message)


def get_site(request: Request, site: str):
    sd = request.app.state.store.get(site)
    if sd is None:
        raise APIError(404, "unknown_site", f"no processed data for site '{site}'")
    return sd

"""Production hardening middleware.

Provides:
- RequestIDMiddleware: attaches a unique X-Request-ID to every request/response
- APIKeyMiddleware: enforces X-API-Key header when Settings.api_key is set
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response.

    Respects an incoming ``X-Request-ID`` header if present; otherwise
    generates a new UUID4. The ID is stored in ``request.state.request_id``
    and echoed back in the ``X-Request-ID`` response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key authentication when configured.

    Only active when ``Settings.api_key`` is set. Exempt paths:
    - ``/health`` and ``/`` (liveness probes)
    - ``/docs``, ``/redoc``, ``/openapi.json`` (API docs, dev only)

    The key must be supplied in the ``X-API-Key`` request header.
    """

    _EXEMPT: frozenset[str] = frozenset({"/", "/health", "/docs", "/redoc", "/openapi.json"})

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.api_key:
            return await call_next(request)

        if request.url.path in self._EXEMPT:
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not provided or provided != settings.api_key:
            logger.warning(
                "API key auth failed",
                path=request.url.path,
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "detail": "Invalid or missing X-API-Key header."},
                headers={"X-Request-ID": getattr(request.state, "request_id", "")},
            )

        return await call_next(request)

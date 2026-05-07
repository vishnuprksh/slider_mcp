"""FastAPI application factory.

Wires together config, logging, middleware, routes, and the MCP server.
Every phase adds to this file minimally; the core structure is fixed here.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.middleware import APIKeyMiddleware, RequestIDMiddleware
from app.models.base import APIError
from app.mcp_server import mcp_server
from app.routes.health import router as health_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    settings = get_settings()
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    os.makedirs(settings.output_dir, exist_ok=True)
    logger.info(
        "Slider MCP starting",
        version=settings.app_version,
        environment=settings.environment,
        mcp_endpoint="/mcp",
    )
    # The MCP session manager needs its own task group to be running.
    # FastAPI does not propagate lifespan to mounted sub-apps, so we
    # start the session manager explicitly here.
    async with mcp_server.session_manager.run():
        yield
    logger.info("Slider MCP stopped")


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Remote MCP server for visually rich slide generation. "
            "Connect MCP-compatible agents to generate presentation decks."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # ── Domain error handler ──────────────────────────────────────────────────
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=exc.detail.model_dump(),
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(health_router)

    # ── MCP mount ─────────────────────────────────────────────────────────────
    # FastMCP's Starlette app exposes its route at /mcp internally.
    # Mount at root "/" so requests to /mcp are forwarded correctly.
    # FastAPI's own routes (/health, /docs, etc.) are matched first.
    mcp_asgi = mcp_server.streamable_http_app()
    app.mount("/", mcp_asgi)

    return app


app = create_app()

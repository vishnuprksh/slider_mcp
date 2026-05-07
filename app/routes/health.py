"""Health and root routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str
    timestamp: str
    version: str
    environment: str
    mcp_endpoint: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    """Return server liveness and version metadata."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
        environment=settings.environment,
        mcp_endpoint="/mcp",
    )


@router.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root redirect info — not shown in schema."""
    settings = get_settings()
    return {
        "service": settings.app_name,
        "status": "running",
        "health": "/health",
        "mcp": "/mcp",
        "docs": "/docs",
    }

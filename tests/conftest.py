"""Pytest configuration and shared fixtures for Slider MCP tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(scope="session")
def settings():
    """Return application settings (session-scoped — they don't change)."""
    return get_settings()


@pytest.fixture()
async def async_client():
    """Async HTTPX test client — suitable for routes that don't need ASGI lifespan."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=True,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def lifespan_client():
    """Sync Starlette TestClient — runs the ASGI lifespan (required for MCP routes).

    Session-scoped: MCP session manager can only be started once per process.
    base_url=http://localhost so Host header passes FastMCP's DNS-rebinding check.
    """
    with TestClient(
        app,
        base_url="http://localhost",
        raise_server_exceptions=False,
        follow_redirects=True,
    ) as client:
        yield client

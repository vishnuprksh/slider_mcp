"""Phase 1 — health endpoint tests."""
from __future__ import annotations


async def test_health_returns_ok(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200


async def test_health_schema(async_client):
    data = (await async_client.get("/health")).json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "version" in data
    assert "environment" in data
    assert data["mcp_endpoint"] == "/mcp"


async def test_root_returns_running(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


async def test_health_content_type(async_client):
    response = await async_client.get("/health")
    assert "application/json" in response.headers["content-type"]

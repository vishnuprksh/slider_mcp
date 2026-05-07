"""Phase 9 — Production Hardening tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import create_app


# ─────────────────────────────────────────────────────────────────────────────
# RequestIDMiddleware
# ─────────────────────────────────────────────────────────────────────────────


class TestRequestIDMiddleware:
    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app, raise_server_exceptions=True)

    def test_response_has_request_id_header(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers

    def test_request_id_is_uuid_when_not_provided(self, client):
        import uuid
        resp = client.get("/health")
        rid = resp.headers.get("X-Request-ID", "")
        # Should be parseable as UUID
        uuid.UUID(rid)  # raises if invalid

    def test_incoming_request_id_echoed(self, client):
        rid = "my-custom-id-12345"
        resp = client.get("/health", headers={"X-Request-ID": rid})
        assert resp.headers.get("X-Request-ID") == rid

    def test_request_id_present_on_all_routes(self, client):
        for path in ["/", "/health"]:
            resp = client.get(path)
            assert "X-Request-ID" in resp.headers, f"Missing on {path}"


# ─────────────────────────────────────────────────────────────────────────────
# APIKeyMiddleware
# ─────────────────────────────────────────────────────────────────────────────


class TestAPIKeyMiddleware:
    @pytest.fixture
    def secured_client(self, monkeypatch):
        """App with API key configured."""
        monkeypatch.setenv("API_KEY", "test-secret-key-xyz")
        from app import config
        config.get_settings.cache_clear()
        app = create_app()
        yield TestClient(app, raise_server_exceptions=False)
        config.get_settings.cache_clear()

    @pytest.fixture
    def open_client(self, monkeypatch):
        """App with no API key configured."""
        monkeypatch.delenv("API_KEY", raising=False)
        from app import config
        config.get_settings.cache_clear()
        app = create_app()
        yield TestClient(app, raise_server_exceptions=False)
        config.get_settings.cache_clear()

    def test_no_api_key_config_allows_all(self, open_client):
        resp = open_client.get("/health")
        assert resp.status_code == 200

    def test_health_exempt_without_key(self, secured_client):
        resp = secured_client.get("/health")
        assert resp.status_code == 200

    def test_root_exempt_without_key(self, secured_client):
        resp = secured_client.get("/")
        # Root returns redirect or 200 from MCP; shouldn't be 401
        assert resp.status_code != 401

    def test_protected_endpoint_returns_401_without_key(self, secured_client):
        # POST to /mcp requires auth when api_key is set
        resp = secured_client.post("/mcp", json={})
        assert resp.status_code == 401

    def test_protected_endpoint_returns_401_wrong_key(self, secured_client):
        resp = secured_client.post("/mcp", json={}, headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_correct_key_passes_through(self, secured_client):
        resp = secured_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"X-API-Key": "test-secret-key-xyz"},
        )
        # Not 401 (may be 200 or other MCP response)
        assert resp.status_code != 401

    def test_401_response_body_has_error_key(self, secured_client):
        resp = secured_client.post("/mcp", json={})
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body

    def test_401_response_has_request_id(self, secured_client):
        resp = secured_client.post("/mcp", json={})
        assert "X-Request-ID" in resp.headers

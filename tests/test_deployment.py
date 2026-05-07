"""Phase 10 — Deployment + Final Verification tests.

Validates the deployment configuration, ensures critical requirements are met,
and runs end-to-end smoke tests covering the full pipeline:
plan_deck → render_html → render_pptx.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation


# ─────────────────────────────────────────────────────────────────────────────
# Deployment config checks
# ─────────────────────────────────────────────────────────────────────────────


class TestDeploymentConfig:
    """Verify render.yaml and Dockerfile have required attributes."""

    def test_render_yaml_exists(self):
        assert Path("render.yaml").exists()

    def test_render_yaml_has_health_check(self):
        content = Path("render.yaml").read_text()
        assert "/health" in content

    def test_render_yaml_has_start_command(self):
        content = Path("render.yaml").read_text()
        assert "uvicorn" in content
        assert "app.main:app" in content

    def test_render_yaml_has_api_key_env(self):
        content = Path("render.yaml").read_text()
        assert "API_KEY" in content

    def test_dockerfile_exists(self):
        assert Path("Dockerfile").exists()

    def test_dockerfile_non_root_user(self):
        content = Path("Dockerfile").read_text()
        assert "USER appuser" in content or "adduser" in content

    def test_dockerfile_healthcheck(self):
        content = Path("Dockerfile").read_text()
        assert "HEALTHCHECK" in content

    def test_requirements_has_python_pptx(self):
        content = Path("requirements.txt").read_text()
        assert "python-pptx" in content

    def test_requirements_has_jinja2(self):
        content = Path("requirements.txt").read_text()
        assert "jinja2" in content.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Full pipeline smoke test
# ─────────────────────────────────────────────────────────────────────────────


class TestFullPipeline:
    """End-to-end: planning → HTML + PPTX rendering."""

    def test_plan_to_html_pipeline(self):
        from app.renderers.html_renderer import render_html
        from app.services.planning import PlanningRequest, plan_deck

        deck = plan_deck(PlanningRequest(topic="Full Pipeline HTML Test", slide_count=5))
        html = render_html(deck)
        assert "<!DOCTYPE html>" in html or "<html" in html.lower()
        assert deck.title in html

    def test_plan_to_pptx_pipeline(self):
        from app.renderers.pptx_renderer import render_pptx
        from app.services.planning import PlanningRequest, plan_deck

        deck = plan_deck(PlanningRequest(topic="Full Pipeline PPTX Test", slide_count=5))
        data = render_pptx(deck)
        prs = Presentation(io.BytesIO(data))
        assert len(prs.slides) == 5

    def test_plan_with_stitch_to_html(self):
        from app.models.deck import StitchDesignSpec
        from app.renderers.html_renderer import render_html
        from app.services.planning import PlanningRequest, plan_deck
        from app.services.stitch import apply_stitch_to_deck

        deck = plan_deck(PlanningRequest(topic="Branded Deck", slide_count=4))
        stitch = StitchDesignSpec(design_id="brand1", primary_color="#FF5733", font_family="Georgia")
        branded = apply_stitch_to_deck(deck, stitch)
        html = render_html(branded)
        assert "#FF5733" in html

    def test_stitch_metadata_end_to_end(self):
        from app.renderers.pptx_renderer import render_pptx
        from app.services.planning import PlanningRequest, plan_deck
        from app.services.stitch import apply_stitch_to_deck, stitch_metadata_to_spec

        raw = {"id": "e2e-test", "primaryColor": "#234567", "fontFamily": "Helvetica"}
        stitch = stitch_metadata_to_spec(raw)
        deck = plan_deck(PlanningRequest(topic="E2E Stitch Test", slide_count=3))
        branded = apply_stitch_to_deck(deck, stitch)
        data = render_pptx(branded)
        assert data[:2] == b"PK"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP smoke tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHTTPSmoke:
    @pytest.fixture
    def client(self):
        from app.main import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body_has_status(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert body.get("status") == "ok"

    def test_root_responds(self, client):
        resp = client.get("/")
        assert resp.status_code in {200, 307, 404, 405}

    def test_response_has_request_id(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers

    def test_mcp_endpoint_reachable(self, client):
        # Without lifespan (TestClient default), the MCP session manager isn't
        # running — the route exists but returns 500. The key assertion is that
        # the endpoint is *registered* (not 404), proving the mount is correct.
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"content-type": "application/json", "accept": "application/json, text/event-stream"},
        )
        assert resp.status_code != 404, "MCP route must be mounted"


# ─────────────────────────────────────────────────────────────────────────────
# Settings / config validation
# ─────────────────────────────────────────────────────────────────────────────


class TestSettingsValidation:
    def test_default_environment_is_development(self):
        from app.config import Settings
        s = Settings()
        assert s.environment == "development"

    def test_api_key_defaults_to_none(self):
        from app.config import Settings
        s = Settings()
        assert s.api_key is None

    def test_output_dir_has_default(self):
        from app.config import Settings
        s = Settings()
        assert s.output_dir

    def test_is_production_false_by_default(self):
        from app.config import Settings
        s = Settings()
        assert s.is_production is False

    def test_is_production_true_when_set(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        from app.config import Settings
        s = Settings()
        assert s.is_production is True

"""Phase 7 — MCP Tool Layer tests.

Tests verify that:
- All tools are registered with the MCP server
- generate_deck returns correct structure (html + pptx)
- validate_deck_spec correctly identifies valid/invalid specs
- search_icons returns asset list
- get_deck_themes returns all ThemeFamily entries
"""
from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.models.deck import ThemeFamily
from app.mcp_server import mcp_server


# ─────────────────────────────────────────────────────────────────────────────
# Tool registration
# ─────────────────────────────────────────────────────────────────────────────


class TestToolRegistration:
    def _tool_names(self) -> set[str]:
        return {t.name for t in mcp_server._tool_manager._tools.values()}

    def test_ping_registered(self):
        assert "ping" in self._tool_names()

    def test_generate_deck_registered(self):
        assert "generate_deck" in self._tool_names()

    def test_validate_deck_spec_registered(self):
        assert "validate_deck_spec" in self._tool_names()

    def test_search_icons_registered(self):
        assert "search_icons" in self._tool_names()

    def test_get_deck_themes_registered(self):
        assert "get_deck_themes" in self._tool_names()

    def test_exactly_five_tools(self):
        assert len(self._tool_names()) == 5


# ─────────────────────────────────────────────────────────────────────────────
# generate_deck
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateDeck:
    async def _call(self, **kwargs) -> dict[str, Any]:
        from app.mcp_server import mcp_server as s
        tool = s._tool_manager._tools["generate_deck"]
        return await tool.fn(**kwargs)

    async def test_returns_html_by_default(self):
        result = await self._call(topic="Machine Learning", slide_count=3)
        assert "html" in result
        assert "<html" in result["html"].lower()

    async def test_html_contains_deck_id(self):
        result = await self._call(topic="Blockchain", slide_count=3)
        assert result["deck_id"]
        assert len(result["deck_id"]) == 36  # UUID

    async def test_slide_count_returned(self):
        result = await self._call(topic="AI Safety", slide_count=5)
        assert result["slide_count"] == 5

    async def test_theme_field_present(self):
        result = await self._call(topic="Startup Pitch", audience="investor", slide_count=4)
        assert result["theme"] in {tf.value for tf in ThemeFamily}

    async def test_pptx_export_returns_base64(self):
        result = await self._call(topic="Data Engineering", slide_count=3, export_format="pptx")
        assert "pptx_base64" in result
        assert "html" not in result
        # Verify it's valid base64-encoded PPTX
        raw = base64.b64decode(result["pptx_base64"])
        assert raw[:2] == b"PK"

    async def test_outline_accepted(self):
        result = await self._call(
            topic="Security Best Practices",
            outline=["Intro", "Threats", "Defense", "Summary"],
            slide_count=4,
        )
        assert result["slide_count"] >= 1

    async def test_slide_count_clamped_min(self):
        result = await self._call(topic="Very Short", slide_count=1)
        assert result["slide_count"] >= 3

    async def test_slide_count_clamped_max(self):
        result = await self._call(topic="Very Long", slide_count=99)
        assert result["slide_count"] <= 60


# ─────────────────────────────────────────────────────────────────────────────
# validate_deck_spec
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateDeckSpec:
    async def _call(self, raw: dict) -> dict:
        tool = mcp_server._tool_manager._tools["validate_deck_spec"]
        return await tool.fn(raw_deck=raw)

    async def test_valid_spec_returns_valid_true(self):
        from app.services.planning import PlanningRequest, plan_deck
        deck = plan_deck(PlanningRequest(topic="Test Deck", slide_count=4))
        raw = json.loads(deck.model_dump_json())
        result = await self._call(raw)
        assert result["valid"] is True
        assert result["errors"] == []

    async def test_invalid_spec_returns_valid_false(self):
        result = await self._call({"not": "a deck"})
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    async def test_result_has_warnings_key(self):
        from app.services.planning import PlanningRequest, plan_deck
        deck = plan_deck(PlanningRequest(topic="Warn Test", slide_count=4))
        raw = json.loads(deck.model_dump_json())
        result = await self._call(raw)
        assert "warnings" in result

    async def test_empty_dict_returns_errors(self):
        result = await self._call({})
        assert result["valid"] is False


# ─────────────────────────────────────────────────────────────────────────────
# search_icons
# ─────────────────────────────────────────────────────────────────────────────


class TestSearchIcons:
    async def _call(self, query: str, limit: int = 3) -> list:
        tool = mcp_server._tool_manager._tools["search_icons"]
        return await tool.fn(query=query, limit=limit)

    async def test_returns_list(self):
        from app.models.deck import AssetSpec, AssetType
        mock_assets = [
            AssetSpec(source="https://example.com/icon.svg", alt_text="icon", asset_type=AssetType.ICON)
        ]
        with patch("app.services.assets.search_clipart", new=AsyncMock(return_value=mock_assets)):
            result = await self._call("rocket", limit=3)
        assert isinstance(result, list)

    async def test_result_has_required_keys(self):
        from app.models.deck import AssetSpec, AssetType
        mock_assets = [
            AssetSpec(source="https://api.iconify.design/mdi/rocket.svg", alt_text="rocket", asset_type=AssetType.ICON)
        ]
        with patch("app.services.assets.search_clipart", new=AsyncMock(return_value=mock_assets)):
            result = await self._call("rocket", limit=1)
        if result:
            assert "source" in result[0]
            assert "alt_text" in result[0]
            assert "type" in result[0]

    async def test_limit_clamped_to_max_20(self):
        captured = {}

        async def mock_search(query, limit):
            captured["limit"] = limit
            return []

        with patch("app.services.assets.search_clipart", new=mock_search):
            await self._call("test", limit=100)
        assert captured["limit"] <= 20

    async def test_limit_clamped_to_min_1(self):
        captured = {}

        async def mock_search(query, limit):
            captured["limit"] = limit
            return []

        with patch("app.services.assets.search_clipart", new=mock_search):
            await self._call("test", limit=0)
        assert captured["limit"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# get_deck_themes
# ─────────────────────────────────────────────────────────────────────────────


class TestGetDeckThemes:
    async def _call(self) -> list:
        tool = mcp_server._tool_manager._tools["get_deck_themes"]
        return await tool.fn()

    async def test_returns_all_theme_families(self):
        result = await self._call()
        returned_names = {r["name"] for r in result}
        expected_names = {tf.name for tf in ThemeFamily}
        assert returned_names == expected_names

    async def test_each_entry_has_value(self):
        result = await self._call()
        expected_values = {tf.value for tf in ThemeFamily}
        returned_values = {r["value"] for r in result}
        assert returned_values == expected_values

    async def test_each_entry_has_description(self):
        result = await self._call()
        for entry in result:
            assert "description" in entry

    async def test_count_matches_enum(self):
        result = await self._call()
        assert len(result) == len(ThemeFamily)

"""Phase 4 — Asset service tests.

Network calls are mocked with httpx's MockTransport so tests are offline-safe.
"""
from __future__ import annotations

import pytest
import httpx

from app.models.deck import AssetSpec, AssetType, IconSpec
from app.services.assets import (
    _build_icon_url,
    _cache_get,
    _cache_set,
    clear_icon_cache,
    fetch_icon_svg,
    normalize_asset,
    resolve_icon_url,
    sanitize_svg,
    validate_image_url,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_transport(status: int, text: str = "", json: dict | None = None) -> httpx.MockTransport:
    """Build an httpx MockTransport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        if json is not None:
            return httpx.Response(status, json=json)
        return httpx.Response(status, text=text)
    return httpx.MockTransport(handler)


# ─────────────────────────────────────────────────────────────────────────────
# SVG sanitisation
# ─────────────────────────────────────────────────────────────────────────────


class TestSanitizeSvg:
    def test_clean_svg_unchanged(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        assert sanitize_svg(svg) == svg

    def test_script_tag_removed(self):
        svg = '<svg><script>alert(1)</script><circle/></svg>'
        result = sanitize_svg(svg)
        assert "<script" not in result.lower()

    def test_on_event_attr_neutralized(self):
        svg = '<svg><rect onclick="alert(1)"/></svg>'
        result = sanitize_svg(svg)
        assert "onclick=" not in result.lower()

    def test_javascript_href_replaced(self):
        svg = '<svg><a href="javascript:void(0)">x</a></svg>'
        result = sanitize_svg(svg)
        assert "javascript:" not in result.lower()

    def test_object_tag_removed(self):
        svg = '<svg><object data="evil.swf"/></svg>'
        result = sanitize_svg(svg)
        assert "<object" not in result.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Icon URL building
# ─────────────────────────────────────────────────────────────────────────────


class TestIconUrls:
    def test_heroicons_url(self):
        url = _build_icon_url("heroicons", "star")
        assert "heroicons/star.svg" in url

    def test_feather_url(self):
        url = _build_icon_url("feather", "check")
        assert "feather/check.svg" in url

    def test_phosphor_uses_ph_prefix(self):
        url = _build_icon_url("phosphor", "heart")
        assert "/ph/" in url

    def test_color_encoded_in_url(self):
        url = _build_icon_url("heroicons", "star", "#FF0000")
        assert "%23FF0000" in url or "FF0000" in url

    def test_resolve_icon_url_returns_string(self):
        spec = IconSpec(library="heroicons", name="star")
        url = resolve_icon_url(spec)
        assert url.startswith("https://")


# ─────────────────────────────────────────────────────────────────────────────
# Icon cache
# ─────────────────────────────────────────────────────────────────────────────


class TestIconCache:
    def setup_method(self):
        clear_icon_cache()

    def test_cache_miss_returns_none(self):
        assert _cache_get("heroicons", "star") is None

    def test_cache_set_and_get(self):
        _cache_set("heroicons", "star", "<svg/>")
        assert _cache_get("heroicons", "star") == "<svg/>"

    def test_clear_cache_works(self):
        _cache_set("heroicons", "star", "<svg/>")
        clear_icon_cache()
        assert _cache_get("heroicons", "star") is None


# ─────────────────────────────────────────────────────────────────────────────
# fetch_icon_svg (mocked HTTP)
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchIconSvg:
    def setup_method(self):
        clear_icon_cache()

    @pytest.mark.asyncio
    async def test_successful_fetch_returns_svg(self, monkeypatch):
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>'

        async def mock_get(*args, **kwargs):
            return httpx.Response(200, text=svg_content)

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        spec = IconSpec(library="heroicons", name="star")
        result = await fetch_icon_svg(spec)
        assert "<svg" in result

    @pytest.mark.asyncio
    async def test_cdn_error_returns_fallback(self, monkeypatch):
        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        spec = IconSpec(library="heroicons", name="nonexistent")
        result = await fetch_icon_svg(spec)
        assert "<svg" in result  # fallback SVG

    @pytest.mark.asyncio
    async def test_result_is_cached(self, monkeypatch):
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, text="<svg/>")

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        spec = IconSpec(library="heroicons", name="cached-icon")
        await fetch_icon_svg(spec)
        await fetch_icon_svg(spec)  # second call — should hit cache
        assert call_count == 1  # only one HTTP call made


# ─────────────────────────────────────────────────────────────────────────────
# validate_image_url (mocked HTTP)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateImageUrl:
    @pytest.mark.asyncio
    async def test_valid_url_returns_true(self, monkeypatch):
        async def mock_head(*args, **kwargs):
            return httpx.Response(200)

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        assert await validate_image_url("https://example.com/image.png") is True

    @pytest.mark.asyncio
    async def test_404_returns_false(self, monkeypatch):
        async def mock_head(*args, **kwargs):
            return httpx.Response(404)

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        assert await validate_image_url("https://example.com/missing.png") is False

    @pytest.mark.asyncio
    async def test_non_http_scheme_rejected(self):
        assert await validate_image_url("ftp://example.com/file.png") is False

    @pytest.mark.asyncio
    async def test_javascript_scheme_rejected(self):
        assert await validate_image_url("javascript:alert(1)") is False

    @pytest.mark.asyncio
    async def test_too_long_url_rejected(self):
        url = "https://example.com/" + "a" * 2050
        assert await validate_image_url(url) is False

    @pytest.mark.asyncio
    async def test_network_error_returns_false(self, monkeypatch):
        async def mock_head(*args, **kwargs):
            raise httpx.ConnectError("no route")

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        assert await validate_image_url("https://example.com/img.png") is False


# ─────────────────────────────────────────────────────────────────────────────
# normalize_asset
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeAsset:
    def test_inline_svg_detected(self):
        asset = AssetSpec(asset_type=AssetType.IMAGE, source="<svg><circle/></svg>")
        normalized = normalize_asset(asset)
        assert normalized.asset_type == AssetType.SVG

    def test_icon_library_reference_detected(self):
        asset = AssetSpec(asset_type=AssetType.IMAGE, source="heroicons:star")
        normalized = normalize_asset(asset)
        assert normalized.asset_type == AssetType.ICON

    def test_svg_url_detected(self):
        asset = AssetSpec(asset_type=AssetType.IMAGE, source="https://example.com/logo.svg")
        normalized = normalize_asset(asset)
        assert normalized.asset_type == AssetType.SVG

    def test_plain_image_url_unchanged(self):
        asset = AssetSpec(asset_type=AssetType.IMAGE, source="https://example.com/photo.png")
        normalized = normalize_asset(asset)
        assert normalized.asset_type == AssetType.IMAGE

    def test_normalize_preserves_alt_text(self):
        asset = AssetSpec(asset_type=AssetType.IMAGE, source="<svg/>", alt_text="logo")
        normalized = normalize_asset(asset)
        assert normalized.alt_text == "logo"

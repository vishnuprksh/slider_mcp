"""Phase 8 — Stitch Integration tests."""
from __future__ import annotations

import pytest

from app.models.deck import (
    ColorPaletteSpec,
    DeckSpec,
    StitchDesignSpec,
    ThemeFamily,
    ThemeSpec,
    TypographySpec,
)
from app.services.planning import PlanningRequest, plan_deck
from app.services.stitch import (
    _contrast_color,
    _is_valid_hex,
    _normalise_hex,
    apply_stitch_to_deck,
    stitch_metadata_to_spec,
    stitch_to_theme,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_is_valid_hex_6_char(self):
        assert _is_valid_hex("#2563EB")

    def test_is_valid_hex_3_char(self):
        assert _is_valid_hex("#FFF")

    def test_is_valid_hex_without_hash(self):
        assert _is_valid_hex("FF0000")

    def test_is_valid_hex_none(self):
        assert not _is_valid_hex(None)

    def test_is_valid_hex_invalid_chars(self):
        assert not _is_valid_hex("#GGGGGG")

    def test_is_valid_hex_empty(self):
        assert not _is_valid_hex("")

    def test_normalise_hex_adds_hash(self):
        assert _normalise_hex("2563EB") == "#2563EB"

    def test_normalise_hex_keeps_hash(self):
        assert _normalise_hex("#2563EB") == "#2563EB"

    def test_contrast_dark_bg_returns_white(self):
        assert _contrast_color("#0F172A") == "#FFFFFF"

    def test_contrast_light_bg_returns_dark(self):
        assert _contrast_color("#FFFFFF") == "#0F172A"

    def test_contrast_mid_luminance(self):
        # Red ~128 luminance boundary — just ensure it returns one of the two values
        result = _contrast_color("#800000")
        assert result in {"#FFFFFF", "#0F172A"}


# ─────────────────────────────────────────────────────────────────────────────
# stitch_to_theme
# ─────────────────────────────────────────────────────────────────────────────


class TestStitchToTheme:
    def _stitch(self, **kwargs) -> StitchDesignSpec:
        return StitchDesignSpec(design_id="test", **kwargs)

    def test_returns_theme_spec(self):
        spec = self._stitch(primary_color="#FF5733")
        result = stitch_to_theme(spec)
        assert isinstance(result, ThemeSpec)

    def test_primary_color_applied(self):
        spec = self._stitch(primary_color="#FF5733")
        result = stitch_to_theme(spec)
        assert result.colors.primary == "#FF5733"

    def test_secondary_color_applied(self):
        spec = self._stitch(secondary_color="#10B981")
        result = stitch_to_theme(spec)
        assert result.colors.secondary == "#10B981"

    def test_invalid_primary_falls_back_to_base(self):
        from app.services.stitch import _default_theme
        base = _default_theme()
        spec = self._stitch(primary_color="not-a-color")
        result = stitch_to_theme(spec)
        assert result.colors.primary == base.colors.primary

    def test_font_family_applied_to_heading(self):
        spec = self._stitch(font_family="Georgia")
        result = stitch_to_theme(spec)
        assert result.typography.heading_font == "Georgia"

    def test_font_family_applied_to_body(self):
        spec = self._stitch(font_family="Verdana")
        result = stitch_to_theme(spec)
        assert result.typography.font_family == "Verdana"

    def test_no_font_preserves_base(self):
        from app.services.stitch import _default_theme
        base = _default_theme()
        spec = self._stitch()
        result = stitch_to_theme(spec)
        assert result.typography.heading_font == base.typography.heading_font

    def test_text_on_primary_auto_computed(self):
        # Dark primary → white text
        spec = self._stitch(primary_color="#0F172A")
        result = stitch_to_theme(spec)
        assert result.colors.text_on_primary == "#FFFFFF"

    def test_base_theme_border_radius_preserved(self):
        from app.services.stitch import _default_theme
        base = _default_theme()
        spec = self._stitch()
        result = stitch_to_theme(spec, base_theme=base)
        assert result.border_radius == base.border_radius

    def test_custom_base_theme_used(self):
        from app.services.planning import PlanningRequest, select_theme
        tech_theme = select_theme(PlanningRequest(topic="tech", audience="developer"))
        spec = self._stitch()
        result = stitch_to_theme(spec, base_theme=tech_theme)
        assert result.family == ThemeFamily.TECH


# ─────────────────────────────────────────────────────────────────────────────
# apply_stitch_to_deck
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyStitchToDeck:
    def _deck(self) -> DeckSpec:
        return plan_deck(PlanningRequest(topic="Stitch Test", slide_count=3))

    def test_returns_deck_spec(self):
        deck = self._deck()
        stitch = StitchDesignSpec(design_id="d1", primary_color="#FF5733")
        result = apply_stitch_to_deck(deck, stitch)
        assert isinstance(result, DeckSpec)

    def test_primary_color_updated(self):
        deck = self._deck()
        stitch = StitchDesignSpec(design_id="d1", primary_color="#FF5733")
        result = apply_stitch_to_deck(deck, stitch)
        assert result.theme.colors.primary == "#FF5733"

    def test_original_deck_not_mutated(self):
        deck = self._deck()
        original_primary = deck.theme.colors.primary
        stitch = StitchDesignSpec(design_id="d1", primary_color="#AA0000")
        apply_stitch_to_deck(deck, stitch)
        assert deck.theme.colors.primary == original_primary

    def test_slides_preserved(self):
        deck = self._deck()
        stitch = StitchDesignSpec(design_id="d1", primary_color="#123456")
        result = apply_stitch_to_deck(deck, stitch)
        assert len(result.slides) == len(deck.slides)


# ─────────────────────────────────────────────────────────────────────────────
# stitch_metadata_to_spec
# ─────────────────────────────────────────────────────────────────────────────


class TestStitchMetadataToSpec:
    def test_parses_camelCase_keys(self):
        spec = stitch_metadata_to_spec({"id": "s1", "primaryColor": "#1234AB", "fontFamily": "Arial"})
        assert spec.primary_color == "#1234AB"
        assert spec.font_family == "Arial"

    def test_parses_snake_case_keys(self):
        spec = stitch_metadata_to_spec({"design_id": "s2", "primary_color": "#AABBCC"})
        assert spec.primary_color == "#AABBCC"

    def test_parses_nested_colors(self):
        spec = stitch_metadata_to_spec({"colors": {"primary": "#001122", "secondary": "#334455"}})
        assert spec.primary_color == "#001122"
        assert spec.secondary_color == "#334455"

    def test_logo_url_extracted(self):
        spec = stitch_metadata_to_spec({"logoUrl": "https://example.com/logo.png"})
        assert spec.logo_url == "https://example.com/logo.png"

    def test_raw_metadata_preserved(self):
        raw = {"id": "x", "customKey": "value"}
        spec = stitch_metadata_to_spec(raw)
        assert spec.raw_metadata == raw

    def test_design_id_fallback(self):
        spec = stitch_metadata_to_spec({})
        assert spec.design_id == "stitch-import"

    def test_returns_stitch_design_spec(self):
        spec = stitch_metadata_to_spec({"id": "abc"})
        assert isinstance(spec, StitchDesignSpec)

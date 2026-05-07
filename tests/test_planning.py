"""Phase 3 — Planning engine tests."""
from __future__ import annotations

import pytest

from app.models.deck import (
    AspectRatio,
    DeckSpec,
    SlideLayout,
    SlideRole,
    ThemeFamily,
)
from app.services.planning import (
    PlanningRequest,
    _assign_layouts,
    _infer_theme_family,
    plan_deck,
    select_theme,
)
from app.services.validation import validate_deck


# ─────────────────────────────────────────────────────────────────────────────
# _assign_layouts
# ─────────────────────────────────────────────────────────────────────────────


class TestAssignLayouts:
    def test_always_starts_with_title(self):
        for n in range(3, 12):
            layouts = _assign_layouts(n)
            assert layouts[0] == SlideLayout.TITLE

    def test_always_ends_with_closing(self):
        for n in range(3, 12):
            layouts = _assign_layouts(n)
            assert layouts[-1] == SlideLayout.CLOSING

    def test_exact_slide_count(self):
        for n in range(3, 16):
            layouts = _assign_layouts(n)
            assert len(layouts) == n

    def test_agenda_present_for_4plus(self):
        layouts = _assign_layouts(6)
        assert SlideLayout.BULLETS in layouts[:3]

    def test_section_break_for_6plus(self):
        layouts = _assign_layouts(7)
        assert SlideLayout.SECTION_BREAK in layouts

    def test_no_consecutive_duplicates(self):
        layouts = _assign_layouts(12)
        for i in range(1, len(layouts)):
            if layouts[i] in {SlideLayout.TITLE, SlideLayout.CLOSING}:
                continue
            assert layouts[i] != layouts[i - 1], (
                f"Consecutive duplicates at {i}: {layouts[i]}"
            )

    def test_minimum_3_slides(self):
        req = PlanningRequest(topic="Test", slide_count=1)
        assert req.slide_count == 3  # clamped in __post_init__


# ─────────────────────────────────────────────────────────────────────────────
# Theme selection
# ─────────────────────────────────────────────────────────────────────────────


class TestThemeSelection:
    def test_explicit_theme_respected(self):
        req = PlanningRequest(topic="T", theme_family=ThemeFamily.DARK)
        theme = select_theme(req)
        assert theme.family == ThemeFamily.DARK

    def test_investor_audience_gets_corporate(self):
        family = _infer_theme_family("investor", "pitch", "Series A")
        assert family == ThemeFamily.CORPORATE

    def test_startup_purpose_gets_startup(self):
        family = _infer_theme_family("general", "pitch", "my app")
        assert family == ThemeFamily.STARTUP

    def test_developer_audience_gets_tech(self):
        family = _infer_theme_family("developer", "demo", "API")
        assert family == ThemeFamily.TECH

    def test_nature_topic_gets_nature(self):
        family = _infer_theme_family("general", "inform", "sustainability")
        assert family == ThemeFamily.NATURE

    def test_unknown_keywords_fall_back_to_corporate(self):
        family = _infer_theme_family("xyz", "abc", "foo")
        assert family == ThemeFamily.CORPORATE

    def test_theme_colors_valid(self):
        for family in ThemeFamily:
            req = PlanningRequest(topic="Test", theme_family=family)
            theme = select_theme(req)
            assert theme.colors.primary.startswith("#")


# ─────────────────────────────────────────────────────────────────────────────
# plan_deck — integration
# ─────────────────────────────────────────────────────────────────────────────


class TestPlanDeck:
    def test_returns_deck_spec(self):
        req = PlanningRequest(topic="AI in Healthcare", slide_count=8)
        deck = plan_deck(req)
        assert isinstance(deck, DeckSpec)

    def test_slide_count_matches_request(self):
        for n in (3, 5, 8, 12):
            req = PlanningRequest(topic="Topic", slide_count=n)
            deck = plan_deck(req)
            assert len(deck.slides) == n

    def test_first_slide_is_cover(self):
        req = PlanningRequest(topic="Test")
        deck = plan_deck(req)
        assert deck.slides[0].role == SlideRole.COVER

    def test_last_slide_is_closing(self):
        req = PlanningRequest(topic="Test", slide_count=6)
        deck = plan_deck(req)
        assert deck.slides[-1].role == SlideRole.CLOSING

    def test_deck_title_matches_topic(self):
        req = PlanningRequest(topic="Quantum Computing for Beginners")
        deck = plan_deck(req)
        assert deck.title == "Quantum Computing for Beginners"

    def test_audience_propagated(self):
        req = PlanningRequest(topic="T", audience="engineering leadership")
        deck = plan_deck(req)
        assert deck.audience == "engineering leadership"

    def test_outline_overrides_slide_titles(self):
        outline = ["Introduction", "Problem Statement", "Our Solution", "Next Steps"]
        req = PlanningRequest(topic="Product Launch", slide_count=5, outline=outline)
        deck = plan_deck(req)
        # Outline titles should appear in slide titles
        assert deck.slides[0].title == "Introduction"
        assert deck.slides[1].title == "Problem Statement"

    def test_theme_selected_by_audience(self):
        req = PlanningRequest(topic="API Docs", audience="developer", slide_count=5)
        deck = plan_deck(req)
        assert deck.theme.family == ThemeFamily.TECH

    def test_aspect_ratio_propagated(self):
        req = PlanningRequest(topic="T", aspect_ratio=AspectRatio.STANDARD)
        deck = plan_deck(req)
        assert deck.aspect_ratio == AspectRatio.STANDARD

    def test_author_in_metadata(self):
        req = PlanningRequest(topic="T", author="Alice", organization="Acme")
        deck = plan_deck(req)
        assert deck.metadata.author == "Alice"
        assert deck.metadata.organization == "Acme"

    def test_planned_deck_passes_schema_validation(self):
        req = PlanningRequest(topic="Business Review", audience="executive", slide_count=8)
        deck = plan_deck(req)
        # Should not raise
        raw = deck.model_dump()
        restored = DeckSpec.model_validate(raw)
        assert len(restored.slides) == 8

    def test_planned_deck_passes_business_validation(self):
        req = PlanningRequest(topic="Year in Review", audience="board", slide_count=10)
        deck = plan_deck(req)
        result = validate_deck(deck)
        # Planning engine output should have no blocking errors
        assert result.valid, [e.message for e in result.errors]

    def test_slide_content_blocks_scaffolded(self):
        req = PlanningRequest(topic="Metrics", slide_count=6)
        deck = plan_deck(req)
        # At least some slides should have content blocks
        total_blocks = sum(len(s.content_blocks) for s in deck.slides)
        assert total_blocks > 0

    def test_serialization_roundtrip(self):
        req = PlanningRequest(topic="Roundtrip Test", slide_count=6)
        deck = plan_deck(req)
        raw = deck.model_dump()
        restored = DeckSpec.model_validate(raw)
        assert restored.id == deck.id

    def test_layout_diversity_in_8_slides(self):
        req = PlanningRequest(topic="Diversity Test", slide_count=8)
        deck = plan_deck(req)
        layouts = [s.layout.layout for s in deck.slides]
        unique_layouts = set(layouts)
        assert len(unique_layouts) >= 3, f"Only {len(unique_layouts)} unique layouts: {layouts}"

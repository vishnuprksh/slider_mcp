"""Phase 2 — Deck domain model tests.

Tests cover:
- Schema validation for all model types
- Invalid payload rejection
- Discriminated union deserialization
- Business rule validators in the validation service
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.deck import (
    AspectRatio,
    AssetSpec,
    AssetType,
    BulletListBlock,
    ColorPaletteSpec,
    ContentBlockType,
    DeckMetadata,
    DeckSpec,
    IconSpec,
    ImageBlock,
    LayoutSpec,
    QuoteBlock,
    SlideLayout,
    SlideRole,
    SlideSpec,
    StatBlock,
    StitchDesignSpec,
    TextBlock,
    ThemeFamily,
    ThemeSpec,
)
from app.services.validation import (
    ValidationResult,
    parse_and_validate_deck,
    validate_deck,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def make_text_block(text: str = "Hello world") -> TextBlock:
    return TextBlock(text=text)


def make_image_block() -> ImageBlock:
    return ImageBlock(asset=AssetSpec(asset_type=AssetType.IMAGE, source="https://example.com/img.png"))


def make_slide(
    title: str = "My Slide",
    layout: SlideLayout = SlideLayout.TWO_COLUMN,
    role: SlideRole = SlideRole.CONTENT,
) -> SlideSpec:
    return SlideSpec(
        title=title,
        role=role,
        layout=LayoutSpec(layout=layout),
        content_blocks=[make_text_block(), make_image_block()],
    )


def make_deck(num_slides: int = 5, **kwargs) -> DeckSpec:
    slides = [
        make_slide(title=f"Slide {i+1}", role=SlideRole.COVER if i == 0 else SlideRole.CONTENT)
        for i in range(num_slides)
    ]
    slides[-1] = make_slide(title="Thank You", role=SlideRole.CLOSING)
    return DeckSpec(title="Test Deck", slides=slides, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# ThemeSpec
# ─────────────────────────────────────────────────────────────────────────────


class TestThemeSpec:
    def test_default_theme_valid(self):
        t = ThemeSpec()
        assert t.family == ThemeFamily.CORPORATE
        assert t.colors.primary == "#2563EB"

    def test_custom_colors_accepted(self):
        t = ThemeSpec(colors=ColorPaletteSpec(primary="#FF0000", background="#000000"))
        assert t.colors.primary == "#FF0000"

    def test_invalid_hex_color_rejected(self):
        with pytest.raises(ValidationError):
            ColorPaletteSpec(primary="#GGGGGG")

    def test_short_hex_valid(self):
        c = ColorPaletteSpec(primary="#FFF")
        assert c.primary == "#FFF"

    def test_rgb_color_accepted(self):
        c = ColorPaletteSpec(primary="rgb(255, 0, 0)")
        assert c.primary == "rgb(255, 0, 0)"

    def test_border_radius_range(self):
        t = ThemeSpec(border_radius=0)
        assert t.border_radius == 0
        with pytest.raises(ValidationError):
            ThemeSpec(border_radius=100)


# ─────────────────────────────────────────────────────────────────────────────
# LayoutSpec
# ─────────────────────────────────────────────────────────────────────────────


class TestLayoutSpec:
    def test_two_column_valid_ratios(self):
        ls = LayoutSpec(layout=SlideLayout.TWO_COLUMN, column_ratios=[60, 40])
        assert ls.column_ratios == [60, 40]

    def test_two_column_invalid_ratios(self):
        with pytest.raises(ValidationError):
            LayoutSpec(layout=SlideLayout.TWO_COLUMN, column_ratios=[50, 40])

    def test_three_column_must_sum_to_100(self):
        LayoutSpec(layout=SlideLayout.THREE_COLUMN, column_ratios=[33, 33, 34])
        with pytest.raises(ValidationError):
            LayoutSpec(layout=SlideLayout.THREE_COLUMN, column_ratios=[33, 33, 33])

    def test_single_layout_ignores_ratios(self):
        # TITLE layout doesn't enforce column ratios
        ls = LayoutSpec(layout=SlideLayout.TITLE)
        assert ls is not None


# ─────────────────────────────────────────────────────────────────────────────
# ContentBlock discriminated union
# ─────────────────────────────────────────────────────────────────────────────


class TestContentBlocks:
    def test_text_block_discriminator(self):
        raw = {"block_type": "text", "text": "Hello"}
        block = TextBlock.model_validate(raw)
        assert block.block_type == ContentBlockType.TEXT

    def test_bullet_list_min_items(self):
        with pytest.raises(ValidationError):
            BulletListBlock(items=[])

    def test_bullet_list_max_items(self):
        with pytest.raises(ValidationError):
            BulletListBlock(items=[f"item {i}" for i in range(10)])

    def test_stat_block_valid(self):
        sb = StatBlock(value="98%", label="Uptime")
        assert sb.value == "98%"

    def test_quote_block_min_length(self):
        with pytest.raises(ValidationError):
            QuoteBlock(text="Hi")  # too short

    def test_image_block_with_asset(self):
        block = ImageBlock(
            asset=AssetSpec(asset_type=AssetType.SVG, source="inline:<svg/>")
        )
        assert block.asset.asset_type == AssetType.SVG

    def test_icon_spec_defaults(self):
        icon = IconSpec(name="star")
        assert icon.library == "heroicons"
        assert icon.size == 48


# ─────────────────────────────────────────────────────────────────────────────
# SlideSpec
# ─────────────────────────────────────────────────────────────────────────────


class TestSlideSpec:
    def test_slide_valid(self):
        slide = make_slide()
        assert slide.id  # IdentifiedModel gives a UUID

    def test_placeholder_title_rejected(self):
        with pytest.raises(ValidationError):
            make_slide(title="Slide Title")

    def test_slide_max_content_blocks(self):
        with pytest.raises(ValidationError):
            SlideSpec(
                title="Many Blocks",
                layout=LayoutSpec(layout=SlideLayout.BLANK),
                content_blocks=[make_text_block() for _ in range(21)],
            )

    def test_speaker_notes_optional(self):
        slide = make_slide()
        slide2 = SlideSpec(
            title="With Notes",
            layout=LayoutSpec(layout=SlideLayout.TITLE),
            speaker_notes="Remember to pause here.",
        )
        assert slide2.speaker_notes == "Remember to pause here."


# ─────────────────────────────────────────────────────────────────────────────
# DeckSpec
# ─────────────────────────────────────────────────────────────────────────────


class TestDeckSpec:
    def test_valid_deck(self):
        deck = make_deck(5)
        assert len(deck.slides) == 5
        assert deck.aspect_ratio == AspectRatio.WIDESCREEN

    def test_empty_slides_rejected(self):
        with pytest.raises(ValidationError):
            DeckSpec(title="Empty", slides=[])

    def test_too_many_slides_rejected(self):
        with pytest.raises(ValidationError):
            DeckSpec(title="Huge", slides=[make_slide(title=f"S{i}") for i in range(101)])

    def test_empty_export_formats_rejected(self):
        with pytest.raises(ValidationError):
            DeckSpec(title="No export", slides=[make_slide()], export_formats=[])

    def test_metadata_fields(self):
        deck = make_deck(3, metadata=DeckMetadata(author="Alice", organization="Acme"))
        assert deck.metadata.author == "Alice"

    def test_serialization_roundtrip(self):
        deck = make_deck(3)
        raw = deck.model_dump()
        restored = DeckSpec.model_validate(raw)
        assert restored.id == deck.id
        assert len(restored.slides) == 3


# ─────────────────────────────────────────────────────────────────────────────
# ValidationService
# ─────────────────────────────────────────────────────────────────────────────


class TestValidationService:
    def test_valid_deck_passes(self):
        deck = make_deck(5)
        result = validate_deck(deck)
        assert result.valid
        assert not result.errors

    def test_few_slides_warning(self):
        deck = make_deck(2)
        result = validate_deck(deck)
        # Should warn about slide count but not error
        assert result.valid
        assert any("slide" in w.message.lower() for w in result.warnings)

    def test_bullet_heavy_deck_warns(self):
        slides = [
            SlideSpec(
                title=f"Bullet slide {i}",
                role=SlideRole.CONTENT,
                layout=LayoutSpec(layout=SlideLayout.BULLETS),
                content_blocks=[BulletListBlock(items=["a", "b"])],
            )
            for i in range(6)
        ]
        deck = DeckSpec(title="Bullets Everywhere", slides=slides)
        result = validate_deck(deck)
        assert any("bullet" in w.message.lower() for w in result.warnings)

    def test_repeated_layout_warns(self):
        slides = [
            make_slide(title=f"S{i}", layout=SlideLayout.BULLETS)
            for i in range(6)
        ]
        deck = DeckSpec(title="Monotone", slides=slides)
        result = validate_deck(deck)
        assert any("repeated" in w.message.lower() for w in result.warnings)

    def test_duplicate_titles_warn(self):
        slides = [
            make_slide(title="Same Title"),
            make_slide(title="Same Title"),
            make_slide(title="Other Title"),
        ]
        deck = DeckSpec(title="Dupe Titles", slides=slides)
        result = validate_deck(deck)
        assert any("duplicate" in w.message.lower() for w in result.warnings)

    def test_invisible_text_is_error(self):
        theme = ThemeSpec(
            colors=ColorPaletteSpec(text_primary="#FFFFFF", background="#FFFFFF")
        )
        deck = make_deck(3, theme=theme)
        result = validate_deck(deck)
        assert not result.valid
        assert any("invisible" in e.message.lower() for e in result.errors)

    def test_parse_and_validate_from_dict(self):
        raw = make_deck(3).model_dump()
        deck, result = parse_and_validate_deck(raw)
        assert isinstance(deck, DeckSpec)
        assert result.valid

    def test_parse_invalid_dict_raises(self):
        with pytest.raises(Exception):
            parse_and_validate_deck({"title": ""})  # empty title

    def test_text_wall_slide_warns(self):
        text_heavy_slide = SlideSpec(
            title="Text Wall",
            role=SlideRole.CONTENT,
            layout=LayoutSpec(layout=SlideLayout.BULLETS),
            content_blocks=[
                TextBlock(text=f"paragraph {i}") for i in range(4)
            ],
        )
        deck = DeckSpec(title="Wordy", slides=[text_heavy_slide])
        result = validate_deck(deck)
        assert any("visual" in w.message.lower() for w in result.warnings)


# ─────────────────────────────────────────────────────────────────────────────
# StitchDesignSpec
# ─────────────────────────────────────────────────────────────────────────────


class TestStitchDesignSpec:
    def test_minimal_stitch_spec(self):
        spec = StitchDesignSpec(design_id="ds-001")
        assert spec.design_id == "ds-001"
        assert spec.raw_metadata == {}

    def test_full_stitch_spec(self):
        spec = StitchDesignSpec(
            design_id="ds-002",
            primary_color="#FF5733",
            font_family="Roboto",
            logo_url="https://example.com/logo.svg",
            raw_metadata={"brand_kit": "v2"},
        )
        assert spec.raw_metadata["brand_kit"] == "v2"

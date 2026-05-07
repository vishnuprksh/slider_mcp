"""Stitch Design System Integration.

Translates a StitchDesignSpec (design tokens from a Stitch project) into
a ThemeSpec that can be applied to a DeckSpec. Falls back gracefully when
tokens are absent or invalid.
"""
from __future__ import annotations

import re

from app.models.deck import (
    ColorPaletteSpec,
    DeckSpec,
    StitchDesignSpec,
    ThemeFamily,
    ThemeSpec,
    TypographySpec,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?$")


def _is_valid_hex(color: str | None) -> bool:
    if not color:
        return False
    return bool(_HEX_RE.match(color.strip()))


def _normalise_hex(color: str) -> str:
    """Ensure the color is prefixed with #."""
    color = color.strip()
    return color if color.startswith("#") else f"#{color}"


def _contrast_color(hex_color: str) -> str:
    """Return #FFFFFF or #0F172A depending on luminance of the given hex color."""
    c = hex_color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return "#FFFFFF" if luminance < 128 else "#0F172A"
    except (ValueError, IndexError):
        return "#FFFFFF"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def stitch_to_theme(stitch: StitchDesignSpec, base_theme: ThemeSpec | None = None) -> ThemeSpec:
    """Convert a StitchDesignSpec to a ThemeSpec.

    Applies available design tokens on top of ``base_theme`` (or a sensible
    CORPORATE default if None). Tokens that are absent or invalid are ignored
    and the base values are preserved.

    Args:
        stitch: Design tokens from a Stitch project.
        base_theme: Starting theme to overlay tokens onto. Defaults to CORPORATE.

    Returns:
        A new ThemeSpec with Stitch tokens applied.
    """
    if base_theme is None:
        base_theme = _default_theme()

    # Build new color palette — start from existing
    old_colors = base_theme.colors
    primary = _normalise_hex(stitch.primary_color) if _is_valid_hex(stitch.primary_color) else old_colors.primary
    secondary = _normalise_hex(stitch.secondary_color) if _is_valid_hex(stitch.secondary_color) else old_colors.secondary
    text_on_primary = _contrast_color(primary)

    new_colors = ColorPaletteSpec(
        primary=primary,
        secondary=secondary,
        accent=old_colors.accent,
        background=old_colors.background,
        surface=old_colors.surface,
        text_primary=old_colors.text_primary,
        text_secondary=old_colors.text_secondary,
        text_on_primary=text_on_primary,
    )

    # Build typography — override family if provided
    old_typo = base_theme.typography
    heading_font = stitch.font_family or old_typo.heading_font
    font_family = stitch.font_family or old_typo.font_family
    new_typo = TypographySpec(
        font_family=font_family,
        heading_font=heading_font,
        mono_font=old_typo.mono_font,
        base_size=old_typo.base_size,
        scale_ratio=old_typo.scale_ratio,
    )

    return ThemeSpec(
        family=base_theme.family,
        colors=new_colors,
        typography=new_typo,
        border_radius=base_theme.border_radius,
        shadow_intensity=base_theme.shadow_intensity,
        use_gradients=base_theme.use_gradients,
        use_patterns=base_theme.use_patterns,
    )


def apply_stitch_to_deck(deck: DeckSpec, stitch: StitchDesignSpec) -> DeckSpec:
    """Return a new DeckSpec with the Stitch design applied to its theme.

    Args:
        deck: Original deck.
        stitch: Stitch design tokens to overlay.

    Returns:
        A copy of the deck with an updated ThemeSpec.
    """
    new_theme = stitch_to_theme(stitch, base_theme=deck.theme)
    return deck.model_copy(update={"theme": new_theme})


def stitch_metadata_to_spec(metadata: dict) -> StitchDesignSpec:
    """Parse raw Stitch metadata dict into a StitchDesignSpec.

    Extracts common Stitch design-system token keys. Unknown keys are
    stored in ``raw_metadata`` for forward-compatibility.

    Args:
        metadata: Raw dict from Stitch API or config.

    Returns:
        Populated StitchDesignSpec.
    """
    # Common Stitch / design-token key aliases
    primary = (
        metadata.get("primaryColor")
        or metadata.get("primary_color")
        or metadata.get("brand")
        or metadata.get("colors", {}).get("primary")
    )
    secondary = (
        metadata.get("secondaryColor")
        or metadata.get("secondary_color")
        or metadata.get("colors", {}).get("secondary")
    )
    font = (
        metadata.get("fontFamily")
        or metadata.get("font_family")
        or metadata.get("typography", {}).get("fontFamily")
    )
    logo = (
        metadata.get("logoUrl")
        or metadata.get("logo_url")
        or metadata.get("logo")
    )
    design_id = str(metadata.get("id") or metadata.get("design_id") or "stitch-import")

    return StitchDesignSpec(
        design_id=design_id,
        primary_color=primary,
        secondary_color=secondary,
        font_family=font,
        logo_url=logo,
        raw_metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal defaults
# ─────────────────────────────────────────────────────────────────────────────


def _default_theme() -> ThemeSpec:
    from app.models.deck import ColorPaletteSpec, TypographySpec
    from app.services.planning import _THEME_PRESETS  # type: ignore[attr-defined]

    preset = _THEME_PRESETS[ThemeFamily.CORPORATE]
    return ThemeSpec(
        family=ThemeFamily.CORPORATE,
        name=preset["name"],
        colors=ColorPaletteSpec(**preset["colors"]),
        typography=TypographySpec(),
        border_radius=preset["border_radius"],
        shadow_intensity=preset["shadow_intensity"],
        use_gradients=preset["use_gradients"],
        use_patterns=preset["use_patterns"],
    )

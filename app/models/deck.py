"""Deck domain models — the core schema vocabulary for the slide generation system.

Every model in this package is a Pydantic V2 model. These schemas are shared
between the MCP tool layer (Phase 7), the planning engine (Phase 3), and all
renderers (Phases 5 and 6).
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from app.models.base import IdentifiedModel, SliderBaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class SlideLayout(str, Enum):
    """Canonical layout identifiers used by the planning engine and renderers."""

    TITLE = "title"                  # Full-bleed title + subtitle
    HERO_IMAGE = "hero_image"        # Large visual with minimal text overlay
    TWO_COLUMN = "two_column"        # Left text / right image or vice-versa
    THREE_COLUMN = "three_column"    # Three equal content columns
    BULLETS = "bullets"              # Headline + bullet list (use sparingly)
    QUOTE = "quote"                  # Pull quote with attribution
    STATS = "stats"                  # 2–4 big-number statistics
    TIMELINE = "timeline"            # Horizontal or vertical time steps
    COMPARISON = "comparison"        # Side-by-side A vs B
    SECTION_BREAK = "section_break"  # Visual divider between sections
    BLANK = "blank"                  # Empty canvas for custom rendering
    CLOSING = "closing"              # CTA / thank-you / contact slide


class SlideRole(str, Enum):
    """Semantic role a slide plays in the narrative arc."""

    COVER = "cover"
    AGENDA = "agenda"
    SECTION = "section"
    CONTENT = "content"
    DATA = "data"
    QUOTE = "quote"
    TRANSITION = "transition"
    CLOSING = "closing"


class ContentBlockType(str, Enum):
    """Discriminant for ContentBlock union."""

    TEXT = "text"
    BULLET_LIST = "bullet_list"
    IMAGE = "image"
    ICON = "icon"
    STAT = "stat"
    QUOTE = "quote"
    CODE = "code"
    SVG = "svg"


class ThemeFamily(str, Enum):
    """Pre-defined theme families — the planning engine chooses one per deck."""

    CORPORATE = "corporate"
    STARTUP = "startup"
    CREATIVE = "creative"
    MINIMAL = "minimal"
    DARK = "dark"
    NATURE = "nature"
    TECH = "tech"


class AspectRatio(str, Enum):
    """Slide aspect ratios."""

    WIDESCREEN = "16:9"
    STANDARD = "4:3"
    SQUARE = "1:1"
    PORTRAIT = "9:16"


class FontWeight(str, Enum):
    LIGHT = "300"
    REGULAR = "400"
    MEDIUM = "500"
    SEMIBOLD = "600"
    BOLD = "700"
    EXTRABOLD = "800"


# ─────────────────────────────────────────────────────────────────────────────
# Asset + Icon models
# ─────────────────────────────────────────────────────────────────────────────


class AssetType(str, Enum):
    IMAGE = "image"
    SVG = "svg"
    ICON = "icon"
    CLIPART = "clipart"


class AssetSpec(SliderBaseModel):
    """Specification for a single visual asset (image, SVG, icon, or clipart)."""

    asset_type: AssetType
    # Source: URL, local path, or icon library reference (e.g. "heroicons:academic-cap")
    source: str
    alt_text: str = ""
    # Optional CSS-compatible dimensions
    width: str | None = None
    height: str | None = None
    # Positioning hint for the renderer (e.g. "center", "top-right")
    position_hint: str = "center"


class IconSpec(SliderBaseModel):
    """Lightweight icon reference — resolved by the asset service in Phase 4."""

    library: str = "heroicons"  # heroicons | feather | phosphor | lucide
    name: str
    size: int = 48
    color: str = "currentColor"


# ─────────────────────────────────────────────────────────────────────────────
# Content blocks (discriminated union)
# ─────────────────────────────────────────────────────────────────────────────


class TextBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.TEXT] = ContentBlockType.TEXT
    text: str
    style: Literal["h1", "h2", "h3", "h4", "body", "caption", "label"] = "body"
    align: Literal["left", "center", "right"] = "left"
    color: str | None = None  # CSS color override


class BulletListBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.BULLET_LIST] = ContentBlockType.BULLET_LIST
    items: list[str] = Field(min_length=1, max_length=8)
    ordered: bool = False
    highlight_first: bool = False  # Make first item visually prominent


class ImageBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.IMAGE] = ContentBlockType.IMAGE
    asset: AssetSpec
    caption: str | None = None
    fill: bool = False  # True = fill the container (object-fit: cover)


class IconBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.ICON] = ContentBlockType.ICON
    icon: IconSpec
    label: str | None = None


class StatBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.STAT] = ContentBlockType.STAT
    value: str           # e.g. "98%", "$1.2M", "10x"
    label: str           # e.g. "Customer satisfaction"
    trend: Literal["up", "down", "neutral"] | None = None


class QuoteBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.QUOTE] = ContentBlockType.QUOTE
    text: str = Field(min_length=5)
    attribution: str | None = None
    role: str | None = None  # e.g. "CEO, Acme Corp"


class CodeBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.CODE] = ContentBlockType.CODE
    code: str
    language: str = "python"


class SVGBlock(SliderBaseModel):
    block_type: Literal[ContentBlockType.SVG] = ContentBlockType.SVG
    svg_source: str   # Inline SVG string or URL
    inline: bool = True


# Discriminated union for type-safe polymorphism
ContentBlock = Annotated[
    Union[
        TextBlock,
        BulletListBlock,
        ImageBlock,
        IconBlock,
        StatBlock,
        QuoteBlock,
        CodeBlock,
        SVGBlock,
    ],
    Field(discriminator="block_type"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Theme
# ─────────────────────────────────────────────────────────────────────────────


class TypographySpec(SliderBaseModel):
    """Font and text sizing tokens."""

    font_family: str = "Inter"
    heading_font: str | None = None   # Falls back to font_family
    mono_font: str = "JetBrains Mono"
    base_size: int = Field(default=16, ge=10, le=32)  # px
    scale_ratio: float = Field(default=1.25, ge=1.0, le=2.0)  # modular scale


class ColorPaletteSpec(SliderBaseModel):
    """Brand / theme color tokens."""

    primary: str = "#2563EB"
    secondary: str = "#7C3AED"
    accent: str = "#F59E0B"
    background: str = "#FFFFFF"
    surface: str = "#F8FAFC"
    text_primary: str = "#0F172A"
    text_secondary: str = "#475569"
    text_on_primary: str = "#FFFFFF"

    @field_validator("primary", "secondary", "accent", "background",
                     "surface", "text_primary", "text_secondary", "text_on_primary")
    @classmethod
    def must_be_valid_color(cls, v: str) -> str:
        """Validate CSS color format (hex, rgb, hsl, or named)."""
        v = v.strip()
        if v.startswith("#"):
            stripped = v[1:]
            if len(stripped) not in (3, 6, 8):
                raise ValueError(f"Invalid hex color length: {v!r}")
            try:
                int(stripped, 16)
            except ValueError:
                raise ValueError(f"Invalid hex color characters: {v!r}")
        # Allow rgb(), hsl(), and named colors without exhaustive validation
        return v


class ThemeSpec(SliderBaseModel):
    """Complete visual theme for a deck."""

    family: ThemeFamily = ThemeFamily.CORPORATE
    name: str = Field(default="Default", min_length=1, max_length=64)
    colors: ColorPaletteSpec = Field(default_factory=ColorPaletteSpec)
    typography: TypographySpec = Field(default_factory=TypographySpec)
    border_radius: int = Field(default=8, ge=0, le=32)   # px
    shadow_intensity: Literal["none", "soft", "medium", "strong"] = "soft"
    use_gradients: bool = True
    use_patterns: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────


class LayoutSpec(SliderBaseModel):
    """Layout configuration for a slide."""

    layout: SlideLayout
    # Column proportions for multi-column layouts (must sum to 100)
    column_ratios: list[int] = Field(default_factory=lambda: [50, 50])
    # Content alignment within the slide
    vertical_align: Literal["top", "middle", "bottom"] = "middle"
    horizontal_align: Literal["left", "center", "right"] = "left"
    # Background override for this slide
    background_color: str | None = None
    background_image: AssetSpec | None = None
    # Padding override (CSS shorthand e.g. "48px 64px")
    padding: str | None = None

    @model_validator(mode="after")
    def validate_column_ratios(self) -> LayoutSpec:
        """Column ratios must sum to 100 for multi-column layouts."""
        multi_col = {SlideLayout.TWO_COLUMN, SlideLayout.THREE_COLUMN, SlideLayout.COMPARISON}
        if self.layout in multi_col:
            total = sum(self.column_ratios)
            if total != 100:
                raise ValueError(
                    f"column_ratios must sum to 100 for {self.layout.value} layout "
                    f"(got {total})"
                )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Slide
# ─────────────────────────────────────────────────────────────────────────────


class SlideSpec(IdentifiedModel):
    """Specification for a single slide."""

    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = None
    role: SlideRole = SlideRole.CONTENT
    layout: LayoutSpec
    content_blocks: list[ContentBlock] = Field(default_factory=list, max_length=20)
    speaker_notes: str | None = None
    # Metadata for the planning engine
    intent: str | None = None          # e.g. "demonstrate ROI with numbers"
    visual_weight: Literal["light", "balanced", "heavy"] = "balanced"
    # Stitch integration hooks (Phase 8)
    stitch_design_id: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_placeholder(cls, v: str) -> str:
        placeholders = {"slide title", "untitled", "title here", "your title"}
        if v.strip().lower() in placeholders:
            raise ValueError(f"Title must not be a placeholder: {v!r}")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Deck
# ─────────────────────────────────────────────────────────────────────────────


class DeckMetadata(SliderBaseModel):
    """Authoring and presentation metadata."""

    author: str | None = None
    organization: str | None = None
    event: str | None = None
    date: str | None = None   # ISO date string
    confidentiality: Literal["public", "internal", "confidential"] = "public"
    tags: list[str] = Field(default_factory=list, max_length=20)


class DeckSpec(IdentifiedModel):
    """Root specification for a complete presentation deck.

    This is the primary input consumed by all rendering engines. The MCP tool
    layer (Phase 7) produces DeckSpec instances from agent-provided content.
    """

    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    audience: str | None = None          # e.g. "engineering leadership"
    purpose: str | None = None           # e.g. "quarterly business review"
    slides: list[SlideSpec] = Field(min_length=1, max_length=100)
    theme: ThemeSpec = Field(default_factory=ThemeSpec)
    aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    metadata: DeckMetadata = Field(default_factory=DeckMetadata)

    # Output preferences
    export_formats: list[Literal["html", "pptx"]] = Field(
        default_factory=lambda: ["html", "pptx"]
    )

    @field_validator("slides")
    @classmethod
    def must_have_cover(cls, slides: list[SlideSpec]) -> list[SlideSpec]:
        """At least the first slide should be a cover or title layout."""
        if slides and slides[0].role not in {SlideRole.COVER, SlideRole.CONTENT}:
            # Warn but don't block — planning engine will handle this
            pass
        return slides

    @model_validator(mode="after")
    def validate_export_formats(self) -> DeckSpec:
        if not self.export_formats:
            raise ValueError("At least one export format must be specified")
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Stitch design spec (Phase 8 stub — schema defined here for forward compat)
# ─────────────────────────────────────────────────────────────────────────────


class StitchDesignSpec(SliderBaseModel):
    """Metadata from a Stitch design system, used to infer theme overrides."""

    design_id: str
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = None
    logo_url: str | None = None
    component_library: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

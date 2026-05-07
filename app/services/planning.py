"""Deck Planning Engine.

Takes a minimal prompt (topic, audience, purpose, slide count) and produces
a complete, visually coherent DeckSpec with:
- Intelligently assigned slide layouts
- Appropriate slide roles + narrative arc
- Theme selection based on purpose/audience keywords
- Visual rhythm (prevents repetitive layout sequences)
- Content block scaffolding for each layout type

Design principle: pure functions only — no I/O, no side effects.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.deck import (
    AspectRatio,
    BulletListBlock,
    ColorPaletteSpec,
    ContentBlockType,
    DeckMetadata,
    DeckSpec,
    IconBlock,
    IconSpec,
    LayoutSpec,
    QuoteBlock,
    SlideLayout,
    SlideRole,
    SlideSpec,
    StatBlock,
    TextBlock,
    ThemeFamily,
    ThemeSpec,
    TypographySpec,
)


# ─────────────────────────────────────────────────────────────────────────────
# Planning request
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PlanningRequest:
    """Minimal input for deck generation. All fields except topic are optional."""

    topic: str
    audience: str = "general"
    purpose: str = "inform"
    slide_count: int = 8
    # Optional: list of section titles or bullet points to expand
    outline: list[str] = field(default_factory=list)
    # Override auto-selected theme
    theme_family: ThemeFamily | None = None
    aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    # Deck metadata overrides
    author: str | None = None
    organization: str | None = None

    def __post_init__(self) -> None:
        self.slide_count = max(3, min(60, self.slide_count))


# ─────────────────────────────────────────────────────────────────────────────
# Theme selection
# ─────────────────────────────────────────────────────────────────────────────

_THEME_PRESETS: dict[ThemeFamily, dict[str, Any]] = {
    ThemeFamily.CORPORATE: {
        "name": "Corporate Blue",
        "colors": {"primary": "#1E3A8A", "secondary": "#1D4ED8", "accent": "#F59E0B",
                   "background": "#FFFFFF", "surface": "#F8FAFC",
                   "text_primary": "#0F172A", "text_secondary": "#475569",
                   "text_on_primary": "#FFFFFF"},
        "border_radius": 4, "shadow_intensity": "medium",
        "use_gradients": False, "use_patterns": False,
    },
    ThemeFamily.STARTUP: {
        "name": "Startup Violet",
        "colors": {"primary": "#7C3AED", "secondary": "#4F46E5", "accent": "#EC4899",
                   "background": "#FFFFFF", "surface": "#FAF5FF",
                   "text_primary": "#1E1B4B", "text_secondary": "#6B7280",
                   "text_on_primary": "#FFFFFF"},
        "border_radius": 12, "shadow_intensity": "soft",
        "use_gradients": True, "use_patterns": False,
    },
    ThemeFamily.CREATIVE: {
        "name": "Creative Coral",
        "colors": {"primary": "#F97316", "secondary": "#EAB308", "accent": "#84CC16",
                   "background": "#FFFBF0", "surface": "#FFF7ED",
                   "text_primary": "#1C1917", "text_secondary": "#78716C",
                   "text_on_primary": "#FFFFFF"},
        "border_radius": 16, "shadow_intensity": "soft",
        "use_gradients": True, "use_patterns": True,
    },
    ThemeFamily.MINIMAL: {
        "name": "Clean Minimal",
        "colors": {"primary": "#18181B", "secondary": "#52525B", "accent": "#2563EB",
                   "background": "#FFFFFF", "surface": "#FAFAFA",
                   "text_primary": "#09090B", "text_secondary": "#71717A",
                   "text_on_primary": "#FFFFFF"},
        "border_radius": 2, "shadow_intensity": "none",
        "use_gradients": False, "use_patterns": False,
    },
    ThemeFamily.DARK: {
        "name": "Dark Mode",
        "colors": {"primary": "#818CF8", "secondary": "#C084FC", "accent": "#34D399",
                   "background": "#0F172A", "surface": "#1E293B",
                   "text_primary": "#F1F5F9", "text_secondary": "#94A3B8",
                   "text_on_primary": "#0F172A"},
        "border_radius": 8, "shadow_intensity": "strong",
        "use_gradients": True, "use_patterns": False,
    },
    ThemeFamily.NATURE: {
        "name": "Nature Green",
        "colors": {"primary": "#16A34A", "secondary": "#15803D", "accent": "#CA8A04",
                   "background": "#F0FDF4", "surface": "#DCFCE7",
                   "text_primary": "#14532D", "text_secondary": "#4B5563",
                   "text_on_primary": "#FFFFFF"},
        "border_radius": 8, "shadow_intensity": "soft",
        "use_gradients": False, "use_patterns": True,
    },
    ThemeFamily.TECH: {
        "name": "Tech Slate",
        "colors": {"primary": "#06B6D4", "secondary": "#0EA5E9", "accent": "#A855F7",
                   "background": "#0A0E1A", "surface": "#111827",
                   "text_primary": "#E2E8F0", "text_secondary": "#94A3B8",
                   "text_on_primary": "#0A0E1A"},
        "border_radius": 6, "shadow_intensity": "strong",
        "use_gradients": True, "use_patterns": False,
    },
}

_AUDIENCE_THEME_MAP: dict[str, ThemeFamily] = {
    "investor": ThemeFamily.CORPORATE,
    "board": ThemeFamily.CORPORATE,
    "executive": ThemeFamily.CORPORATE,
    "enterprise": ThemeFamily.CORPORATE,
    "startup": ThemeFamily.STARTUP,
    "pitch": ThemeFamily.STARTUP,
    "vc": ThemeFamily.STARTUP,
    "creative": ThemeFamily.CREATIVE,
    "design": ThemeFamily.CREATIVE,
    "marketing": ThemeFamily.CREATIVE,
    "developer": ThemeFamily.TECH,
    "engineering": ThemeFamily.TECH,
    "technical": ThemeFamily.TECH,
    "tech": ThemeFamily.TECH,
    "academic": ThemeFamily.MINIMAL,
    "research": ThemeFamily.MINIMAL,
    "science": ThemeFamily.NATURE,
    "sustainability": ThemeFamily.NATURE,
    "environment": ThemeFamily.NATURE,
}

_PURPOSE_THEME_MAP: dict[str, ThemeFamily] = {
    "pitch": ThemeFamily.STARTUP,
    "fundraise": ThemeFamily.STARTUP,
    "sales": ThemeFamily.CORPORATE,
    "quarterly": ThemeFamily.CORPORATE,
    "review": ThemeFamily.CORPORATE,
    "tutorial": ThemeFamily.TECH,
    "demo": ThemeFamily.TECH,
    "workshop": ThemeFamily.MINIMAL,
    "training": ThemeFamily.MINIMAL,
}


def select_theme(request: PlanningRequest) -> ThemeSpec:
    """Choose the best ThemeFamily from audience/purpose keywords, build ThemeSpec."""
    if request.theme_family:
        family = request.theme_family
    else:
        family = _infer_theme_family(request.audience, request.purpose, request.topic)

    preset = _THEME_PRESETS[family]
    return ThemeSpec(
        family=family,
        name=preset["name"],
        colors=ColorPaletteSpec(**preset["colors"]),
        typography=TypographySpec(),
        border_radius=preset["border_radius"],
        shadow_intensity=preset["shadow_intensity"],
        use_gradients=preset["use_gradients"],
        use_patterns=preset["use_patterns"],
    )


def _infer_theme_family(audience: str, purpose: str, topic: str) -> ThemeFamily:
    """Match keywords in audience/purpose/topic to a ThemeFamily."""
    text = f"{audience} {purpose} {topic}".lower()
    words = set(re.findall(r"\w+", text))

    for keyword, family in _AUDIENCE_THEME_MAP.items():
        if keyword in words:
            return family
    for keyword, family in _PURPOSE_THEME_MAP.items():
        if keyword in words:
            return family

    return ThemeFamily.CORPORATE  # safe default


# ─────────────────────────────────────────────────────────────────────────────
# Layout sequencing
# ─────────────────────────────────────────────────────────────────────────────

# Preferred layout progressions for different deck types (by purpose keyword)
_CONTENT_LAYOUT_POOL = [
    SlideLayout.TWO_COLUMN,
    SlideLayout.STATS,
    SlideLayout.BULLETS,
    SlideLayout.QUOTE,
    SlideLayout.TWO_COLUMN,
    SlideLayout.TIMELINE,
    SlideLayout.THREE_COLUMN,
    SlideLayout.COMPARISON,
    SlideLayout.STATS,
    SlideLayout.BULLETS,
    SlideLayout.TWO_COLUMN,
    SlideLayout.QUOTE,
]


def _assign_layouts(slide_count: int) -> list[SlideLayout]:
    """Assign layouts to all slides for anti-repetition visual rhythm.

    Structure:
    - Slide 0:   TITLE (cover)
    - Slide 1:   BULLETS (agenda) — if slide_count >= 4
    - Slides 2..-2: content pool (cycled with variety)
    - Slide -2:  SECTION_BREAK (if slide_count >= 6)
    - Slide -1:  CLOSING
    """
    layouts: list[SlideLayout] = []

    # Cover
    layouts.append(SlideLayout.TITLE)

    # Agenda
    if slide_count >= 4:
        layouts.append(SlideLayout.BULLETS)

    # How many content slides do we need?
    reserved = len(layouts) + 1  # +1 for closing
    if slide_count >= 6:
        reserved += 1  # section break
    content_slots = max(0, slide_count - reserved)

    # Fill content slots from pool, ensuring no two consecutive identical layouts
    pool = _CONTENT_LAYOUT_POOL
    prev: SlideLayout | None = None
    pool_idx = 0
    for _ in range(content_slots):
        layout = pool[pool_idx % len(pool)]
        # Skip if same as previous to prevent consecutive duplicates
        attempts = 0
        while layout == prev and attempts < len(pool):
            pool_idx += 1
            layout = pool[pool_idx % len(pool)]
            attempts += 1
        layouts.append(layout)
        prev = layout
        pool_idx += 1

    # Section break before closing (for longer decks)
    if slide_count >= 6:
        layouts.append(SlideLayout.SECTION_BREAK)

    # Closing
    layouts.append(SlideLayout.CLOSING)

    return layouts[:slide_count]


def _layout_to_role(layout: SlideLayout, idx: int, total: int) -> SlideRole:
    """Infer semantic role from layout and position."""
    if idx == 0:
        return SlideRole.COVER
    if idx == total - 1:
        return SlideRole.CLOSING
    return {
        SlideLayout.TITLE: SlideRole.COVER,
        SlideLayout.BULLETS: SlideRole.CONTENT if idx > 1 else SlideRole.AGENDA,
        SlideLayout.QUOTE: SlideRole.QUOTE,
        SlideLayout.STATS: SlideRole.DATA,
        SlideLayout.SECTION_BREAK: SlideRole.SECTION,
        SlideLayout.CLOSING: SlideRole.CLOSING,
        SlideLayout.TIMELINE: SlideRole.CONTENT,
        SlideLayout.TWO_COLUMN: SlideRole.CONTENT,
        SlideLayout.THREE_COLUMN: SlideRole.CONTENT,
        SlideLayout.COMPARISON: SlideRole.CONTENT,
        SlideLayout.HERO_IMAGE: SlideRole.CONTENT,
        SlideLayout.BLANK: SlideRole.CONTENT,
    }.get(layout, SlideRole.CONTENT)


# ─────────────────────────────────────────────────────────────────────────────
# Content scaffolding
# ─────────────────────────────────────────────────────────────────────────────


def _make_slide_title(idx: int, total: int, topic: str, outline: list[str]) -> str:
    """Generate a slide title from outline or topic-based defaults."""
    if idx < len(outline) and outline[idx].strip():
        return outline[idx].strip()[:200]

    # Positional defaults
    if idx == 0:
        return topic
    if idx == total - 1:
        return "Thank You"
    if idx == 1 and total >= 4:
        return "Agenda"
    if idx == total - 2 and total >= 6:
        return "Key Takeaways"
    return f"{topic} — Part {idx}"


def _scaffold_content_blocks(layout: SlideLayout, topic: str) -> list[Any]:
    """Create placeholder content blocks appropriate for the layout type."""
    blocks: list[Any] = []

    if layout == SlideLayout.TITLE:
        blocks.append(TextBlock(text=f"A comprehensive overview of {topic}", style="h3", align="center"))

    elif layout == SlideLayout.BULLETS:
        blocks.append(BulletListBlock(items=[
            "Key insight one",
            "Key insight two",
            "Key insight three",
            "Key insight four",
        ]))

    elif layout == SlideLayout.STATS:
        blocks.extend([
            StatBlock(value="90%", label="Customer satisfaction"),
            StatBlock(value="3x", label="Growth this year"),
            StatBlock(value="50+", label="Team members"),
        ])

    elif layout == SlideLayout.QUOTE:
        blocks.append(QuoteBlock(
            text="The best way to predict the future is to create it.",
            attribution="Peter Drucker",
        ))

    elif layout in {SlideLayout.TWO_COLUMN, SlideLayout.THREE_COLUMN}:
        blocks.append(TextBlock(text=f"Details about {topic}", style="body"))
        blocks.append(IconBlock(icon=IconSpec(name="presentation-chart-bar", size=64)))

    elif layout == SlideLayout.SECTION_BREAK:
        blocks.append(TextBlock(text="Wrapping Up", style="h2", align="center"))

    elif layout == SlideLayout.CLOSING:
        blocks.extend([
            TextBlock(text="Questions?", style="h2", align="center"),
            TextBlock(text="contact@example.com", style="caption", align="center"),
        ])

    elif layout == SlideLayout.TIMELINE:
        blocks.append(BulletListBlock(ordered=True, items=[
            "Phase one: Foundation",
            "Phase two: Growth",
            "Phase three: Scale",
        ]))

    elif layout == SlideLayout.COMPARISON:
        blocks.append(TextBlock(text="Option A", style="h3"))
        blocks.append(TextBlock(text="Option B", style="h3"))

    return blocks


def _build_layout_spec(layout: SlideLayout) -> LayoutSpec:
    """Build a LayoutSpec with sensible defaults for the given layout."""
    if layout == SlideLayout.TWO_COLUMN:
        return LayoutSpec(layout=layout, column_ratios=[50, 50])
    if layout == SlideLayout.THREE_COLUMN:
        return LayoutSpec(layout=layout, column_ratios=[34, 33, 33])
    if layout == SlideLayout.COMPARISON:
        return LayoutSpec(layout=layout, column_ratios=[50, 50])
    return LayoutSpec(layout=layout)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def plan_deck(request: PlanningRequest) -> DeckSpec:
    """Generate a complete DeckSpec from a PlanningRequest.

    The returned DeckSpec is schema-valid and passes validation,
    but content blocks contain scaffolding placeholders that the
    MCP tool layer (Phase 7) will fill with real content.

    Args:
        request: Minimal planning parameters.

    Returns:
        A fully structured DeckSpec ready for rendering or further editing.
    """
    layouts = _assign_layouts(request.slide_count)
    total = len(layouts)
    theme = select_theme(request)

    slides: list[SlideSpec] = []
    for idx, layout in enumerate(layouts):
        title = _make_slide_title(idx, total, request.topic, request.outline)
        role = _layout_to_role(layout, idx, total)
        layout_spec = _build_layout_spec(layout)
        blocks = _scaffold_content_blocks(layout, request.topic)

        slides.append(SlideSpec(
            title=title,
            role=role,
            layout=layout_spec,
            content_blocks=blocks,
            intent=f"Communicate about: {request.topic}" if idx > 0 else None,
        ))

    from app.models.deck import DeckMetadata
    metadata = DeckMetadata(
        author=request.author,
        organization=request.organization,
    )

    return DeckSpec(
        title=request.topic,
        audience=request.audience,
        purpose=request.purpose,
        slides=slides,
        theme=theme,
        aspect_ratio=request.aspect_ratio,
        metadata=metadata,
    )

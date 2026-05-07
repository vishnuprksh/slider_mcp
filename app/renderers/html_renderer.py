"""HTML Rendering Engine.

Converts a DeckSpec into a single self-contained HTML file using Jinja2.
All CSS is inline (no external dependencies) so the file works offline.

Design decisions:
- Single-file output: all styles embedded in <style>, no CDN links.
- Jinja2 AutoEscape enabled (html mode) for XSS safety in user content.
- SVG blocks are passed through unsanitized only if the caller has already
  run sanitize_svg(); raw SVG from external sources must be sanitized first.
- The renderer is synchronous — no I/O, fully testable without a server.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.deck import (
    AspectRatio,
    ContentBlock,
    DeckSpec,
    IconBlock,
    SVGBlock,
    SlideSpec,
    ThemeSpec,
)
from app.services.assets import resolve_icon_url, sanitize_svg

# ─────────────────────────────────────────────────────────────────────────────
# Jinja2 environment
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "jinja2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Aspect ratio helpers
# ─────────────────────────────────────────────────────────────────────────────

_ASPECT_DIMENSIONS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.WIDESCREEN: (16, 9),
    AspectRatio.STANDARD: (4, 3),
    AspectRatio.SQUARE: (1, 1),
    AspectRatio.PORTRAIT: (9, 16),
}


def _aspect_parts(ratio: AspectRatio) -> tuple[int, int]:
    return _ASPECT_DIMENSIONS.get(ratio, (16, 9))


# ─────────────────────────────────────────────────────────────────────────────
# Column splitting helper
# ─────────────────────────────────────────────────────────────────────────────


def _split_blocks(blocks: list[Any], n_cols: int) -> list[list[Any]]:
    """Distribute content_blocks evenly across n_cols columns."""
    if n_cols <= 1 or not blocks:
        return [blocks]
    cols: list[list[Any]] = [[] for _ in range(n_cols)]
    per = math.ceil(len(blocks) / n_cols)
    for i, block in enumerate(blocks):
        cols[min(i // per, n_cols - 1)].append(block)
    return cols


# ─────────────────────────────────────────────────────────────────────────────
# SVG safety pass for SVGBlock
# ─────────────────────────────────────────────────────────────────────────────


def _sanitize_slide_svgs(slides: list[SlideSpec]) -> list[SlideSpec]:
    """Return slides with all SVGBlock sources sanitized (mutates copies)."""
    result = []
    for slide in slides:
        new_blocks = []
        for block in slide.content_blocks:
            if hasattr(block, "block_type") and block.block_type.value == "svg":
                safe_src = sanitize_svg(block.svg_source)
                block = block.model_copy(update={"svg_source": safe_src})
            new_blocks.append(block)
        result.append(slide.model_copy(update={"content_blocks": new_blocks}))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public renderer
# ─────────────────────────────────────────────────────────────────────────────


def render_html(deck: DeckSpec) -> str:
    """Render a DeckSpec to a self-contained HTML string.

    Args:
        deck: A schema-valid DeckSpec (from plan_deck or user input).

    Returns:
        Complete HTML document as a string.
    """
    aspect_w, aspect_h = _aspect_parts(deck.aspect_ratio)
    sanitized_slides = _sanitize_slide_svgs(deck.slides)

    template = _env.get_template("deck.html.jinja2")

    # Disable Jinja2 autoescaping for the icon_url helper (returns plain URL)
    # and for SVG blocks (already sanitized). Use |e filter explicitly in template.
    html = template.render(
        deck=deck,
        slides=sanitized_slides,
        theme=deck.theme,
        aspect_w=aspect_w,
        aspect_h=aspect_h,
        # Template helpers
        icon_url=lambda icon: resolve_icon_url(icon),
        split_blocks=_split_blocks,
    )
    return html


def render_html_to_file(deck: DeckSpec, output_path: Path) -> Path:
    """Render deck to an HTML file. Creates parent directories if needed.

    Args:
        deck: A schema-valid DeckSpec.
        output_path: Destination file path (must have .html extension).

    Returns:
        The resolved output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(deck)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()

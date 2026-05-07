"""Phase 5 — HTML renderer tests."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from app.models.deck import (
    AspectRatio,
    BulletListBlock,
    CodeBlock,
    DeckSpec,
    IconBlock,
    IconSpec,
    LayoutSpec,
    QuoteBlock,
    SVGBlock,
    SlideLayout,
    SlideRole,
    SlideSpec,
    StatBlock,
    TextBlock,
    ThemeSpec,
)
from app.renderers.html_renderer import _split_blocks, render_html, render_html_to_file
from app.services.planning import PlanningRequest, plan_deck


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def minimal_deck(n_slides: int = 3) -> DeckSpec:
    req = PlanningRequest(topic="Minimal Test Deck", slide_count=n_slides)
    return plan_deck(req)


def slide_with_blocks(*blocks) -> SlideSpec:
    return SlideSpec(
        title="Test Slide",
        role=SlideRole.CONTENT,
        layout=LayoutSpec(layout=SlideLayout.BULLETS),
        content_blocks=list(blocks),
    )


# ─────────────────────────────────────────────────────────────────────────────
# _split_blocks helper
# ─────────────────────────────────────────────────────────────────────────────


class TestSplitBlocks:
    def test_single_col_returns_all_in_one(self):
        blocks = [1, 2, 3]
        result = _split_blocks(blocks, 1)
        assert result == [[1, 2, 3]]

    def test_two_cols_even_split(self):
        result = _split_blocks([1, 2, 3, 4], 2)
        assert len(result) == 2
        assert sum(len(c) for c in result) == 4

    def test_three_cols_distributes(self):
        result = _split_blocks([1, 2, 3, 4, 5, 6], 3)
        assert len(result) == 3

    def test_empty_blocks_returns_single_empty(self):
        result = _split_blocks([], 2)
        assert result == [[]]


# ─────────────────────────────────────────────────────────────────────────────
# render_html — structure
# ─────────────────────────────────────────────────────────────────────────────


class TestRenderHtml:
    def test_returns_string(self):
        deck = minimal_deck()
        html = render_html(deck)
        assert isinstance(html, str)

    def test_is_valid_html_skeleton(self):
        html = render_html(minimal_deck())
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_deck_title_in_output(self):
        deck = minimal_deck()
        html = render_html(deck)
        assert deck.title in html

    def test_all_slide_titles_present(self):
        deck = minimal_deck(5)
        html = render_html(deck)
        for slide in deck.slides:
            assert slide.title in html

    def test_slide_count_in_output(self):
        deck = minimal_deck(6)
        html = render_html(deck)
        assert f"{len(deck.slides)} slides" in html or str(len(deck.slides)) in html

    def test_theme_primary_color_in_css(self):
        deck = minimal_deck()
        html = render_html(deck)
        assert deck.theme.colors.primary in html

    def test_aspect_ratio_16_9(self):
        deck = minimal_deck()
        deck = deck.model_copy(update={"aspect_ratio": AspectRatio.WIDESCREEN})
        html = render_html(deck)
        assert "16" in html and "9" in html

    def test_aspect_ratio_4_3(self):
        deck = minimal_deck()
        deck = deck.model_copy(update={"aspect_ratio": AspectRatio.STANDARD})
        html = render_html(deck)
        assert "4" in html and "3" in html


# ─────────────────────────────────────────────────────────────────────────────
# Content block rendering
# ─────────────────────────────────────────────────────────────────────────────


class TestContentBlockRendering:
    def _render_slide(self, *blocks) -> str:
        slide = slide_with_blocks(*blocks)
        deck = DeckSpec(title="Block Test", slides=[slide])
        return render_html(deck)

    def test_text_block_rendered(self):
        html = self._render_slide(TextBlock(text="Hello World"))
        assert "Hello World" in html

    def test_text_block_style_class(self):
        html = self._render_slide(TextBlock(text="Big Heading", style="h1"))
        assert "block-text" in html
        assert "h1" in html

    def test_bullet_list_rendered(self):
        html = self._render_slide(BulletListBlock(items=["Alpha", "Beta", "Gamma"]))
        assert "Alpha" in html and "Beta" in html

    def test_ordered_list_uses_ol(self):
        html = self._render_slide(BulletListBlock(items=["Step 1", "Step 2"], ordered=True))
        assert "<ol" in html

    def test_stat_block_rendered(self):
        html = self._render_slide(StatBlock(value="42%", label="Win rate"))
        assert "42%" in html
        assert "Win rate" in html

    def test_quote_block_rendered(self):
        html = self._render_slide(
            QuoteBlock(text="Innovation distinguishes leaders", attribution="Steve Jobs")
        )
        assert "Innovation distinguishes" in html
        assert "Steve Jobs" in html

    def test_code_block_rendered(self):
        html = self._render_slide(CodeBlock(code="print('hello')", language="python"))
        assert "print" in html
        assert "block-code" in html

    def test_icon_block_rendered(self):
        html = self._render_slide(IconBlock(icon=IconSpec(name="star")))
        assert "star" in html

    def test_svg_block_sanitized(self):
        malicious = '<svg><script>alert(1)</script></svg>'
        html = self._render_slide(SVGBlock(svg_source=malicious))
        assert "<script" not in html.lower()

    def test_xss_in_text_escaped(self):
        html = self._render_slide(TextBlock(text='<script>alert("xss")</script>'))
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html


# ─────────────────────────────────────────────────────────────────────────────
# Layout-specific rendering
# ─────────────────────────────────────────────────────────────────────────────


class TestLayoutRendering:
    def test_two_column_layout_has_columns_class(self):
        slide = SlideSpec(
            title="Two Col",
            role=SlideRole.CONTENT,
            layout=LayoutSpec(layout=SlideLayout.TWO_COLUMN, column_ratios=[60, 40]),
            content_blocks=[TextBlock(text="Left"), TextBlock(text="Right")],
        )
        deck = DeckSpec(title="T", slides=[slide])
        html = render_html(deck)
        assert "columns" in html
        assert "layout-two_column" in html

    def test_title_layout_has_correct_class(self):
        deck = minimal_deck(3)
        html = render_html(deck)
        assert "layout-title" in html

    def test_stats_layout_has_class(self):
        slide = SlideSpec(
            title="Numbers",
            role=SlideRole.DATA,
            layout=LayoutSpec(layout=SlideLayout.STATS),
            content_blocks=[
                StatBlock(value="90%", label="Uptime"),
                StatBlock(value="2ms", label="Latency"),
            ],
        )
        deck = DeckSpec(title="T", slides=[slide])
        html = render_html(deck)
        assert "layout-stats" in html


# ─────────────────────────────────────────────────────────────────────────────
# render_html_to_file
# ─────────────────────────────────────────────────────────────────────────────


class TestRenderHtmlToFile:
    def test_creates_file(self, tmp_path):
        deck = minimal_deck(3)
        out = render_html_to_file(deck, tmp_path / "output.html")
        assert out.exists()
        assert out.suffix == ".html"

    def test_file_content_is_html(self, tmp_path):
        deck = minimal_deck(3)
        out = render_html_to_file(deck, tmp_path / "deck.html")
        content = out.read_text()
        assert "<!DOCTYPE html>" in content

    def test_creates_parent_dirs(self, tmp_path):
        deck = minimal_deck(3)
        nested = tmp_path / "a" / "b" / "c" / "deck.html"
        out = render_html_to_file(deck, nested)
        assert out.exists()

    def test_planning_to_html_end_to_end(self, tmp_path):
        req = PlanningRequest(topic="AI in Finance", audience="investor", slide_count=8)
        deck = plan_deck(req)
        out = render_html_to_file(deck, tmp_path / "ai_finance.html")
        content = out.read_text()
        assert "AI in Finance" in content
        assert len(content) > 2000  # non-trivial output

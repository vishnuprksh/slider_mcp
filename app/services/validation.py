"""Deck validation service.

Pure-function validation layer that sits between the MCP tool input (raw dicts)
and the planning engine. Enforces business rules beyond Pydantic schema validation.

Design principle: no I/O, no side effects — all functions are deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.deck import (
    ContentBlockType,
    DeckSpec,
    SlideLayout,
    SlideRole,
    SlideSpec,
    ThemeSpec,
)


# ─────────────────────────────────────────────────────────────────────────────
# Validation result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """A single validation problem with its location and severity."""

    path: str                                   # e.g. "slides[2].title"
    message: str
    severity: str = "error"                     # "error" | "warning"


@dataclass
class ValidationResult:
    """Aggregated result of validating a DeckSpec."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add_error(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(path=path, message=message, severity="error"))
        self.valid = False

    def add_warning(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(path=path, message=message, severity="warning"))


# ─────────────────────────────────────────────────────────────────────────────
# Business rule validators
# ─────────────────────────────────────────────────────────────────────────────


def _check_slide_count(deck: DeckSpec, result: ValidationResult) -> None:
    """Reasonable slide count heuristics."""
    n = len(deck.slides)
    if n < 3:
        result.add_warning("slides", f"Deck has only {n} slide(s); consider adding more substance.")
    if n > 60:
        result.add_warning("slides", f"Deck has {n} slides — consider splitting into multiple decks.")


def _check_layout_diversity(slides: list[SlideSpec], result: ValidationResult) -> None:
    """Prevent repetitive layout sequences."""
    if len(slides) < 3:
        return

    # Flag 4+ consecutive identical layouts
    MAX_CONSECUTIVE = 3
    run_layout: SlideLayout | None = None
    run_count = 0
    for i, slide in enumerate(slides):
        layout = slide.layout.layout
        if layout == run_layout:
            run_count += 1
            if run_count > MAX_CONSECUTIVE:
                result.add_warning(
                    f"slides[{i}]",
                    f"Layout '{layout.value}' repeated {run_count} times in a row — "
                    "visual monotony risk.",
                )
        else:
            run_layout = layout
            run_count = 1

    # Flag excessive bullet slides
    bullet_count = sum(1 for s in slides if s.layout.layout == SlideLayout.BULLETS)
    if bullet_count > len(slides) * 0.4:
        result.add_warning(
            "slides",
            f"{bullet_count}/{len(slides)} slides use the 'bullets' layout — "
            "consider replacing some with visual layouts.",
        )


def _check_content_blocks(slides: list[SlideSpec], result: ValidationResult) -> None:
    """Validate content block business rules."""
    for i, slide in enumerate(slides):
        path_prefix = f"slides[{i}]"

        # Check for text-wall slides
        text_blocks = [
            b for b in slide.content_blocks
            if getattr(b, "block_type", None) in {ContentBlockType.TEXT, ContentBlockType.BULLET_LIST}
        ]
        visual_blocks = [
            b for b in slide.content_blocks
            if getattr(b, "block_type", None) in {
                ContentBlockType.IMAGE, ContentBlockType.SVG,
                ContentBlockType.ICON, ContentBlockType.STAT,
            }
        ]
        if len(text_blocks) > 3 and len(visual_blocks) == 0:
            result.add_warning(
                path_prefix,
                "Slide has many text blocks but no visual elements — "
                "consider adding an image, icon, or statistic.",
            )

        # Check bullet list length
        for j, block in enumerate(slide.content_blocks):
            block_path = f"{path_prefix}.content_blocks[{j}]"
            if getattr(block, "block_type", None) == ContentBlockType.BULLET_LIST:
                items = getattr(block, "items", [])
                if len(items) > 6:
                    result.add_warning(
                        block_path,
                        f"Bullet list has {len(items)} items — recommend ≤6 for readability.",
                    )

        # Two/Three column layouts need some content
        if slide.layout.layout in {SlideLayout.TWO_COLUMN, SlideLayout.THREE_COLUMN}:
            if len(slide.content_blocks) < 2:
                result.add_warning(
                    path_prefix,
                    f"Layout '{slide.layout.layout.value}' expects multiple content blocks.",
                )


def _check_slide_roles(slides: list[SlideSpec], result: ValidationResult) -> None:
    """Validate narrative structure."""
    if not slides:
        return

    first = slides[0]
    if first.role not in {SlideRole.COVER, SlideRole.CONTENT}:
        result.add_warning(
            "slides[0]",
            f"First slide has role '{first.role.value}' — expected 'cover'.",
        )

    last = slides[-1]
    if last.role not in {SlideRole.CLOSING, SlideRole.CONTENT}:
        result.add_warning(
            f"slides[{len(slides)-1}]",
            "Last slide should have role 'closing' for a complete deck.",
        )


def _check_duplicate_titles(slides: list[SlideSpec], result: ValidationResult) -> None:
    """Flag duplicate slide titles."""
    seen: dict[str, int] = {}
    for i, slide in enumerate(slides):
        norm = slide.title.strip().lower()
        if norm in seen:
            result.add_warning(
                f"slides[{i}]",
                f"Duplicate slide title '{slide.title}' (also at slides[{seen[norm]}]).",
            )
        else:
            seen[norm] = i


def _check_theme(theme: ThemeSpec, result: ValidationResult) -> None:
    """Theme-level sanity checks."""
    colors = theme.colors
    # Warn if text color is too similar to background (accessibility)
    if colors.text_primary.lower() == colors.background.lower():
        result.add_error(
            "theme.colors",
            "text_primary and background are the same color — text will be invisible.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def validate_deck(deck: DeckSpec) -> ValidationResult:
    """Run all business-rule validators on a DeckSpec.

    Pydantic schema validation is assumed to have already passed.

    Args:
        deck: A fully constructed, schema-valid DeckSpec.

    Returns:
        ValidationResult with errors (blocking) and warnings (advisory).
    """
    result = ValidationResult(valid=True)

    _check_slide_count(deck, result)
    _check_layout_diversity(deck.slides, result)
    _check_content_blocks(deck.slides, result)
    _check_slide_roles(deck.slides, result)
    _check_duplicate_titles(deck.slides, result)
    _check_theme(deck.theme, result)

    return result


def parse_and_validate_deck(raw: dict[str, Any]) -> tuple[DeckSpec, ValidationResult]:
    """Parse a raw dict into a DeckSpec and run full validation.

    Args:
        raw: Unvalidated input dict (e.g. from JSON payload).

    Returns:
        Tuple of (DeckSpec, ValidationResult).

    Raises:
        pydantic.ValidationError: If schema validation fails.
    """
    deck = DeckSpec.model_validate(raw)
    result = validate_deck(deck)
    return deck, result

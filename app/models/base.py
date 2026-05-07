"""Shared base Pydantic models.

Phase 2 extends these with domain-specific deck, slide, and theme schemas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class SliderBaseModel(BaseModel):
    """Root base class for all Slider MCP models.

    Enables:
    - strict mode (no coercion surprises)
    - JSON serialisation of datetime/UUID
    - frozen instances where required by subclasses
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampedModel(SliderBaseModel):
    """Adds audit timestamps to a model."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdentifiedModel(TimestampedModel):
    """Adds a unique ID to a timestamped model."""

    id: str = Field(default_factory=lambda: str(uuid4()))


class ErrorDetail(SliderBaseModel):
    """Standard error payload returned by API and MCP tools."""

    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class APIError(Exception):
    """Raised for user-facing errors within Slider MCP domain logic."""

    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = ErrorDetail(code=code, message=message, context=context or {})

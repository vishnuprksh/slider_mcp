"""Phase 1 — base model unit tests."""
from __future__ import annotations

import pytest

from app.models.base import APIError, ErrorDetail, IdentifiedModel, SliderBaseModel, TimestampedModel


def test_slider_base_model_instantiates():
    class Foo(SliderBaseModel):
        x: int

    m = Foo(x=1)
    assert m.x == 1


def test_timestamped_model_has_timestamps():
    class Bar(TimestampedModel):
        pass

    b = Bar()
    assert b.created_at is not None
    assert b.updated_at is not None


def test_identified_model_has_id():
    class Baz(IdentifiedModel):
        pass

    b = Baz()
    assert b.id
    # Should be a valid UUID string
    import uuid
    uuid.UUID(b.id)


def test_error_detail_fields():
    e = ErrorDetail(code="TEST_001", message="test error")
    assert e.code == "TEST_001"
    assert e.message == "test error"
    assert e.context == {}


def test_api_error_wraps_detail():
    exc = APIError(code="E001", message="something went wrong", context={"field": "x"})
    assert exc.detail.code == "E001"
    assert exc.detail.context["field"] == "x"
    assert str(exc) == "something went wrong"


def test_string_stripping():
    class M(SliderBaseModel):
        name: str

    m = M(name="  hello  ")
    assert m.name == "hello"

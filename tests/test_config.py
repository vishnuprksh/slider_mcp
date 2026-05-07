"""Phase 1 — configuration loading and validation tests."""
from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def test_default_settings_are_sane():
    s = Settings()
    assert s.app_name == "Slider MCP"
    assert s.environment == "development"
    assert s.port == 8000
    assert s.log_level == "INFO"
    assert s.log_format == "json"
    assert s.api_key is None


def test_is_production_flag_false_by_default():
    s = Settings()
    assert s.is_production is False


def test_is_production_flag_true_when_set():
    s = Settings(environment="production")
    assert s.is_production is True


def test_docs_disabled_in_production():
    s = Settings(environment="production")
    assert s.docs_enabled is False


def test_docs_enabled_in_development():
    s = Settings(environment="development")
    assert s.docs_enabled is True


def test_settings_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_invalid_environment_rejected():
    with pytest.raises(Exception):
        Settings(environment="invalid_env")


def test_invalid_log_level_rejected():
    with pytest.raises(Exception):
        Settings(log_level="VERBOSE")


def test_port_boundary_valid():
    s = Settings(port=443)
    assert s.port == 443


def test_port_out_of_range_rejected():
    with pytest.raises(Exception):
        Settings(port=99999)

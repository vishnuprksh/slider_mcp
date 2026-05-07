"""Application configuration via pydantic-settings.

All values can be overridden with environment variables (case-insensitive).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Slider MCP"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    # ── MCP ──────────────────────────────────────────────────────────────────
    mcp_server_name: str = "slider-mcp"
    mcp_server_version: str = "0.1.0"

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── Security ─────────────────────────────────────────────────────────────
    api_key: str | None = None

    # ── Storage ──────────────────────────────────────────────────────────────
    output_dir: str = "/tmp/slider_output"

    # ── Properties ───────────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        """Return True when running in production environment."""
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        """Disable Swagger/ReDoc in production."""
        return not self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()

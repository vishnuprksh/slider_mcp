"""MCP server bootstrap.

Creates and configures the FastMCP server instance. All MCP tools live here.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.logging_config import get_logger
from app.models.deck import ThemeFamily

logger = get_logger(__name__)


def build_mcp_server() -> FastMCP:
    """Construct the FastMCP server with all registered tools."""
    settings = get_settings()

    server = FastMCP(
        name=settings.mcp_server_name,
        # host="0.0.0.0" prevents auto-enabling DNS rebinding protection.
        # DNS rebinding protection is only meaningful when the server listens on
        # localhost; on Render the service is behind a proxy and accepts any host.
        host="0.0.0.0",
        # stateless_http: no persistent session state — correct for horizontally
        # scaled Render deployments where requests may reach different instances.
        # json_response: return plain JSON instead of SSE — easier for clients.
        stateless_http=True,
        json_response=True,
    )

    # ── Phase 1 connectivity sentinel tool ───────────────────────────────────
    @server.tool()
    def ping(message: str = "hello") -> str:
        """Liveness check tool for MCP connectivity validation.

        Args:
            message: Arbitrary string echoed back with a 'pong:' prefix.

        Returns:
            Echo string confirming the server is reachable.
        """
        logger.debug("ping called", message=message)
        return f"pong: {message}"

    # ── Phase 7 domain tools ─────────────────────────────────────────────────

    @server.tool()
    async def generate_deck(
        topic: str,
        audience: str = "general",
        purpose: str = "inform",
        slide_count: int = 8,
        outline: list[str] | None = None,
        export_format: str = "html",
    ) -> dict[str, Any]:
        """Generate a complete presentation deck from a topic.

        Args:
            topic: The subject matter for the deck.
            audience: Target audience (e.g. 'executive', 'developer', 'general').
            purpose: Deck purpose ('inform', 'pitch', 'educate', 'persuade').
            slide_count: Desired number of slides (3-60, clamped automatically).
            outline: Optional list of slide titles to guide content planning.
            export_format: Output format — 'html' (default) or 'pptx' (base64).

        Returns:
            dict with keys:
              - deck_id: UUID of the generated deck
              - title: Deck title
              - slide_count: Actual number of slides
              - theme: Theme family used
              - html: Rendered HTML string (if export_format='html')
              - pptx_base64: Base64-encoded PPTX bytes (if export_format='pptx')
        """
        import base64

        from app.renderers.html_renderer import render_html
        from app.renderers.pptx_renderer import render_pptx
        from app.services.planning import PlanningRequest, plan_deck

        request = PlanningRequest(
            topic=topic,
            audience=audience,
            purpose=purpose,
            slide_count=slide_count,
            outline=outline or [],
        )
        deck = plan_deck(request)
        logger.info("deck planned", topic=topic, slides=len(deck.slides))

        result: dict[str, Any] = {
            "deck_id": deck.id,
            "title": deck.title,
            "slide_count": len(deck.slides),
            "theme": deck.theme.family.value,
        }

        fmt = export_format.lower()
        if fmt == "pptx":
            pptx_bytes = render_pptx(deck)
            result["pptx_base64"] = base64.b64encode(pptx_bytes).decode()
        else:
            result["html"] = render_html(deck)

        return result

    @server.tool()
    async def validate_deck_spec(raw_deck: dict[str, Any]) -> dict[str, Any]:
        """Validate a deck specification against schema and business rules.

        Args:
            raw_deck: Raw dict conforming to DeckSpec schema.

        Returns:
            dict with keys:
              - valid: bool
              - errors: list of error messages
              - warnings: list of warning messages
        """
        from app.services.validation import parse_and_validate_deck

        try:
            _, result = parse_and_validate_deck(raw_deck)
            return {
                "valid": result.valid,
                "errors": [{"path": i.path, "message": i.message} for i in result.errors],
                "warnings": [{"path": i.path, "message": i.message} for i in result.warnings],
            }
        except Exception as exc:
            return {
                "valid": False,
                "errors": [{"path": "", "message": str(exc)}],
                "warnings": [],
            }

    @server.tool()
    async def search_icons(query: str, limit: int = 6) -> list[dict[str, Any]]:
        """Search for clipart/icon assets matching a query.

        Args:
            query: Search terms (e.g. 'rocket startup', 'data chart').
            limit: Maximum number of results to return (1-20).

        Returns:
            List of asset dicts with keys: source, alt_text, type.
        """
        from app.services.assets import search_clipart

        limit = max(1, min(20, limit))
        assets = await search_clipart(query, limit=limit)
        return [
            {"source": a.source, "alt_text": a.alt_text or "", "type": a.asset_type.value}
            for a in assets
        ]

    @server.tool()
    async def get_deck_themes() -> list[dict[str, str]]:
        """Return all available deck theme families with descriptions.

        Returns:
            List of dicts with keys: name, value.
        """
        descriptions = {
            ThemeFamily.CORPORATE: "Professional blues and greys, serif typography",
            ThemeFamily.STARTUP: "Bold gradients, modern sans-serif, high contrast",
            ThemeFamily.CREATIVE: "Vibrant accents, expressive typography",
            ThemeFamily.TECH: "Dark mode, monospace code blocks, neon accents",
            ThemeFamily.MINIMAL: "Clean white space, single accent color",
            ThemeFamily.DARK: "Dark backgrounds with light text, sleek aesthetic",
            ThemeFamily.NATURE: "Earth tones, organic palette, sustainability focus",
        }
        return [
            {"name": tf.name, "value": tf.value, "description": descriptions.get(tf, "")}
            for tf in ThemeFamily
        ]

    logger.info("MCP server built", name=settings.mcp_server_name)
    return server


# Module-level singleton — imported by main.py and tests
mcp_server: FastMCP = build_mcp_server()

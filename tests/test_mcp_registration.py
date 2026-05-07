"""Phase 1 — MCP server registration and connectivity tests."""
from __future__ import annotations

import json


def test_mcp_server_has_ping_tool():
    """Verify the ping tool is registered on the MCP server instance."""
    from app.mcp_server import mcp_server

    # FastMCP exposes registered tools via _tool_manager._tools dict
    tool_names = list(mcp_server._tool_manager._tools.keys())
    assert "ping" in tool_names, f"Expected 'ping' in {tool_names}"


def test_mcp_endpoint_reachable(lifespan_client):
    """POST to /mcp should respond — not 404."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.0.1"},
        },
    }
    response = lifespan_client.post(
        "/mcp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code != 404, "MCP endpoint must be mounted"
    assert response.status_code < 500, f"Server error on MCP init: {response.text}"


def test_mcp_initialize_returns_server_info(lifespan_client):
    """MCP initialize should return server capabilities and name."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        },
    }
    response = lifespan_client.post(
        "/mcp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("jsonrpc") == "2.0"
    assert "result" in data
    result = data["result"]
    assert "serverInfo" in result
    assert result["serverInfo"]["name"] == "slider-mcp"


def test_mcp_tools_list(lifespan_client):
    """tools/list should return at least the ping tool."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    # Initialize first
    init_resp = lifespan_client.post(
        "/mcp",
        content=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.0.1"},
            },
        }),
        headers=headers,
    )
    assert init_resp.status_code == 200

    # List tools (stateless: no session ID needed)
    tools_resp = lifespan_client.post(
        "/mcp",
        content=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        headers=headers,
    )
    assert tools_resp.status_code == 200
    data = tools_resp.json()
    tool_names = [t["name"] for t in data.get("result", {}).get("tools", [])]
    assert "ping" in tool_names, f"Expected 'ping' in {tool_names}"


def test_mcp_ping_tool_call(lifespan_client):
    """Calling the ping tool should echo the message."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    response = lifespan_client.post(
        "/mcp",
        content=json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {"message": "phase1"}},
        }),
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    content = data.get("result", {}).get("content", [])
    assert any("phase1" in str(c) for c in content), f"Expected echo in {content}"


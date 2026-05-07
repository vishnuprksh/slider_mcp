# Slider MCP

Remote MCP server for visually rich slide / presentation generation. Designed to be deployed on Render and consumed by MCP-compatible agents (Claude, Cursor, VS Code Copilot, etc.).

## Quick start (local)

```bash
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt
python3 -m pytest tests/          # all green
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`. MCP endpoint: `http://localhost:8000/mcp`.

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/health` | GET | Liveness + version |
| `/` | GET | Root info |
| `/mcp` | POST | MCP Streamable HTTP (JSON-RPC) |
| `/docs` | GET | Swagger UI (dev only) |

## MCP client config (VS Code / Claude / Cursor)

```json
{
  "mcpServers": {
    "slider-mcp": {
      "url": "https://<your-render-url>/mcp",
      "type": "http"
    }
  }
}
```

## Deployment (Render)

1. Push to GitHub
2. Connect repo on Render → Web Service
3. Render auto-detects `render.yaml`
4. Set `API_KEY` in Render env vars (auto-generated if you use `generateValue: true`)
5. Health check: `/health`

## Project structure

```
app/
  main.py            # FastAPI app factory
  config.py          # pydantic-settings config
  logging_config.py
  mcp_server.py      # FastMCP server + tool registration
  routes/health.py
  models/base.py     # Shared Pydantic base models
tests/
  conftest.py
  test_health.py
  test_config.py
  test_base_models.py
  test_mcp_registration.py
Dockerfile
docker-compose.yml
render.yaml
```

## Development

```bash
pytest tests/ -q                    # run tests
pytest tests/ --cov=app             # with coverage
uvicorn app.main:app --reload       # hot-reload dev server
docker compose up                   # Docker dev environment
```

## Build phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Core foundation: FastAPI + MCP bootstrap, config, logging, health |
| 2 | ⏳ | Deck domain models + validation layer |
| 3 | ⏳ | Deck planning engine |
| 4 | ⏳ | Asset + clipart system |
| 5 | ⏳ | HTML rendering engine |
| 6 | ⏳ | PPTX rendering engine |
| 7 | ⏳ | MCP tool layer |
| 8 | ⏳ | Stitch integration |
| 9 | ⏳ | Production hardening |
| 10 | ⏳ | Deployment + final verification |
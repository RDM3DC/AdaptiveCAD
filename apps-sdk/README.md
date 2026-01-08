# AdaptiveCAD + Apps SDK (MCP) quickstart

This folder adds a minimal **MCP HTTP server** and a small **HTML widget UI** so ChatGPT (Apps & Connectors / Developer Mode) can drive an AdaptiveCAD tool.

The first tool is intentionally simple and headless-safe:
- `run_josephson` runs the example simulation in `examples/adaptive_josephson_lattice.py` **without opening any GUI windows**.

## Files

- `public/adaptivecad-widget.html` — widget UI rendered in ChatGPT
- `server.js` — MCP server exposing AdaptiveCAD tools
- `adaptivecad_bridge.py` — Python bridge (outputs JSON)

## Install

From the repo’s `AdaptiveCAD` folder:

```powershell
cd AdaptiveCAD\apps-sdk
npm install
```

## Run locally

```powershell
npm start
```

You should see:

- `AdaptiveCAD MCP server listening on http://localhost:8787/mcp`

Health check:

- `http://localhost:8787/`

## Test with MCP Inspector

```powershell
npx @modelcontextprotocol/inspector@latest --server-url http://localhost:8787/mcp --transport http
```

## Connect from ChatGPT

1. Enable **Developer mode** in ChatGPT settings.
2. Expose your local server via a tunnel (e.g. `ngrok http 8787`).
3. In **Settings → Connectors → Create**, paste the tunnel URL + `/mcp` (e.g. `https://xxxx.ngrok.app/mcp`).
4. Add the connector to a chat and ask it to run the simulation.

## Notes

- Python resolution order:
  1. `PYTHON` env var if set
  2. `..\.venv\Scripts\python.exe` relative to the `AdaptiveCAD` folder
  3. `python` from PATH

If you want the MCP to expose additional AdaptiveCAD tools (mesh repair, analytic viewport exports, etc.), we can add more subcommands to `adaptivecad_bridge.py` and register more tools in `server.js`.

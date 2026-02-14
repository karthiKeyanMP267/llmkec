# OpenCode Chat UI (Simple)

A minimal ChatGPT-like web UI that uses the OpenCode SDK on a local Node server.

## Prereqs

- Node.js (you already have this)
- OpenCode configured with at least one provider (via `opencode` TUI `/connect`, or your existing setup)

## Run (dev)

From the repo root:

```bash
npm install
npm run dev
```

- Web UI: http://localhost:5173
- API: http://localhost:8787/api/health

## Provider API keys (.env)

Create a .env file at the repo root (see [.env.example](.env.example)) and add provider keys like:

- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GROQ_API_KEY
- GOOGLE_API_KEY
- MISTRAL_API_KEY

The server loads .env on startup and passes these to OpenCode automatically.

## Notes

- The backend starts an OpenCode server via the OpenCode CLI (`opencode-ai`).
- By default, OpenCode picks a free port automatically.
- You can force a fixed port (pick a free one):

```bash
set OPENCODE_PORT=8010
```

Then re-run `npm run dev`.

- Automatic port selection is the default. You can also force it explicitly:

```bash
set OPENCODE_PORT=auto
```

- OpenCode is started automatically when the API starts (to avoid first-message cold start). To disable and start it only when needed:

```bash
set OPENCODE_EAGER_START=0
```

- If the very first request feels slow (cold start), you can start OpenCode immediately when the API starts:

```bash
set OPENCODE_EAGER_START=1
```

- If you hit `Timeout waiting for OpenCode server to start...`, you can increase the startup timeout:

```bash
set OPENCODE_STARTUP_TIMEOUT_MS=60000
```

Note: a fixed port does not make the model itself faster; it just makes the OpenCode URL predictable.

## If you see `spawn opencode ENOENT`

This means the backend cannot find the `opencode` CLI on PATH.

Fix options:

1) Add npm global bin to PATH (Windows)

- Find it with: `npm bin -g`
- Add that folder to your user PATH (often `C:\Users\<you>\AppData\Roaming\npm`)

2) Or set an explicit path to the CLI:

```bash
set OPENCODE_BIN=C:\path\to\opencode.exe
```

## MCP (Model Context Protocol)

If you already have MCP servers configured (for example from a Copilot/MCP setup), this app can surface them and their tools.

- The backend no longer overwrites `OPENCODE_CONFIG_CONTENT`, so OpenCode can load your normal config (including `mcp` entries).
- MCP endpoints:
	- `GET /api/mcp/status`
	- `POST /api/mcp/add` (body: `{ "name": "...", "config": { ... } }`)
	- `POST /api/mcp/connect` / `POST /api/mcp/disconnect` (body: `{ "name": "..." }`)
- Tools endpoint:
	- `GET /api/tools?provider=...&model=...`

Optional directory context:
- `OPENCODE_DIRECTORY` controls the directory context OpenCode uses. If not set, the backend uses `INIT_CWD` (when started via npm) or `process.cwd()`.

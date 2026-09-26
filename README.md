# claude-muse-bridge

An MCP bridge between **Claude** and **Muse** (or any producer/consumer pair).

One side produces markdown briefs — reports, analytics, content plans. This server
exposes them to Claude as MCP tools, so Claude can ground its work in real data
instead of vibes. Backends and transports are configurable via env vars, so the
same code runs on a laptop (stdio + local folder) or on Azure (HTTP + Blob Storage).

## Tools

| Tool | What it does |
|---|---|
| `list_briefs` | Lists available briefs, oldest first |
| `get_latest_brief` | Returns the newest brief (markdown) |
| `get_brief` | Returns one brief by name |

## Quickstart — local (5 minutes)

```bash
git clone https://github.com/<you>/claude-muse-bridge.git
cd claude-muse-bridge
pip install "."

mkdir -p ~/briefs
# drop a markdown brief into ~/briefs/

# test it
mcp dev src/bridge/server.py
```

Connect to Claude Code:

```bash
claude mcp add my-briefs -- python -m bridge.server
# (with BRIDGE_BRIEFS_DIR exported, or a .env file in the working dir)
```

Then in Claude: *"list my briefs"* / *"read the latest brief and use it."*

## Configuration

Copy `.env.example` to `.env` and edit, or export the variables directly.
CLI flags (`--transport`, `--backend`, `--briefs-dir`, `--port`) override env vars.

| Variable | Default | Purpose |
|---|---|---|
| `BRIDGE_BACKEND` | `local` | `local` (folder) or `azure` (Blob Storage) |
| `BRIDGE_TRANSPORT` | `stdio` | `stdio` (local) or `http` (hosted) |
| `BRIDGE_BRIEFS_DIR` | `~/briefs` | Folder of `*.md` briefs (local backend) |
| `BRIDGE_STORAGE_ACCOUNT` | — | Azure storage account (azure backend) |
| `BRIDGE_CONTAINER` | `briefs` | Blob container (azure backend) |
| `BRIDGE_SAS_TOKEN` | — | SAS token, create/write/list on the container |
| `BRIDGE_API_KEY` | — | **Required** for `http` transport; sent as `X-Api-Key` header |
| `BRIDGE_HOST` | `127.0.0.1` | HTTP bind host |
| `BRIDGE_PORT` | `8000` | HTTP port |

## Hosted on Azure (always-on)

1. Create a resource group, storage account, and `briefs` container in the
   Azure Portal or CLI; generate a SAS token (create/write/list, container scope).
2. Build and push the Docker image, or deploy straight from source:

```bash
az containerapp up \
  --name claude-muse-bridge \
  --resource-group <rg> \
  --location canadacentral \
  --source . \
  --ingress external \
  --target-port 8000

az containerapp secret set --name claude-muse-bridge --resource-group <rg> \
  --secrets apikey=<random-key> sas=<sas-token>

az containerapp update --name claude-muse-bridge --resource-group <rg> \
  --set-env-vars \
    BRIDGE_TRANSPORT=http \
    BRIDGE_BACKEND=azure \
    BRIDGE_API_KEY=secretref:apikey \
    BRIDGE_STORAGE_ACCOUNT=<account> \
    BRIDGE_SAS_TOKEN=secretref:sas
```

3. Connect Claude to the remote server:

```bash
claude mcp add --transport http my-briefs \
  https://<app-url>/mcp \
  --header "X-Api-Key: <random-key>"
```

At this volume (a few calls per session) Azure Container Apps costs pennies —
it scales to zero when idle.

## The loop this was built for

A producer (e.g. a scheduled Muse agent) writes a fresh brief after every run
and uploads it to the backend. Claude reads it at the start of each session.
Nobody ferries files by hand.

## Adding a backend

1. Subclass `bridge.backends.base.BriefBackend`
   (`list_briefs()` oldest-first, `read_brief(name)` raising `FileNotFoundError`).
2. Register it in `bridge/backends/__init__.py:get_backend`.
3. Add its settings to `bridge/config.py` and document them here.

## Security notes

- The `http` transport requires `BRIDGE_API_KEY`; without it the server refuses to start.
- Scope SAS tokens to the briefs container only (create/write/list, no delete).
- Never commit `.env` or secrets — `.gitignore` already excludes them.

## License

MIT — see [LICENSE](LICENSE).

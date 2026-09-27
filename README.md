# claude-muse-bridge

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAmRaghuAkula%2Fclaude-muse-bridge%2Fmain%2Fazuredeploy.json)

*One-click Azure deploy, no terminal. Walkthrough: [docs/azure-deploy.md](docs/azure-deploy.md).*

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
| `verify_brief` | Checks a brief against its SHA-256 sidecar (`OK` / `SKIPPED` / `FAILED` / `NOT FOUND`) |
| `list_channels` | Lists bidirectional message channels |
| `read_messages` | Reads messages from a channel (JSON; `after_id` for new ones only) |
| `send_message` | Posts a message to a channel |

## Integrity: hash-sealed briefs

A sealed brief `brief.md` has a sibling `brief.md.sha256`. When a sidecar is
present, the server verifies content on every read and **refuses to serve**
tampered briefs instead of letting them flow into Claude's context.
`verify_brief` reports the status explicitly.

```bash
# seal all briefs after writing them (producer side)
python -m bridge.cli seal
```

Unsealed briefs keep working as before — sealing is opt-in per file.

## Bidirectional channels

Channels are named mailboxes shared between a Muse chat and a Claude session
(or any two parties). Pair a chat with a session by agreeing on a channel name,
then both sides converse through `send_message` / `read_messages`.

Storage follows `BRIDGE_BACKEND`: local JSONL files, or one Azure append blob
per channel (`<name>.jsonl`) in the channels container. Append blobs mean every
send is a single atomic append — concurrent writers can't clobber each other.

```bash
# operator CLI (Muse side)
python -m bridge.cli channels
python -m bridge.cli send -c content-strategy -a chitti "fresh brief is up"
python -m bridge.cli read -c content-strategy
```

Server-enforced ceilings (v1): channel names limited to `a-z 0-9 _ -`
(also blocks path traversal), authors ≤ 64 chars, messages ≤ 4000 chars,
reads ≤ 200 messages per call.

## Quickstart — local (5 minutes)

```bash
git clone https://github.com/AmRaghuAkula/claude-muse-bridge.git
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
| `BRIDGE_CHANNELS_DIR` | `~/bridge-channels` | Folder holding channel message files (local backend) |
| `BRIDGE_CHANNELS_CONTAINER` | `channels` | Blob container for channels (azure backend) |

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
- Sealed briefs are verified on every read; tampered content is refused, not served.
- Channel guardrails live in the server, not in prompts: name allowlist,
  author/message length caps, read limits.
- Never commit `.env` or secrets — `.gitignore` already excludes them.

## License

MIT — see [LICENSE](LICENSE).

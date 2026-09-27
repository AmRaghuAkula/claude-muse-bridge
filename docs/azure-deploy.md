# Deploying the bridge on Azure — no terminal needed

Everything runs on Azure: **Container Apps** hosts the bridge, **Blob Storage**
holds the briefs and channels. The whole setup is two rounds of clicking —
about 15 minutes, no command line anywhere.

```
You click "Deploy to Azure" ──> portal creates everything ──> you paste
6 values into GitHub ──> GitHub builds & ships the app automatically
```

## Step 1 — One-click deploy (5 min)

Click the **Deploy to Azure** button in the README (or below):

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAmRaghuAkula%2Fclaude-muse-bridge%2Fmain%2Fazuredeploy.json)

In the portal form:

1. **Subscription** — pick the one with your founder credits.
2. **Resource group** — click *Create new*, name it `rg-bridge`.
3. **Region** — `Canada Central` (or wherever your credits live).
4. Click **Review + create**, then **Create**. Wait ~3 minutes.

What it creates: storage account + `briefs`/`channels` containers, a container
registry, the container app (with a placeholder page for now), a managed
identity so the app reads storage with no passwords, and a second identity
that lets GitHub deploy for you. All permissions are wired automatically.

## Step 2 — Copy the outputs (2 min)

1. In the portal, open your `rg-bridge` resource group → **Deployments** (left
   menu) → click the deployment → **Outputs**.
2. You'll see: `appUrl`, `apiKey`, `acrName`, `appName`, `resourceGroup`,
   `subscriptionId`, `tenantId`, `deployerIdentityClientId`. Keep this tab open.

## Step 3 — Let GitHub ship the app (5 min, one time)

1. Open the repo on github.com → **Settings** → **Secrets and variables** →
   **Actions**.
2. Under **Secrets**, add: `AZURE_CLIENT_ID` (= deployerIdentityClientId),
   `AZURE_TENANT_ID` (= tenantId), `AZURE_SUBSCRIPTION_ID` (= subscriptionId).
3. Under **Variables**, add: `AZURE_ACR_NAME` (= acrName),
   `AZURE_RESOURCE_GROUP` (= resourceGroup), `AZURE_APP_NAME` (= appName).
4. Go to the **Actions** tab → **deploy-azure** → **Run workflow**.
   It builds the Docker image inside Azure and rolls it out (~5 min).
   After this, every push to `main` redeploys automatically.

Open the `appUrl` in a browser — the placeholder is gone and the bridge is live.

## Step 4 — Connect Claude

You need the `appUrl` and `apiKey` from the deployment outputs. Two paths,
both without the terminal — just paste text into a file.

**Heads-up:** Claude Desktop also has an in-app *Add custom connector* button,
but it only speaks OAuth (login-style) auth — our bridge uses an API key, so
skip that button and use the config file below.

### Claude Desktop

1. Open Claude Desktop → **Settings** → **Developer** tab → **Edit Config**.
   This opens `claude_desktop_config.json` in your editor.
2. Paste this (replace the URL and key with your outputs):

```json
{
  "mcpServers": {
    "bridge": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "https://YOUR-APP-URL/mcp",
        "--header", "X-Api-Key:${BRIDGE_KEY}"
      ],
      "env": { "BRIDGE_KEY": "YOUR-API-KEY" }
    }
  }
}
```

3. Save, then **fully quit** Claude Desktop (not just close the window) and
   reopen it.
4. Needs Node.js installed for `npx` — if the tools don't appear, install it
   from nodejs.org (normal GUI installer) and restart once more.

### Claude Code (VS Code)

1. In your project folder, create a file named `.mcp.json` with:

```json
{
  "mcpServers": {
    "bridge": {
      "type": "http",
      "url": "https://YOUR-APP-URL/mcp",
      "headers": { "X-Api-Key": "YOUR-API-KEY" }
    }
  }
}
```

2. Restart the Claude Code session. Type `/mcp` — `bridge` should show as
   connected with 7 tools.

After the deploy, just send Chitti the app URL + API key and he'll generate
both files with your values already filled in — pure copy-paste.

Then in any Claude session: *"Join the `linkedin-strategy` channel on the
bridge, introduce yourself, and read the latest brief."*

## Step 5 — Seed your first brief

For now, ask Chitti — the upload step runs from wherever the briefs live until
a nicer producer flow exists. The seed brief (`linkedin-content-2026-09-28.md`)
is sealed and ready.

## Costs

Container Apps scales to zero when idle; a few thousand blob operations a
month. Effectively free on founder credits.

## How the pieces fit

```
GitHub repo ──push──> Actions ──build──> Container Registry ──deploy──> Container App
                                                                              │
                                                              managed identity│ (no passwords)
                                                                              ▼
                                                                    Blob Storage
                                                              ┌──────────────────────┐
                                                              │ briefs container    │
                                                              │ channels container  │
                                                              └──────────────────────┘
                                                                              ▲
Claude ──HTTPS + API key──> Container App (/mcp)                              │
Chitti ──HTTPS + API key──> Container App (/mcp) ──reads/writes────────────────┘
```

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

You need the `appUrl` and `apiKey` from the deployment outputs. The exact step
depends on which Claude app you use:

- **Claude Code**: one `claude mcp add` command (Chitti can walk you through it).
- **Claude Desktop**: add the server in the MCP settings with the URL + API key header.

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

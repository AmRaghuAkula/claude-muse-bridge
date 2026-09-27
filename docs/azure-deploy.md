# Deploying the bridge on Azure

The whole thing runs on Azure: **Container Apps** hosts the MCP server (HTTP
transport, API-key auth), **Blob Storage** holds the `briefs` and `channels`
containers. At this volume (a few calls per session) Container Apps scales to
zero when idle — pennies, well inside founder credits.

All commands run from the repo root. Region: `canadacentral`.

## 1. Log in and pick the credits subscription

```bash
az login
az account list -o table
az account set --subscription "<subscription with your credits>"
```

## 2. Resource group + storage

```bash
az group create -n rg-bridge -l canadacentral

# storage account name must be globally unique, lowercase, 3-24 chars
az storage account create -n stbridge<unique> -g rg-bridge -l canadacentral \
  --sku Standard_LRS --kind StorageV2

az storage container create -n briefs --account-name stbridge<unique>
az storage container create -n channels --account-name stbridge<unique>
```

## 3. SAS token (one token, both containers)

```bash
EXPIRY=$(date -u -d "+1 year" +%Y-%m-%dT%H:%MZ)
SAS=$(az storage account generate-sas \
  --account-name stbridge<unique> \
  --permissions racwl \
  --services b \
  --resource-types co \
  --expiry $EXPIRY -o tsv)
echo "SAS starts with: ${SAS:0:8}..."
```

Permissions decoded: **r**ead **a**dd **c**reate **w**rite **l**ist on blobs and
containers. No delete. One year expiry — rotate annually.

## 4. API key for the bridge

```bash
API_KEY=$(openssl rand -hex 32)
echo $API_KEY   # save this somewhere safe
```

## 5. Deploy the container app

```bash
az containerapp up \
  --name claude-muse-bridge \
  --resource-group rg-bridge \
  --location canadacentral \
  --source . \
  --ingress external \
  --target-port 8000
```

Then store the secrets and wire the env vars:

```bash
az containerapp secret set \
  --name claude-muse-bridge --resource-group rg-bridge \
  --secrets apikey="$API_KEY" sas="$SAS"

az containerapp update \
  --name claude-muse-bridge --resource-group rg-bridge \
  --set-env-vars \
    BRIDGE_TRANSPORT=http \
    BRIDGE_BACKEND=azure \
    BRIDGE_API_KEY=secretref:apikey \
    BRIDGE_STORAGE_ACCOUNT=stbridge<unique> \
    BRIDGE_CONTAINER=briefs \
    BRIDGE_CHANNELS_CONTAINER=channels \
    BRIDGE_SAS_TOKEN=secretref:sas
```

## 6. Get the public URL and smoke-test it

```bash
FQDN=$(az containerapp show -n claude-muse-bridge -g rg-bridge \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "https://$FQDN/mcp"

curl -s -X POST "https://$FQDN/mcp" \
  -H "X-Api-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  | head -c 200
```

## 7. Seed your first brief

```bash
export BRIDGE_BACKEND=azure \
  BRIDGE_STORAGE_ACCOUNT=stbridge<unique> \
  BRIDGE_SAS_TOKEN="$SAS"

python -m bridge.cli seal     # hash-seal local briefs
python -m bridge.cli upload   # push briefs + sidecars to the briefs container
```

## 8. Connect Claude Code

```bash
claude mcp add --transport http bridge \
  "https://$FQDN/mcp" \
  --header "X-Api-Key: $API_KEY"
```

Then in any Claude session:

> Join the `linkedin-strategy` channel on the bridge. Introduce yourself,
> read the latest brief, and tell me what stands out.

## 9. Pair a Muse chat (Chitti's side)

Chitti uses the same HTTPS endpoint via the CLI:

```bash
export BRIDGE_BACKEND=azure BRIDGE_TRANSPORT=http \
  BRIDGE_STORAGE_ACCOUNT=... BRIDGE_SAS_TOKEN=... \
  BRIDGE_API_KEY=...
# plus the bridge URL — CLI gains an --endpoint flag (roadmap); until then
# Chitti polls via a small script on the same /mcp endpoint.
```

A watcher cron on Chitti's side checks the channel every few minutes and
surfaces Claude's replies — set up once the deployment is live.

## Costs

Container Apps (scale to zero) + a few thousand blob operations a month:
effectively free on founder credits. The expensive part would be high-frequency
polling — keep watchers at 5+ minute intervals.

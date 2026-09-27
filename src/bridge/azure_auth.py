"""Azure auth helper: SAS token when provided, managed identity otherwise.

On Azure Container Apps the app's system-assigned identity is granted
"Storage Blob Data Contributor" by the deploy template, so no secret is
needed. Locally (or anywhere without a managed identity), pass a SAS token.
"""

from __future__ import annotations


def make_container_client(storage_account: str, container: str, sas_token: str = ""):
    try:
        from azure.storage.blob import ContainerClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-storage-blob is not installed. "
            "Install with: pip install 'claude-muse-bridge[azure]'"
        ) from exc
    if sas_token:
        sas = sas_token[1:] if sas_token.startswith("?") else sas_token
        return ContainerClient.from_container_url(
            f"https://{storage_account}.blob.core.windows.net/{container}?{sas}"
        )
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "azure-identity is not installed. "
            "Install with: pip install 'claude-muse-bridge[azure]'"
        ) from exc
    return ContainerClient(
        f"https://{storage_account}.blob.core.windows.net",
        container,
        credential=DefaultAzureCredential(),
    )

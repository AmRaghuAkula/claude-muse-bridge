"""Azure Blob Storage backend: briefs are *.md blobs in a container."""

from __future__ import annotations

from .base import BriefBackend


class AzureBlobBackend(BriefBackend):
    def __init__(self, storage_account: str, container: str, sas_token: str) -> None:
        try:
            from azure.storage.blob import ContainerClient
        except ImportError as exc:
            raise RuntimeError(
                "azure-storage-blob is not installed. Install with: pip install 'claude-muse-bridge[azure]'"
            ) from exc
        sas = sas_token[1:] if sas_token.startswith("?") else sas_token
        self._client = ContainerClient.from_container_url(
            f"https://{storage_account}.blob.core.windows.net/{container}?{sas}"
        )

    def _blobs(self) -> list:
        blobs = [b for b in self._client.list_blobs() if b.name.endswith(".md")]
        return sorted(blobs, key=lambda b: b.last_modified)

    def list_briefs(self) -> list[str]:
        return [b.name for b in self._blobs()]

    def read_brief(self, name: str) -> str:
        if "/" in name or "\\" in name or not name.endswith(".md"):
            raise FileNotFoundError(f"brief not found: {name}")
        try:
            return self._client.download_blob(name).readall().decode("utf-8")
        except Exception as exc:
            raise FileNotFoundError(f"brief not found: {name}") from exc

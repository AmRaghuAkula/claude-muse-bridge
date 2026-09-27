"""Azure Blob Storage backend: briefs are *.md blobs in a container."""

from __future__ import annotations

from bridge.azure_auth import make_container_client
from bridge.integrity import IntegrityError, sha256_text

from .base import BriefBackend


class AzureBlobBackend(BriefBackend):
    def __init__(
        self, storage_account: str, container: str, sas_token: str = ""
    ) -> None:
        self._client = make_container_client(storage_account, container, sas_token)

    def _blobs(self) -> list:
        blobs = [b for b in self._client.list_blobs() if b.name.endswith(".md")]
        return sorted(blobs, key=lambda b: b.last_modified)

    def list_briefs(self) -> list[str]:
        return [b.name for b in self._blobs()]

    def _download(self, name: str) -> str:
        try:
            return self._client.download_blob(name).readall().decode("utf-8")
        except Exception as exc:
            raise FileNotFoundError(f"brief not found: {name}") from exc

    def _check(self, name: str, content: str) -> None:
        """Verify content against the <name>.sha256 blob. Raises IntegrityError."""
        try:
            sidecar = self._download(name + ".sha256")
        except FileNotFoundError:
            return  # unsealed brief: backwards compatible
        expected = sidecar.split()[0]
        actual = sha256_text(content)
        if actual != expected:
            raise IntegrityError(
                f"{name}: content hash {actual[:12]}... does not match "
                f"sidecar {expected[:12]}..."
            )

    def read_brief(self, name: str) -> str:
        if "/" in name or "\\" in name or not name.endswith(".md"):
            raise FileNotFoundError(f"brief not found: {name}")
        content = self._download(name)
        self._check(name, content)  # raises IntegrityError on tampered content
        return content

    def verify_brief(self, name: str) -> str:
        if "/" in name or "\\" in name or not name.endswith(".md"):
            return f"NOT FOUND: {name}"
        try:
            content = self._download(name)
        except FileNotFoundError:
            return f"NOT FOUND: {name}"
        try:
            sidecar = self._download(name + ".sha256")
        except FileNotFoundError:
            return f"SKIPPED: {name} has no sidecar (unsealed brief)"
        expected = sidecar.split()[0]
        if sha256_text(content) == expected:
            return f"OK: {name} matches its sha256 sidecar"
        return f"FAILED: {name} content does not match its sidecar"

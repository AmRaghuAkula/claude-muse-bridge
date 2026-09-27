"""Azure Blob Storage channel backend: one append blob per channel (<name>.jsonl).

Append blobs are the right primitive here: every send is one atomic
``append_block`` call, so concurrent writers can't clobber each other the way
a read-modify-write would.

Auth: SAS token when provided, otherwise the managed identity of the host
(e.g. the Container App's system-assigned identity).
"""

from __future__ import annotations

from .azure_auth import make_container_client
from .channels import BaseChannelStore


class AzureBlobChannelStore(BaseChannelStore):
    def __init__(
        self, storage_account: str, container: str, sas_token: str = ""
    ) -> None:
        try:
            from azure.core.exceptions import ResourceNotFoundError
        except ImportError as exc:
            raise RuntimeError(
                "azure-core is not installed. "
                "Install with: pip install 'claude-muse-bridge[azure]'"
            ) from exc
        self._not_found = ResourceNotFoundError
        self._container = make_container_client(storage_account, container, sas_token)

    def _blob(self, channel: str):
        return self._container.get_blob_client(f"{channel}.jsonl")

    def _list_names(self) -> list[str]:
        return sorted(
            b.name[:-6]
            for b in self._container.list_blobs()
            if b.name.endswith(".jsonl")
        )

    def _read_all(self, channel: str) -> list[dict]:
        from .channels import decode_messages

        try:
            data = self._blob(channel).download_blob().readall()
        except self._not_found:
            return []
        return decode_messages(data)

    def _append(self, channel: str, raw: bytes) -> None:
        blob = self._blob(channel)
        try:
            blob.append_block(raw)
        except self._not_found:
            blob.create_append_blob()
            blob.append_block(raw)

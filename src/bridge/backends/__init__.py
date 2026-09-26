"""Backend factory."""

from __future__ import annotations

from ..config import Settings
from .base import BriefBackend
from .local import LocalBackend


def get_backend(settings: Settings) -> BriefBackend:
    if settings.backend == "local":
        return LocalBackend(settings.briefs_dir)
    if settings.backend == "azure":
        from .azure_blob import AzureBlobBackend

        return AzureBlobBackend(
            storage_account=settings.storage_account,
            container=settings.container,
            sas_token=settings.sas_token,
        )
    raise ValueError(f"unknown backend: {settings.backend!r}")

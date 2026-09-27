"""Configuration for claude-muse-bridge.

Everything is driven by environment variables, with an optional `.env` file
in the working directory. No third-party dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, no variable expansion."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            os.environ.setdefault(key, value)
        break


@dataclass
class Settings:
    backend: str = "local"          # local | azure
    transport: str = "stdio"        # stdio | http
    briefs_dir: Path = field(default_factory=lambda: Path.home() / "briefs")
    storage_account: str = ""       # azure backend
    container: str = "briefs"       # azure backend
    sas_token: str = ""             # azure backend
    api_key: str = ""               # http transport
    host: str = "127.0.0.1"         # http transport
    port: int = 8000                # http transport
    channels_dir: Path = field(     # message channels (local backend)
        default_factory=lambda: Path.home() / "bridge-channels"
    )
    channels_container: str = "channels"  # message channels (azure backend)

    def validate(self) -> None:
        if self.backend not in ("local", "azure"):
            raise ValueError(f"BRIDGE_BACKEND must be 'local' or 'azure', got {self.backend!r}")
        if self.transport not in ("stdio", "http"):
            raise ValueError(f"BRIDGE_TRANSPORT must be 'stdio' or 'http', got {self.transport!r}")
        if self.transport == "http" and not self.api_key:
            raise ValueError("BRIDGE_API_KEY is required when BRIDGE_TRANSPORT=http")
        if self.backend == "azure" and not (self.storage_account and self.sas_token):
            raise ValueError(
                "BRIDGE_STORAGE_ACCOUNT and BRIDGE_SAS_TOKEN are required "
                "when BRIDGE_BACKEND=azure"
            )


def load_settings() -> Settings:
    _load_dotenv()
    return Settings(
        backend=os.environ.get("BRIDGE_BACKEND", "local").strip().lower(),
        transport=os.environ.get("BRIDGE_TRANSPORT", "stdio").strip().lower(),
        briefs_dir=Path(os.environ.get("BRIDGE_BRIEFS_DIR", "~/briefs")).expanduser(),
        storage_account=os.environ.get("BRIDGE_STORAGE_ACCOUNT", "").strip(),
        container=os.environ.get("BRIDGE_CONTAINER", "briefs").strip(),
        sas_token=os.environ.get("BRIDGE_SAS_TOKEN", "").strip(),
        api_key=os.environ.get("BRIDGE_API_KEY", ""),
        host=os.environ.get("BRIDGE_HOST", "127.0.0.1").strip(),
        port=int(os.environ.get("BRIDGE_PORT", "8000")),
        channels_dir=Path(os.environ.get("BRIDGE_CHANNELS_DIR", "~/bridge-channels")).expanduser(),
        channels_container=os.environ.get("BRIDGE_CHANNELS_CONTAINER", "channels").strip(),
    )

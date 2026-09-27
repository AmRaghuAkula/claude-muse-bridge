"""Bidirectional message channels.

A channel is a named mailbox shared by one Muse chat and one Claude session
(or any two parties). Both sides use the MCP tools ``send_message`` /
``read_messages``; operators can also use ``python -m bridge.cli``.

Storage backends:
- ``ChannelStore`` — local JSONL files, one per channel.
- ``bridge.channels_azure.AzureBlobChannelStore`` — Azure append blobs.

Server-enforced ceilings (all backends): channel names are restricted to
``[a-z0-9_-]`` (also blocks path traversal), authors cap at 64 chars,
messages cap at 4000 chars, reads cap at 200 messages per call.
"""

from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_AUTHOR_LEN = 64
MAX_TEXT_LEN = 4000
MAX_READ_LIMIT = 200


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_channel_name(channel: str) -> None:
    if not CHANNEL_RE.match(channel):
        raise ValueError(
            f"invalid channel name {channel!r}: use 1-64 chars of a-z 0-9 _ -"
        )


def make_message(author: str, text: str) -> dict:
    author = author.strip()[:MAX_AUTHOR_LEN]
    text = text.strip()
    if not author:
        raise ValueError("author must not be empty")
    if not text:
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_LEN:
        raise ValueError(f"text exceeds {MAX_TEXT_LEN} characters")
    return {
        "id": uuid.uuid4().hex[:12],
        "ts": _utcnow(),
        "author": author,
        "text": text,
    }


def encode_message(msg: dict) -> bytes:
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def decode_messages(data: bytes) -> list[dict]:
    return [
        json.loads(line)
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]


class BaseChannelStore(ABC):
    """Validation + envelope logic. Subclasses provide the storage."""

    @abstractmethod
    def _list_names(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def _read_all(self, channel: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def _append(self, channel: str, raw: bytes) -> None:
        raise NotImplementedError

    def list_channels(self) -> list[str]:
        return self._list_names()

    def send_message(self, channel: str, author: str, text: str) -> dict:
        check_channel_name(channel)
        msg = make_message(author, text)
        self._append(channel, encode_message(msg))
        return msg

    def read_messages(
        self, channel: str, after_id: str = "", limit: int = 50
    ) -> list[dict]:
        check_channel_name(channel)
        limit = max(1, min(limit, MAX_READ_LIMIT))
        msgs = self._read_all(channel)
        if after_id:
            idx = next(
                (i for i, m in enumerate(msgs) if m.get("id") == after_id), None
            )
            msgs = msgs[idx + 1 :] if idx is not None else msgs
        return msgs[-limit:]


class ChannelStore(BaseChannelStore):
    """Local JSONL-backed channels. One file per channel: <name>.jsonl."""

    def __init__(self, channels_dir: Path) -> None:
        self.channels_dir = channels_dir

    def _path(self, channel: str) -> Path:
        check_channel_name(channel)
        path = (self.channels_dir / f"{channel}.jsonl").resolve()
        if self.channels_dir.resolve() not in path.parents:
            raise ValueError(f"invalid channel name {channel!r}")
        return path

    def _list_names(self) -> list[str]:
        if not self.channels_dir.is_dir():
            return []
        return sorted(p.stem for p in self.channels_dir.glob("*.jsonl"))

    def _read_all(self, channel: str) -> list[dict]:
        path = self._path(channel)
        if not path.is_file():
            return []
        return decode_messages(path.read_bytes())

    def _append(self, channel: str, raw: bytes) -> None:
        path = self._path(channel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as f:
            f.write(raw)


def get_channel_store(settings) -> BaseChannelStore:
    """Channel store matching the configured backend (local dir / azure blob)."""
    if settings.backend == "azure":
        from .channels_azure import AzureBlobChannelStore

        return AzureBlobChannelStore(
            storage_account=settings.storage_account,
            container=settings.channels_container,
            sas_token=settings.sas_token,
        )
    return ChannelStore(settings.channels_dir)

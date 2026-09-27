"""Bidirectional message channels.

A channel is a named mailbox shared by one Muse chat and one Claude session
(or any two parties). Both sides use the MCP tools ``send_message`` /
``read_messages``; operators can also use ``python -m bridge.cli``.

Server-enforced ceilings (v1): channel names are restricted to
``[a-z0-9_-]`` (also blocks path traversal), authors cap at 64 chars,
messages cap at 4000 chars, reads cap at 200 messages per call.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_AUTHOR_LEN = 64
MAX_TEXT_LEN = 4000
MAX_READ_LIMIT = 200


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ChannelStore:
    """Local JSONL-backed channels. One file per channel: <name>.jsonl."""

    def __init__(self, channels_dir: Path) -> None:
        self.channels_dir = channels_dir

    def _path(self, channel: str) -> Path:
        if not CHANNEL_RE.match(channel):
            raise ValueError(
                f"invalid channel name {channel!r}: use 1-64 chars of a-z 0-9 _ -"
            )
        path = (self.channels_dir / f"{channel}.jsonl").resolve()
        if self.channels_dir.resolve() not in path.parents:
            raise ValueError(f"invalid channel name {channel!r}")
        return path

    def list_channels(self) -> list[str]:
        if not self.channels_dir.is_dir():
            return []
        return sorted(p.stem for p in self.channels_dir.glob("*.jsonl"))

    def send_message(self, channel: str, author: str, text: str) -> dict:
        author = author.strip()[:MAX_AUTHOR_LEN]
        text = text.strip()
        if not author:
            raise ValueError("author must not be empty")
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > MAX_TEXT_LEN:
            raise ValueError(f"text exceeds {MAX_TEXT_LEN} characters")
        path = self._path(channel)
        path.parent.mkdir(parents=True, exist_ok=True)
        msg = {
            "id": uuid.uuid4().hex[:12],
            "ts": _utcnow(),
            "author": author,
            "text": text,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        return msg

    def read_messages(
        self, channel: str, after_id: str = "", limit: int = 50
    ) -> list[dict]:
        limit = max(1, min(limit, MAX_READ_LIMIT))
        path = self._path(channel)
        if not path.is_file():
            return []
        msgs = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if after_id:
            idx = next(
                (i for i, m in enumerate(msgs) if m.get("id") == after_id), None
            )
            msgs = msgs[idx + 1 :] if idx is not None else msgs
        return msgs[-limit:]

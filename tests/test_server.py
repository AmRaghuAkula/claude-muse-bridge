"""Tests for MCP server wiring: all tools discoverable and working."""

import asyncio
import json

from bridge.config import Settings
from bridge.server import create_server
from bridge.integrity import seal_brief


def _settings(tmp_path, **kw):
    s = Settings(backend="local", transport="stdio", briefs_dir=tmp_path, **kw)
    s.channels_dir = tmp_path / "channels"
    s.validate()
    return s


def _tools(server):
    return sorted(t.name for t in asyncio.run(server.list_tools()))


def _call(server, name, args):
    res = asyncio.run(server.call_tool(name, args))
    texts = [c.text for c in res.content]
    return texts[0] if len(texts) == 1 else texts


def test_all_tools_registered(tmp_path):
    server = create_server(_settings(tmp_path))
    assert _tools(server) == [
        "get_brief",
        "get_latest_brief",
        "list_briefs",
        "list_channels",
        "read_messages",
        "send_message",
        "verify_brief",
    ]


def test_brief_tools_with_integrity(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    sealed = tmp_path / "b.md"
    sealed.write_text("# B")
    seal_brief(sealed)
    tampered = tmp_path / "c.md"
    tampered.write_text("# C")
    seal_brief(tampered)
    tampered.write_text("# C hacked")

    server = create_server(_settings(tmp_path))
    assert _call(server, "list_briefs", {}) == ["a.md", "b.md", "c.md"]
    assert "# B" in _call(server, "get_brief", {"name": "b.md"})
    assert "Brief not found" in _call(server, "get_brief", {"name": "nope.md"})
    assert "INTEGRITY CHECK FAILED" in _call(server, "get_brief", {"name": "c.md"})
    assert _call(server, "verify_brief", {"name": "b.md"}).startswith("OK")
    assert _call(server, "verify_brief", {"name": "a.md"}).startswith("SKIPPED")
    assert _call(server, "verify_brief", {"name": "c.md"}).startswith("FAILED")


def test_channel_tools_roundtrip(tmp_path):
    server = create_server(_settings(tmp_path))
    assert "No channels" in _call(server, "list_channels", {})

    receipt = json.loads(
        _call(
            server,
            "send_message",
            {"channel": "strategy", "author": "chitti", "text": "hello claude"},
        )
    )
    assert receipt["ok"] is True

    _call(
        server,
        "send_message",
        {"channel": "strategy", "author": "claude", "text": "hello back"},
    )
    got = _call(server, "list_channels", {})
    assert got == "strategy" or got == ["strategy"]

    msgs = json.loads(_call(server, "read_messages", {"channel": "strategy"}))
    assert [m["author"] for m in msgs] == ["chitti", "claude"]

    newer = json.loads(
        _call(
            server,
            "read_messages",
            {"channel": "strategy", "after_id": msgs[0]["id"]},
        )
    )
    assert [m["author"] for m in newer] == ["claude"]

    # invalid channel rejected, not a crash
    assert "error" in _call(server, "send_message",
                             {"channel": "../x", "author": "a", "text": "hi"})

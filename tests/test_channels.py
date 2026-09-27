"""Tests for bidirectional message channels."""

import json

import pytest

from bridge.channels import MAX_TEXT_LEN, ChannelStore


def test_send_and_read(tmp_path):
    store = ChannelStore(tmp_path)
    m1 = store.send_message("content-strategy", "chitti", "hello claude")
    m2 = store.send_message("content-strategy", "claude", "hello back")
    assert store.list_channels() == ["content-strategy"]
    msgs = store.read_messages("content-strategy")
    assert [m["author"] for m in msgs] == ["chitti", "claude"]
    assert msgs[0]["id"] == m1["id"]
    # pagination
    assert store.read_messages("content-strategy", after_id=m1["id"]) == [m2]
    assert store.read_messages("content-strategy", after_id=m2["id"]) == []


def test_unknown_channel_reads_empty(tmp_path):
    assert ChannelStore(tmp_path).read_messages("nope") == []
    assert ChannelStore(tmp_path).list_channels() == []


def test_bad_channel_names_rejected(tmp_path):
    store = ChannelStore(tmp_path)
    for bad in ["../evil", "a/b", "UPPER", "", "x" * 65, "has space"]:
        with pytest.raises(ValueError):
            store.send_message(bad, "a", "hi")
        with pytest.raises(ValueError):
            store.read_messages(bad)


def test_limits_enforced(tmp_path):
    store = ChannelStore(tmp_path)
    with pytest.raises(ValueError):
        store.send_message("ok", "a", "x" * (MAX_TEXT_LEN + 1))
    with pytest.raises(ValueError):
        store.send_message("ok", "", "hi")
    with pytest.raises(ValueError):
        store.send_message("ok", "a", "   ")
    # read limit is capped, not an error
    for i in range(5):
        store.send_message("ok", "a", f"m{i}")
    assert len(store.read_messages("ok", limit=10_000)) == 5


def test_jsonl_format(tmp_path):
    store = ChannelStore(tmp_path)
    store.send_message("ch", "chitti", "héllo wörld")
    lines = (tmp_path / "ch.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    msg = json.loads(lines[0])
    assert msg["text"] == "héllo wörld"
    assert set(msg) == {"id", "ts", "author", "text"}

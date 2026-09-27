"""Tests for the Azure Blob channel store (stubbed client)."""

import sys
import types

import pytest

from bridge.channels import MAX_TEXT_LEN


class _NotFound(Exception):
    pass


class _FakeDownload:
    def __init__(self, data: bytes):
        self._data = data

    def readall(self):
        return self._data


class _FakeBlobClient:
    def __init__(self, blobs: dict, name: str):
        self._blobs = blobs
        self.name = name

    def download_blob(self):
        if self.name not in self._blobs:
            raise _NotFound(self.name)
        return _FakeDownload(bytes(self._blobs[self.name]))

    def append_block(self, data: bytes):
        if self.name not in self._blobs:
            raise _NotFound(self.name)
        self._blobs[self.name] += data

    def create_append_blob(self):
        self._blobs.setdefault(self.name, bytearray())


class _FakeBlob:
    def __init__(self, name):
        self.name = name


class _FakeContainerClient:
    def __init__(self):
        self.blobs: dict = {}

    @classmethod
    def from_container_url(cls, url):
        return cls()

    def get_blob_client(self, name):
        return _FakeBlobClient(self.blobs, name)

    def list_blobs(self):
        return [_FakeBlob(n) for n in self.blobs]


def _stub_azure():
    for mod in ("azure", "azure.storage", "azure.storage.blob", "azure.core",
                "azure.core.exceptions"):
        sys.modules.setdefault(mod, types.ModuleType(mod))
    sys.modules["azure.storage.blob"].ContainerClient = _FakeContainerClient
    sys.modules["azure.core.exceptions"].ResourceNotFoundError = _NotFound


def _store():
    _stub_azure()
    from bridge.channels_azure import AzureBlobChannelStore

    return AzureBlobChannelStore("acct", "channels", "token")


def test_send_read_roundtrip():
    store = _store()
    m1 = store.send_message("strategy", "chitti", "hello claude")
    m2 = store.send_message("strategy", "claude", "hello back")
    assert store.list_channels() == ["strategy"]
    msgs = store.read_messages("strategy")
    assert [m["author"] for m in msgs] == ["chitti", "claude"]
    assert store.read_messages("strategy", after_id=m1["id"]) == [m2]
    assert store.read_messages("strategy", after_id="nope") == msgs


def test_unknown_channel_empty():
    store = _store()
    assert store.read_messages("ghost") == []
    assert store.list_channels() == []


def test_ceilings_shared_with_local():
    store = _store()
    for bad in ["../x", "UPPER", ""]:
        with pytest.raises(ValueError):
            store.send_message(bad, "a", "hi")
    with pytest.raises(ValueError):
        store.send_message("ok", "a", "x" * (MAX_TEXT_LEN + 1))
    with pytest.raises(ValueError):
        store.send_message("ok", "a", "   ")


def test_append_blob_layout():
    store = _store()
    store.send_message("ch", "a", "one")
    store.send_message("ch", "b", "two")
    # one blob per channel, JSON lines
    blobs = store._container.blobs
    assert list(blobs) == ["ch.jsonl"]
    lines = bytes(blobs["ch.jsonl"]).decode().splitlines()
    assert len(lines) == 2


def test_factory_selects_backend(tmp_path):
    from bridge.channels import ChannelStore, get_channel_store
    from bridge.channels_azure import AzureBlobChannelStore
    from bridge.config import Settings

    local = Settings(backend="local", briefs_dir=tmp_path)
    assert isinstance(get_channel_store(local), ChannelStore)

    _stub_azure()
    az = Settings(backend="azure", briefs_dir=tmp_path,
                  storage_account="a", sas_token="t")
    assert isinstance(get_channel_store(az), AzureBlobChannelStore)

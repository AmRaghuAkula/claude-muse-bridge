"""Tests for brief backends (local + azure with a stubbed client)."""

import sys
import types
from datetime import datetime, timezone

import pytest

from bridge.backends.local import LocalBackend
from bridge.integrity import IntegrityError, seal_brief


def _write(d, name, text):
    p = d / name
    p.write_text(text)
    return p


def test_local_listing_and_read(tmp_path):
    _write(tmp_path, "2026-09-01.md", "# First")
    _write(tmp_path, "2026-09-15.md", "# Second")
    backend = LocalBackend(tmp_path)
    assert backend.list_briefs() == ["2026-09-01.md", "2026-09-15.md"]
    assert backend.read_latest() == ("2026-09-15.md", "# Second")
    assert backend.read_brief("2026-09-01.md") == "# First"


def test_local_missing_dir(tmp_path):
    backend = LocalBackend(tmp_path / "nope")
    assert backend.list_briefs() == []
    with pytest.raises(FileNotFoundError):
        backend.read_latest()


def test_local_path_traversal_blocked(tmp_path):
    outside = tmp_path / "secret.md"
    outside.write_text("x")
    backend = LocalBackend(tmp_path / "briefs")
    for evil in ["../secret.md", "..\\secret.md", "/etc/passwd"]:
        with pytest.raises(FileNotFoundError):
            backend.read_brief(evil)
        assert backend.verify_brief(evil).startswith("NOT FOUND")


def test_local_verify_states(tmp_path):
    sealed = _write(tmp_path, "sealed.md", "# s")
    seal_brief(sealed)
    _write(tmp_path, "plain.md", "# p")
    tampered = _write(tmp_path, "tampered.md", "# t")
    seal_brief(tampered)
    tampered.write_text("# t edited")

    backend = LocalBackend(tmp_path)
    assert backend.verify_brief("sealed.md").startswith("OK")
    assert backend.verify_brief("plain.md").startswith("SKIPPED")
    assert backend.verify_brief("tampered.md").startswith("FAILED")
    assert backend.verify_brief("missing.md").startswith("NOT FOUND")
    # tampered briefs are refused, not served
    with pytest.raises(IntegrityError):
        backend.read_brief("tampered.md")
    # sealed briefs still read fine
    assert backend.read_brief("sealed.md") == "# s"


# --- Azure backend with a stubbed ContainerClient ---


class _FakeDownload:
    def __init__(self, data: bytes):
        self._data = data

    def readall(self):
        return self._data


class _FakeBlob:
    def __init__(self, name, last_modified):
        self.name = name
        self.last_modified = last_modified


class _FakeContainerClient:
    blobs: dict = {}

    @classmethod
    def from_container_url(cls, url):
        return cls()

    def list_blobs(self):
        return [
            _FakeBlob(name, datetime(2026, 9, i + 1, tzinfo=timezone.utc))
            for i, name in enumerate(sorted(self.blobs))
        ]

    def download_blob(self, name):
        if name not in self.blobs:
            raise Exception("not found")
        return _FakeDownload(self.blobs[name])


def _stub_azure():
    for mod in ("azure", "azure.storage", "azure.storage.blob"):
        sys.modules.setdefault(mod, types.ModuleType(mod))
    sys.modules["azure.storage.blob"].ContainerClient = _FakeContainerClient


def test_azure_backend(tmp_path):
    _stub_azure()
    from bridge.backends.azure_blob import AzureBlobBackend

    _FakeContainerClient.blobs = {
        "a.md": b"# A",
        "b.md": b"# B",
        "b.md.sha256": (
            "216f4c6ac9ef17add951aa097934202649a6c6ea5f29263b00c59772ea6cff61  b.md\n"
        ).encode(),
    }
    backend = AzureBlobBackend("acct", "briefs", "token")
    assert backend.list_briefs() == ["a.md", "b.md"]  # sidecar not listed
    assert backend.read_brief("a.md") == "# A"
    assert backend.read_brief("b.md") == "# B"
    assert backend.verify_brief("b.md").startswith("OK")
    assert backend.verify_brief("a.md").startswith("SKIPPED")

    # tampered content fails verification and is refused
    _FakeContainerClient.blobs["b.md"] = b"# B tampered"
    assert backend.verify_brief("b.md").startswith("FAILED")
    with pytest.raises(IntegrityError):
        backend.read_brief("b.md")

    # traversal / wrong extension rejected
    with pytest.raises(FileNotFoundError):
        backend.read_brief("../a.md")
    with pytest.raises(FileNotFoundError):
        backend.read_brief("a.txt")

"""Tests for Azure auth selection: SAS token vs managed identity."""

import sys
import types

from bridge.azure_auth import make_container_client


def _stub(monkeypatch, use_identity=True):
    blob_mod = types.ModuleType("azure.storage.blob")
    identity_mod = types.ModuleType("azure.identity")
    calls = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

        @classmethod
        def from_container_url(cls, url):
            calls["url"] = url
            return cls()

    class FakeCredential:
        pass

    blob_mod.ContainerClient = FakeClient
    identity_mod.DefaultAzureCredential = FakeCredential
    monkeypatch.setitem(sys.modules, "azure.storage.blob", blob_mod)
    if use_identity:
        monkeypatch.setitem(sys.modules, "azure.identity", identity_mod)
    else:
        monkeypatch.delitem(sys.modules, "azure.identity", raising=False)
    return calls


def test_sas_token_path(monkeypatch):
    calls = _stub(monkeypatch)
    make_container_client("acct", "briefs", "mytoken")
    assert calls["url"] == "https://acct.blob.core.windows.net/briefs?mytoken"


def test_sas_leading_question_mark_stripped(monkeypatch):
    calls = _stub(monkeypatch)
    make_container_client("acct", "briefs", "?mytoken")
    assert calls["url"].endswith("/briefs?mytoken")


def test_managed_identity_path(monkeypatch):
    calls = _stub(monkeypatch)
    make_container_client("acct", "briefs", "")
    assert calls["args"][0] == "https://acct.blob.core.windows.net"
    assert calls["args"][1] == "briefs"
    assert "credential" in calls["kwargs"]


def test_missing_identity_package_errors(monkeypatch):
    # Simulate azure-identity not being installed: None in sys.modules makes
    # the import raise ImportError even when the package exists on disk.
    _stub(monkeypatch, use_identity=False)
    monkeypatch.setitem(sys.modules, "azure.identity", None)
    try:
        make_container_client("acct", "briefs", "")
    except RuntimeError as exc:
        assert "azure-identity" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

"""Tests for the bridge image entrypoint dispatcher (src/bridge/__main__.py)."""

from __future__ import annotations

import os
import runpy
from unittest import mock

import pytest

import bridge.__main__ as entry


def test_defaults_to_server(monkeypatch):
    monkeypatch.delenv("BRIDGE_MODE", raising=False)
    with mock.patch.object(runpy, "run_module") as rm:
        entry.main()
    rm.assert_called_once_with("bridge.server", run_name="__main__", alter_sys=True)


def test_watcher_mode(monkeypatch):
    monkeypatch.setenv("BRIDGE_MODE", "watcher")
    with mock.patch.object(runpy, "run_module") as rm:
        entry.main()
    rm.assert_called_once_with("bridge.watcher", run_name="__main__", alter_sys=True)


def test_mode_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("BRIDGE_MODE", "  Watcher ")
    with mock.patch.object(runpy, "run_module") as rm:
        entry.main()
    rm.assert_called_once_with("bridge.watcher", run_name="__main__", alter_sys=True)


def test_unknown_mode_exits():
    with mock.patch.dict(os.environ, {"BRIDGE_MODE": "bogus"}):
        with pytest.raises(SystemExit, match="Unknown BRIDGE_MODE"):
            entry.main()

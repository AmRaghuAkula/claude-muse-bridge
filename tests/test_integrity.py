"""Tests for SHA-256 sidecar integrity."""

import pytest

from bridge.integrity import IntegrityError, seal_brief, sha256_text, verify_brief


def test_roundtrip(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("# Hello")
    seal_brief(brief)
    assert verify_brief(brief) == "ok"


def test_unsealed(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("# Hello")
    assert verify_brief(brief) == "unverified"


def test_tampered(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("# Hello")
    seal_brief(brief)
    brief.write_text("# Hello (edited by attacker)")
    with pytest.raises(IntegrityError):
        verify_brief(brief)


def test_reseal_after_edit(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("# v1")
    seal_brief(brief)
    brief.write_text("# v2")
    seal_brief(brief)  # producer re-seals after legitimate edit
    assert verify_brief(brief) == "ok"


def test_sha256_text_known():
    assert sha256_text("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )

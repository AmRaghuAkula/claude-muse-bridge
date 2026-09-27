"""Local-folder backend: briefs are *.md files in a directory."""

from __future__ import annotations

from pathlib import Path

from bridge.integrity import IntegrityError, verify_brief as _verify_file

from .base import BriefBackend


class LocalBackend(BriefBackend):
    def __init__(self, briefs_dir: Path) -> None:
        self.briefs_dir = briefs_dir

    def _files(self) -> list[Path]:
        if not self.briefs_dir.is_dir():
            return []
        return sorted(self.briefs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)

    def _resolve(self, name: str) -> Path:
        path = (self.briefs_dir / name).resolve()
        # Containment check: never serve files outside the briefs dir.
        if self.briefs_dir.resolve() not in path.parents or not path.is_file():
            raise FileNotFoundError(f"brief not found: {name}")
        return path

    def list_briefs(self) -> list[str]:
        return [p.name for p in self._files()]

    def read_brief(self, name: str) -> str:
        path = self._resolve(name)
        _verify_file(path)  # raises IntegrityError on tampered content
        return path.read_text(encoding="utf-8")

    def verify_brief(self, name: str) -> str:
        try:
            path = self._resolve(name)
        except FileNotFoundError:
            return f"NOT FOUND: {name}"
        try:
            result = _verify_file(path)
        except IntegrityError as exc:
            return f"FAILED: {exc}"
        if result == "ok":
            return f"OK: {name} matches its sha256 sidecar"
        return f"SKIPPED: {name} has no sidecar (unsealed brief)"

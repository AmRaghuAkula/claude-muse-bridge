"""Local-folder backend: briefs are *.md files in a directory."""

from __future__ import annotations

from pathlib import Path

from .base import BriefBackend


class LocalBackend(BriefBackend):
    def __init__(self, briefs_dir: Path) -> None:
        self.briefs_dir = briefs_dir

    def _files(self) -> list[Path]:
        if not self.briefs_dir.is_dir():
            return []
        return sorted(self.briefs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)

    def list_briefs(self) -> list[str]:
        return [p.name for p in self._files()]

    def read_brief(self, name: str) -> str:
        path = (self.briefs_dir / name).resolve()
        # Containment check: never serve files outside the briefs dir.
        if self.briefs_dir.resolve() not in path.parents or not path.is_file():
            raise FileNotFoundError(f"brief not found: {name}")
        return path.read_text(encoding="utf-8")

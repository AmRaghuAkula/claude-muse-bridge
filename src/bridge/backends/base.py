"""Storage backends for briefs.

A backend serves versioned markdown documents ("briefs") to the MCP tools.
Add a new backend by subclassing BriefBackend and registering it in
`bridge.backends.get_backend`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BriefBackend(ABC):
    """Oldest-first listing; read_latest() returns the newest brief."""

    @abstractmethod
    def list_briefs(self) -> list[str]:
        """Return brief names (e.g. filenames), oldest first."""
        raise NotImplementedError

    @abstractmethod
    def read_brief(self, name: str) -> str:
        """Return the markdown content of one brief. Raises FileNotFoundError."""
        raise NotImplementedError

    def read_latest(self) -> tuple[str, str]:
        names = self.list_briefs()
        if not names:
            raise FileNotFoundError("no briefs found")
        return names[-1], self.read_brief(names[-1])

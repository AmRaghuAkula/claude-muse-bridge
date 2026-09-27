"""Content integrity for briefs: SHA-256 sidecars.

Convention: a sealed brief ``brief.md`` has a sibling ``brief.md.sha256``
containing "<hex-digest>  <filename>". Readers verify on read whenever a
sidecar is present and refuse to serve tampered content; unsealed briefs
read as before (backwards compatible).

Seal briefs with ``python -m bridge.cli seal``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


class IntegrityError(Exception):
    """Raised when brief content does not match its hash sidecar."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seal_brief(path: Path) -> Path:
    """Write (or refresh) the .sha256 sidecar for a brief. Returns sidecar path."""
    digest = sha256_text(path.read_text(encoding="utf-8"))
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return sidecar


def verify_brief(path: Path) -> str:
    """Check a brief file against its sidecar.

    Returns "ok", or "unverified" when no sidecar exists.
    Raises IntegrityError when the content does not match.
    """
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.is_file():
        return "unverified"
    expected = sidecar.read_text(encoding="utf-8").split()[0]
    actual = sha256_text(path.read_text(encoding="utf-8"))
    if actual != expected:
        raise IntegrityError(
            f"{path.name}: content hash {actual[:12]}... does not match "
            f"sidecar {expected[:12]}..."
        )
    return "ok"

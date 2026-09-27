"""Image entrypoint dispatcher.

The same container image serves two roles:

- the HTTP bridge server (the Container App), and
- the scheduled watcher job (``bridge-watcher``).

``BRIDGE_MODE`` selects which one runs, so the job needs no CLI command
override (``az containerapp job create --args`` only accepts a single value,
which made ``python -m bridge.watcher`` impossible to express):

- ``server`` (default)  ->  ``bridge.server``
- ``watcher``           ->  ``bridge.watcher``
"""

from __future__ import annotations

import os
import runpy

_MODE_MODULES = {
    "server": "bridge.server",
    "watcher": "bridge.watcher",
}


def main() -> None:
    mode = os.environ.get("BRIDGE_MODE", "server").strip().lower()
    module = _MODE_MODULES.get(mode)
    if module is None:
        raise SystemExit(
            f"Unknown BRIDGE_MODE={mode!r}; expected one of: {sorted(_MODE_MODULES)}"
        )
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()

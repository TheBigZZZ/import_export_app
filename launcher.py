from __future__ import annotations

import multiprocessing
import os
import sys

# Ensure optional async DB driver is referenced so PyInstaller includes it
try:
    import aiosqlite  # noqa: F401
except Exception:
    # If not available in the build environment, backend will fail loudly
    # at runtime; import here ensures PyInstaller bundles the module.
    pass


def run() -> int:
    multiprocessing.freeze_support()

    # In CI smoke mode the packaged executable should behave as a backend-only
    # process so the health endpoint is exercised directly instead of going
    # through the GUI wrapper and a second spawned child process.
    if os.environ.get("TRADEDESK_HEADLESS_SMOKE"):
        from tradedesk.backend.cli import main as backend_cli_main

        return backend_cli_main(["--serve"])

    # Allow the frozen executable to act as a backend worker when launched by
    # the GUI host. Use an explicit environment flag first because some frozen
    # Windows launch paths can mangle command-line handling before Python sees it.
    if os.environ.get("TRADEDESK_BACKEND_CHILD") or "--backend-cli" in sys.argv:
        from tradedesk.backend.cli import main as backend_cli_main

        args = [arg for arg in sys.argv[1:] if arg != "--backend-cli"]
        return backend_cli_main(args)

    from frontend.main import main

    return main()


if __name__ == "__main__":
    sys.exit(run())

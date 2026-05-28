from __future__ import annotations

import os
import multiprocessing
import sys


def run() -> int:
    multiprocessing.freeze_support()

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
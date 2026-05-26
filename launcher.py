from __future__ import annotations

import multiprocessing
import sys


def run() -> int:
    multiprocessing.freeze_support()

    # Allow the frozen executable to act as a backend worker when launched by
    # the GUI host. This avoids multiprocessing spawn edge cases in packaged
    # Windows runners and gives us a dedicated, logged backend process.
    if "--backend-cli" in sys.argv:
        from tradedesk.backend.cli import main as backend_cli_main

        args = [arg for arg in sys.argv[1:] if arg != "--backend-cli"]
        return backend_cli_main(args)

    from frontend.main import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
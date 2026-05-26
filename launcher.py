from __future__ import annotations

import multiprocessing
import sys

from frontend.main import main


def run() -> int:
    # When running as a frozen executable (PyInstaller) ensure stdio
    # streams exist and multiprocessing is using a compatible start method.
    if getattr(sys, "frozen", False):
        # Some frozen environments may have stdout/stderr set to None;
        # ensure they are at least connected to devnull to avoid errors
        # when multiprocessing.spawn tries to write to the parent pipe.
        import os

        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")

        try:
            multiprocessing.set_start_method("spawn", force=True)
        except RuntimeError:
            # start method already set; ignore
            pass

    multiprocessing.freeze_support()
    return main()


if __name__ == "__main__":
    sys.exit(run())
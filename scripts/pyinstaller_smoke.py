"""Minimal import-only launcher for PyInstaller packaging smoke test."""

# ensure project dir on path
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# import a representative set of modules used in packaging
# Static imports so PyInstaller will detect and include these modules
try:
    import frontend.main  # noqa: F401

    print("frontend.main import ok")
except Exception as e:
    print("frontend.main IMPORT_FAIL", e)

try:
    import frontend.backend_manager  # noqa: F401

    print("frontend.backend_manager import ok")
except Exception as e:
    print("frontend.backend_manager IMPORT_FAIL", e)

try:
    import frontend.api_client  # noqa: F401

    print("frontend.api_client import ok")
except Exception as e:
    print("frontend.api_client IMPORT_FAIL", e)

try:
    import tradedesk.backend.main  # noqa: F401

    print("tradedesk.backend.main import ok")
except Exception as e:
    print("tradedesk.backend.main IMPORT_FAIL", e)

# Ensure optional async DB dependency is included in frozen builds
try:
    import aiosqlite  # noqa: F401

    print("aiosqlite import ok")
except Exception as e:
    print("aiosqlite IMPORT_FAIL", e)

print("smoke import complete")

import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if len(sys.argv) > 1 and sys.argv[1] == "async":
    os.environ["TRADEDESK_USE_QTASYNCIO"] = "1"
    print("TRADEDESK_USE_QTASYNCIO=1")
else:
    os.environ.pop("TRADEDESK_USE_QTASYNCIO", None)
    print("TRADEDESK_USE_QTASYNCIO not set")
mods = [
    "frontend.backend_manager",
    "frontend.api_client",
    "frontend.live_updates",
    "frontend.workers",
    "frontend.modules.settings",
    "frontend.modules.products",
    "tradedesk.backend.database",
]
for m in mods:
    try:
        importlib.invalidate_caches()
        importlib.import_module(m)
        print(m + " import ok")
    except Exception as e:
        print(m + " IMPORT_FAIL", e)

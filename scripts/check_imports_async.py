import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["TRADEDESK_USE_QTASYNCIO"] = "1"
mods = [
    "frontend.modules.settings",
    "frontend.modules.products",
    "frontend.modules.users",
    "frontend.modules.customers",
    "frontend.modules.reports",
    "frontend.modules.dashboard",
    "frontend.modules.suppliers",
    "frontend.modules.banks",
]
for m in mods:
    try:
        importlib.invalidate_caches()
        importlib.import_module(m)
        print(m + " import ok")
    except Exception as e:
        print(m + " IMPORT_FAIL", e)

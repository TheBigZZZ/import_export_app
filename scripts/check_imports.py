import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
mods = [
    "frontend.modules.banks",
    "frontend.modules.cash_register",
    "frontend.modules.chart_of_accounts",
    "frontend.modules.import_costing",
    "frontend.modules.expenses",
    "frontend.modules.purchases",
    "frontend.modules.suppliers",
    "frontend.modules.sales",
    "frontend.modules.products",
    "frontend.modules.users",
    "frontend.modules.customers",
    "frontend.modules.dashboard",
    "frontend.modules.reports",
]
for m in mods:
    try:
        importlib.invalidate_caches()
        importlib.import_module(m)
        print(m + " import ok")
    except Exception as e:
        print(m + " IMPORT_FAIL", e)

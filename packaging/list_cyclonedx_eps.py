import importlib.metadata as m

eps = m.entry_points()
console = [e for e in eps if getattr(e, "group", None) == "console_scripts"]
for e in console:
    if "cyclonedx" in e.name or "cyclonedx" in e.value:
        print(e.name, "->", e.value)
print("done")

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files


workspace = Path.cwd()
frontend_dir = workspace / "frontend"

datas = [
    (str(frontend_dir / "assets" / "style.qss"), "frontend/assets"),
    (str(workspace / "packaging" / "sbom.xml"), "packaging"),
]

version_file = workspace / "version.txt"
if version_file.exists():
    datas.append((str(version_file), "."))

hiddenimports = collect_submodules("tradedesk") + collect_submodules("aiosqlite") + [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "httpx",
    "keyring",
    "sentry_sdk",
]

# Include aiosqlite package data explicitly (some installs place resources that
# PyInstaller may not pick up via module analysis).
try:
    datas += collect_data_files("aiosqlite")
except Exception:
    pass


a = Analysis(
    [str(workspace / "launcher.py")],
    pathex=[str(workspace)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(workspace / "packaging" / "rth_aiosqlite.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TradeDeskERP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TradeDeskERP",
)
#!/usr/bin/env python3
"""Helpers for preparing a local release: tag, build, smoke-test, and create manifest.

This script is intended to be run locally by a release engineer. It does not
automatically push tags or upload artifacts; it prepares artifacts and runs
the smoke test to verify the build before publishing.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True, help="Release tag (e.g., v1.0.0)")
    args = p.parse_args(argv)

    tag = args.tag
    # 1) create lightweight annotated tag (local)
    run(["git", "tag", "-a", tag, "-m", f"Release {tag}"])

    # 2) build exe using packaging spec
    run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "packaging/tradedesk.spec"])

    exe = Path("dist") / "TradeDeskERP" / "TradeDeskERP.exe"
    if not exe.exists():
        print("Expected built exe not found:", exe)
        return 2

    # 3) run smoke test (powershell wrapper)
    run([
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "./scripts/smoke_test.ps1",
        "-ExePath",
        str(exe),
        "-Timeout",
        "180",
    ])

    # 4) create updates.json manifest (local)
    installer = Path("dist") / "TradeDeskERP-Setup.exe"
    manifest = Path("updates.json")
    if installer.exists():
        import hashlib

        h = hashlib.sha256(installer.read_bytes()).hexdigest()
        manifest.write_text(
            f"{{\n"
            f"  \"version\": \"{tag}\",\n"
            f"  \"installer_url\": \"https://example.com/{installer.name}\",\n"
            f"  \"installer_sha256\": \"{h}\",\n"
            f"  \"published_at\": \"TODO\"\n"
            f"}}\n"
        )
        print("Written updates.json manifest for manual upload")
    else:
        print("Installer not found; skipping updates.json creation")

    print("Release preparation complete. Please push the tag and upload artifacts via GitHub or your release process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

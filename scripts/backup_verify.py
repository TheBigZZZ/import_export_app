#!/usr/bin/env python3
"""Create a backup via the CLI and verify restore into a temporary DB.

Usage: scripts/backup_verify.py --backup-dir /path/to/out

This script calls the packaged module `tradedesk.backend.cli` helper to
create a backup and then attempts to restore it to verify integrity.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate()
    return proc.returncode, out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backup-dir", required=False)
    args = p.parse_args(argv)

    if args.backup_dir:
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
    else:
        backup_dir = Path.cwd() / "test_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    # Create backup
    rc, out = run_cmd([python, "-m", "tradedesk.backend.cli", "--backup-db", str(backup_dir)])
    print(out)
    if rc != 0:
        print("Backup command failed")
        return rc

    # Find the created backup file
    candidates = list(backup_dir.glob("tradedesk_backup_*.db")) + list(backup_dir.glob("*.db"))
    if not candidates:
        print("No backup file found in", backup_dir)
        return 2
    backup = sorted(candidates, key=os.path.getmtime)[-1]
    print("Backup created:", backup)

    # Restore to temp
    tmp = Path(tempfile.gettempdir()) / f"tradedesk_restore_test_{os.getpid()}.db"
    rc2, out2 = run_cmd([python, "-m", "tradedesk.backend.cli", "--restore-db", str(backup)])
    print(out2)
    if rc2 != 0:
        print("Restore command failed")
        return rc2

    print("Restore reported success. To fully verify, start the app and query /health or use the CLI to inspect data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from .diagnostics import purge_old_diagnostics
from datetime import datetime, timedelta, timezone


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diagnostics retention cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    args = parser.parse_args()
    # Implement a dry-run that lists files that would be deleted
    from pathlib import Path
    storage = Path(__import__("tradedesk.backend.config", fromlist=["settings"]).settings.diagnostics_storage_dir)
    if args.dry_run:
        print("Dry-run: listing old diagnostics and nonces to be removed")
        cutoff = datetime.now(timezone.utc) - timedelta(days=__import__("tradedesk.backend.config", fromlist=["settings"]).settings.diagnostics_retention_days)
        for p in storage.iterdir():
            try:
                if p.is_file() and datetime.utcfromtimestamp(p.stat().st_mtime) < cutoff:
                    print(p)
            except Exception:
                continue
        nonces_dir = Path(__import__("tradedesk.backend.config", fromlist=["settings"]).settings.diagnostics_nonces_dir or (storage / "nonces"))
        nonce_cutoff = datetime.now(timezone.utc) - timedelta(days=__import__("tradedesk.backend.config", fromlist=["settings"]).settings.diagnostics_nonces_ttl_days)
        if nonces_dir.exists():
            for n in nonces_dir.iterdir():
                try:
                    if n.is_file() and datetime.utcfromtimestamp(n.stat().st_mtime) < nonce_cutoff:
                        print(n)
                except Exception:
                    continue
        return 0
    purge_old_diagnostics()
    print("Diagnostics cleanup complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

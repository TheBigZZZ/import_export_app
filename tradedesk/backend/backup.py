from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import settings


def backup_db(destination_dir: Optional[Path] = None, retention_days: int = 30) -> Path:
    """Create a timestamped backup of the SQLite database and return its path."""
    db_path = settings.db_path
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    dest_base = Path(destination_dir) if destination_dir else settings.backup_dir
    dest_base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = dest_base / f"tradedesk_backup_{ts}.db"
    shutil.copy2(db_path, target)
    # Rotate old backups older than retention_days
    try:
        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        for p in dest_base.iterdir():
            try:
                if p.is_file() and p.name.startswith("tradedesk-db-"):
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
            except Exception:
                continue
    except Exception:
        pass

    return target


def restore_db(backup_file: Path) -> Path:
    """Restore the SQLite DB from a backup file. Returns the restored path."""
    backup_file = Path(backup_file)
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, db_path)
    return db_path

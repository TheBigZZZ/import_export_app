from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status

from ..config import settings
from ..database import engine
from ..utils.secret_store import delete_secret, get_secret, set_secret


@dataclass
class BackupFile:
    file_name: str
    file_path: str
    size_bytes: int
    created_at: datetime


class SettingsService:
    SETTINGS_FILE = "app_settings.json"

    def _settings_path(self) -> Path:
        return settings.data_dir / self.SETTINGS_FILE

    def _default_settings(self) -> dict[str, object]:
        return {
            "company_name": "TradeDesk ERP",
            "company_address": None,
            "company_phone": None,
            "company_email": None,
            "allow_negative_stock": False,
            # SMTP/email defaults
            "diagnostics_smtp_host": None,
            "diagnostics_smtp_port": None,
            "diagnostics_smtp_user": None,
            "diagnostics_notify_email_from": None,
            "diagnostics_notify_email_to": None,
        }

    def get_settings(self) -> dict[str, object]:
        settings_path = self._settings_path()
        if not settings_path.exists():
            defaults = self._default_settings()
            settings_path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
            # Add a flag indicating whether SMTP password is configured in secret store
            defaults["diagnostics_smtp_password_set"] = bool(
                get_secret("diagnostics_smtp_password")
            )
            return defaults

        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid settings file",
            ) from exc

        defaults = self._default_settings()
        defaults.update(loaded)
        # Do not expose SMTP password; instead expose a boolean flag
        defaults["diagnostics_smtp_password_set"] = bool(
            get_secret("diagnostics_smtp_password")
        )
        # Clean any sensitive payload accidentally stored
        if "diagnostics_smtp_password" in defaults:
            defaults.pop("diagnostics_smtp_password")
        return defaults

    def update_settings(self, payload: dict[str, object]) -> dict[str, object]:
        current = self.get_settings()
        # Handle sensitive values: diagnostics_smtp_password should be stored in secret store
        if "diagnostics_smtp_password" in payload:
            val = payload.pop("diagnostics_smtp_password")
            if val is None or val == "":
                delete_secret("diagnostics_smtp_password")
            else:
                set_secret("diagnostics_smtp_password", str(val))

        current.update(payload)
        self._settings_path().write_text(
            json.dumps(current, indent=2), encoding="utf-8"
        )
        # Ensure response includes password-set flag
        current["diagnostics_smtp_password_set"] = bool(
            get_secret("diagnostics_smtp_password")
        )
        return current

    def list_backups(self) -> list[BackupFile]:
        backups: list[BackupFile] = []
        for file_path in sorted(
            settings.backup_dir.glob("tradedesk_backup_*.db"), reverse=True
        ):
            stat = file_path.stat()
            backups.append(
                BackupFile(
                    file_name=file_path.name,
                    file_path=str(file_path),
                    size_bytes=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                )
            )
        return backups

    def create_backup(self) -> BackupFile:
        if not settings.db_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Database file not found"
            )
        # Use centralized backup helper which also applies retention
        try:
            from ..backup import backup_db

            backup_path = backup_db(None)
            stat = Path(backup_path).stat()
        except Exception:
            # Fallback to direct copy if helper unavailable
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = settings.backup_dir / f"tradedesk_backup_{timestamp}.db"
            shutil.copy2(settings.db_path, backup_path)
            stat = backup_path.stat()
        return BackupFile(
            file_name=backup_path.name,
            file_path=str(backup_path),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime),
        )

    async def restore_backup(self, file_name: str) -> BackupFile:
        if "/" in file_name or "\\" in file_name or ".." in file_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid backup file name",
            )

        backup_path = settings.backup_dir / file_name
        if not backup_path.exists() or not backup_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found"
            )

        await engine.dispose()
        shutil.copy2(backup_path, settings.db_path)
        stat = backup_path.stat()
        return BackupFile(
            file_name=backup_path.name,
            file_path=str(backup_path),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime),
        )

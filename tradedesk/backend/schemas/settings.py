from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    company_address: str | None
    company_phone: str | None
    company_email: str | None
    allow_negative_stock: bool
    # SMTP/email config (optional)
    diagnostics_smtp_host: str | None = None
    diagnostics_smtp_port: int | None = None
    diagnostics_smtp_user: str | None = None
    # Do NOT expose the SMTP password. Expose whether it is configured.
    diagnostics_smtp_password_set: bool = False
    diagnostics_notify_email_from: str | None = None
    diagnostics_notify_email_to: str | None = None


class AppSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=2, max_length=200)
    company_address: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    allow_negative_stock: bool
    diagnostics_smtp_host: str | None = None
    diagnostics_smtp_port: int | None = None
    diagnostics_smtp_user: str | None = None
    diagnostics_smtp_password: str | None = None
    diagnostics_notify_email_from: str | None = None
    diagnostics_notify_email_to: str | None = None


class BackupInfo(BaseModel):
    file_name: str
    file_path: str
    size_bytes: int
    created_at: datetime


class BackupCreateResponse(BaseModel):
    backup: BackupInfo


class RestoreBackupRequest(BaseModel):
    file_name: str = Field(min_length=1)


class RestoreBackupResponse(BaseModel):
    restored_backup: BackupInfo

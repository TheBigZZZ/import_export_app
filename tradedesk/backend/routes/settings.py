from fastapi import APIRouter, Depends, status

from ..dependencies import require_roles
from ..live import LiveEvent, broadcast_live_event
from ..schemas.settings import (
	AppSettingsRead,
	AppSettingsUpdate,
	BackupCreateResponse,
	BackupInfo,
	RestoreBackupRequest,
	RestoreBackupResponse,
)
from ..services.settings_service import SettingsService
from ..services.email_service import send_simple_email
from ..services.sms_service import send_sms
from fastapi import Body

router = APIRouter()


@router.get("", response_model=AppSettingsRead)
async def get_app_settings(
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "viewer")),
) -> AppSettingsRead:
	return AppSettingsRead.model_validate(SettingsService().get_settings())


@router.put("", response_model=AppSettingsRead)
async def update_app_settings(
	payload: AppSettingsUpdate,
	_: object = Depends(require_roles("super_admin", "admin")),
) -> AppSettingsRead:
	updated = SettingsService().update_settings(payload.model_dump())
	broadcast_live_event(
		LiveEvent(
			event_type="entity.changed",
			table_name="settings",
			action="update",
		)
	)
	return AppSettingsRead.model_validate(updated)


@router.get("/backups", response_model=list[BackupInfo])
async def list_backups(
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> list[BackupInfo]:
	backups = SettingsService().list_backups()
	return [
		BackupInfo(
			file_name=item.file_name,
			file_path=item.file_path,
			size_bytes=item.size_bytes,
			created_at=item.created_at,
		)
		for item in backups
	]


@router.post("/backups", response_model=BackupCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_backup(
	_: object = Depends(require_roles("super_admin", "admin")),
) -> BackupCreateResponse:
	backup = SettingsService().create_backup()
	return BackupCreateResponse(
		backup=BackupInfo(
			file_name=backup.file_name,
			file_path=backup.file_path,
			size_bytes=backup.size_bytes,
			created_at=backup.created_at,
		)
	)


@router.post("/backups/restore", response_model=RestoreBackupResponse)
async def restore_backup(
	payload: RestoreBackupRequest,
	_: object = Depends(require_roles("super_admin", "admin")),
) -> RestoreBackupResponse:
	restored = await SettingsService().restore_backup(payload.file_name)
	broadcast_live_event(
		LiveEvent(
			event_type="entity.changed",
			table_name="database",
			action="restore",
		)
	)
	return RestoreBackupResponse(
		restored_backup=BackupInfo(
			file_name=restored.file_name,
			file_path=restored.file_path,
			size_bytes=restored.size_bytes,
			created_at=restored.created_at,
		)
	)




@router.post('/email/test')
async def send_test_email(
	payload: dict = Body(...),
	_: object = Depends(require_roles("super_admin", "admin")),
) -> dict:
	"""Send a test email using configured SMTP settings. Expects {to, subject, body}."""
	to = payload.get('to')
	subject = payload.get('subject') or 'Test Email from TradeDesk'
	body = payload.get('body') or 'This is a test email.'
	if not to:
		return {"ok": False, "error": "Missing 'to' address"}
	try:
		send_simple_email(to, subject, body)
	except Exception as exc:
		return {"ok": False, "error": str(exc)}
	return {"ok": True}

@router.post('/sms/test')
async def send_test_sms(
	payload: dict = Body(...),
	_: object = Depends(require_roles("super_admin", "admin")),
) -> dict:
	to = payload.get('to')
	message = payload.get('message') or 'Test SMS from TradeDesk'
	if not to:
		return {"ok": False, "error": "Missing 'to' number"}
	try:
		send_sms(to, message)
	except Exception as exc:
		return {"ok": False, "error": str(exc)}
	return {"ok": True}

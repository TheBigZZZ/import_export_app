from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.voucher import (VoucherCreate, VoucherListResponse, VoucherRead,
                               VoucherVoidRequest)
from ..services.accounting_service import AccountingValidationError
from ..services.voucher_service import VoucherService

router = APIRouter()


@router.get("", response_model=VoucherListResponse)
async def list_vouchers(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> VoucherListResponse:
    items = await VoucherService(db).list_vouchers()
    return VoucherListResponse(items=items, total=len(items))


@router.post("", response_model=VoucherRead, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    payload: VoucherCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> VoucherRead:
    try:
        return await VoucherService(db).create_voucher(payload, created_by=user.id)
    except AccountingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{line_id}", response_model=VoucherRead)
async def get_voucher(
    line_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> VoucherRead:
    voucher = await VoucherService(db).get_voucher_by_line_id(line_id)
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found"
        )
    return voucher


@router.put("/{line_id}", response_model=VoucherRead)
async def update_voucher(
    line_id: int,
    payload: VoucherCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> VoucherRead:
    try:
        return await VoucherService(db).update_voucher(
            line_id, payload, updated_by=user.id
        )
    except AccountingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/{line_id}/void", response_model=VoucherRead)
async def void_voucher(
    line_id: int,
    payload: VoucherVoidRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> VoucherRead:
    return await VoucherService(db).void_voucher(
        line_id, payload.reason, user_id=user.id
    )

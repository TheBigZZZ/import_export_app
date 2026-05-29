from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.banking import (BankCreate, BankRead, BankStatementResponse,
                               BankTransferRequest)
from ..services.bank_service import BankService

router = APIRouter()


@router.get("", response_model=list[BankRead])
async def list_banks(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> list[BankRead]:
    items = await BankService(db).list_banks()
    return [BankRead.model_validate(item) for item in items]


@router.post("", response_model=BankRead, status_code=status.HTTP_201_CREATED)
async def create_bank(
    payload: BankCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> BankRead:
    created = await BankService(db).create_bank(payload)
    return BankRead.model_validate(created)


@router.post("/transfer")
async def transfer_bank_to_bank(
    payload: BankTransferRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
):
    return await BankService(db).transfer(
        from_bank_account_id=payload.from_bank_account_id,
        to_bank_account_id=payload.to_bank_account_id,
        amount=payload.amount,
        transaction_date=payload.transaction_date,
        reference_no=payload.reference_no,
        description=payload.description,
        created_by=user.id,
    )


@router.get("/{bank_id}/statement", response_model=BankStatementResponse)
async def bank_statement(
    bank_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> BankStatementResponse:
    return await BankService(db).statement(bank_id)

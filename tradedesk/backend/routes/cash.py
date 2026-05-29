from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.cash import CashTransactionCreate, DailyClosingResponse
from ..services.cash_service import CashService

router = APIRouter()


@router.post("")
async def create_cash_transaction(
    payload: CashTransactionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
):
    return await CashService(db).create_cash_entry(
        transaction_date=payload.transaction_date,
        amount=payload.amount,
        direction=payload.direction,
        account_id=payload.account_id,
        description=payload.description,
        reference_no=payload.reference_no,
        created_by=user.id,
    )


@router.get("")
async def list_cash_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
):
    rows = await CashService(db).list_cash_entries(limit=limit)
    return [
        {
            "id": row.id,
            "voucher_no": row.voucher_no,
            "voucher_type": row.voucher_type.value,
            "transaction_date": row.transaction_date.isoformat(),
            "debit": str(row.debit),
            "credit": str(row.credit),
            "description": row.description,
        }
        for row in rows
    ]


@router.get("/daily-closing", response_model=DailyClosingResponse)
async def daily_closing(
    for_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> DailyClosingResponse:
    return await CashService(db).daily_closing(for_date)

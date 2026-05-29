from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.transaction import Transaction
from ..schemas.cash import DailyClosingResponse
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .voucher_service import VoucherService


class CashService:
    CASH_ACCOUNT_ID = 1

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_cash_entries(self, limit: int = 100):
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.account_id == self.CASH_ACCOUNT_ID)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_cash_entry(
        self,
        transaction_date: date,
        amount: Decimal,
        direction: str,
        account_id: int,
        description: str | None,
        reference_no: str | None,
        created_by: int | None,
    ):
        voucher_type = "CRV" if direction == "in" else "CPV"
        lines = (
            [
                VoucherLineIn(
                    account_id=self.CASH_ACCOUNT_ID,
                    debit=amount,
                    credit=Decimal("0.00"),
                    description=description,
                ),
                VoucherLineIn(
                    account_id=account_id,
                    debit=Decimal("0.00"),
                    credit=amount,
                    description=description,
                ),
            ]
            if direction == "in"
            else [
                VoucherLineIn(
                    account_id=account_id,
                    debit=amount,
                    credit=Decimal("0.00"),
                    description=description,
                ),
                VoucherLineIn(
                    account_id=self.CASH_ACCOUNT_ID,
                    debit=Decimal("0.00"),
                    credit=amount,
                    description=description,
                ),
            ]
        )

        return await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type=voucher_type,
                transaction_date=transaction_date,
                reference_no=reference_no,
                description=description,
                lines=lines,
            ),
            created_by=created_by,
        )

    async def daily_closing(self, for_date: date) -> DailyClosingResponse:
        opening_res = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                and_(
                    Transaction.account_id == self.CASH_ACCOUNT_ID,
                    Transaction.transaction_date < for_date,
                )
            )
        )
        opening_debit, opening_credit = opening_res.one()
        opening = Decimal(opening_debit) - Decimal(opening_credit)

        day_res = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                and_(
                    Transaction.account_id == self.CASH_ACCOUNT_ID,
                    Transaction.transaction_date == for_date,
                )
            )
        )
        receipts, payments = day_res.one()

        receipts_d = Decimal(receipts)
        payments_d = Decimal(payments)
        closing = opening + receipts_d - payments_d

        return DailyClosingResponse(
            date=for_date,
            opening=opening,
            receipts=receipts_d,
            payments=payments_d,
            closing=closing,
        )

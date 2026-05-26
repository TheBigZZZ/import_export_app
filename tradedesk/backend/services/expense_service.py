from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import ChartOfAccount
from ..models.bank import BankAccount
from ..models.expense import Expense, PaymentMethod
from ..schemas.expense_ops import ExpenseCreate
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .voucher_service import VoucherService


class ExpenseService:
    CASH_ACCOUNT_ID = 1
    BANK_ACCOUNT_ID = 2

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_expenses(self) -> list[Expense]:
        rows = await self.db.execute(select(Expense).order_by(Expense.expense_date.desc(), Expense.id.desc()))
        return list(rows.scalars().all())

    async def create_expense(self, payload: ExpenseCreate, created_by: int | None) -> tuple[Expense, str]:
        account_row = await self.db.execute(select(ChartOfAccount.id).where(ChartOfAccount.id == payload.account_id))
        if account_row.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense account not found")

        payment_method = PaymentMethod(payload.payment_method)
        if payment_method == PaymentMethod.bank:
            if payload.bank_account_id is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bank_account_id is required")
            bank_row = await self.db.execute(select(BankAccount.id).where(BankAccount.id == payload.bank_account_id))
            if bank_row.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")

        expense = Expense(
            expense_no=payload.expense_no,
            expense_date=payload.expense_date,
            account_id=payload.account_id,
            amount=Decimal(payload.amount),
            payment_method=payment_method,
            bank_account_id=payload.bank_account_id,
            description=payload.description,
            reference=payload.reference,
            created_by=created_by,
        )
        self.db.add(expense)

        settlement_account_id = self.CASH_ACCOUNT_ID if payment_method == PaymentMethod.cash else self.BANK_ACCOUNT_ID
        voucher_type = "CPV" if payment_method == PaymentMethod.cash else "BPV"
        voucher = await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type=voucher_type,
                transaction_date=payload.expense_date,
                reference_no=payload.reference,
                description=payload.description or f"Expense {payload.expense_no}",
                lines=[
                    VoucherLineIn(
                        account_id=payload.account_id,
                        debit=Decimal(payload.amount),
                        credit=Decimal("0.00"),
                        description=payload.description,
                    ),
                    VoucherLineIn(
                        account_id=settlement_account_id,
                        debit=Decimal("0.00"),
                        credit=Decimal(payload.amount),
                        description=payload.description,
                    ),
                ],
            ),
            created_by=created_by,
        )

        await self.db.refresh(expense)
        return expense, voucher.voucher_no
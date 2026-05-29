from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bank import BankAccount
from ..models.transaction import Transaction
from ..schemas.banking import BankCreate, BankStatementResponse, StatementEntry
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .voucher_service import VoucherService


class BankService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_banks(self) -> list[BankAccount]:
        result = await self.db.execute(
            select(BankAccount).order_by(BankAccount.bank_name.asc())
        )
        return list(result.scalars().all())

    async def create_bank(self, payload: BankCreate) -> BankAccount:
        bank = BankAccount(
            bank_name=payload.bank_name,
            account_name=payload.account_name,
            account_number=payload.account_number,
            branch_name=payload.branch_name,
            swift_code=payload.swift_code,
            currency=payload.currency,
            opening_balance=payload.opening_balance,
            current_balance=payload.opening_balance,
            is_active=True,
        )
        self.db.add(bank)
        await self.db.commit()
        await self.db.refresh(bank)
        return bank

    async def transfer(
        self,
        from_bank_account_id: int,
        to_bank_account_id: int,
        amount: Decimal,
        transaction_date,
        reference_no: str | None,
        description: str | None,
        created_by: int | None,
    ):
        if from_bank_account_id == to_bank_account_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Source and target bank must differ",
            )

        banks = await self.db.execute(
            select(BankAccount).where(
                BankAccount.id.in_([from_bank_account_id, to_bank_account_id])
            )
        )
        bank_map = {bank.id: bank for bank in banks.scalars().all()}
        if from_bank_account_id not in bank_map or to_bank_account_id not in bank_map:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found"
            )

        source = bank_map[from_bank_account_id]
        target = bank_map[to_bank_account_id]
        if source.current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Insufficient source bank balance",
            )

        source.current_balance -= amount
        target.current_balance += amount

        voucher = await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type="Contra",
                transaction_date=transaction_date,
                reference_no=reference_no,
                description=description,
                lines=[
                    VoucherLineIn(
                        account_id=2,
                        debit=Decimal("0.00"),
                        credit=amount,
                        description=f"Transfer out: {source.bank_name}",
                    ),
                    VoucherLineIn(
                        account_id=2,
                        debit=amount,
                        credit=Decimal("0.00"),
                        description=f"Transfer in: {target.bank_name}",
                    ),
                ],
            ),
            created_by=created_by,
        )
        await self.db.commit()
        return voucher

    async def statement(self, bank_account_id: int) -> BankStatementResponse:
        exists = await self.db.execute(
            select(BankAccount.id).where(BankAccount.id == bank_account_id)
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found"
            )

        rows = await self.db.execute(
            select(Transaction)
            .where(Transaction.account_id == 2)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        )

        entries = [
            StatementEntry(
                id=row.id,
                voucher_no=row.voucher_no,
                voucher_type=row.voucher_type.value,
                transaction_date=row.transaction_date,
                debit=Decimal(row.debit),
                credit=Decimal(row.credit),
                description=row.description,
            )
            for row in rows.scalars().all()
        ]
        return BankStatementResponse(bank_account_id=bank_account_id, entries=entries)

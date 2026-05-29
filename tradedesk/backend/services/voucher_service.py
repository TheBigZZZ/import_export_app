from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import ChartOfAccount
from ..models.transaction import PartyType, Transaction, VoucherType
from ..schemas.voucher import VoucherCreate, VoucherRead
from .accounting_service import JournalLine, validate_double_entry


class VoucherService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _next_voucher_no(self, voucher_type: VoucherType, year: int) -> str:
        prefix = f"{voucher_type.value}-{year}-"
        stmt = select(Transaction.voucher_no).where(
            Transaction.voucher_no.like(f"{prefix}%")
        )
        result = await self.db.execute(stmt)
        max_n = 0
        for (voucher_no,) in result.all():
            try:
                serial = int(voucher_no.split("-")[-1])
                if serial > max_n:
                    max_n = serial
            except ValueError:
                continue
        return f"{prefix}{(max_n + 1):04d}"

    async def list_vouchers(self) -> list[VoucherRead]:
        rows = await self.db.execute(
            select(Transaction).order_by(
                Transaction.transaction_date.desc(), Transaction.id.desc()
            )
        )
        grouped: dict[str, list[Transaction]] = defaultdict(list)
        for row in rows.scalars().all():
            grouped[row.voucher_no].append(row)

        vouchers: list[VoucherRead] = []
        for voucher_no, lines in grouped.items():
            lines.sort(key=lambda item: item.id)
            first = lines[0]
            vouchers.append(
                VoucherRead(
                    voucher_no=voucher_no,
                    voucher_type=first.voucher_type.value,
                    transaction_date=first.transaction_date,
                    created_at=first.created_at,
                    lines=lines,
                )
            )
        vouchers.sort(
            key=lambda item: (item.transaction_date, item.voucher_no), reverse=True
        )
        return vouchers

    async def get_voucher_by_line_id(self, line_id: int) -> VoucherRead | None:
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == line_id)
        )
        line = result.scalar_one_or_none()
        if not line:
            return None

        rows = await self.db.execute(
            select(Transaction)
            .where(Transaction.voucher_no == line.voucher_no)
            .order_by(Transaction.id.asc())
        )
        lines = list(rows.scalars().all())
        first = lines[0]
        return VoucherRead(
            voucher_no=first.voucher_no,
            voucher_type=first.voucher_type.value,
            transaction_date=first.transaction_date,
            created_at=first.created_at,
            lines=lines,
        )

    async def create_voucher(
        self, payload: VoucherCreate, created_by: int | None = None
    ) -> VoucherRead:
        try:
            voucher_type = VoucherType(payload.voucher_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid voucher type",
            ) from exc

        validate_double_entry(
            [
                JournalLine(debit=Decimal(line.debit), credit=Decimal(line.credit))
                for line in payload.lines
            ]
        )

        account_ids = [line.account_id for line in payload.lines]
        accounts = await self.db.execute(
            select(ChartOfAccount.id).where(ChartOfAccount.id.in_(account_ids))
        )
        existing_ids = {item[0] for item in accounts.all()}
        missing = [
            account_id for account_id in account_ids if account_id not in existing_ids
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Missing account(s): {missing}",
            )

        voucher_no = await self._next_voucher_no(
            voucher_type, payload.transaction_date.year
        )

        lines: list[Transaction] = []
        for item in payload.lines:
            party_type = PartyType(item.party_type) if item.party_type else None
            line = Transaction(
                voucher_no=voucher_no,
                voucher_type=voucher_type,
                transaction_date=payload.transaction_date,
                account_id=item.account_id,
                party_type=party_type,
                party_id=item.party_id,
                debit=Decimal(item.debit),
                credit=Decimal(item.credit),
                description=item.description or payload.description,
                reference_no=item.reference_no or payload.reference_no,
                created_by=created_by,
            )
            self.db.add(line)
            lines.append(line)

        await self.db.commit()
        for line in lines:
            await self.db.refresh(line)

        return VoucherRead(
            voucher_no=voucher_no,
            voucher_type=voucher_type.value,
            transaction_date=payload.transaction_date,
            created_at=lines[0].created_at,
            lines=lines,
        )

    async def update_voucher(
        self, line_id: int, payload: VoucherCreate, updated_by: int | None = None
    ) -> VoucherRead:
        existing = await self.get_voucher_by_line_id(line_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found"
            )

        rows = await self.db.execute(
            select(Transaction).where(Transaction.voucher_no == existing.voucher_no)
        )
        for row in rows.scalars().all():
            await self.db.delete(row)
        await self.db.flush()

        rebuilt = await self.create_voucher(payload, created_by=updated_by)
        return rebuilt

    async def void_voucher(
        self, line_id: int, reason: str, user_id: int | None = None
    ) -> VoucherRead:
        existing = await self.get_voucher_by_line_id(line_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found"
            )

        reversal_type = VoucherType.JV
        today = datetime.now(timezone.utc).date()
        reversal_no = await self._next_voucher_no(reversal_type, today.year)

        original_rows = await self.db.execute(
            select(Transaction)
            .where(Transaction.voucher_no == existing.voucher_no)
            .order_by(Transaction.id.asc())
        )
        originals = list(original_rows.scalars().all())
        for row in originals:
            self.db.add(
                Transaction(
                    voucher_no=reversal_no,
                    voucher_type=reversal_type,
                    transaction_date=today,
                    account_id=row.account_id,
                    party_type=row.party_type,
                    party_id=row.party_id,
                    debit=row.credit,
                    credit=row.debit,
                    description=f"Void reversal for {existing.voucher_no}: {reason}",
                    reference_no=row.reference_no,
                    created_by=user_id,
                )
            )

        await self.db.commit()
        # Mark originals as void in description while preserving number sequence.
        for row in originals:
            row.description = (row.description or "") + f" | VOID: {reason}"
        await self.db.commit()

        return await self.get_voucher_by_line_id(originals[0].id)  # type: ignore[return-value]

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.supplier import Supplier
from ..models.transaction import PartyType, Transaction
from ..schemas.party import (PartyLedgerEntry, PartyLedgerResponse,
                             SupplierCreate, SupplierUpdate)

MONEY = Decimal("0.01")


class SupplierService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_suppliers(self) -> list[Supplier]:
        rows = await self.db.execute(
            select(Supplier).order_by(Supplier.supplier_code.asc())
        )
        suppliers = list(rows.scalars().all())
        for supplier in suppliers:
            supplier.current_balance = await self._calculate_current_balance(supplier)
        return suppliers

    async def get_supplier(self, supplier_id: int) -> Supplier | None:
        row = await self.db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = row.scalar_one_or_none()
        if supplier:
            supplier.current_balance = await self._calculate_current_balance(supplier)
        return supplier

    async def create_supplier(self, payload: SupplierCreate) -> Supplier:
        supplier = Supplier(
            supplier_code=payload.supplier_code,
            supplier_name=payload.supplier_name,
            country=payload.country,
            contact_person=payload.contact_person,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            address=payload.address,
            currency=payload.currency,
            opening_balance=Decimal(payload.opening_balance).quantize(MONEY),
            current_balance=Decimal(payload.opening_balance).quantize(MONEY),
        )
        self.db.add(supplier)
        await self.db.commit()
        await self.db.refresh(supplier)
        return supplier

    async def update_supplier(
        self, supplier: Supplier, payload: SupplierUpdate
    ) -> Supplier:
        data = payload.model_dump(exclude_unset=True)
        if "email" in data and data["email"] is not None:
            data["email"] = str(data["email"])
        for key, value in data.items():
            setattr(supplier, key, value)

        supplier.current_balance = await self._calculate_current_balance(supplier)
        await self.db.commit()
        await self.db.refresh(supplier)
        return supplier

    async def _calculate_current_balance(self, supplier: Supplier) -> Decimal:
        totals = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                Transaction.party_type == PartyType.supplier,
                Transaction.party_id == supplier.id,
            )
        )
        debit, credit = totals.one()
        current = Decimal(supplier.opening_balance) + Decimal(credit) - Decimal(debit)
        return current.quantize(MONEY)

    async def ledger(self, supplier_id: int) -> PartyLedgerResponse:
        supplier = await self.get_supplier(supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
            )

        rows = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.party_type == PartyType.supplier,
                Transaction.party_id == supplier.id,
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        )
        entries_rows = list(rows.scalars().all())

        total_row = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                Transaction.party_type == PartyType.supplier,
                Transaction.party_id == supplier.id,
            )
        )
        total_debit, total_credit = total_row.one()

        entries = [
            PartyLedgerEntry(
                id=item.id,
                voucher_no=item.voucher_no,
                voucher_type=item.voucher_type.value,
                transaction_date=item.transaction_date,
                debit=Decimal(item.debit),
                credit=Decimal(item.credit),
                description=item.description,
                reference_no=item.reference_no,
            )
            for item in entries_rows
        ]

        return PartyLedgerResponse(
            party_id=supplier.id,
            party_type="supplier",
            total_debit=Decimal(total_debit),
            total_credit=Decimal(total_credit),
            opening_balance=Decimal(supplier.opening_balance),
            current_balance=Decimal(supplier.current_balance),
            entries=entries,
        )

    async def delete_supplier(self, supplier: Supplier) -> None:
        await self.db.delete(supplier)
        await self.db.commit()

    async def bulk_delete_suppliers(self, ids: list[int]) -> list[int]:
        from sqlalchemy import delete

        failed: list[int] = []
        try:
            stmt = delete(Supplier).where(Supplier.id.in_(ids))
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            for sid in ids:
                try:
                    sup = await self.get_supplier(sid)
                    if sup:
                        await self.delete_supplier(sup)
                    else:
                        failed.append(sid)
                except Exception:
                    failed.append(sid)
        return failed

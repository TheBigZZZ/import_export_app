from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customer import Customer
from ..models.transaction import PartyType, Transaction
from ..schemas.party import (CustomerCreate, CustomerUpdate, PartyLedgerEntry,
                             PartyLedgerResponse)

MONEY = Decimal("0.01")


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_customers(self) -> list[Customer]:
        rows = await self.db.execute(
            select(Customer).order_by(Customer.customer_code.asc())
        )
        customers = list(rows.scalars().all())
        for customer in customers:
            customer.current_balance = await self._calculate_current_balance(customer)
        return customers

    async def get_customer(self, customer_id: int) -> Customer | None:
        row = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        customer = row.scalar_one_or_none()
        if customer:
            customer.current_balance = await self._calculate_current_balance(customer)
        return customer

    async def create_customer(self, payload: CustomerCreate) -> Customer:
        customer = Customer(
            customer_code=payload.customer_code,
            customer_name=payload.customer_name,
            contact_person=payload.contact_person,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            address=payload.address,
            bin_no=payload.bin_no,
            credit_limit=Decimal(payload.credit_limit).quantize(MONEY),
            opening_balance=Decimal(payload.opening_balance).quantize(MONEY),
            current_balance=Decimal(payload.opening_balance).quantize(MONEY),
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def update_customer(
        self, customer: Customer, payload: CustomerUpdate
    ) -> Customer:
        data = payload.model_dump(exclude_unset=True)
        if "email" in data and data["email"] is not None:
            data["email"] = str(data["email"])
        for key, value in data.items():
            setattr(customer, key, value)

        customer.current_balance = await self._calculate_current_balance(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def _calculate_current_balance(self, customer: Customer) -> Decimal:
        totals = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                Transaction.party_type == PartyType.customer,
                Transaction.party_id == customer.id,
            )
        )
        debit, credit = totals.one()
        current = Decimal(customer.opening_balance) + Decimal(debit) - Decimal(credit)
        return current.quantize(MONEY)

    async def ledger(self, customer_id: int) -> PartyLedgerResponse:
        customer = await self.get_customer(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
            )

        rows = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.party_type == PartyType.customer,
                Transaction.party_id == customer.id,
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        )
        entries_rows = list(rows.scalars().all())

        total_row = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(
                Transaction.party_type == PartyType.customer,
                Transaction.party_id == customer.id,
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
            party_id=customer.id,
            party_type="customer",
            total_debit=Decimal(total_debit),
            total_credit=Decimal(total_credit),
            opening_balance=Decimal(customer.opening_balance),
            current_balance=Decimal(customer.current_balance),
            entries=entries,
        )

    async def delete_customer(self, customer: Customer) -> None:
        await self.db.delete(customer)
        await self.db.commit()

    async def bulk_delete_customers(self, ids: list[int]) -> list[int]:
        """Delete multiple customers by id. Returns list of ids that were not found or failed."""
        from sqlalchemy import delete

        failed: list[int] = []
        try:
            stmt = delete(Customer).where(Customer.id.in_(ids))
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            # Fallback: try deleting individually to record failures
            for cid in ids:
                try:
                    cust = await self.get_customer(cid)
                    if cust:
                        await self.delete_customer(cust)
                    else:
                        failed.append(cid)
                except Exception:
                    failed.append(cid)
        return failed

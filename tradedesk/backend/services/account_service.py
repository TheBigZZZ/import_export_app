from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import AccountType, ChartOfAccount
from ..models.transaction import Transaction
from ..schemas.accounting import (AccountCreate, AccountTreeNode,
                                  AccountUpdate, LedgerEntry, LedgerResponse)


class AccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_accounts(self) -> list[ChartOfAccount]:
        result = await self.db.execute(
            select(ChartOfAccount).order_by(ChartOfAccount.account_code.asc())
        )
        return list(result.scalars().all())

    async def get_account(self, account_id: int) -> ChartOfAccount | None:
        result = await self.db.execute(
            select(ChartOfAccount).where(ChartOfAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def create_account(self, payload: AccountCreate) -> ChartOfAccount:
        account = ChartOfAccount(
            account_code=payload.account_code,
            account_name=payload.account_name,
            account_type=AccountType(payload.account_type),
            parent_id=payload.parent_id,
            is_system=payload.is_system,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def update_account(
        self, account: ChartOfAccount, payload: AccountUpdate
    ) -> ChartOfAccount:
        data = payload.model_dump(exclude_unset=True)
        if "account_type" in data and data["account_type"] is not None:
            data["account_type"] = AccountType(data["account_type"])
        for key, value in data.items():
            setattr(account, key, value)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def get_tree(self) -> list[AccountTreeNode]:
        accounts = await self.list_accounts()
        nodes = {
            item.id: AccountTreeNode(
                id=item.id,
                account_code=item.account_code,
                account_name=item.account_name,
                account_type=item.account_type.value,
                parent_id=item.parent_id,
                children=[],
            )
            for item in accounts
        }

        roots: list[AccountTreeNode] = []
        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots

    async def ledger(self, account_id: int) -> LedgerResponse:
        tx_result = await self.db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        )
        rows = list(tx_result.scalars().all())

        total_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            ).where(Transaction.account_id == account_id)
        )
        debit, credit = total_result.one()
        total_debit = Decimal(debit)
        total_credit = Decimal(credit)

        entries = [
            LedgerEntry(
                id=row.id,
                voucher_no=row.voucher_no,
                voucher_type=row.voucher_type.value,
                transaction_date=row.transaction_date,
                debit=Decimal(row.debit),
                credit=Decimal(row.credit),
                description=row.description,
                reference_no=row.reference_no,
            )
            for row in rows
        ]

        return LedgerResponse(
            account_id=account_id,
            total_debit=total_debit,
            total_credit=total_credit,
            balance=total_debit - total_credit,
            entries=entries,
        )

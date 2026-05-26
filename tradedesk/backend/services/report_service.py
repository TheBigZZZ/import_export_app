from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import AccountType, ChartOfAccount
from ..models.expense import Expense
from ..models.import_shipment import ImportShipment, ShipmentStatus
from ..models.product import Product
from ..models.purchase import PurchaseOrder, PurchaseStatus
from ..models.sales import SalesInvoice, SalesInvoiceStatus
from ..models.transaction import Transaction
from ..schemas.reports import (
    DashboardKpiResponse,
    ProfitLossResponse,
    StockPositionResponse,
    StockPositionRow,
    TrialBalanceResponse,
    TrialBalanceRow,
    AgingResponse,
    AgingBucket,
)

MONEY = Decimal("0.01")


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dashboard_kpis(self) -> DashboardKpiResponse:
        today = date.today()
        month_start = today.replace(day=1)

        sales_month = await self._scalar_sum(
            select(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).where(
                SalesInvoice.invoice_date >= month_start,
                SalesInvoice.status.in_([SalesInvoiceStatus.issued, SalesInvoiceStatus.partial, SalesInvoiceStatus.paid]),
            )
        )
        purchases_month = await self._scalar_sum(
            select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(
                PurchaseOrder.order_date >= month_start,
                PurchaseOrder.status.in_([PurchaseStatus.ordered, PurchaseStatus.partial, PurchaseStatus.received]),
            )
        )
        expenses_month = await self._scalar_sum(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.expense_date >= month_start)
        )

        open_receivables = await self._scalar_sum(
            select(func.coalesce(func.sum(SalesInvoice.due_amount), 0)).where(
                SalesInvoice.status.in_([SalesInvoiceStatus.issued, SalesInvoiceStatus.partial])
            )
        )
        open_payables = await self._scalar_sum(
            select(func.coalesce(func.sum(PurchaseOrder.due_amount), 0)).where(
                PurchaseOrder.status.in_([PurchaseStatus.ordered, PurchaseStatus.partial, PurchaseStatus.received])
            )
        )
        inventory_value = await self._scalar_sum(
            select(func.coalesce(func.sum(Product.current_stock * Product.purchase_price), 0))
        )

        low_stock_count = await self._scalar_count(
            select(func.count(Product.id)).where(Product.reorder_level > 0, Product.current_stock <= Product.reorder_level)
        )
        draft_sales = await self._scalar_count(
            select(func.count(SalesInvoice.id)).where(SalesInvoice.status == SalesInvoiceStatus.draft)
        )
        draft_purchases = await self._scalar_count(
            select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status == PurchaseStatus.draft)
        )
        draft_imports = await self._scalar_count(
            select(func.count(ImportShipment.id)).where(ImportShipment.status != ShipmentStatus.posted)
        )

        return DashboardKpiResponse(
            sales_month=sales_month,
            purchases_month=purchases_month,
            expenses_month=expenses_month,
            open_receivables=open_receivables,
            open_payables=open_payables,
            inventory_value=inventory_value,
            low_stock_count=low_stock_count,
            draft_sales_count=draft_sales,
            draft_purchases_count=draft_purchases,
            draft_imports_count=draft_imports,
        )

    async def trial_balance(self) -> TrialBalanceResponse:
        rows = await self.db.execute(
            select(
                ChartOfAccount.id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            )
            .outerjoin(Transaction, Transaction.account_id == ChartOfAccount.id)
            .group_by(ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name)
            .order_by(ChartOfAccount.account_code.asc())
        )

        items: list[TrialBalanceRow] = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for account_id, account_code, account_name, debit, credit in rows.all():
            debit_d = Decimal(debit).quantize(MONEY)
            credit_d = Decimal(credit).quantize(MONEY)
            total_debit += debit_d
            total_credit += credit_d
            items.append(
                TrialBalanceRow(
                    account_id=account_id,
                    account_code=account_code,
                    account_name=account_name,
                    debit=debit_d,
                    credit=credit_d,
                )
            )

        total_debit = total_debit.quantize(MONEY)
        total_credit = total_credit.quantize(MONEY)
        return TrialBalanceResponse(
            rows=items,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=(total_debit == total_credit),
        )

    async def profit_loss(self) -> ProfitLossResponse:
        income_row = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.credit), 0),
                func.coalesce(func.sum(Transaction.debit), 0),
            )
            .join(ChartOfAccount, Transaction.account_id == ChartOfAccount.id)
            .where(ChartOfAccount.account_type == AccountType.income)
        )
        income_credit, income_debit = income_row.one()
        income_total = (Decimal(income_credit) - Decimal(income_debit)).quantize(MONEY)

        expense_row = await self.db.execute(
            select(
                func.coalesce(func.sum(Transaction.debit), 0),
                func.coalesce(func.sum(Transaction.credit), 0),
            )
            .join(ChartOfAccount, Transaction.account_id == ChartOfAccount.id)
            .where(ChartOfAccount.account_type == AccountType.expense)
        )
        expense_debit, expense_credit = expense_row.one()
        expense_total = (Decimal(expense_debit) - Decimal(expense_credit)).quantize(MONEY)

        return ProfitLossResponse(
            income_total=income_total,
            expense_total=expense_total,
            net_profit=(income_total - expense_total).quantize(MONEY),
        )

    async def stock_position(self) -> StockPositionResponse:
        rows = await self.db.execute(select(Product).order_by(Product.product_code.asc()))
        items: list[StockPositionRow] = []
        total = Decimal("0.00")
        for product in rows.scalars().all():
            stock_value = (Decimal(product.current_stock) * Decimal(product.purchase_price)).quantize(MONEY)
            total += stock_value
            items.append(
                StockPositionRow(
                    product_id=product.id,
                    product_code=product.product_code,
                    product_name=product.product_name,
                    current_stock=Decimal(product.current_stock),
                    unit_cost=Decimal(product.purchase_price),
                    stock_value=stock_value,
                )
            )

        return StockPositionResponse(rows=items, total_stock_value=total.quantize(MONEY))

    async def _bucket_label(self, days_overdue: int) -> str:
        if days_overdue <= 30:
            return '0-30'
        if 31 <= days_overdue <= 60:
            return '31-60'
        if 61 <= days_overdue <= 90:
            return '61-90'
        return '>90'

    async def _aging_buckets(self, invoices: list[tuple[int, Decimal, int]]) -> dict:
        # invoices: list of (party_id, amount, days_overdue)
        from collections import defaultdict
        buckets_map: dict[str, Decimal] = defaultdict(lambda: Decimal('0.00'))
        total = Decimal('0.00')
        for pid, amt, days in invoices:
            total += Decimal(amt)
            label = await self._bucket_label(int(days))
            buckets_map[label] += Decimal(amt)

        # ensure deterministic bucket order
        ordered = []
        for label in ('0-30', '31-60', '61-90', '>90'):
            ordered.append({'bucket': label, 'amount': buckets_map[label].quantize(MONEY)})
        return {'total': total.quantize(MONEY), 'buckets': ordered}

    async def ar_aging(self) -> list[AgingResponse]:
        # Aggregate open receivables per customer
        # fetch per-invoice due amounts + due dates so we can bucket by days past due
        rows = await self.db.execute(
            select(SalesInvoice.customer_id, SalesInvoice.due_amount, SalesInvoice.due_date)
            .where(SalesInvoice.status.in_([SalesInvoiceStatus.issued, SalesInvoiceStatus.partial]))
        )
        from collections import defaultdict
        today = date.today()
        per_party_invoices: dict[int, list[tuple[int, Decimal, int]]] = defaultdict(list)
        for customer_id, due_amount, due_date in rows.all():
            days = 0
            if due_date is not None:
                days = max((today - due_date).days, 0)
            per_party_invoices[customer_id].append((customer_id, Decimal(due_amount), int(days)))

        items: list[AgingResponse] = []
        for party_id, invs in per_party_invoices.items():
            data = await self._aging_buckets(invs)
            items.append(AgingResponse(party_id=party_id, party_type='customer', total_due=data['total'], buckets=data['buckets']))
        return items

    async def ap_aging(self) -> list[AgingResponse]:
        # Aggregate open payables per supplier
        # For purchases we use order_date as proxy for invoice due; gather per-order days since order
        rows = await self.db.execute(
            select(PurchaseOrder.supplier_id, PurchaseOrder.due_amount, PurchaseOrder.order_date)
            .where(PurchaseOrder.status.in_([PurchaseStatus.ordered, PurchaseStatus.partial, PurchaseStatus.received]))
        )
        from collections import defaultdict
        today = date.today()
        per_party_invoices: dict[int, list[tuple[int, Decimal, int]]] = defaultdict(list)
        for supplier_id, due_amount, order_date in rows.all():
            days = 0
            if order_date is not None:
                days = max((today - order_date).days, 0)
            per_party_invoices[supplier_id].append((supplier_id, Decimal(due_amount), int(days)))

        items: list[AgingResponse] = []
        for party_id, invs in per_party_invoices.items():
            data = await self._aging_buckets(invs)
            items.append(AgingResponse(party_id=party_id, party_type='supplier', total_due=data['total'], buckets=data['buckets']))
        return items

    async def _scalar_sum(self, stmt) -> Decimal:
        row = await self.db.execute(stmt)
        return Decimal(row.scalar_one()).quantize(MONEY)

    async def _scalar_count(self, stmt) -> int:
        row = await self.db.execute(stmt)
        return int(row.scalar_one())
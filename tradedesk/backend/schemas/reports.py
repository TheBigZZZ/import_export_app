from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DashboardKpiResponse(BaseModel):
    sales_month: Decimal
    purchases_month: Decimal
    expenses_month: Decimal
    open_receivables: Decimal
    open_payables: Decimal
    inventory_value: Decimal
    low_stock_count: int
    draft_sales_count: int
    draft_purchases_count: int
    draft_imports_count: int


class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


class TrialBalanceResponse(BaseModel):
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool


class ProfitLossResponse(BaseModel):
    income_total: Decimal
    expense_total: Decimal
    net_profit: Decimal


class StockPositionRow(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    current_stock: Decimal
    unit_cost: Decimal
    stock_value: Decimal


class StockPositionResponse(BaseModel):
    rows: list[StockPositionRow]
    total_stock_value: Decimal


class AgingBucket(BaseModel):
    bucket: str
    amount: Decimal


class AgingResponse(BaseModel):
    party_id: int | None = None
    party_type: str | None = None
    total_due: Decimal
    buckets: list[AgingBucket]

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesInvoiceItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0)


class SalesInvoiceCreate(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=100)
    customer_id: int
    invoice_date: date
    due_date: date | None = None
    vat: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None
    items: list[SalesInvoiceItemIn] = Field(min_length=1)


class SalesInvoiceItemRead(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    cost_price: Decimal
    discount: Decimal
    line_total: Decimal


class SalesInvoiceRead(BaseModel):
    id: int
    invoice_no: str
    customer_id: int
    invoice_date: date
    due_date: date | None
    subtotal: Decimal
    vat: Decimal
    discount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    due_amount: Decimal
    status: str
    notes: str | None
    created_at: datetime
    items: list[SalesInvoiceItemRead]


class SalesPostResponse(BaseModel):
    invoice_id: int
    invoice_no: str
    status: str
    voucher_no: str

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0)


class PurchaseOrderCreate(BaseModel):
    po_no: str = Field(min_length=1, max_length=100)
    supplier_id: int
    order_date: date
    expected_date: date | None = None
    vat: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = None
    items: list[PurchaseOrderItemIn] = Field(min_length=1)


class PurchaseOrderItemRead(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal


class PurchaseOrderRead(BaseModel):
    id: int
    po_no: str
    supplier_id: int
    order_date: date
    expected_date: date | None
    subtotal: Decimal
    vat: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    due_amount: Decimal
    status: str
    notes: str | None
    created_at: datetime
    items: list[PurchaseOrderItemRead]


class PurchasePostResponse(BaseModel):
    purchase_order_id: int
    po_no: str
    status: str
    voucher_no: str

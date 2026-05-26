from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    product_code: str = Field(min_length=1, max_length=100)
    product_name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    secondary_unit: str | None = Field(default=None, max_length=50)
    conversion_factor: Decimal | None = None
    purchase_price: Decimal = Decimal("0.00")
    selling_price: Decimal = Decimal("0.00")
    reorder_level: Decimal = Decimal("0.0000")
    warehouse: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class ProductUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    secondary_unit: str | None = Field(default=None, max_length=50)
    conversion_factor: Decimal | None = None
    purchase_price: Decimal | None = None
    selling_price: Decimal | None = None
    reorder_level: Decimal | None = None
    warehouse: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_code: str
    product_name: str
    category: str | None
    unit: str
    secondary_unit: str | None
    conversion_factor: Decimal | None
    purchase_price: Decimal
    selling_price: Decimal
    current_stock: Decimal
    reorder_level: Decimal
    warehouse: str | None
    is_active: bool


class StockMovementCreate(BaseModel):
    product_id: int
    movement_type: str = Field(pattern="^(in|out|adjustment)$")
    quantity: Decimal = Field(gt=0)
    movement_date: date
    unit_cost: Decimal = Field(default=Decimal("0.0000"), ge=0)
    document_type: str | None = Field(default=None, max_length=50)
    document_no: str | None = Field(default=None, max_length=100)
    document_status: str = Field(default="posted", min_length=1, max_length=30)
    remarks: str | None = None
    allow_negative: bool = False


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    movement_date: date
    movement_type: str
    quantity_in: Decimal
    quantity_out: Decimal
    balance_qty: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    document_type: str | None
    document_no: str | None
    document_status: str
    remarks: str | None


class StockLedgerResponse(BaseModel):
    product_id: int
    current_stock: Decimal
    entries: list[StockMovementRead]

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ImportShipmentItemIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    fob_unit_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    allocated_landed_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    total_landed_unit_cost: Decimal = Field(default=Decimal("0.00"), ge=0)


class ImportShipmentCreate(BaseModel):
    supplier_id: int
    lc_no: str | None = Field(default=None, max_length=100)
    lc_date: date | None = None
    shipment_date: date | None = None
    arrival_date: date | None = None
    exchange_rate: Decimal = Field(default=Decimal("1.0000"), gt=0)
    fob_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    freight_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    insurance_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    customs_duty: Decimal = Field(default=Decimal("0.00"), ge=0)
    vat: Decimal = Field(default=Decimal("0.00"), ge=0)
    lc_charge: Decimal = Field(default=Decimal("0.00"), ge=0)
    cf_charge: Decimal = Field(default=Decimal("0.00"), ge=0)
    port_charge: Decimal = Field(default=Decimal("0.00"), ge=0)
    transport_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    items: list[ImportShipmentItemIn] = Field(min_length=1)


class ImportShipmentItemRead(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    unit: str
    fob_unit_cost: Decimal
    allocated_landed_cost: Decimal
    total_landed_unit_cost: Decimal


class ImportShipmentRead(BaseModel):
    id: int
    lc_no: str | None
    supplier_id: int
    shipment_date: date | None
    arrival_date: date | None
    exchange_rate: Decimal
    fob_cost: Decimal
    freight_cost: Decimal
    insurance_cost: Decimal
    customs_duty: Decimal
    vat: Decimal
    lc_charge: Decimal
    cf_charge: Decimal
    port_charge: Decimal
    transport_cost: Decimal
    other_cost: Decimal
    total_landed_cost: Decimal
    status: str
    created_at: datetime
    items: list[ImportShipmentItemRead]


class ImportPostResponse(BaseModel):
    shipment_id: int
    status: str
    voucher_no: str

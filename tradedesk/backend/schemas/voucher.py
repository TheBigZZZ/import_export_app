from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VoucherLineIn(BaseModel):
    account_id: int
    party_type: str | None = None
    party_id: int | None = None
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    description: str | None = None
    reference_no: str | None = None


class VoucherCreate(BaseModel):
    voucher_type: str = Field(min_length=2, max_length=20)
    transaction_date: date
    reference_no: str | None = None
    description: str | None = None
    lines: list[VoucherLineIn] = Field(min_length=2)


class VoucherLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    party_type: str | None
    party_id: int | None
    debit: Decimal
    credit: Decimal
    description: str | None
    reference_no: str | None


class VoucherRead(BaseModel):
    voucher_no: str
    voucher_type: str
    transaction_date: date
    created_at: datetime | None
    lines: list[VoucherLineRead]


class VoucherListResponse(BaseModel):
    items: list[VoucherRead]
    total: int


class VoucherVoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)

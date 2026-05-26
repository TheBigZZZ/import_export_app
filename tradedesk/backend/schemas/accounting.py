from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=50)
    account_name: str = Field(min_length=1, max_length=200)
    account_type: str = Field(min_length=3, max_length=20)
    parent_id: int | None = None
    is_system: bool = False


class AccountUpdate(BaseModel):
    account_code: str | None = Field(default=None, min_length=1, max_length=50)
    account_name: str | None = Field(default=None, min_length=1, max_length=200)
    account_type: str | None = Field(default=None, min_length=3, max_length=20)
    parent_id: int | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_code: str
    account_name: str
    account_type: str
    parent_id: int | None
    is_system: bool
    created_at: datetime


class AccountTreeNode(BaseModel):
    id: int
    account_code: str
    account_name: str
    account_type: str
    parent_id: int | None
    children: list["AccountTreeNode"] = Field(default_factory=list)


class LedgerEntry(BaseModel):
    id: int
    voucher_no: str
    voucher_type: str
    transaction_date: date
    debit: Decimal
    credit: Decimal
    description: str | None
    reference_no: str | None


class LedgerResponse(BaseModel):
    account_id: int
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal
    entries: list[LedgerEntry]

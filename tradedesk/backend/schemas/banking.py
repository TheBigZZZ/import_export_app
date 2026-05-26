from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BankCreate(BaseModel):
    bank_name: str = Field(min_length=1, max_length=150)
    account_name: str = Field(min_length=1, max_length=150)
    account_number: str = Field(min_length=1, max_length=100)
    branch_name: str | None = None
    swift_code: str | None = None
    currency: str = "BDT"
    opening_balance: Decimal = Decimal("0.00")


class BankRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bank_name: str
    account_name: str
    account_number: str
    branch_name: str | None
    swift_code: str | None
    currency: str
    opening_balance: Decimal
    current_balance: Decimal
    is_active: bool


class BankTransferRequest(BaseModel):
    from_bank_account_id: int
    to_bank_account_id: int
    amount: Decimal = Field(gt=0)
    transaction_date: date
    reference_no: str | None = None
    description: str | None = None


class StatementEntry(BaseModel):
    id: int
    voucher_no: str
    voucher_type: str
    transaction_date: date
    debit: Decimal
    credit: Decimal
    description: str | None


class BankStatementResponse(BaseModel):
    bank_account_id: int
    entries: list[StatementEntry]

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreate(BaseModel):
    expense_no: str = Field(min_length=3, max_length=100)
    expense_date: date
    account_id: int
    amount: Decimal = Field(gt=Decimal("0"))
    payment_method: str = Field(pattern="^(cash|bank)$")
    bank_account_id: int | None = None
    description: str | None = None
    reference: str | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_no: str
    expense_date: date
    account_id: int
    amount: Decimal
    payment_method: str
    bank_account_id: int | None
    description: str | None
    reference: str | None


class ExpensePostResponse(BaseModel):
    expense: ExpenseRead
    voucher_no: str
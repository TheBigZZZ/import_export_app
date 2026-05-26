from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CashTransactionCreate(BaseModel):
    transaction_date: date
    amount: Decimal = Field(gt=0)
    direction: str = Field(pattern="^(in|out)$")
    account_id: int
    description: str | None = None
    reference_no: str | None = None


class DailyClosingResponse(BaseModel):
    date: date
    opening: Decimal
    receipts: Decimal
    payments: Decimal
    closing: Decimal

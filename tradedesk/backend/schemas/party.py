from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    customer_code: str = Field(min_length=1, max_length=50)
    customer_name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bin_no: str | None = Field(default=None, max_length=50)
    credit_limit: Decimal = Decimal("0.00")
    opening_balance: Decimal = Decimal("0.00")


class CustomerUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    bin_no: str | None = Field(default=None, max_length=50)
    credit_limit: Decimal | None = None
    opening_balance: Decimal | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_code: str
    customer_name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    bin_no: str | None
    credit_limit: Decimal
    opening_balance: Decimal
    current_balance: Decimal
    created_at: datetime


class SupplierCreate(BaseModel):
    supplier_code: str = Field(min_length=1, max_length=50)
    supplier_name: str = Field(min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    currency: str = Field(default="USD", min_length=1, max_length=10)
    opening_balance: Decimal = Decimal("0.00")


class SupplierUpdate(BaseModel):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    opening_balance: Decimal | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_code: str
    supplier_name: str
    country: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    currency: str
    opening_balance: Decimal
    current_balance: Decimal
    created_at: datetime


class PartyLedgerEntry(BaseModel):
    id: int
    voucher_no: str
    voucher_type: str
    transaction_date: date
    debit: Decimal
    credit: Decimal
    description: str | None
    reference_no: str | None


class PartyLedgerResponse(BaseModel):
    party_id: int
    party_type: str
    total_debit: Decimal
    total_credit: Decimal
    opening_balance: Decimal
    current_balance: Decimal
    entries: list[PartyLedgerEntry]

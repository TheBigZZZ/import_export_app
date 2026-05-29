import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class VoucherType(str, enum.Enum):
    CPV = "CPV"
    CRV = "CRV"
    BPV = "BPV"
    BRV = "BRV"
    JV = "JV"
    Contra = "Contra"


class PartyType(str, enum.Enum):
    customer = "customer"
    supplier = "supplier"
    other = "other"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voucher_no: Mapped[str] = mapped_column(String(100), nullable=False)
    voucher_type: Mapped[VoucherType] = mapped_column(Enum(VoucherType), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id"), nullable=False
    )
    party_type: Mapped[PartyType | None] = mapped_column(Enum(PartyType), nullable=True)
    party_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    bank = "bank"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False
    )
    bank_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

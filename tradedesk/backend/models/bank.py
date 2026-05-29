from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    swift_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BDT")
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

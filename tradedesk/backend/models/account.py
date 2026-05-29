import enum
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Integer, String,
                        func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class AccountType(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("chart_of_accounts.id"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    parent: Mapped["ChartOfAccount | None"] = relationship(
        remote_side=[id], backref="children"
    )

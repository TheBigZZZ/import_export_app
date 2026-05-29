from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency_from: Mapped[str] = mapped_column(String(8), nullable=False)
    currency_to: Mapped[str] = mapped_column(String(8), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

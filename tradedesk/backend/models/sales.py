import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SalesInvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    partial = "partial"
    paid = "paid"
    cancelled = "cancelled"


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    vat: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    due_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[SalesInvoiceStatus] = mapped_column(
        Enum(SalesInvoiceStatus), nullable=False, default=SalesInvoiceStatus.draft
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SalesInvoiceItem(Base):
    __tablename__ = "sales_invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("sales_invoices.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )

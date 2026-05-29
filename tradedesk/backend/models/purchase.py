import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PurchaseStatus(str, enum.Enum):
    draft = "draft"
    ordered = "ordered"
    received = "received"
    partial = "partial"
    cancelled = "cancelled"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    vat: Mapped[Decimal] = mapped_column(
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
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus), nullable=False, default=PurchaseStatus.draft
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )

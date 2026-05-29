import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, func)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ShipmentStatus(str, enum.Enum):
    draft = "draft"
    arrived = "arrived"
    costed = "costed"
    posted = "posted"


class ImportShipment(Base):
    __tablename__ = "import_shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lc_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    shipment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    container_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bl_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("1.0000")
    )
    fob_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    freight_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    insurance_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    customs_duty: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    vat: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    lc_charge: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    cf_charge: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    port_charge: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    transport_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    other_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    total_landed_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus), nullable=False, default=ShipmentStatus.draft
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ImportShipmentItem(Base):
    __tablename__ = "import_shipment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("import_shipments.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    fob_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    allocated_landed_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_landed_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

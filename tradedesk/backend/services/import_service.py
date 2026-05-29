from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import ChartOfAccount
from ..models.import_shipment import (ImportShipment, ImportShipmentItem,
                                      ShipmentStatus)
from ..models.product import Product
from ..models.supplier import Supplier
from ..models.transaction import PartyType
from ..schemas.import_ops import (ImportPostResponse, ImportShipmentCreate,
                                  ImportShipmentItemRead, ImportShipmentRead)
from ..schemas.inventory import StockMovementCreate
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .product_service import ProductService
from .voucher_service import VoucherService

MONEY = Decimal("0.01")


class ImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _account_id(self, code: str) -> int:
        row = await self.db.execute(
            select(ChartOfAccount).where(ChartOfAccount.account_code == code)
        )
        account = row.scalar_one_or_none()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account {code} is not configured",
            )
        return account.id

    async def list_shipments(self) -> list[ImportShipmentRead]:
        rows = await self.db.execute(
            select(ImportShipment).order_by(ImportShipment.id.desc())
        )
        return [await self._to_read(item) for item in rows.scalars().all()]

    async def _to_read(self, shipment: ImportShipment) -> ImportShipmentRead:
        rows = await self.db.execute(
            select(ImportShipmentItem)
            .where(ImportShipmentItem.shipment_id == shipment.id)
            .order_by(ImportShipmentItem.id.asc())
        )
        items = [
            ImportShipmentItemRead(
                id=item.id,
                product_id=item.product_id,
                quantity=Decimal(item.quantity),
                unit=item.unit,
                fob_unit_cost=Decimal(item.fob_unit_cost),
                allocated_landed_cost=Decimal(item.allocated_landed_cost),
                total_landed_unit_cost=Decimal(item.total_landed_unit_cost),
            )
            for item in rows.scalars().all()
        ]
        return ImportShipmentRead(
            id=shipment.id,
            lc_no=shipment.lc_no,
            supplier_id=shipment.supplier_id,
            shipment_date=shipment.shipment_date,
            arrival_date=shipment.arrival_date,
            exchange_rate=Decimal(shipment.exchange_rate),
            fob_cost=Decimal(shipment.fob_cost),
            freight_cost=Decimal(shipment.freight_cost),
            insurance_cost=Decimal(shipment.insurance_cost),
            customs_duty=Decimal(shipment.customs_duty),
            vat=Decimal(shipment.vat),
            lc_charge=Decimal(shipment.lc_charge),
            cf_charge=Decimal(shipment.cf_charge),
            port_charge=Decimal(shipment.port_charge),
            transport_cost=Decimal(shipment.transport_cost),
            other_cost=Decimal(shipment.other_cost),
            total_landed_cost=Decimal(shipment.total_landed_cost),
            status=shipment.status.value,
            created_at=shipment.created_at,
            items=items,
        )

    async def create_shipment(
        self, payload: ImportShipmentCreate, created_by: int | None
    ) -> ImportShipmentRead:
        supplier_row = await self.db.execute(
            select(Supplier).where(Supplier.id == payload.supplier_id)
        )
        if not supplier_row.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
            )

        product_ids = [item.product_id for item in payload.items]
        products = await self.db.execute(
            select(Product.id).where(Product.id.in_(product_ids))
        )
        existing = {row[0] for row in products.all()}
        missing = [pid for pid in product_ids if pid not in existing]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Missing product(s): {missing}",
            )

        charges = (
            Decimal(payload.fob_cost)
            + Decimal(payload.freight_cost)
            + Decimal(payload.insurance_cost)
            + Decimal(payload.customs_duty)
            + Decimal(payload.vat)
            + Decimal(payload.lc_charge)
            + Decimal(payload.cf_charge)
            + Decimal(payload.port_charge)
            + Decimal(payload.transport_cost)
            + Decimal(payload.other_cost)
        ).quantize(MONEY)

        shipment = ImportShipment(
            lc_no=payload.lc_no,
            lc_date=payload.lc_date,
            supplier_id=payload.supplier_id,
            shipment_date=payload.shipment_date,
            arrival_date=payload.arrival_date,
            exchange_rate=payload.exchange_rate,
            fob_cost=payload.fob_cost,
            freight_cost=payload.freight_cost,
            insurance_cost=payload.insurance_cost,
            customs_duty=payload.customs_duty,
            vat=payload.vat,
            lc_charge=payload.lc_charge,
            cf_charge=payload.cf_charge,
            port_charge=payload.port_charge,
            transport_cost=payload.transport_cost,
            other_cost=payload.other_cost,
            total_landed_cost=charges,
            status=ShipmentStatus.costed,
            created_by=created_by,
        )
        self.db.add(shipment)
        await self.db.flush()

        for item in payload.items:
            self.db.add(
                ImportShipmentItem(
                    shipment_id=shipment.id,
                    product_id=item.product_id,
                    quantity=Decimal(item.quantity),
                    unit=item.unit,
                    fob_unit_cost=Decimal(item.fob_unit_cost),
                    allocated_landed_cost=Decimal(item.allocated_landed_cost),
                    total_landed_unit_cost=Decimal(item.total_landed_unit_cost),
                )
            )

        await self.db.commit()
        await self.db.refresh(shipment)
        return await self._to_read(shipment)

    async def post_shipment(
        self, shipment_id: int, user_id: int | None
    ) -> ImportPostResponse:
        row = await self.db.execute(
            select(ImportShipment).where(ImportShipment.id == shipment_id)
        )
        shipment = row.scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import shipment not found",
            )
        if shipment.status == ShipmentStatus.posted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment already posted",
            )

        item_rows = await self.db.execute(
            select(ImportShipmentItem).where(
                ImportShipmentItem.shipment_id == shipment.id
            )
        )
        items = list(item_rows.scalars().all())
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Shipment has no items"
            )

        product_service = ProductService(self.db)
        computed_total = Decimal("0.00")
        for item in items:
            unit_cost = Decimal(item.total_landed_unit_cost or item.fob_unit_cost)
            computed_total += (Decimal(item.quantity) * unit_cost).quantize(MONEY)
            await product_service.create_stock_movement(
                StockMovementCreate(
                    product_id=item.product_id,
                    movement_type="in",
                    quantity=Decimal(item.quantity),
                    movement_date=shipment.arrival_date or shipment.shipment_date,
                    unit_cost=unit_cost,
                    document_type="import_shipment",
                    document_no=shipment.lc_no or f"SHIP-{shipment.id}",
                    document_status="posted",
                    remarks=f"Import shipment {shipment.id}",
                ),
                created_by=user_id,
            )

        if Decimal(shipment.total_landed_cost) <= Decimal("0.00"):
            shipment.total_landed_cost = computed_total.quantize(MONEY)

        inventory_account_id = await self._account_id("1200")
        payable_account_id = await self._account_id("2000")
        amount = Decimal(shipment.total_landed_cost).quantize(MONEY)

        voucher = await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type="JV",
                transaction_date=shipment.arrival_date or shipment.shipment_date,
                reference_no=shipment.lc_no,
                description=f"Posted import shipment {shipment.id}",
                lines=[
                    VoucherLineIn(
                        account_id=inventory_account_id,
                        debit=amount,
                        credit=Decimal("0.00"),
                        description=f"Import shipment {shipment.id}",
                    ),
                    VoucherLineIn(
                        account_id=payable_account_id,
                        party_type=PartyType.supplier.value,
                        party_id=shipment.supplier_id,
                        debit=Decimal("0.00"),
                        credit=amount,
                        description=f"Import shipment {shipment.id}",
                    ),
                ],
            ),
            created_by=user_id,
        )

        shipment.status = ShipmentStatus.posted
        await self.db.commit()

        return ImportPostResponse(
            shipment_id=shipment.id,
            status=shipment.status.value,
            voucher_no=voucher.voucher_no,
        )

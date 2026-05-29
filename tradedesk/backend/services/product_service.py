from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.product import Product
from ..models.stock_ledger import StockLedger, StockMovementType
from ..schemas.inventory import (ProductCreate, ProductUpdate,
                                 StockMovementCreate)
from .inventory_service import (apply_stock_movement,
                                validate_document_is_posted)
from .settings_service import SettingsService


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_products(self) -> list[Product]:
        rows = await self.db.execute(
            select(Product).order_by(Product.product_code.asc())
        )
        return list(rows.scalars().all())

    async def get_product(self, product_id: int) -> Product | None:
        row = await self.db.execute(select(Product).where(Product.id == product_id))
        return row.scalar_one_or_none()

    async def create_product(self, payload: ProductCreate) -> Product:
        product = Product(
            product_code=payload.product_code,
            product_name=payload.product_name,
            category=payload.category,
            unit=payload.unit,
            secondary_unit=payload.secondary_unit,
            conversion_factor=payload.conversion_factor,
            purchase_price=payload.purchase_price,
            selling_price=payload.selling_price,
            current_stock=Decimal("0.0000"),
            reorder_level=payload.reorder_level,
            warehouse=payload.warehouse,
            is_active=payload.is_active,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def update_product(self, product: Product, payload: ProductUpdate) -> Product:
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def create_stock_movement(
        self, payload: StockMovementCreate, created_by: int | None
    ) -> StockLedger:
        validate_document_is_posted(payload.document_status)

        product = await self.get_product(payload.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        quantity = Decimal(payload.quantity)
        movement_type = StockMovementType(payload.movement_type)
        signed_qty = -quantity if movement_type == StockMovementType.OUT else quantity

        app_settings = SettingsService().get_settings()
        allow_negative_stock = (
            bool(app_settings.get("allow_negative_stock")) or payload.allow_negative
        )

        new_stock = apply_stock_movement(
            current_stock=Decimal(product.current_stock),
            movement_qty=signed_qty,
            allow_negative=allow_negative_stock,
        )

        quantity_in = quantity if signed_qty >= 0 else Decimal("0.0000")
        quantity_out = quantity if signed_qty < 0 else Decimal("0.0000")
        unit_cost = Decimal(payload.unit_cost)

        movement = StockLedger(
            product_id=product.id,
            movement_date=payload.movement_date,
            movement_type=movement_type,
            quantity_in=quantity_in,
            quantity_out=quantity_out,
            balance_qty=new_stock,
            unit_cost=unit_cost,
            total_cost=(quantity * unit_cost).quantize(Decimal("0.01")),
            document_type=payload.document_type,
            document_no=payload.document_no,
            document_status=payload.document_status,
            remarks=payload.remarks,
            created_by=created_by,
        )
        self.db.add(movement)

        product.current_stock = new_stock
        await self.db.commit()
        await self.db.refresh(movement)
        return movement

    async def stock_ledger(
        self, product_id: int, limit: int = 200
    ) -> tuple[Product, list[StockLedger]]:
        product = await self.get_product(product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        rows = await self.db.execute(
            select(StockLedger)
            .where(StockLedger.product_id == product.id)
            .order_by(StockLedger.movement_date.desc(), StockLedger.id.desc())
            .limit(limit)
        )
        entries = list(rows.scalars().all())
        return product, entries

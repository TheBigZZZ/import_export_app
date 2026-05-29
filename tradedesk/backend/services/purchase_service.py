from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import ChartOfAccount
from ..models.product import Product
from ..models.purchase import PurchaseOrder, PurchaseOrderItem, PurchaseStatus
from ..models.supplier import Supplier
from ..models.transaction import PartyType
from ..schemas.inventory import StockMovementCreate
from ..schemas.purchase_ops import (PurchaseOrderCreate, PurchaseOrderItemRead,
                                    PurchaseOrderRead, PurchasePostResponse)
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .product_service import ProductService
from .voucher_service import VoucherService

MONEY = Decimal("0.01")


def calculate_purchase_subtotal(items: list[PurchaseOrderItem]) -> Decimal:
    return sum((Decimal(item.line_total) for item in items), Decimal("0.00")).quantize(
        MONEY
    )


class PurchaseService:
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

    async def list_orders(self) -> list[PurchaseOrderRead]:
        rows = await self.db.execute(
            select(PurchaseOrder).order_by(
                PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc()
            )
        )
        orders = list(rows.scalars().all())
        return [await self._to_read(order) for order in orders]

    async def _to_read(self, order: PurchaseOrder) -> PurchaseOrderRead:
        item_rows = await self.db.execute(
            select(PurchaseOrderItem)
            .where(PurchaseOrderItem.purchase_order_id == order.id)
            .order_by(PurchaseOrderItem.id.asc())
        )
        items = [
            PurchaseOrderItemRead(
                id=item.id,
                product_id=item.product_id,
                quantity=Decimal(item.quantity),
                unit_price=Decimal(item.unit_price),
                discount=Decimal(item.discount),
                line_total=Decimal(item.line_total),
            )
            for item in item_rows.scalars().all()
        ]
        return PurchaseOrderRead(
            id=order.id,
            po_no=order.po_no,
            supplier_id=order.supplier_id,
            order_date=order.order_date,
            expected_date=order.expected_date,
            subtotal=Decimal(order.subtotal),
            vat=Decimal(order.vat),
            total_amount=Decimal(order.total_amount),
            paid_amount=Decimal(order.paid_amount),
            due_amount=Decimal(order.due_amount),
            status=order.status.value,
            notes=order.notes,
            created_at=order.created_at,
            items=items,
        )

    async def create_order(
        self, payload: PurchaseOrderCreate, created_by: int | None
    ) -> PurchaseOrderRead:
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

        order = PurchaseOrder(
            po_no=payload.po_no,
            supplier_id=payload.supplier_id,
            order_date=payload.order_date,
            expected_date=payload.expected_date,
            subtotal=Decimal("0.00"),
            vat=Decimal(payload.vat).quantize(MONEY),
            total_amount=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            due_amount=Decimal("0.00"),
            status=PurchaseStatus.ordered,
            notes=payload.notes,
            created_by=created_by,
        )
        self.db.add(order)
        await self.db.flush()

        subtotal = Decimal("0.00")
        for item in payload.items:
            line_total = (
                Decimal(item.quantity) * Decimal(item.unit_price)
                - Decimal(item.discount)
            ).quantize(MONEY)
            subtotal += line_total
            self.db.add(
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    product_id=item.product_id,
                    quantity=Decimal(item.quantity),
                    unit_price=Decimal(item.unit_price),
                    discount=Decimal(item.discount),
                    line_total=line_total,
                )
            )

        order.subtotal = subtotal.quantize(MONEY)
        order.total_amount = (order.subtotal + order.vat).quantize(MONEY)
        order.due_amount = order.total_amount

        await self.db.commit()
        await self.db.refresh(order)
        return await self._to_read(order)

    async def post_order(
        self, order_id: int, user_id: int | None
    ) -> PurchasePostResponse:
        row = await self.db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == order_id)
        )
        order = row.scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found"
            )
        if order.status not in (PurchaseStatus.ordered, PurchaseStatus.draft):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft/ordered purchase can be posted",
            )

        item_rows = await self.db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == order.id
            )
        )
        items = list(item_rows.scalars().all())
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase order has no items",
            )

        product_service = ProductService(self.db)
        for item in items:
            await product_service.create_stock_movement(
                StockMovementCreate(
                    product_id=item.product_id,
                    movement_type="in",
                    quantity=Decimal(item.quantity),
                    movement_date=order.order_date,
                    unit_cost=Decimal(item.unit_price),
                    document_type="purchase_order",
                    document_no=order.po_no,
                    document_status="posted",
                    remarks=f"Purchase order {order.po_no}",
                ),
                created_by=user_id,
            )

        inventory_account_id = await self._account_id("1200")
        payable_account_id = await self._account_id("2000")

        voucher = await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type="JV",
                transaction_date=order.order_date,
                reference_no=order.po_no,
                description=f"Posted purchase order {order.po_no}",
                lines=[
                    VoucherLineIn(
                        account_id=inventory_account_id,
                        debit=Decimal(order.total_amount),
                        credit=Decimal("0.00"),
                        description=f"Purchase order {order.po_no}",
                    ),
                    VoucherLineIn(
                        account_id=payable_account_id,
                        party_type=PartyType.supplier.value,
                        party_id=order.supplier_id,
                        debit=Decimal("0.00"),
                        credit=Decimal(order.total_amount),
                        description=f"Purchase order {order.po_no}",
                    ),
                ],
            ),
            created_by=user_id,
        )

        order.status = PurchaseStatus.received
        order.due_amount = Decimal(order.total_amount) - Decimal(order.paid_amount)
        await self.db.commit()

        return PurchasePostResponse(
            purchase_order_id=order.id,
            po_no=order.po_no,
            status=order.status.value,
            voucher_no=voucher.voucher_no,
        )

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import ChartOfAccount
from ..models.customer import Customer
from ..models.product import Product
from ..models.sales import SalesInvoice, SalesInvoiceItem, SalesInvoiceStatus
from ..models.transaction import PartyType
from ..schemas.inventory import StockMovementCreate
from ..schemas.sales_ops import (SalesInvoiceCreate, SalesInvoiceItemRead,
                                 SalesInvoiceRead, SalesPostResponse)
from ..schemas.voucher import VoucherCreate, VoucherLineIn
from .product_service import ProductService
from .voucher_service import VoucherService

MONEY = Decimal("0.01")


def calculate_sales_subtotal(items: list[SalesInvoiceItem]) -> Decimal:
    return sum((Decimal(item.line_total) for item in items), Decimal("0.00")).quantize(
        MONEY
    )


class SalesService:
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

    async def list_invoices(self) -> list[SalesInvoiceRead]:
        rows = await self.db.execute(
            select(SalesInvoice).order_by(
                SalesInvoice.invoice_date.desc(), SalesInvoice.id.desc()
            )
        )
        invoices = list(rows.scalars().all())
        return [await self._to_read(invoice) for invoice in invoices]

    async def _to_read(self, invoice: SalesInvoice) -> SalesInvoiceRead:
        item_rows = await self.db.execute(
            select(SalesInvoiceItem)
            .where(SalesInvoiceItem.invoice_id == invoice.id)
            .order_by(SalesInvoiceItem.id.asc())
        )
        items = [
            SalesInvoiceItemRead(
                id=item.id,
                product_id=item.product_id,
                quantity=Decimal(item.quantity),
                unit_price=Decimal(item.unit_price),
                cost_price=Decimal(item.cost_price),
                discount=Decimal(item.discount),
                line_total=Decimal(item.line_total),
            )
            for item in item_rows.scalars().all()
        ]
        return SalesInvoiceRead(
            id=invoice.id,
            invoice_no=invoice.invoice_no,
            customer_id=invoice.customer_id,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            subtotal=Decimal(invoice.subtotal),
            vat=Decimal(invoice.vat),
            discount=Decimal(invoice.discount),
            total_amount=Decimal(invoice.total_amount),
            paid_amount=Decimal(invoice.paid_amount),
            due_amount=Decimal(invoice.due_amount),
            status=invoice.status.value,
            notes=invoice.notes,
            created_at=invoice.created_at,
            items=items,
        )

    async def create_invoice(
        self, payload: SalesInvoiceCreate, created_by: int | None
    ) -> SalesInvoiceRead:
        customer_row = await self.db.execute(
            select(Customer).where(Customer.id == payload.customer_id)
        )
        if not customer_row.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
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

        invoice = SalesInvoice(
            invoice_no=payload.invoice_no,
            customer_id=payload.customer_id,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            subtotal=Decimal("0.00"),
            vat=Decimal(payload.vat).quantize(MONEY),
            discount=Decimal(payload.discount).quantize(MONEY),
            total_amount=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            due_amount=Decimal("0.00"),
            status=SalesInvoiceStatus.draft,
            notes=payload.notes,
            created_by=created_by,
        )
        self.db.add(invoice)
        await self.db.flush()

        subtotal = Decimal("0.00")
        for item in payload.items:
            line_total = (
                Decimal(item.quantity) * Decimal(item.unit_price)
                - Decimal(item.discount)
            ).quantize(MONEY)
            subtotal += line_total
            self.db.add(
                SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_id=item.product_id,
                    quantity=Decimal(item.quantity),
                    unit_price=Decimal(item.unit_price),
                    cost_price=Decimal(item.cost_price),
                    discount=Decimal(item.discount),
                    line_total=line_total,
                )
            )

        invoice.subtotal = subtotal.quantize(MONEY)
        invoice.total_amount = (
            invoice.subtotal + invoice.vat - invoice.discount
        ).quantize(MONEY)
        invoice.due_amount = invoice.total_amount

        await self.db.commit()
        await self.db.refresh(invoice)
        return await self._to_read(invoice)

    async def post_invoice(
        self, invoice_id: int, user_id: int | None, allow_negative_stock: bool = False
    ) -> SalesPostResponse:
        row = await self.db.execute(
            select(SalesInvoice).where(SalesInvoice.id == invoice_id)
        )
        invoice = row.scalar_one_or_none()
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sales invoice not found"
            )
        if invoice.status != SalesInvoiceStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft invoice can be posted",
            )

        item_rows = await self.db.execute(
            select(SalesInvoiceItem).where(SalesInvoiceItem.invoice_id == invoice.id)
        )
        items = list(item_rows.scalars().all())
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice has no items"
            )

        product_service = ProductService(self.db)
        for item in items:
            await product_service.create_stock_movement(
                StockMovementCreate(
                    product_id=item.product_id,
                    movement_type="out",
                    quantity=Decimal(item.quantity),
                    movement_date=invoice.invoice_date,
                    unit_cost=Decimal(item.cost_price),
                    document_type="sales_invoice",
                    document_no=invoice.invoice_no,
                    document_status="posted",
                    remarks=f"Sales invoice {invoice.invoice_no}",
                    allow_negative=allow_negative_stock,
                ),
                created_by=user_id,
            )

        ar_account_id = await self._account_id("1300")
        sales_account_id = await self._account_id("4000")
        vat_account_id = await self._account_id("2200")

        sales_credit = (Decimal(invoice.total_amount) - Decimal(invoice.vat)).quantize(
            MONEY
        )
        lines = [
            VoucherLineIn(
                account_id=ar_account_id,
                party_type=PartyType.customer.value,
                party_id=invoice.customer_id,
                debit=Decimal(invoice.total_amount),
                credit=Decimal("0.00"),
                description=f"Sales invoice {invoice.invoice_no}",
            ),
            VoucherLineIn(
                account_id=sales_account_id,
                debit=Decimal("0.00"),
                credit=sales_credit,
                description=f"Sales invoice {invoice.invoice_no}",
            ),
        ]
        if Decimal(invoice.vat) > Decimal("0.00"):
            lines.append(
                VoucherLineIn(
                    account_id=vat_account_id,
                    debit=Decimal("0.00"),
                    credit=Decimal(invoice.vat),
                    description=f"VAT on {invoice.invoice_no}",
                )
            )

        voucher = await VoucherService(self.db).create_voucher(
            VoucherCreate(
                voucher_type="JV",
                transaction_date=invoice.invoice_date,
                reference_no=invoice.invoice_no,
                description=f"Posted sales invoice {invoice.invoice_no}",
                lines=lines,
            ),
            created_by=user_id,
        )

        invoice.status = SalesInvoiceStatus.issued
        invoice.due_amount = Decimal(invoice.total_amount) - Decimal(
            invoice.paid_amount
        )
        await self.db.commit()

        return SalesPostResponse(
            invoice_id=invoice.id,
            invoice_no=invoice.invoice_no,
            status=invoice.status.value,
            voucher_no=voucher.voucher_no,
        )

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.sales import SalesInvoice
from ..models.user import User
from ..schemas.sales_ops import (SalesInvoiceCreate, SalesInvoiceRead,
                                 SalesPostResponse)
from ..services.email_service import (generate_invoice_pdf,
                                      send_email_with_attachment)
from ..services.sales_service import SalesService

router = APIRouter()


@router.get("", response_model=list[SalesInvoiceRead])
async def list_sales(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "sales_manager", "accounts_manager", "viewer"
        )
    ),
) -> list[SalesInvoiceRead]:
    return await SalesService(db).list_invoices()


@router.post("", response_model=SalesInvoiceRead)
async def create_sales_invoice(
    payload: SalesInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "sales_manager")),
) -> SalesInvoiceRead:
    return await SalesService(db).create_invoice(payload, created_by=user.id)


@router.post("/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin", "admin", "accounts_manager")),
):
    # Generate PDF and send using diagnostics SMTP settings
    try:
        pdf = await generate_invoice_pdf(db, invoice_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    # fetch invoice to get customer email
    inv = await db.get(SalesInvoice, invoice_id)
    # naive customer lookup
    cust = await db.get(
        __import__("tradedesk.backend.models", fromlist=["Customer"]).Customer,
        inv.customer_id,
    )
    if not cust or not getattr(cust, "email", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer email not available",
        )
    try:
        send_email_with_attachment(
            cust.email,
            f"Invoice {inv.invoice_no}",
            "Please find attached your invoice.",
            pdf,
            f"invoice-{inv.invoice_no}.pdf",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
    return {"sent": True}


@router.post("/{invoice_id}/post", response_model=SalesPostResponse)
async def post_sales_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles("super_admin", "admin", "sales_manager", "accounts_manager")
    ),
) -> SalesPostResponse:
    return await SalesService(db).post_invoice(invoice_id, user_id=user.id)

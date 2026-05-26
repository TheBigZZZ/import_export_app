from __future__ import annotations

import io
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from sqlalchemy.ext.asyncio import AsyncSession

from .exchange_rate_service import ExchangeRateService
from ..models.sales import SalesInvoice, SalesInvoiceItem
from ..models.customer import Customer
from ..config import settings
from ..utils.secret_store import get_secret


def send_simple_email(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg['From'] = settings.diagnostics_smtp_user or settings.diagnostics_notify_email_from or 'noreply@example.com'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)

    host = settings.diagnostics_smtp_host or 'localhost'
    port = settings.diagnostics_smtp_port or 25
    try:
        smtp_password = get_secret("diagnostics_smtp_password")
        if settings.diagnostics_smtp_user and smtp_password:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if settings.diagnostics_smtp_port == 587:
                    smtp.starttls()
                smtp.login(settings.diagnostics_smtp_user, smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.send_message(msg)
    except Exception:
        raise


async def generate_invoice_pdf(db: AsyncSession, invoice_id: int) -> bytes:
    # Load invoice and items
    inv = await db.get(SalesInvoice, invoice_id)
    if not inv:
        raise FileNotFoundError('Invoice not found')
    # fetch customer
    cust = await db.get(Customer, inv.customer_id)

    # fetch items (use model-based query if available)
    items = (await db.execute(
        "SELECT id, invoice_id, product_id, quantity, unit_price, line_total FROM sales_invoice_items WHERE invoice_id = :iid",
        {'iid': invoice_id}
    )).all()

    buf = io.BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    x = margin
    y = height - margin

    # Header: company name (from settings if present)
    company = getattr(settings, 'company_name', None) or 'Your Company'
    p.setFont('Helvetica-Bold', 16)
    p.drawString(x, y, company)
    p.setFont('Helvetica', 9)
    if getattr(cust, 'customer_name', None):
        p.drawString(x, y - 14, f"Bill To: {cust.customer_name}")
    if getattr(cust, 'address', None):
        p.drawString(x, y - 28, str(cust.address))

    # Invoice metadata on right
    p.setFont('Helvetica', 10)
    p.drawRightString(width - margin, y, f"Invoice: {inv.invoice_no}")
    p.drawRightString(width - margin, y - 14, f"Date: {inv.invoice_date}")
    if getattr(inv, 'due_date', None):
        p.drawRightString(width - margin, y - 28, f"Due: {inv.due_date}")

    y -= 50

    # Table header
    table_data = [["Qty", "Description", "Unit", "Line Total"]]
    for row in items:
        # row may be a RowResult or tuple; access by name if possible
        try:
            qty = str(row.quantity)
            prod = getattr(row, 'product_id', '')
            unit = f"{row.unit_price:.2f}"
            line = f"{row.line_total:.2f}"
        except Exception:
            # fallback to tuple indices
            qty = str(row[3]) if len(row) > 3 else '0'
            prod = row[2] if len(row) > 2 else ''
            unit = f"{row[4]:.2f}" if len(row) > 4 else '0.00'
            line = f"{row[5]:.2f}" if len(row) > 5 else '0.00'
        table_data.append([qty, f"Product {prod}", unit, line])

    # Build table
    tbl = Table(table_data, colWidths=[25*mm, 90*mm, 30*mm, 30*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (-2,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    # draw table onto canvas
    w, h = tbl.wrapOn(p, width - 2*margin, y)
    tbl.drawOn(p, x, y - h)
    y = y - h - 20

    # Totals block
    p.setFont('Helvetica-Bold', 10)
    p.drawRightString(width - margin, y, f"Subtotal: {inv.subtotal:.2f}")
    p.drawRightString(width - margin, y - 14, f"VAT: {inv.vat:.2f}")
    p.drawRightString(width - margin, y - 28, f"Discount: {inv.discount:.2f}")
    p.drawRightString(width - margin, y - 42, f"Total: {inv.total_amount:.2f}")

    p.showPage()
    p.save()
    buf.seek(0)
    return buf.read()


def send_email_with_attachment(to_email: str, subject: str, body: str, attachment_bytes: bytes, attachment_name: str = 'invoice.pdf') -> None:
    msg = EmailMessage()
    msg['From'] = settings.diagnostics_smtp_user or settings.diagnostics_notify_email_from or 'noreply@example.com'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)
    msg.add_attachment(attachment_bytes, maintype='application', subtype='pdf', filename=attachment_name)

    host = settings.diagnostics_smtp_host or 'localhost'
    port = settings.diagnostics_smtp_port or 25
    try:
        smtp_password = get_secret("diagnostics_smtp_password")
        if settings.diagnostics_smtp_user and smtp_password:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if settings.diagnostics_smtp_port == 587 and settings.diagnostics_smtp_user:
                    smtp.starttls()
                smtp.login(settings.diagnostics_smtp_user, smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.send_message(msg)
    except Exception:
        raise

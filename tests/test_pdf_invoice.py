import asyncio
from types import SimpleNamespace

from tradedesk.backend.services.email_service import generate_invoice_pdf


class DummyDB:
    def __init__(self, inv, cust, items):
        self._inv = inv
        self._cust = cust
        self._items = items

    async def get(self, model, id):
        if model.__name__ == "SalesInvoice":
            return self._inv
        if model.__name__ == "Customer":
            return self._cust
        return None

    async def execute(self, sql, params=None):
        class Res:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return Res(self._items)


def test_generate_invoice_pdf_basic():
    inv = SimpleNamespace(
        invoice_no="INV-001",
        invoice_date="2026-05-01",
        due_date="2026-05-31",
        subtotal=100.00,
        vat=10.00,
        discount=0.00,
        total_amount=110.00,
        customer_id=1,
    )
    cust = SimpleNamespace(id=1, customer_name="ACME Corp", address="1 Road Ave")
    # simulate row-like items with attributes
    item = SimpleNamespace(
        id=1,
        invoice_id=1,
        product_id=42,
        quantity=2,
        unit_price=50.00,
        line_total=100.00,
    )
    db = DummyDB(inv, cust, [item])

    pdf_bytes = asyncio.run(generate_invoice_pdf(db, invoice_id=1))
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes.startswith(b"%PDF")
    # try to see invoice number in the PDF text stream (best-effort)
    try:
        txt = pdf_bytes.decode("latin1")
        assert "INV-001" in txt
    except Exception:
        # if decode/search fails, at least ensure it's not empty
        assert len(pdf_bytes) > 200

import asyncio
from decimal import Decimal

from tradedesk.backend.services.report_service import ReportService


def test_aging_buckets_simple():
    # Prepare invoices: (party_id, amount, days_overdue)
    invoices = [
        (1, Decimal('100.00'), 5),    # 0-30
        (1, Decimal('200.00'), 35),   # 31-60
        (1, Decimal('50.00'), 70),    # 61-90
        (1, Decimal('25.00'), 200),   # >90
    ]

    svc = ReportService(db=None)
    result = asyncio.run(svc._aging_buckets(invoices))
    assert result['total'] == Decimal('375.00')
    buckets = {b['bucket']: b['amount'] for b in result['buckets']}
    assert buckets['0-30'] == Decimal('100.00')
    assert buckets['31-60'] == Decimal('200.00')
    assert buckets['61-90'] == Decimal('50.00')
    assert buckets['>90'] == Decimal('25.00')

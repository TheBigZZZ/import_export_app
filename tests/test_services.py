from decimal import Decimal

import pytest

from tradedesk.backend.services.accounting_service import (
    AccountingValidationError, JournalLine, allocate_import_cost,
    validate_double_entry)
from tradedesk.backend.services.inventory_service import (
    StockValidationError, apply_stock_movement, validate_document_is_posted)
from tradedesk.backend.startup_checks import (StartupConfigSnapshot,
                                              evaluate_static_startup_checks)


def test_double_entry_balanced_passes() -> None:
    validate_double_entry(
        [
            JournalLine(debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLine(debit=Decimal("0.00"), credit=Decimal("100.00")),
        ]
    )


def test_double_entry_unbalanced_fails() -> None:
    with pytest.raises(AccountingValidationError):
        validate_double_entry(
            [
                JournalLine(debit=Decimal("100.00"), credit=Decimal("0.00")),
                JournalLine(debit=Decimal("0.00"), credit=Decimal("90.00")),
            ]
        )


def test_import_cost_allocation_by_fob_value() -> None:
    values = [Decimal("100"), Decimal("300")]
    extra = Decimal("200")
    allocations = allocate_import_cost(values, extra, method="fob_value")
    assert allocations == [Decimal("50.00"), Decimal("150.00")]


def test_import_cost_allocation_by_quantity() -> None:
    values = [Decimal("100"), Decimal("300")]
    quantities = [Decimal("2"), Decimal("8")]
    extra = Decimal("100")
    allocations = allocate_import_cost(
        values, extra, method="quantity", quantities=quantities
    )
    assert allocations == [Decimal("20.00"), Decimal("80.00")]


def test_stock_movement_blocks_negative() -> None:
    with pytest.raises(StockValidationError):
        apply_stock_movement(Decimal("2"), Decimal("-3"), allow_negative=False)


def test_stock_movement_allows_negative_when_configured() -> None:
    value = apply_stock_movement(Decimal("2"), Decimal("-3"), allow_negative=True)
    assert value == Decimal("-1")


def test_stock_movement_requires_posted_document() -> None:
    with pytest.raises(StockValidationError):
        validate_document_is_posted("draft")


def test_stock_movement_accepts_posted_document() -> None:
    validate_document_is_posted("POSTED")


def test_startup_checks_fail_production_default_secret() -> None:
    errors, warnings = evaluate_static_startup_checks(
        StartupConfigSnapshot(
            environment="production",
            debug=False,
            jwt_secret_key="change-me-in-production",
            bcrypt_rounds=12,
            access_token_expire_minutes=480,
        )
    )
    assert errors
    assert any("JWT_SECRET_KEY" in item for item in errors)
    assert warnings == []


def test_startup_checks_warn_default_secret_in_dev() -> None:
    errors, warnings = evaluate_static_startup_checks(
        StartupConfigSnapshot(
            environment="development",
            debug=True,
            jwt_secret_key="change-me-in-production",
            bcrypt_rounds=10,
            access_token_expire_minutes=300,
        )
    )
    assert errors == []
    assert any("default development value" in item for item in warnings)

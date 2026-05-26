from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


MONEY = Decimal("0.01")


@dataclass
class JournalLine:
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")


class AccountingValidationError(ValueError):
    pass


def validate_double_entry(lines: list[JournalLine]) -> None:
    total_debit = sum((line.debit for line in lines), Decimal("0.00")).quantize(MONEY, rounding=ROUND_HALF_UP)
    total_credit = sum((line.credit for line in lines), Decimal("0.00")).quantize(MONEY, rounding=ROUND_HALF_UP)
    if total_debit != total_credit:
        raise AccountingValidationError(f"Unbalanced voucher: debit={total_debit} credit={total_credit}")


def allocate_import_cost(
    fob_values: list[Decimal],
    extra_cost_total: Decimal,
    method: str = "fob_value",
    quantities: list[Decimal] | None = None,
) -> list[Decimal]:
    if not fob_values:
        return []

    if method == "fob_value":
        basis = fob_values
    elif method == "quantity":
        if not quantities or len(quantities) != len(fob_values):
            raise AccountingValidationError("Quantity basis requires matching quantities")
        basis = quantities
    else:
        raise AccountingValidationError("Unknown allocation method")

    denominator = sum(basis, Decimal("0.00"))
    if denominator <= Decimal("0.00"):
        raise AccountingValidationError("Allocation basis must be greater than zero")

    allocations: list[Decimal] = []
    running_total = Decimal("0.00")
    for index, value in enumerate(basis):
        if index == len(basis) - 1:
            amount = (extra_cost_total - running_total).quantize(MONEY, rounding=ROUND_HALF_UP)
        else:
            ratio = value / denominator
            amount = (extra_cost_total * ratio).quantize(MONEY, rounding=ROUND_HALF_UP)
            running_total += amount
        allocations.append(amount)

    return allocations

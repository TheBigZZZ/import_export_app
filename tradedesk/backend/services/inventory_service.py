from decimal import Decimal


class StockValidationError(ValueError):
    pass


def apply_stock_movement(
    current_stock: Decimal, movement_qty: Decimal, allow_negative: bool = False
) -> Decimal:
    new_stock = current_stock + movement_qty
    if not allow_negative and new_stock < Decimal("0"):
        raise StockValidationError("Negative stock is not allowed")
    return new_stock


def validate_document_is_posted(document_status: str) -> None:
    if document_status.strip().lower() != "posted":
        raise StockValidationError(
            "Inventory can be updated only when a document is posted"
        )

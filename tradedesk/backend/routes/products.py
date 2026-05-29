from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.inventory import (ProductCreate, ProductRead, ProductUpdate,
                                 StockLedgerResponse, StockMovementCreate,
                                 StockMovementRead)
from ..services.inventory_service import StockValidationError
from ..services.product_service import ProductService

router = APIRouter()


def _movement_to_read(item) -> StockMovementRead:
    return StockMovementRead(
        id=item.id,
        product_id=item.product_id,
        movement_date=item.movement_date,
        movement_type=item.movement_type.value,
        quantity_in=item.quantity_in,
        quantity_out=item.quantity_out,
        balance_qty=item.balance_qty,
        unit_cost=item.unit_cost,
        total_cost=item.total_cost,
        document_type=item.document_type,
        document_no=item.document_no,
        document_status=item.document_status,
        remarks=item.remarks,
    )


@router.get("", response_model=list[ProductRead])
async def list_products(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin",
            "admin",
            "inventory_manager",
            "viewer",
            "sales_manager",
            "purchase_manager",
        )
    ),
) -> list[ProductRead]:
    rows = await ProductService(db).list_products()
    return [ProductRead.model_validate(item) for item in rows]


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "inventory_manager")),
) -> ProductRead:
    created = await ProductService(db).create_product(payload)
    return ProductRead.model_validate(created)


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "inventory_manager")),
) -> ProductRead:
    service = ProductService(db)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    updated = await service.update_product(product, payload)
    return ProductRead.model_validate(updated)


@router.post(
    "/movements", response_model=StockMovementRead, status_code=status.HTTP_201_CREATED
)
async def create_stock_movement(
    payload: StockMovementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "inventory_manager")),
) -> StockMovementRead:
    service = ProductService(db)
    try:
        movement = await service.create_stock_movement(payload, created_by=user.id)
    except StockValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _movement_to_read(movement)


@router.get("/{product_id}/ledger", response_model=StockLedgerResponse)
async def product_stock_ledger(
    product_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin",
            "admin",
            "inventory_manager",
            "viewer",
            "sales_manager",
            "purchase_manager",
        )
    ),
) -> StockLedgerResponse:
    product, entries = await ProductService(db).stock_ledger(product_id, limit=limit)
    return StockLedgerResponse(
        product_id=product.id,
        current_stock=product.current_stock,
        entries=[_movement_to_read(item) for item in entries],
    )

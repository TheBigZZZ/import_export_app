from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.purchase_ops import (PurchaseOrderCreate, PurchaseOrderRead,
                                    PurchasePostResponse)
from ..services.purchase_service import PurchaseService

router = APIRouter()


@router.get("", response_model=list[PurchaseOrderRead])
async def list_purchases(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "purchase_manager", "accounts_manager", "viewer"
        )
    ),
) -> list[PurchaseOrderRead]:
    return await PurchaseService(db).list_orders()


@router.post("", response_model=PurchaseOrderRead)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("super_admin", "admin", "purchase_manager")),
) -> PurchaseOrderRead:
    return await PurchaseService(db).create_order(payload, created_by=user.id)


@router.post("/{order_id}/post", response_model=PurchasePostResponse)
async def post_purchase_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles("super_admin", "admin", "purchase_manager", "accounts_manager")
    ),
) -> PurchasePostResponse:
    return await PurchaseService(db).post_order(order_id, user_id=user.id)

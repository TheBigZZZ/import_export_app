from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.import_ops import (ImportPostResponse, ImportShipmentCreate,
                                  ImportShipmentRead)
from ..services.import_service import ImportService

router = APIRouter()


@router.get("", response_model=list[ImportShipmentRead])
async def list_import_shipments(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin",
            "admin",
            "purchase_manager",
            "inventory_manager",
            "accounts_manager",
            "viewer",
        )
    ),
) -> list[ImportShipmentRead]:
    return await ImportService(db).list_shipments()


@router.post("", response_model=ImportShipmentRead)
async def create_import_shipment(
    payload: ImportShipmentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles("super_admin", "admin", "purchase_manager", "inventory_manager")
    ),
) -> ImportShipmentRead:
    return await ImportService(db).create_shipment(payload, created_by=user.id)


@router.post("/{shipment_id}/post", response_model=ImportPostResponse)
async def post_import_shipment(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(
        require_roles(
            "super_admin",
            "admin",
            "purchase_manager",
            "inventory_manager",
            "accounts_manager",
        )
    ),
) -> ImportPostResponse:
    return await ImportService(db).post_shipment(shipment_id, user_id=user.id)

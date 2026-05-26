from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..schemas.party import PartyLedgerResponse, SupplierCreate, SupplierRead, SupplierUpdate
from ..services.supplier_service import SupplierService

router = APIRouter()


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "viewer", "purchase_manager")),
) -> list[SupplierRead]:
	rows = await SupplierService(db).list_suppliers()
	return [SupplierRead.model_validate(item) for item in rows]


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
	payload: SupplierCreate,
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "purchase_manager")),
) -> SupplierRead:
	created = await SupplierService(db).create_supplier(payload)
	return SupplierRead.model_validate(created)


@router.put("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
	supplier_id: int,
	payload: SupplierUpdate,
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "purchase_manager")),
) -> SupplierRead:
	service = SupplierService(db)
	supplier = await service.get_supplier(supplier_id)
	if not supplier:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
	updated = await service.update_supplier(supplier, payload)
	return SupplierRead.model_validate(updated)


@router.get("/{supplier_id}/ledger", response_model=PartyLedgerResponse)
async def supplier_ledger(
	supplier_id: int,
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "viewer", "purchase_manager")),
) -> PartyLedgerResponse:
	return await SupplierService(db).ledger(supplier_id)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
	supplier_id: int,
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "purchase_manager")),
) -> None:
	service = SupplierService(db)
	supplier = await service.get_supplier(supplier_id)
	if not supplier:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
	await service.delete_supplier(supplier)
	return None


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_suppliers(
	payload: list[int],
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "purchase_manager")),
) -> dict:
	service = SupplierService(db)
	failed = await service.bulk_delete_suppliers(payload)
	return {"failed": failed}

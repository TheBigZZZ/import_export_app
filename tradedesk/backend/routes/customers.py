from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..schemas.party import (CustomerCreate, CustomerRead, CustomerUpdate,
                             PartyLedgerResponse)
from ..services.customer_service import CustomerService

router = APIRouter()


@router.get("", response_model=list[CustomerRead])
async def list_customers(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "sales_manager"
        )
    ),
) -> list[CustomerRead]:
    rows = await CustomerService(db).list_customers()
    return [CustomerRead.model_validate(item) for item in rows]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "sales_manager")
    ),
) -> CustomerRead:
    created = await CustomerService(db).create_customer(payload)
    return CustomerRead.model_validate(created)


@router.put("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "sales_manager")
    ),
) -> CustomerRead:
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )
    updated = await service.update_customer(customer, payload)
    return CustomerRead.model_validate(updated)


@router.get("/{customer_id}/ledger", response_model=PartyLedgerResponse)
async def customer_ledger(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "sales_manager"
        )
    ),
) -> PartyLedgerResponse:
    return await CustomerService(db).ledger(customer_id)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> None:
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )
    await service.delete_customer(customer)
    return None


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_customers(
    payload: list[int],
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> dict:
    service = CustomerService(db)
    failed = await service.bulk_delete_customers(payload)
    return {"failed": failed}

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..schemas.accounting import (AccountCreate, AccountRead, AccountTreeNode,
                                  AccountUpdate, LedgerResponse)
from ..services.account_service import AccountService

router = APIRouter()


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "inventory_manager"
        )
    ),
) -> list[AccountRead]:
    accounts = await AccountService(db).list_accounts()
    return [
        AccountRead(
            id=item.id,
            account_code=item.account_code,
            account_name=item.account_name,
            account_type=item.account_type.value,
            parent_id=item.parent_id,
            is_system=item.is_system,
            created_at=item.created_at,
        )
        for item in accounts
    ]


@router.get("/tree", response_model=list[AccountTreeNode])
async def account_tree(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles(
            "super_admin", "admin", "accounts_manager", "viewer", "inventory_manager"
        )
    ),
) -> list[AccountTreeNode]:
    return await AccountService(db).get_tree()


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> AccountRead:
    created = await AccountService(db).create_account(payload)
    return AccountRead(
        id=created.id,
        account_code=created.account_code,
        account_name=created.account_name,
        account_type=created.account_type.value,
        parent_id=created.parent_id,
        is_system=created.is_system,
        created_at=created.created_at,
    )


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> AccountRead:
    service = AccountService(db)
    account = await service.get_account(account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if account.is_system and payload.account_type is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System account type cannot be changed",
        )
    updated = await service.update_account(account, payload)
    return AccountRead(
        id=updated.id,
        account_code=updated.account_code,
        account_name=updated.account_name,
        account_type=updated.account_type.value,
        parent_id=updated.parent_id,
        is_system=updated.is_system,
        created_at=updated.created_at,
    )


@router.get("/{account_id}/ledger", response_model=LedgerResponse)
async def account_ledger(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(
        require_roles("super_admin", "admin", "accounts_manager", "viewer")
    ),
) -> LedgerResponse:
    return await AccountService(db).ledger(account_id)

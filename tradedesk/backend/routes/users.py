from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.user import UserCreate, UserListResponse, UserRead, UserUpdate
from ..services.user_service import UserService

router = APIRouter()


@router.get("", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin")),
) -> UserListResponse:
    # Honor enable_user_module flag
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    users = await UserService(db).list_users()
    return UserListResponse(
        items=[UserRead.model_validate(user) for user in users], total=len(users)
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin")),
) -> UserRead:
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    service = UserService(db)
    existing = await service.get_by_username(payload.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        )
    try:
        user = await service.create_user(payload)
    except RuntimeError as exc:
        # Translate service-level max-users error to HTTP 409 Conflict
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin")),
) -> UserRead:
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    user = await UserService(db).get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserRead.model_validate(user)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin")),
) -> UserRead:
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    updated = await service.update_user(user, payload)
    return UserRead.model_validate(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("super_admin")),
) -> None:
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await service.update_user(user, UserUpdate(is_active=False))
    return None


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_users(
    payload: list[int],
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin")),
) -> dict:
    service = UserService(db)
    failed = await service.bulk_delete_users(payload)
    return {"failed": failed}


@router.get("/count")
async def user_count(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles("super_admin")),
) -> dict:
    """Return the current user count for super-admin dashboards."""
    from ..config import settings

    if not settings.enable_user_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User module disabled"
        )
    stmt = select(User)
    result = await db.execute(stmt)
    count = len(result.scalars().all())
    return {"count": count}

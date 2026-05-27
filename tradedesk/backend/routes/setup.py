from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.user_service import UserService
from ..schemas.user import UserCreate, UserRead

router = APIRouter()


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)) -> dict[str, int | bool]:
    service = UserService(db)
    users = await service.list_users()
    return {"needs_initial_admin": len(users) == 0, "user_count": len(users)}


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_initial_admin(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create the initial administrator account. This endpoint is only allowed when
    no users exist in the database. Subsequent calls will be rejected.
    """
    svc = UserService(db)
    users = await svc.list_users()
    if users:
        raise HTTPException(status_code=400, detail="Initial setup has already been completed")

    # Force role to super_admin to ensure initial user has full privileges
    payload.role = "super_admin"
    user = await svc.create_user(payload)
    return user

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..schemas.auth import LoginRequest, TokenPair, TokenRefreshRequest
from ..schemas.user import UserRead
from ..services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await AuthService(db).login(payload)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: TokenRefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenPair:
    return await AuthService(db).refresh(payload.refresh_token)


@router.post("/logout")
async def logout() -> dict[str, str]:
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)

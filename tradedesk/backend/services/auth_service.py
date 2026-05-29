from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..schemas.auth import LoginRequest, TokenPair
from ..security import (create_access_token, create_refresh_token,
                        decode_token, verify_password)
from .user_service import UserService


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserService(db)

    async def login(self, payload: LoginRequest) -> TokenPair:
        user = await self.users.get_by_username(payload.username)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        if user.locked_until:
            locked_until_dt = user.locked_until
            if locked_until_dt.tzinfo is None:
                locked_until_dt = locked_until_dt.replace(tzinfo=UTC)
            else:
                locked_until_dt = locked_until_dt.astimezone(UTC)

            if locked_until_dt > datetime.now(UTC):
                locked_until = locked_until_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account is temporarily locked until {locked_until}.",
                )

        if not verify_password(payload.password, user.password_hash):
            await self.users.register_failed_login(
                user,
                limit=settings.failed_login_limit,
                lock_minutes=settings.lock_minutes,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        await self.users.clear_failed_logins(user)

        access_token = create_access_token(
            subject=user.username, extra={"role": user.role, "uid": user.id}
        )
        refresh_token = create_refresh_token(
            subject=user.username, extra={"role": user.role, "uid": user.id}
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject"
            )

        user = await self.users.get_by_username(username)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable"
            )

        access = create_access_token(
            subject=user.username, extra={"role": user.role, "uid": user.id}
        )
        new_refresh = create_refresh_token(
            subject=user.username, extra={"role": user.role, "uid": user.id}
        )
        return TokenPair(access_token=access, refresh_token=new_refresh)

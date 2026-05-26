from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate
from ..security import hash_password


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.id.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_user(self, payload: UserCreate) -> User:
        # Enforce max users from configuration
        from ..config import settings
        stmt = select(User)
        result = await self.db.execute(stmt)
        current_count = len(result.scalars().all())
        if settings.max_users and current_count >= settings.max_users:
            raise RuntimeError(f"Maximum number of users ({settings.max_users}) reached")

        user = User(
            full_name=payload.full_name,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user: User, payload: UserUpdate) -> User:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def reset_password(self, user: User, raw_password: str) -> User:
        user.password_hash = hash_password(raw_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def register_failed_login(self, user: User, limit: int, lock_minutes: int) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= limit:
            user.locked_until = datetime.now(UTC).replace(microsecond=0)
            user.locked_until = user.locked_until + timedelta(minutes=lock_minutes)
        await self.db.commit()

    async def clear_failed_logins(self, user: User) -> None:
        if user.failed_login_attempts or user.locked_until:
            user.failed_login_attempts = 0
            user.locked_until = None
            await self.db.commit()

    async def bulk_delete_users(self, ids: list[int]) -> list[int]:
        from sqlalchemy import delete
        failed: list[int] = []
        try:
            stmt = delete(User).where(User.id.in_(ids))
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            for uid in ids:
                try:
                    user = await self.get_by_id(uid)
                    if user:
                        await self.db.delete(user)
                        await self.db.commit()
                    else:
                        failed.append(uid)
                except Exception:
                    failed.append(uid)
        return failed

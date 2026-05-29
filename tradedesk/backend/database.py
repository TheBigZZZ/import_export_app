from collections.abc import AsyncGenerator

import aiosqlite  # noqa: F401 - ensure PyInstaller includes the async SQLite driver

from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase

from .config import ensure_runtime_dirs, settings

ensure_runtime_dirs()

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

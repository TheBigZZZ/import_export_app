import sys
import os
from pathlib import Path

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tradedesk.backend.bootstrap import DEFAULT_ACCOUNTS
from tradedesk.backend.config import settings
from tradedesk.backend.database import Base, get_db
from tradedesk.backend.models.account import ChartOfAccount
from tradedesk.backend.models.user import User
from tradedesk.backend.security import hash_password


@pytest_asyncio.fixture
async def integration_client(tmp_path: Path):
    db_path = tmp_path / "integration.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    original = {
        "base_dir": settings.base_dir,
        "data_dir": settings.data_dir,
        "backup_dir": settings.backup_dir,
        "logs_dir": settings.logs_dir,
        "db_file_name": settings.db_file_name,
    }

    settings.base_dir = tmp_path
    settings.data_dir = tmp_path
    settings.backup_dir = backup_dir
    settings.logs_dir = tmp_path / "logs"
    settings.db_file_name = db_path.name

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        admin = User(
            full_name="Integration Admin",
            username="admin",
            email=None,
            # Use environment-driven test admin password when set, otherwise use a safe default for local tests
            password_hash=hash_password(
                os.environ.get("TRADEDESK_TEST_ADMIN_PASS", "TestPassw0rd!")
            ),
            role="super_admin",
            is_active=True,
        )
        session.add(admin)
        for code, name, account_type in DEFAULT_ACCOUNTS:
            session.add(
                ChartOfAccount(
                    account_code=code,
                    account_name=name,
                    account_type=account_type,
                    parent_id=None,
                    is_system=True,
                )
            )
        await session.commit()

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    # Attach override for FastAPI dependencies so tests hit the temp DB
    from tradedesk.backend.main import app  # local import to avoid import cycles

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()

    settings.base_dir = original["base_dir"]
    settings.data_dir = original["data_dir"]
    settings.backup_dir = original["backup_dir"]
    settings.logs_dir = original["logs_dir"]
    settings.db_file_name = original["db_file_name"]


async def _auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    # Use the same test password as the fixture (env var overrides default)
    test_pass = os.environ.get("TRADEDESK_TEST_ADMIN_PASS", "TestPassw0rd!")
    response = await client.post(
        "/api/auth/login", json={"username": "admin", "password": test_pass}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _find_account_id(
    client: httpx.AsyncClient, headers: dict[str, str], account_code: str
) -> int:
    response = await client.get("/api/accounts", headers=headers)
    assert response.status_code == 200
    for account in response.json():
        if account["account_code"] == account_code:
            return account["id"]
    raise AssertionError(f"Account code {account_code} not found")

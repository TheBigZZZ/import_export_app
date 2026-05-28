from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tradedesk.backend.main import app
from tradedesk.backend.database import Base, get_db
from tradedesk.backend.security import hash_password
from tradedesk.backend.models.user import User


@pytest_asyncio.fixture
async def empty_db_client(tmp_path: Path):
    db_path = tmp_path / "setup.db"

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_setup_status_and_create_initial_admin(empty_db_client: httpx.AsyncClient) -> None:
    # No users initially
    resp = await empty_db_client.get("/api/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_initial_admin"] is True
    assert body["user_count"] == 0

    payload = {
        "full_name": "First Admin",
        "username": "owner",
        "email": "owner@example.com",
        "password": "S3cureP@ss!",
        "role": "super_admin",
    }

    create = await empty_db_client.post("/api/setup", json=payload)
    assert create.status_code == 201
    created = create.json()
    assert created["username"] == "owner"
    assert created["role"] == "super_admin"

    # Now status shows setup complete
    resp2 = await empty_db_client.get("/api/setup/status")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["needs_initial_admin"] is False
    assert body2["user_count"] == 1

    # Attempting to create again should fail
    retry = await empty_db_client.post("/api/setup", json=payload)
    assert retry.status_code == 400


@pytest.mark.asyncio
async def test_login_with_created_admin(empty_db_client: httpx.AsyncClient) -> None:
    # Create the initial admin first
    payload = {
        "full_name": "First Admin",
        "username": "owner2",
        "email": "owner2@example.com",
        "password": "An0ther$Pass",
        "role": "super_admin",
    }
    create = await empty_db_client.post("/api/setup", json=payload)
    assert create.status_code == 201

    # Login
    login = await empty_db_client.post("/api/auth/login", json={"username": "owner2", "password": "An0ther$Pass"})
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    # Use token to call /api/auth/me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = await empty_db_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    user = me.json()
    assert user["username"] == "owner2"
    assert user["role"] == "super_admin"

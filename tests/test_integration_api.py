from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tradedesk.backend.bootstrap import DEFAULT_ACCOUNTS
from tradedesk.backend.config import settings
from tradedesk.backend.database import Base, get_db
from tradedesk.backend.live import LiveEvent, broadcast_live_event, broker
from tradedesk.backend.main import app
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


@pytest.mark.asyncio
async def test_sales_purchase_posting_and_reports_flow(
    integration_client: httpx.AsyncClient,
) -> None:
    headers = await _auth_headers(integration_client)

    customer_response = await integration_client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "C001",
            "customer_name": "Retail Customer",
            "opening_balance": "0.00",
        },
    )
    assert customer_response.status_code == 201
    customer_id = customer_response.json()["id"]

    supplier_response = await integration_client.post(
        "/api/suppliers",
        headers=headers,
        json={
            "supplier_code": "S001",
            "supplier_name": "Global Supplier",
            "opening_balance": "0.00",
        },
    )
    assert supplier_response.status_code == 201
    supplier_id = supplier_response.json()["id"]

    product_response = await integration_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_code": "P001",
            "product_name": "Test Item",
            "unit": "pcs",
            "purchase_price": "5.00",
            "selling_price": "9.00",
            "reorder_level": "2.0000",
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    purchase_create = await integration_client.post(
        "/api/purchases",
        headers=headers,
        json={
            "po_no": "PO-INT-001",
            "supplier_id": supplier_id,
            "order_date": "2026-05-25",
            "items": [
                {"product_id": product_id, "quantity": "10", "unit_price": "5.00"}
            ],
        },
    )
    assert purchase_create.status_code == 200
    purchase_id = purchase_create.json()["id"]

    purchase_post = await integration_client.post(
        f"/api/purchases/{purchase_id}/post", headers=headers, json={}
    )
    assert purchase_post.status_code == 200
    assert purchase_post.json()["status"] == "received"

    sales_create = await integration_client.post(
        "/api/sales",
        headers=headers,
        json={
            "invoice_no": "INV-INT-001",
            "customer_id": customer_id,
            "invoice_date": "2026-05-25",
            "items": [
                {
                    "product_id": product_id,
                    "quantity": "3",
                    "unit_price": "9.00",
                    "cost_price": "5.00",
                }
            ],
        },
    )
    assert sales_create.status_code == 200
    invoice_id = sales_create.json()["id"]

    sales_post = await integration_client.post(
        f"/api/sales/{invoice_id}/post", headers=headers, json={}
    )
    assert sales_post.status_code == 200
    assert sales_post.json()["status"] == "issued"

    stock_ledger = await integration_client.get(
        f"/api/products/{product_id}/ledger", headers=headers
    )
    assert stock_ledger.status_code == 200
    assert Decimal(stock_ledger.json()["current_stock"]) == Decimal("7.0000")

    trial_balance = await integration_client.get(
        "/api/reports/trial-balance", headers=headers
    )
    assert trial_balance.status_code == 200
    assert trial_balance.json()["is_balanced"] is True

    dashboard = await integration_client.get("/api/reports/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert Decimal(dashboard.json()["sales_month"]) > Decimal("0")


@pytest.mark.asyncio
async def test_settings_and_backup_endpoints(
    integration_client: httpx.AsyncClient,
) -> None:
    headers = await _auth_headers(integration_client)

    update_response = await integration_client.put(
        "/api/settings",
        headers=headers,
        json={
            "company_name": "TradeDesk Integration",
            "company_address": "Dhaka",
            "company_phone": "01700000000",
            "company_email": "ops@example.com",
            "allow_negative_stock": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["allow_negative_stock"] is True

    backup_response = await integration_client.post(
        "/api/settings/backups", headers=headers, json={}
    )
    assert backup_response.status_code == 201
    backup_name = backup_response.json()["backup"]["file_name"]

    backup_list = await integration_client.get("/api/settings/backups", headers=headers)
    assert backup_list.status_code == 200
    assert any(item["file_name"] == backup_name for item in backup_list.json())


@pytest.mark.asyncio
async def test_negative_stock_guard_obeys_settings(
    integration_client: httpx.AsyncClient,
) -> None:
    headers = await _auth_headers(integration_client)

    product_response = await integration_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_code": "P-NEG-1",
            "product_name": "Negative Test Item",
            "unit": "pcs",
            "purchase_price": "1.00",
            "selling_price": "2.00",
        },
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    out_movement_denied = await integration_client.post(
        "/api/products/movements",
        headers=headers,
        json={
            "product_id": product_id,
            "movement_type": "out",
            "quantity": "1",
            "movement_date": "2026-05-25",
            "unit_cost": "1.00",
            "document_status": "posted",
            "allow_negative": False,
        },
    )
    assert out_movement_denied.status_code == 400

    settings_update = await integration_client.put(
        "/api/settings",
        headers=headers,
        json={
            "company_name": "TradeDesk Integration",
            "company_address": None,
            "company_phone": None,
            "company_email": None,
            "allow_negative_stock": True,
        },
    )
    assert settings_update.status_code == 200

    out_movement_allowed = await integration_client.post(
        "/api/products/movements",
        headers=headers,
        json={
            "product_id": product_id,
            "movement_type": "out",
            "quantity": "1",
            "movement_date": "2026-05-25",
            "unit_cost": "1.00",
            "document_status": "posted",
            "allow_negative": False,
        },
    )
    assert out_movement_allowed.status_code == 201

    office_expense_account_id = await _find_account_id(
        integration_client, headers, "5100"
    )
    expense_response = await integration_client.post(
        "/api/expenses",
        headers=headers,
        json={
            "expense_no": "EXP-INT-001",
            "expense_date": "2026-05-25",
            "account_id": office_expense_account_id,
            "amount": "500.00",
            "payment_method": "cash",
            "description": "Office utilities",
        },
    )
    assert expense_response.status_code == 201
    assert expense_response.json()["voucher_no"].startswith("CPV-")


@pytest.mark.asyncio
async def test_live_broker_delivers_change_events() -> None:
    queue = await broker.subscribe()
    try:
        broadcast_live_event(
            LiveEvent(
                event_type="entity.changed",
                table_name="customers",
                action="insert",
                record_id=123,
                user_id=1,
            )
        )

        event = await asyncio.wait_for(queue.get(), timeout=5.0)
        assert event is not None
        assert event.event_type == "entity.changed"
        assert event.table_name == "customers"
        assert event.action == "insert"
        assert event.record_id == 123
    finally:
        await broker.unsubscribe(queue)


@pytest.mark.asyncio
async def test_live_events_endpoint_requires_auth(
    integration_client: httpx.AsyncClient,
) -> None:
    response = await integration_client.get("/api/live/events")
    assert response.status_code == 403

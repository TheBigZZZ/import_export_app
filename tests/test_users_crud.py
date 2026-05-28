from __future__ import annotations

import pytest

from tests.test_integration_api import integration_client, _auth_headers


@pytest.mark.asyncio
async def test_users_crud_and_roles(integration_client) -> None:
    headers = await _auth_headers(integration_client)

    # Create a new user (admin can create users)
    payload = {
        "full_name": "Worker",
        "username": "worker1",
        "email": "worker@example.com",
        "password": "WorkerPass1$",
        "role": "user",
    }
    create = await integration_client.post("/api/users", headers=headers, json=payload)
    assert create.status_code == 201
    user = create.json()
    user_id = user["id"]

    # Fetch user
    fetch = await integration_client.get(f"/api/users/{user_id}", headers=headers)
    assert fetch.status_code == 200
    assert fetch.json()["username"] == "worker1"

    # Update user role (admin can update)
    upd = await integration_client.put(f"/api/users/{user_id}", headers=headers, json={"role": "manager"})
    assert upd.status_code == 200
    assert upd.json()["role"] == "manager"

    # Delete user (204 No Content expected)
    delete = await integration_client.delete(f"/api/users/{user_id}", headers=headers)
    assert delete.status_code == 204

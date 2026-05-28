from __future__ import annotations

import pytest

from tests.test_integration_api import integration_client


@pytest.mark.asyncio
async def test_token_refresh_cycle(integration_client) -> None:
    # Login as the seeded admin in the integration fixture
    resp = await integration_client.post("/api/auth/login", json={"username": "admin", "password": "TestPassw0rd!"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    # Use refresh endpoint
    refresh = await integration_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    new = refresh.json()
    assert new.get("access_token") and new.get("refresh_token")

    # Old refresh token should no longer work if the backend rotates tokens
    # This depends on implementation; at minimum ensure refresh returns tokens

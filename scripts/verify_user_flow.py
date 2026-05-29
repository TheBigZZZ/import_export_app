import sys
import time

import httpx

BASE = "http://127.0.0.1:8742"
ADMIN_USER = "admin"
ADMIN_PASS = "TestP@ssw0rd!"

try:
    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            f"{BASE}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            auth=None,
        )
        print("login status", r.status_code)
        if r.status_code != 200:
            print("Login failed:", r.text)
            sys.exit(1)
        tokens = r.json()
        access = tokens.get("access_token")
        headers = {"Authorization": f"Bearer {access}"}

        # create user
        uname = f"testuser_{int(time.time())}"
        payload = {
            "username": uname,
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "password123",
            "role": "viewer",
        }
        r2 = client.post(f"{BASE}/api/users", json=payload, headers=headers)
        print("create status", r2.status_code, r2.text)
        if r2.status_code not in (200, 201):
            sys.exit(2)
        uid = r2.json().get("id")
        print("created id", uid)

        # delete user
        r3 = client.delete(f"{BASE}/api/users/{uid}", headers=headers)
        print("delete status", r3.status_code, r3.text)
        if r3.status_code in (200, 204):
            print("Delete OK")
            sys.exit(0)
        else:
            print("Delete failed")
            sys.exit(3)
except Exception as e:
    print("ERR", e)
    sys.exit(4)

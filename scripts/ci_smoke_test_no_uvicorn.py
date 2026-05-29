import sys
import time
import uuid

import requests

BASE = "http://127.0.0.1:8742"


def wait_for_health(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"{BASE}/health", timeout=3)
            if r.ok and r.json().get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    run_id = uuid.uuid4().hex[:8]

    if not wait_for_health(60):
        print("Health endpoint did not become ready")
        sys.exit(2)
    print("Health OK")

    import os

    admin_user = os.environ.get("TRADEDESK_TEST_ADMIN_USER")
    admin_pass = os.environ.get("TRADEDESK_TEST_ADMIN_PASS")
    if not admin_user or not admin_pass:
        print(
            "Set TRADEDESK_TEST_ADMIN_USER and TRADEDESK_TEST_ADMIN_PASS in the environment for CI smoke tests"
        )
        sys.exit(2)

    login = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": admin_user, "password": admin_pass},
        timeout=10,
    )
    if login.status_code == 401:
        # Try creating initial admin
        try:
            setup_resp = requests.post(
                f"{BASE}/api/setup",
                json={
                    "full_name": "CI Admin",
                    "username": admin_user,
                    "email": None,
                    "password": admin_pass,
                    "role": "super_admin",
                },
                timeout=10,
            )
            if setup_resp.status_code in (200, 201):
                print("Initial admin created via /api/setup")
            else:
                print(
                    "Setup endpoint did not create admin:",
                    setup_resp.status_code,
                    setup_resp.text,
                )
        except Exception:
            pass
        login = requests.post(
            f"{BASE}/api/auth/login",
            json={"username": admin_user, "password": admin_pass},
            timeout=10,
        )

    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cust = requests.post(
        f"{BASE}/api/customers",
        json={"customer_code": f"CI-CUST-{run_id}", "customer_name": "CI Customer"},
        headers=headers,
        timeout=10,
    )
    cust.raise_for_status()
    cust_id = cust.json()["id"]
    print("Customer created", cust_id)

    prod = requests.post(
        f"{BASE}/api/products",
        json={
            "product_code": f"CI-PROD-{run_id}",
            "product_name": "CI Product",
            "unit": "pcs",
            "purchase_price": 5.0,
            "selling_price": 8.0,
        },
        headers=headers,
        timeout=10,
    )
    prod.raise_for_status()
    prod_id = prod.json()["id"]
    print("Product created", prod_id)

    accounts = requests.get(f"{BASE}/api/accounts", headers=headers, timeout=10).json()
    if len(accounts) < 2:
        print("Not enough accounts")
        sys.exit(3)
    debit = accounts[0]["id"]
    credit = accounts[1]["id"]

    today = time.strftime("%Y-%m-%d")
    voucher = {
        "voucher_type": "JV",
        "transaction_date": today,
        "description": "CI smoke test",
        "lines": [
            {"account_id": debit, "debit": 50.0, "credit": 0.0},
            {"account_id": credit, "debit": 0.0, "credit": 50.0},
        ],
    }
    r = requests.post(f"{BASE}/api/vouchers", json=voucher, headers=headers, timeout=20)
    r.raise_for_status()
    print("Voucher posted")

    mov = requests.post(
        f"{BASE}/api/products/movements",
        json={
            "product_id": prod_id,
            "movement_type": "in",
            "quantity": 10,
            "movement_date": today,
            "unit_cost": 5.0,
            "document_status": "posted",
        },
        headers=headers,
        timeout=10,
    )
    mov.raise_for_status()
    print("Stock movement created")

    print("CI smoke test PASSED")


if __name__ == "__main__":
    main()

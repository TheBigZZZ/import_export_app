import sys
import json
import httpx

BASE = "http://127.0.0.1:8742"

def login(username: str, password: str):
    with httpx.Client(base_url=BASE, timeout=10.0) as client:
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        r.raise_for_status()
        return r.json()


def create_customer(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"customer_code": "TSTCUST", "customer_name": "UI Test Customer", "opening_balance": "0.00"}
    with httpx.Client(base_url=BASE, timeout=10.0, headers=headers) as client:
        r = client.post("/api/customers", json=payload)
        print("Create customer:", r.status_code, r.text)
        return r


def create_supplier(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"supplier_code": "TSTSUPP", "supplier_name": "UI Test Supplier", "opening_balance": "0.00"}
    with httpx.Client(base_url=BASE, timeout=10.0, headers=headers) as client:
        r = client.post("/api/suppliers", json=payload)
        print("Create supplier:", r.status_code, r.text)
        return r


def create_user(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"username": "testui", "full_name": "UI Test User", "password": "UserP@ssw0rd!", "role": "viewer"}
    with httpx.Client(base_url=BASE, timeout=10.0, headers=headers) as client:
        r = client.post("/api/users", json=payload)
        print("Create user:", r.status_code, r.text)
        if r.status_code == 201:
            return r.json().get("id")
        return None


def delete_user(token: str, user_id: int):
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE, timeout=10.0, headers=headers) as client:
        r = client.delete(f"/api/users/{user_id}")
        print("Delete user:", r.status_code, r.text)
        return r


def main():
    try:
        creds = login("admin", "TestP@ssw0rd!")
    except Exception as exc:
        print("Login failed:", exc)
        sys.exit(2)

    token = creds.get("access_token")
    create_customer(token)
    create_supplier(token)
    uid = create_user(token)
    if uid:
        delete_user(token, uid)

    print("UI exercise script completed.")


if __name__ == "__main__":
    main()

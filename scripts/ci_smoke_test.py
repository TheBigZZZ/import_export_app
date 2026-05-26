import subprocess
import sys
import time
import requests
from pathlib import Path
import uuid

BASE = 'http://127.0.0.1:8742'


def wait_for_health(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f'{BASE}/health', timeout=3)
            if r.ok and r.json().get('status') == 'ok':
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    run_id = uuid.uuid4().hex[:8]
    # Start backend via uvicorn
    uvicorn_cmd = [sys.executable, '-m', 'uvicorn', 'tradedesk.backend.main:app', '--host', '127.0.0.1', '--port', '8742', '--no-access-log']
    proc = subprocess.Popen(uvicorn_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not wait_for_health(60):
            print('Health endpoint did not become ready')
            proc.kill()
            sys.exit(2)
        print('Health OK')

        # Login - admin credentials should be provided via environment variables in CI
        import os
        admin_user = os.environ.get('TRADEDESK_TEST_ADMIN_USER')
        admin_pass = os.environ.get('TRADEDESK_TEST_ADMIN_PASS')
        if not admin_user or not admin_pass:
            print('Set TRADEDESK_TEST_ADMIN_USER and TRADEDESK_TEST_ADMIN_PASS in the environment for CI smoke tests')
            proc.kill()
            sys.exit(2)

        # Try to login; if login fails and the setup endpoint is available, attempt
        # to create the initial admin account (useful for fresh databases in CI).
        login = requests.post(f'{BASE}/api/auth/login', json={'username': admin_user, 'password': admin_pass}, timeout=10)
        if login.status_code == 401:
            # Try creating initial admin if setup endpoint is reachable
            try:
                setup_resp = requests.post(f'{BASE}/api/setup', json={'full_name': 'CI Admin', 'username': admin_user, 'email': None, 'password': admin_pass, 'role': 'super_admin'}, timeout=10)
                if setup_resp.status_code in (200, 201):
                    print('Initial admin created via /api/setup')
                else:
                    print('Setup endpoint did not create admin:', setup_resp.status_code, setup_resp.text)
            except Exception:
                pass
            # Retry login
            login = requests.post(f'{BASE}/api/auth/login', json={'username': admin_user, 'password': admin_pass}, timeout=10)

        login.raise_for_status()
        token = login.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        # Create customer
        cust = requests.post(f'{BASE}/api/customers', json={'customer_code': f'CI-CUST-{run_id}', 'customer_name': 'CI Customer'}, headers=headers, timeout=10)
        cust.raise_for_status()
        cust_id = cust.json()['id']
        print('Customer created', cust_id)

        # Create product
        prod = requests.post(f'{BASE}/api/products', json={'product_code': f'CI-PROD-{run_id}', 'product_name': 'CI Product', 'unit': 'pcs', 'purchase_price': 5.0, 'selling_price': 8.0}, headers=headers, timeout=10)
        prod.raise_for_status()
        prod_id = prod.json()['id']
        print('Product created', prod_id)

        # List accounts
        accounts = requests.get(f'{BASE}/api/accounts', headers=headers, timeout=10).json()
        if len(accounts) < 2:
            print('Not enough accounts')
            sys.exit(3)
        debit = accounts[0]['id']
        credit = accounts[1]['id']

        # Create voucher
        today = time.strftime('%Y-%m-%d')
        voucher = {
            'voucher_type': 'JV',
            'transaction_date': today,
            'description': 'CI smoke test',
            'lines': [
                {'account_id': debit, 'debit': 50.0, 'credit': 0.0},
                {'account_id': credit, 'debit': 0.0, 'credit': 50.0},
            ]
        }
        r = requests.post(f'{BASE}/api/vouchers', json=voucher, headers=headers, timeout=20)
        r.raise_for_status()
        print('Voucher posted')

        # Create stock movement
        mov = requests.post(f'{BASE}/api/products/movements', json={'product_id': prod_id, 'movement_type': 'in', 'quantity': 10, 'movement_date': today, 'unit_cost': 5.0, 'document_status': 'posted'}, headers=headers, timeout=10)
        mov.raise_for_status()
        print('Stock movement created')

        # Backup via CLI
        backup_dir = Path('ci_backups')
        backup_dir.mkdir(exist_ok=True)
        res = subprocess.run([sys.executable, '-m', 'tradedesk.backend.cli', '--backup-db', str(backup_dir)], capture_output=True, text=True)
        print(res.stdout)
        if res.returncode != 0:
            print('Backup command failed', res.stderr)
            sys.exit(4)
        print('Backup completed')

        print('CI smoke test PASSED')
    finally:
        proc.kill()


if __name__ == '__main__':
    main()

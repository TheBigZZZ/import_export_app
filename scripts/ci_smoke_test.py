import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request

BASE = 'http://127.0.0.1:8742'


def http_json(method, url, payload=None, headers=None, timeout=10):
    body = None
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode('utf-8')
            return resp.status, json.loads(text) if text else {}
    except error.HTTPError as exc:
        text = exc.read().decode('utf-8')
        return exc.code, json.loads(text) if text else {}


def wait_for_health(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with request.urlopen(f'{BASE}/health', timeout=3) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
                if payload.get('status') == 'ok':
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    run_id = uuid.uuid4().hex[:8]
    uvicorn_cmd = [
        sys.executable,
        '-m',
        'uvicorn',
        'tradedesk.backend.main:app',
        '--host',
        '127.0.0.1',
        '--port',
        '8742',
        '--no-access-log',
    ]
    proc = subprocess.Popen(uvicorn_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # stream stdout/stderr in background so we can show live logs on failure
        import threading

        stdout_lines = []
        stderr_lines = []

        def _read_stream(stream, collector):
            try:
                for line in iter(stream.readline, ''):
                    if not line:
                        break
                    collector.append(line.rstrip('\n'))
            except Exception:
                pass

        t_out = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_lines), daemon=True)
        t_err = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_lines), daemon=True)
        t_out.start()
        t_err.start()

        if not wait_for_health(90):
            print('Health endpoint did not become ready')
            # if process exited, show exit code
            if proc.poll() is not None:
                print('uvicorn exited with code', proc.returncode)
            # dump collected logs (tail last 400 lines)
            if stdout_lines:
                print('--- uvicorn stdout (tail) ---')
                for ln in stdout_lines[-400:]:
                    print(ln)
            if stderr_lines:
                print('--- uvicorn stderr (tail) ---')
                for ln in stderr_lines[-400:]:
                    print(ln)
            try:
                proc.kill()
            except Exception:
                pass
            sys.exit(2)
        print('Health OK')

        admin_user = os.environ.get('TRADEDESK_TEST_ADMIN_USER')
        admin_pass = os.environ.get('TRADEDESK_TEST_ADMIN_PASS')
        if not admin_user or not admin_pass:
            print('Set TRADEDESK_TEST_ADMIN_USER and TRADEDESK_TEST_ADMIN_PASS in the environment for CI smoke tests')
            proc.kill()
            sys.exit(2)

        status, body = http_json('POST', f'{BASE}/api/auth/login', {'username': admin_user, 'password': admin_pass})
        if status == 401:
            try:
                setup_status, _ = http_json(
                    'POST',
                    f'{BASE}/api/setup',
                    {
                        'full_name': 'CI Admin',
                        'username': admin_user,
                        'email': None,
                        'password': admin_pass,
                        'role': 'super_admin',
                    },
                )
                if setup_status in (200, 201):
                    print('Initial admin created via /api/setup')
                else:
                    print('Setup endpoint did not create admin:', setup_status)
            except Exception:
                pass
            status, body = http_json('POST', f'{BASE}/api/auth/login', {'username': admin_user, 'password': admin_pass})

        if status >= 400:
            print('Login failed', status, body)
            sys.exit(2)

        token = body['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        _, cust_body = http_json(
            'POST',
            f'{BASE}/api/customers',
            {'customer_code': f'CI-CUST-{run_id}', 'customer_name': 'CI Customer'},
            headers=headers,
        )
        cust_id = cust_body['id']
        print('Customer created', cust_id)

        _, prod_body = http_json(
            'POST',
            f'{BASE}/api/products',
            {
                'product_code': f'CI-PROD-{run_id}',
                'product_name': 'CI Product',
                'unit': 'pcs',
                'purchase_price': 5.0,
                'selling_price': 8.0,
            },
            headers=headers,
        )
        prod_id = prod_body['id']
        print('Product created', prod_id)

        _, accounts = http_json('GET', f'{BASE}/api/accounts', headers=headers)
        if len(accounts) < 2:
            print('Not enough accounts')
            sys.exit(3)
        debit = accounts[0]['id']
        credit = accounts[1]['id']

        today = time.strftime('%Y-%m-%d')
        voucher = {
            'voucher_type': 'JV',
            'transaction_date': today,
            'description': 'CI smoke test',
            'lines': [
                {'account_id': debit, 'debit': 50.0, 'credit': 0.0},
                {'account_id': credit, 'debit': 0.0, 'credit': 50.0},
            ],
        }
        status, _ = http_json('POST', f'{BASE}/api/vouchers', voucher, headers=headers, timeout=20)
        if status >= 400:
            print('Voucher post failed', status)
            sys.exit(3)
        print('Voucher posted')

        status, _ = http_json(
            'POST',
            f'{BASE}/api/products/movements',
            {
                'product_id': prod_id,
                'movement_type': 'in',
                'quantity': 10,
                'movement_date': today,
                'unit_cost': 5.0,
                'document_status': 'posted',
            },
            headers=headers,
        )
        if status >= 400:
            print('Stock movement failed', status)
            sys.exit(3)
        print('Stock movement created')

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
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == '__main__':
    main()

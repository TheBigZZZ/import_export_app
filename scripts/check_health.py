import time

import requests


def wait_health(timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get("http://127.0.0.1:8742/health", timeout=1)
            if r.ok and r.json().get("status") == "ok":
                print("Health OK")
                return 0
        except Exception:
            pass
        time.sleep(0.5)
    print("Health failed")
    return 2


if __name__ == "__main__":
    raise SystemExit(wait_health())

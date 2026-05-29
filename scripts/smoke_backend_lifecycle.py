#!/usr/bin/env python3
"""Simple smoke script to exercise backend lifecycle handling.

Starts a minimal HTTP server on the configured backend port, verifies
the health endpoint, then stops the server and demonstrates stop/cleanup.
"""

import http.client
import subprocess
import sys
import time
from pathlib import Path

BACKEND_PORT = 8742
PID_FILE = Path.home() / "TradeDesk" / "backend.pid"


def start_simple_server():
    cmd = [
        sys.executable,
        "-m",
        "http.server",
        str(BACKEND_PORT),
        "--bind",
        "127.0.0.1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except Exception:
        pass
    return proc


def wait_for_http(port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
            conn.request("GET", "/")
            conn.getresponse()
            conn.close()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main() -> int:
    print("Starting simple HTTP server on port", BACKEND_PORT)
    proc = start_simple_server()
    try:
        ok = wait_for_http(BACKEND_PORT, timeout=10.0)
        if not ok:
            print("Server did not respond in time")
            return 2
        print("Server responded OK")

        print("Stopping server PID", proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

        time.sleep(0.2)
        if PID_FILE.exists():
            try:
                print("PID file exists at", PID_FILE)
                PID_FILE.unlink()
                print("PID file removed")
            except Exception as exc:
                print("Failed to remove PID file:", exc)

        print("Smoke lifecycle complete")
        return 0
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

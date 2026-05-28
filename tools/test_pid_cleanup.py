from pathlib import Path
import os
import subprocess
import time
import sys

PID_FILE = Path.home() / "TradeDesk" / "backend.pid"

# Create a stale PID file with an unlikely PID
stale_pid = 999999
PID_FILE.parent.mkdir(parents=True, exist_ok=True)
PID_FILE.write_text(str(stale_pid), encoding="utf-8")
print(f"Wrote stale PID {stale_pid} to {PID_FILE}")

# Replicate the validation logic used in frontend/main.py
raw = PID_FILE.read_text(encoding="utf-8").strip()
try:
    old_pid = int(raw) if raw else 0
except Exception:
    old_pid = 0

if old_pid:
    if os.name == "nt":
        proc = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/FO", "CSV"], capture_output=True, text=True)
        if proc.returncode != 0 or str(old_pid) not in proc.stdout:
            try:
                PID_FILE.unlink()
                print("Stale PID file removed (Windows check).")
            except Exception as e:
                print("Failed to remove PID file:", e)
        else:
            print("PID appears active on Windows; would attempt to terminate.")
    else:
        try:
            os.kill(old_pid, 0)
        except Exception:
            try:
                PID_FILE.unlink()
                print("Stale PID file removed (POSIX check).")
            except Exception as e:
                print("Failed to remove PID file:", e)
        else:
            print("PID appears active on POSIX; would attempt to terminate.")
else:
    try:
        PID_FILE.unlink()
        print("Empty or invalid PID file removed.")
    except Exception as e:
        print("Failed to remove PID file:", e)

print("Done.")

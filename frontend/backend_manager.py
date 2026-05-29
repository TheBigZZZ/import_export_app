from __future__ import annotations

import os
import sys
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Mirror same PID file location as main
PID_FILE = Path.home() / "TradeDesk" / "backend.pid"
BACKEND_PORT = 8742
BACKEND_STARTUP_TIMEOUT_SECONDS = 180
BACKEND_STARTUP_POLL_INTERVAL_SECONDS = 0.5


class BackendManager:
    _instance: "BackendManager" | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: Any | None = None

    def _proc_is_running(self, pid: int) -> bool:
        try:
            if os.name == "nt":
                # On windows, use tasklist
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                    capture_output=True,
                    text=True,
                )
                return str(pid) in proc.stdout
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def start(self, project_root: Path) -> Any | None:
        with self._lock:
            # If we already have a proc object and it's running, return it
            try:
                if self._proc is not None:
                    if hasattr(self._proc, "poll") and self._proc.poll() is None:
                        return self._proc
            except Exception:
                pass

            # If PID file exists and refers to a running PID, assume it's running
            try:
                if PID_FILE.exists():
                    raw = PID_FILE.read_text(encoding="utf-8").strip()
                    if raw:
                        pid = int(raw)
                        if self._proc_is_running(pid):
                            return None
                        else:
                            try:
                                PID_FILE.unlink()
                            except Exception:
                                pass
            except Exception:
                pass

            # Spawn backend process
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                creationflags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)

            # Capture backend stdout/stderr to a rotating temp log to aid debugging
            try:
                tmpdir = Path(tempfile.gettempdir())
                tmpdir.mkdir(parents=True, exist_ok=True)
                log_path = (
                    tmpdir
                    / f"tradedesk-backend-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.log"
                )
                log_file = open(log_path, "a", encoding="utf-8")
            except Exception:
                log_file = None

            # When packaged as a frozen single-file EXE, spawning a separate
            # Python process with the embedded interpreter will fail. In that
            # case, run an embedded Uvicorn server in a background thread so
            # the packaged app can start the backend without external Python.
            proc = None
            try:
                if getattr(sys, "frozen", False):
                    try:
                        import uvicorn
                        # Import the FastAPI app object directly so it runs inside
                        # this process. This avoids spawning a separate Python
                        # interpreter which is not available in onefile frozen builds.
                        from tradedesk.backend.main import app as backend_app

                        def _run_uvicorn_in_thread():
                            try:
                                import asyncio as _asyncio

                                cfg = uvicorn.Config(
                                    app=backend_app,
                                    host="127.0.0.1",
                                    port=BACKEND_PORT,
                                    log_level="info",
                                    lifespan="on",
                                )
                                server = uvicorn.Server(cfg)

                                # Run server startup on a fresh event loop in this thread
                                loop = _asyncio.new_event_loop()
                                _asyncio.set_event_loop(loop)
                                try:
                                    loop.run_until_complete(server.startup())
                                except Exception:
                                    # If startup failed, log and continue to allow serve() to report
                                    try:
                                        print("Embedded server startup failed", flush=True)
                                    except Exception:
                                        pass

                                # expose server for external control/shutdown
                                self._embedded_server = server

                                # signal that startup has been invoked
                                try:
                                    print("EMBEDDED_UVICORN_STARTED", flush=True)
                                except Exception:
                                    pass

                                # Now run the serve coroutine; this will block until shutdown
                                try:
                                    loop.run_until_complete(server.serve())
                                finally:
                                    try:
                                        loop.run_until_complete(server.shutdown())
                                    except Exception:
                                        pass
                                    try:
                                        loop.close()
                                    except Exception:
                                        pass
                            except Exception:
                                try:
                                    print("Embedded uvicorn thread failed", flush=True)
                                except Exception:
                                    pass

                        thr = threading.Thread(target=_run_uvicorn_in_thread, daemon=True)
                        thr.start()
                        # keep thread reference
                        self._embedded_server_thread = thr
                        # Wait briefly for uvicorn.Server to report started if available
                        try:
                            srv = getattr(self, "_embedded_server", None)
                            waited = 0.0
                            poll = 0.05
                            timeout = 5.0
                            while srv is None and waited < timeout:
                                srv = getattr(self, "_embedded_server", None)
                                time.sleep(poll)
                                waited += poll
                            # If server exposes a 'started' flag, wait until it's True
                            if srv is not None and hasattr(srv, "started"):
                                waited = 0.0
                                while not getattr(srv, "started") and waited < BACKEND_STARTUP_TIMEOUT_SECONDS:
                                    time.sleep(0.05)
                                    waited += 0.05
                        except Exception:
                            pass
                        # surface log path to stdout for smoke-test discovery
                        try:
                            if log_file is not None and 'log_path' in locals():
                                try:
                                    print(f"BACKEND_LOG={log_path}", flush=True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # simple fake proc for compatibility
                        class _FakeProc:
                            def __init__(self):
                                self.pid = -1

                            def poll(self):
                                return None

                            def terminate(self):
                                return None

                        proc = _FakeProc()
                    except Exception:
                        proc = None
                if proc is None:
                    proc = subprocess.Popen(
                        [
                            sys_executable(),
                            "-m",
                            "uvicorn",
                            "tradedesk.backend.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(BACKEND_PORT),
                            "--no-access-log",
                        ],
                        cwd=str(project_root),
                        env={**os.environ, "PYTHONPATH": str(project_root)},
                        creationflags=creationflags,
                        stdout=(log_file if log_file is not None else subprocess.DEVNULL),
                        stderr=(log_file if log_file is not None else subprocess.DEVNULL),
                    )
            except Exception:
                if log_file is not None:
                    try:
                        log_file.close()
                    except Exception:
                        pass
                raise

            try:
                PID_FILE.parent.mkdir(parents=True, exist_ok=True)
                PID_FILE.write_text(str(proc.pid), encoding="utf-8")
            except Exception:
                pass

            # Close our logfile handle in the parent process; the child has its own FD
            try:
                if "log_file" in locals() and log_file is not None:
                    try:
                        log_file.close()
                    except Exception:
                        pass
            except Exception:
                pass

            # Wait for health - poll HTTP endpoint until ready or timeout
            deadline = time.time() + BACKEND_STARTUP_TIMEOUT_SECONDS
            last_exc: Exception | None = None
            while time.time() < deadline:
                try:
                    httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1.0)
                    self._proc = proc
                    return proc
                except Exception as exc:  # noqa: BLE001 - broad catch for readiness polling
                    last_exc = exc
                    # if a real subprocess exited, give up early
                    try:
                        if hasattr(proc, "poll") and proc.poll() is not None:
                            return None
                    except Exception:
                        pass
                    time.sleep(BACKEND_STARTUP_POLL_INTERVAL_SECONDS)

            # timeout reached
            try:
                # attempt graceful terminate
                proc.terminate()
            except Exception:
                pass
            return None

            try:
                proc.terminate()
            except Exception:
                pass
            return None

    def stop(self) -> None:
        with self._lock:
            try:
                proc = self._proc
                if proc is None and PID_FILE.exists():
                    try:
                        raw = PID_FILE.read_text(encoding="utf-8").strip()
                        pid = int(raw) if raw else 0
                        if pid:
                            if os.name == "nt":
                                subprocess.run(
                                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                            else:
                                try:
                                    os.killpg(pid, signal.SIGTERM)
                                except Exception:
                                    try:
                                        os.kill(pid, signal.SIGTERM)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                else:
                    try:
                        if proc is not None:
                            if os.name == "nt":
                                subprocess.run(
                                    ["taskkill", "/PID", str(proc.pid), "/F", "/T"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                            else:
                                try:
                                    os.killpg(proc.pid, signal.SIGTERM)
                                except Exception:
                                    try:
                                        proc.terminate()
                                    except Exception:
                                        pass
                            if hasattr(proc, "wait"):
                                try:
                                    proc.wait(timeout=5)
                                except Exception:
                                    try:
                                        proc.kill()
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                try:
                    if PID_FILE.exists():
                        PID_FILE.unlink()
                except Exception:
                    pass

                self._proc = None
            finally:
                pass

    def restart(self, project_root: Path) -> Any | None:
        with self._lock:
            try:
                self.stop()
            except Exception:
                pass
            return self.start(project_root)


def sys_executable() -> str:
    # Try to find a sensible python executable
    import sys

    return sys.executable

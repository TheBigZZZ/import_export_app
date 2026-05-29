import subprocess
import types


def make_fake_proc(pid=12345):
    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            return None

        def kill(self):
            return None

    return FakeProc(pid)


def test_start_success(monkeypatch, tmp_path):
    # Arrange: point PID_FILE to a temp path to avoid touching user's home
    import frontend.backend_manager as bm

    bm.PID_FILE = tmp_path / "backend.pid"

    fake_proc = make_fake_proc(9999)

    # Monkeypatch subprocess.Popen to return our fake proc
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: fake_proc)

    # Monkeypatch httpx.get to simulate successful health check
    class DummyResponse:
        status_code = 200

    monkeypatch.setattr(
        bm, "httpx", types.SimpleNamespace(get=lambda *a, **k: DummyResponse())
    )

    manager = bm.BackendManager()

    # Act
    proc = manager.start(project_root=tmp_path)

    # Assert
    assert proc is fake_proc
    # PID file should be written
    assert bm.PID_FILE.exists()


def test_restart_calls_start_and_stop(monkeypatch, tmp_path):
    import frontend.backend_manager as bm

    bm.PID_FILE = tmp_path / "backend.pid"

    called = {"start": 0, "stop": 0}

    def fake_start(project_root):
        called["start"] += 1
        return make_fake_proc(1111)

    def fake_stop():
        called["stop"] += 1

    monkeypatch.setattr(bm.BackendManager, "start", staticmethod(fake_start))
    monkeypatch.setattr(bm.BackendManager, "stop", lambda self: fake_stop())

    manager = bm.BackendManager()
    proc = manager.restart(project_root=tmp_path)

    assert called["stop"] == 1
    assert called["start"] == 1
    assert proc is not None


def test_stop_cleans_pid_and_handles_missing_proc(monkeypatch, tmp_path):
    import frontend.backend_manager as bm

    bm.PID_FILE = tmp_path / "backend.pid"

    # Write a fake pid file
    bm.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    bm.PID_FILE.write_text("4321", encoding="utf-8")

    # Monkeypatch taskkill/os.kill to avoid affecting the host
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(__import__("os"), "kill", lambda *a, **k: None)

    manager = bm.BackendManager()
    # Ensure no in-memory proc
    manager._proc = None
    manager.stop()

    assert not bm.PID_FILE.exists()


def test_start_returns_none_when_pid_file_is_running(monkeypatch, tmp_path):
    import frontend.backend_manager as bm

    bm.PID_FILE = tmp_path / "backend.pid"
    bm.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    bm.PID_FILE.write_text("1234", encoding="utf-8")

    called = {"spawn": 0}

    def fake_popen(*args, **kwargs):
        called["spawn"] += 1
        raise AssertionError("Popen should not be called when PID file is active")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(bm.BackendManager, "_proc_is_running", lambda self, pid: True)

    manager = bm.BackendManager()
    proc = manager.start(project_root=tmp_path)

    assert proc is None
    assert called["spawn"] == 0

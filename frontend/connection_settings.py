from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ConnectionSettings:
    backend_url: str
    remember: bool = True


def connection_settings_path() -> Path:
    return Path.home() / "TradeDesk" / "client-settings.json"


def load_connection_settings() -> ConnectionSettings | None:
    path = connection_settings_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    backend_url = str(data.get("backend_url") or "").strip()
    if not backend_url:
        return None

    return ConnectionSettings(
        backend_url=backend_url,
        remember=bool(data.get("remember", True)),
    )


def save_connection_settings(settings: ConnectionSettings) -> None:
    path = connection_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "backend_url": settings.backend_url,
                "remember": settings.remember,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def clear_connection_settings() -> None:
    path = connection_settings_path()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
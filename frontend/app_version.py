from __future__ import annotations

import os
import sys
from pathlib import Path


def _read_version_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return text or None


def get_app_version() -> str:
    version = os.environ.get("TRADEDESK_VERSION", "").strip()
    if version:
        return version

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "version.txt")
        candidates.append(Path(sys.executable).resolve().with_name("version.txt"))
    else:
        project_root = Path(__file__).resolve().parents[1]
        candidates.append(project_root / "version.txt")
        candidates.append(project_root / "frontend" / "version.txt")

    for candidate in candidates:
        version = _read_version_file(candidate)
        if version:
            return version

    return "0.0.0"
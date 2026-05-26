from __future__ import annotations

import logging
import logging.handlers
import contextvars
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
except Exception:  # pragma: no cover - optional
    jsonlogger = None

CORRELATION_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)


class CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        cid = CORRELATION_ID.get()
        record.correlation_id = cid or "-"
        return True


def _build_formatter() -> logging.Formatter:
    if jsonlogger is not None:
        return jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s')
    return logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s [cid=%(correlation_id)s]')


def setup_logging(log_dir: str | None = None, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        # Don't reconfigure if already configured externally
        return

    root.setLevel(level)
    fmt = _build_formatter()
    corr_filter = CorrelationFilter()

    # Stream handler
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(corr_filter)
    root.addHandler(sh)

    # File handler
    if log_dir:
        app_log = f"{log_dir}/app.log"
        fh = logging.handlers.RotatingFileHandler(app_log, maxBytes=5_242_880, backupCount=7, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(corr_filter)
        root.addHandler(fh)

    # Audit file (separate handler for append-only audit logs)
    if log_dir:
        audit_log = f"{log_dir}/audit.log"
        ah = logging.handlers.RotatingFileHandler(audit_log, maxBytes=10_485_760, backupCount=30, encoding="utf-8")
        ah.setFormatter(fmt)
        ah.addFilter(corr_filter)
        ah.setLevel(logging.INFO)
        root.addHandler(ah)


def set_correlation_id(cid: Optional[str]) -> None:
    if cid is None:
        # reset to default
        CORRELATION_ID.set(None)
    else:
        CORRELATION_ID.set(cid)

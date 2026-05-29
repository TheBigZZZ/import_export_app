import logging
import logging.config
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Import optional structured-logging support dynamically to avoid static
# missing-import diagnostics in development environments that don't have
# `pythonjsonlogger` installed. Use importlib so static checkers don't
# report missing imports while preserving runtime behavior.
import importlib

jsonlogger = None
try:  # pragma: no cover - optional dependency
    _pj = importlib.import_module("pythonjsonlogger")
    jsonlogger = getattr(_pj, "jsonlogger", _pj)
except Exception:
    jsonlogger = None

import uuid

from . import cli as backend_cli
from .audit import register_audit_listeners
from .bootstrap import seed_defaults
from .config import settings
from .utils.logging_config import set_correlation_id, setup_logging

# Load optional Sentry SDK dynamically so missing dev/time packages don't
# surface as static import errors in editors.
sentry_sdk = None
try:  # pragma: no cover - optional dependency
    sentry_sdk = importlib.import_module("sentry_sdk")
except Exception:
    sentry_sdk = None
import asyncio
import tempfile
from pathlib import Path
from typing import Any

from .admin import router as admin_router
from .database import AsyncSessionLocal
from .diagnostics import purge_old_diagnostics
from .diagnostics import router as diagnostics_router
from .routes import (accounts, auth, banks, cash, customers, exchange_rates,
                     expenses, imports, live, products, purchases, reports,
                     roles, sales)
from .routes import settings as app_settings
from .routes import setup, suppliers, users, vouchers
from .services.exchange_rate_service import ExchangeRateService
from .startup_checks import run_startup_safety_checks
from .utils.logging_config import flush_logging_handlers, set_correlation_id, setup_logging

logger = logging.getLogger(__name__)

PROMETHEUS_ENABLED = False


def _write_startup_sentinel() -> Path:
    tmp = Path(tempfile.gettempdir())
    sentinel = tmp / f"tradedesk-startup-{os.getpid()}.ready"
    sentinel.write_text("ready", encoding="utf-8")
    return sentinel


async def _cancel_background_task(task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Background task shutdown failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "lifespan: startup begin env=%s logs_dir=%s sentry=%s metrics=%s",
        settings.environment,
        settings.logs_dir,
        bool(sentry_sdk and settings.sentry_dsn),
        PROMETHEUS_ENABLED,
    )
    try:
        from .config import ensure_runtime_dirs

        ensure_runtime_dirs()
    except Exception:
        logger.exception("Failed to ensure runtime directories")

    warnings = await run_startup_safety_checks()
    for item in warnings:
        logger.warning("Startup warning: %s", item)
    register_audit_listeners()

    try:
        reset_flag = os.environ.get("TRADEDESK_RESET_ON_STARTUP", "").lower()
        if reset_flag in ("1", "true", "yes"):
            try:
                dbp = settings.db_path
                if dbp.exists():
                    logger.info(
                        "TRADEDESK_RESET_ON_STARTUP enabled — removing existing DB: %s",
                        dbp,
                    )
                    try:
                        dbp.unlink()
                    except Exception:
                        logger.exception("Failed to remove DB file")
                try:
                    rc = backend_cli.init_db()
                    if rc != 0:
                        logger.warning("init_db returned non-zero: %s", rc)
                except Exception:
                    logger.exception("Failed to initialize database after reset")
            except Exception:
                logger.exception("Error during reset-on-startup handling")
    except Exception:
        logger.exception("Failed to check reset-on-startup flag")

    try:
        app.state._seed_task = asyncio.create_task(seed_defaults())
        logger.info("seed_defaults scheduled in background")
    except Exception:
        logger.exception("Failed to schedule seed_defaults task")

    try:
        try:
            if settings.diagnostics_storage_dir:
                settings.diagnostics_storage_dir.mkdir(parents=True, exist_ok=True)
            if settings.diagnostics_nonces_dir:
                settings.diagnostics_nonces_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("Failed to create diagnostics directories")

        purge_old_diagnostics()
    except Exception:
        logger.exception("Failed to purge old diagnostics")

    try:
        if settings.exchange_rate_auto_sync:

            async def _rate_sync_loop():
                while True:
                    try:
                        async with AsyncSessionLocal() as session:
                            svc = ExchangeRateService(session)
                            await svc.sync_from_public()
                    except Exception:
                        logger.exception("Exchange rate sync failed")
                    await asyncio.sleep(
                        settings.exchange_rate_sync_interval_minutes * 60
                    )

            app.state._rate_sync_task = asyncio.create_task(_rate_sync_loop())
    except Exception:
        logger.exception("Failed to start exchange-rate sync task")

    try:
        sentinel = _write_startup_sentinel()
        logger.info("wrote startup sentinel: %s", str(sentinel))
    except Exception:
        logger.exception("Failed to write startup sentinel file")

    flush_logging_handlers()
    logger.info("lifespan: startup complete")
    try:
        yield
    finally:
        logger.info("lifespan: shutdown begin")
        await _cancel_background_task(getattr(app.state, "_rate_sync_task", None))
        await _cancel_background_task(getattr(app.state, "_seed_task", None))
        flush_logging_handlers()
        logger.info("lifespan: shutdown complete")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Initialize structured logging (stream + rotating file handlers)
try:
    setup_logging(
        log_dir=str(settings.logs_dir),
        level=logging.INFO if settings.environment == "production" else logging.DEBUG,
    )
except Exception:
    # if logging setup fails, continue with defaults
    logger.exception("Failed to initialize structured logging")

# Register standardized error handlers
try:
    from .errors import generic_exception_handler, http_exception_handler

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
except Exception:
    # If import fails, continue without custom handlers
    pass


def _build_log_formatter() -> logging.Formatter:
    if jsonlogger is not None:
        return jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        )
    return logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")


# Configure basic structured JSON logging for production use. If an external
# logging configuration exists (e.g., from a container or systemd unit), this
# will not override it.
if not logging.getLogger().handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(_build_log_formatter())
    logging.getLogger().setLevel(
        logging.INFO if settings.environment == "production" else logging.DEBUG
    )
    logging.getLogger().addHandler(handler)


# Initialize Sentry if a DSN is configured. Sentry is optional and must be
# explicitly enabled by setting the TRADEDESK_SENTRY_DSN environment variable.
if sentry_sdk is not None and settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.05,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID middleware: set per-request contextvar for logs and return header
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID")
        if not cid:
            cid = str(uuid.uuid4())
        set_correlation_id(cid)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            set_correlation_id(None)


app.add_middleware(CorrelationIdMiddleware)


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        # Add common security headers
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "")
        resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
        # HSTS only when running in production behind TLS
        if settings.environment == "production":
            resp.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return resp


app.add_middleware(SecureHeadersMiddleware)


# Simple request-size limit middleware and very small in-memory rate limiter
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body = max_body

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body:
                    return Response("Request body too large", status_code=413)
            except Exception:
                pass
        return await call_next(request)


class SimpleRateLimiter:
    def __init__(self, calls: int = 100, period: int = 60):
        self.calls = calls
        self.period = period
        self._store: dict[str, list[float]] = {}

    async def __call__(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - self.period
        arr = self._store.get(ip, [])
        # remove old
        arr = [t for t in arr if t > window]
        if len(arr) >= self.calls:
            return Response("Too Many Requests", status_code=429)
        arr.append(now)
        self._store[ip] = arr
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware, max_body=10 * 1024 * 1024)
app.add_middleware(BaseHTTPMiddleware, dispatch=SimpleRateLimiter().__call__)

try:
    _prom = importlib.import_module("prometheus_client")
    CONTENT_TYPE_LATEST = getattr(_prom, "CONTENT_TYPE_LATEST")
    generate_latest = getattr(_prom, "generate_latest")
    PROMETHEUS_ENABLED = True

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

except Exception:
    # prometheus_client is optional; skip metrics endpoint when unavailable
    pass

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(roles.router, prefix="/api/roles", tags=["roles"])
app.include_router(banks.router, prefix="/api/banks", tags=["banks"])
app.include_router(cash.router, prefix="/api/cash", tags=["cash"])
app.include_router(vouchers.router, prefix="/api/vouchers", tags=["vouchers"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(sales.router, prefix="/api/sales", tags=["sales"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["purchases"])
app.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(app_settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(
    exchange_rates.router, prefix="/api/exchange-rates", tags=["exchange-rates"]
)
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(diagnostics_router, prefix="/diagnostics", tags=["diagnostics"])
app.include_router(
    admin_router, prefix="/diagnostics/admin", tags=["diagnostics-admin"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    logger.debug("health: requested")
    return {"status": "ok"}


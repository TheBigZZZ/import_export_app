from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from .config import settings
from .database import Base, engine

DEFAULT_JWT_SECRET = "change-me-in-production"
REQUIRED_TABLES = ("users", "chart_of_accounts", "transactions")


@dataclass(frozen=True)
class StartupConfigSnapshot:
    environment: str
    debug: bool
    jwt_secret_key: str
    bcrypt_rounds: int
    access_token_expire_minutes: int


def evaluate_static_startup_checks(snapshot: StartupConfigSnapshot) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    env = snapshot.environment.strip().lower()
    is_production = env == "production"

    if is_production and snapshot.debug:
        errors.append("TRADEDESK_DEBUG must be false in production")

    if is_production and snapshot.jwt_secret_key == DEFAULT_JWT_SECRET:
        errors.append("TRADEDESK_JWT_SECRET_KEY uses insecure default value")
    elif snapshot.jwt_secret_key == DEFAULT_JWT_SECRET:
        warnings.append("JWT secret uses default development value")

    if is_production and snapshot.bcrypt_rounds < 12:
        errors.append("TRADEDESK_BCRYPT_ROUNDS must be >= 12 in production")

    if snapshot.access_token_expire_minutes > 60 * 24:
        warnings.append("Access token expiry exceeds 24 hours")

    # Diagnostics related checks
    try:
        from .config import settings as _settings
    except Exception:
        _settings = None

    if _settings:
        if _settings.diagnostics_enabled:
            if is_production and not _settings.diagnostics_admin_key:
                errors.append("Diagnostics enabled in production but TRADEDESK_DIAGNOSTICS_ADMIN_KEY is not set")
            elif not _settings.diagnostics_admin_key:
                warnings.append("Diagnostics admin key not configured; self-registration may be limited")

            if is_production and _settings.diagnostics_notify_via_email:
                missing_smtp = [k for k in ("diagnostics_smtp_host", "diagnostics_smtp_user", "diagnostics_smtp_password") if not getattr(_settings, k)]
                if missing_smtp:
                    errors.append("Diagnostics email notifications are enabled but SMTP settings are missing: %s" % ",".join(missing_smtp))
            elif _settings.diagnostics_notify_via_email:
                missing = [k for k in ("diagnostics_smtp_host", "diagnostics_smtp_user", "diagnostics_smtp_password") if not getattr(_settings, k)]
                if missing:
                    warnings.append("Diagnostics email notifications configured but SMTP settings missing: %s" % ",".join(missing))

        # Nonce persistence recommended in production when diagnostics are enabled
        if _settings.diagnostics_enabled and is_production and not _settings.diagnostics_nonces_dir:
            errors.append("TRADEDESK_DIAGNOSTICS_NONCES_DIR must be set in production when diagnostics are enabled to prevent replay attacks")

    return errors, warnings


def _snapshot_from_settings() -> StartupConfigSnapshot:
    return StartupConfigSnapshot(
        environment=settings.environment,
        debug=settings.debug,
        jwt_secret_key=settings.jwt_secret_key,
        bcrypt_rounds=settings.bcrypt_rounds,
        access_token_expire_minutes=settings.access_token_expire_minutes,
    )


async def ensure_database_schema_ready() -> bool:
    async with engine.connect() as conn:
        missing: list[str] = []
        for table_name in REQUIRED_TABLES:
            row = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
                {"table_name": table_name},
            )
            if row.scalar_one_or_none() is None:
                missing.append(table_name)

    # Do not auto-create schema when running in production. In production the
    # operator must run Alembic migrations explicitly (recommended) via the
    # `tradedesk.backend.cli --init-db` helper or by running `alembic upgrade head`.
    if missing:
        return True

    return False


async def run_startup_safety_checks() -> list[str]:
    snapshot = _snapshot_from_settings()
    errors, warnings = evaluate_static_startup_checks(snapshot)
    if errors:
        raise RuntimeError("Startup safety check failed: " + " | ".join(errors))

    if settings.enforce_startup_checks:
        missing_schema = await ensure_database_schema_ready()
        if missing_schema:
            # In production, fail fast and instruct operator to run migrations.
            if snapshot.environment.strip().lower() == "production":
                raise RuntimeError(
                    "Database schema is not initialized. Run 'tradedesk.backend.cli --init-db' or 'alembic upgrade head' before starting in production."
                )
            # In non-production environments we initialize automatically to
            # make first-run developer experience smoother.
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            warnings.append("Database schema was initialized on first launch")

    return warnings
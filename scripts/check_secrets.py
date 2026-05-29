#!/usr/bin/env python3
"""Check required environment secrets and warn/error when insecure.

This script is safe to run locally in CI to validate required env vars
before proceeding with a release. It does not print secret values.
"""
from __future__ import annotations

import os
import sys

DEFAULT_JWT = "change-me-in-production"


def fail(msg: str) -> None:
    print("ERROR:", msg)
    sys.exit(2)


def warn(msg: str) -> None:
    print("WARN:", msg)


def main() -> int:
    ok = True

    jwt = os.environ.get("TRADEDESK_JWT_SECRET_KEY", "")
    if not jwt:
        fail("TRADEDESK_JWT_SECRET_KEY is not set")
    if jwt == DEFAULT_JWT or len(jwt) < 32:
        fail("TRADEDESK_JWT_SECRET_KEY is insecure or too short (>=32 chars recommended)")

    bcrypt = os.environ.get("TRADEDESK_BCRYPT_ROUNDS")
    if bcrypt:
        try:
            rounds = int(bcrypt)
            if rounds < 12:
                warn("TRADEDESK_BCRYPT_ROUNDS < 12; use >= 12 for production")
        except Exception:
            warn("TRADEDESK_BCRYPT_ROUNDS is not an integer")
    else:
        warn("TRADEDESK_BCRYPT_ROUNDS not set; default may be insecure for production")

    diag_enabled = os.environ.get("TRADEDESK_DIAGNOSTICS_ENABLED", "").lower() in ("1", "true", "yes")
    if diag_enabled:
        admin = os.environ.get("TRADEDESK_DIAGNOSTICS_ADMIN_KEY")
        nonces = os.environ.get("TRADEDESK_DIAGNOSTICS_NONCES_DIR")
        if not admin:
            warn("Diagnostics enabled but TRADEDESK_DIAGNOSTICS_ADMIN_KEY is not set")
        if not nonces:
            warn("Diagnostics enabled but TRADEDESK_DIAGNOSTICS_NONCES_DIR is not set")

    # Minimal smoke for other important envs
    env = os.environ.get("TRADEDESK_ENVIRONMENT", "development")
    if env.strip().lower() == "production":
        if os.environ.get("TRADEDESK_DEBUG", "").lower() in ("1", "true", "yes"):
            fail("TRADEDESK_DEBUG must be false in production")

    if not ok:
        return 2
    print("Secrets check passed (no secret values were printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

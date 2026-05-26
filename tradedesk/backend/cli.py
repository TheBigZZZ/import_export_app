from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .config import settings
from .security import hash_password


def _alembic_ini_path() -> str:
    # Locate the alembic.ini relative to this file so the module is runnable
    base = Path(__file__).resolve().parents[1]
    candidate = base / "alembic.ini"
    if candidate.exists():
        return str(candidate)
    # Fallback to package-relative alembic.ini path
    return str(Path(__file__).resolve().parents[0] / "alembic.ini")


def init_db() -> int:
    """Run Alembic `upgrade head` programmatically.

    Returns 0 on success, non-zero on failure.
    """
    try:
        from alembic import command
        from alembic.config import Config
    except Exception as exc:  # pragma: no cover - runtime helper
        print("alembic is required to initialize the database; please install alembic", file=sys.stderr)
        return 2

    ini_path = _alembic_ini_path()
    cfg = Config(ini_path)

    # The env.py in the alembic directory should read settings and set the
    # SQLAlchemy URL appropriately. Call upgrade head.
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:  # pragma: no cover - runtime helper
        print("Failed to apply migrations:", exc, file=sys.stderr)
        return 1

    print("Database migrations applied successfully.")
    return 0


def backup_db_cmd(destination: str | None = None) -> int:
    try:
        from .backup import backup_db
    except Exception:
        print("Backup helper not available", file=sys.stderr)
        return 2

    try:
        target = backup_db(Path(destination) if destination else None)
    except Exception as exc:
        print("Failed to create backup:", exc, file=sys.stderr)
        return 1

    print("Database backup created:", target)
    return 0


def restore_db_cmd(source: str) -> int:
    try:
        from .backup import restore_db
    except Exception:
        print("Restore helper not available", file=sys.stderr)
        return 2

    try:
        target = restore_db(Path(source))
    except Exception as exc:
        print("Failed to restore backup:", exc, file=sys.stderr)
        return 1

    print("Database restored to:", target)
    return 0


def reset_db_cmd(force: bool = False) -> int:
    from .config import settings
    import os
    allow_env = str(os.environ.get("TRADEDESK_ALLOW_RESET", "0")).lower() in ("1", "true", "yes")
    if not force and not allow_env:
        print("Refusing to reset DB: pass --force or set TRADEDESK_ALLOW_RESET=1 to confirm", file=sys.stderr)
        return 2

    db_path = settings.db_path
    if db_path.exists():
        try:
            # Create a timestamped backup copy first
            import shutil
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            backup = db_path.parent / f"{db_path.name}.bak.{ts}"
            shutil.copy2(db_path, backup)
            db_path.unlink()
            print(f"Database reset: original backed up to {backup}")
            return 0
        except Exception as exc:
            print("Failed to reset DB:", exc, file=sys.stderr)
            return 1
    else:
        print("No database file found; nothing to do")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tradedesk.backend.cli")
    parser.add_argument("--init-db", action="store_true", help="Apply Alembic migrations (upgrade head)")
    parser.add_argument("--backup-db", nargs="?", const="", help="Create a DB backup. Optionally pass a destination directory.")
    parser.add_argument("--restore-db", help="Restore DB from a backup file")
    parser.add_argument("--reset-db", action="store_true", help="Reset the database file (destructive). Requires --force or TRADEDESK_ALLOW_RESET=1")

    # Initial admin creation (non-interactive) - intended for first-run/installer
    parser.add_argument("--init-admin", action="store_true", help="Create initial admin user non-interactively (requires --admin-username and --admin-password)")
    parser.add_argument("--admin-username", help="Username for initial admin")
    parser.add_argument("--admin-password", help="Password for initial admin")
    parser.add_argument("--admin-full-name", help="Full name for initial admin", default="System Administrator")
    parser.add_argument("--admin-email", help="Email for initial admin", default=None)
    parser.add_argument("--admin-role", help="Role for initial admin", default="super_admin")
    parser.add_argument("--force", action="store_true", help="Force operation even if users already exist")
    parser.add_argument("--set-secret", nargs=2, metavar=("KEY", "VALUE"), help="Set a secret in the OS keyring (example: --set-secret jwt_secret_key hunter2)")

    # Reset admin password safely
    parser.add_argument("--reset-admin-password", action="store_true", help="Reset password for an existing user (requires --target-username and --admin-password)")
    parser.add_argument("--target-username", help="Username to reset password for")

    args = parser.parse_args(argv)
    if args.init_db:
        return init_db()
    if args.reset_db:
        return reset_db_cmd(force=args.force)
    if args.backup_db is not None:
        # argparse gives '' when const used; treat as None
        dest = args.backup_db or None
        return backup_db_cmd(dest)
    if args.restore_db:
        return restore_db_cmd(args.restore_db)

    if args.set_secret:
        from .utils.secret_store import set_secret

        key, value = args.set_secret
        try:
            set_secret(key, value)
        except Exception as exc:
            print("Failed to set secret:", exc, file=sys.stderr)
            return 1
        print(f"Secret '{key}' set successfully.")
        return 0

    if args.init_admin:
        if not args.admin_username or not args.admin_password:
            print("--admin-username and --admin-password are required when using --init-admin", file=sys.stderr)
            return 2
        return init_admin_cmd(
            username=args.admin_username,
            password=args.admin_password,
            full_name=args.admin_full_name,
            email=args.admin_email,
            role=args.admin_role,
            force=args.force,
        )

    if args.reset_admin_password:
        if not args.target_username or not args.admin_password:
            print("--target-username and --admin-password are required when using --reset-admin-password", file=sys.stderr)
            return 2
        return reset_admin_password_cmd(username=args.target_username, new_password=args.admin_password)

    parser.print_help()
    return 0


def _connect_db():
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    return conn


def init_admin_cmd(username: str, password: str, full_name: str, email: str | None, role: str = "super_admin", force: bool = False) -> int:
    conn = _connect_db()
    cur = conn.cursor()

    # Ensure users table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cur.fetchone():
        print("Users table not found. Run migrations first (python -m tradedesk.backend.cli --init-db)", file=sys.stderr)
        return 1

    # Check existing users
    cur.execute("SELECT COUNT(1) FROM users")
    count = cur.fetchone()[0]
    if count > 0 and not force:
        print("Users already exist. Refusing to create initial admin unless --force is provided.", file=sys.stderr)
        return 1

    # Insert new user
    pwd_hash = hash_password(password)
    try:
        cur.execute(
            "INSERT INTO users (full_name, username, email, password_hash, role, is_active, failed_login_attempts, locked_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (full_name, username, email, pwd_hash, role, 1, 0, None),
        )
        conn.commit()
    except Exception as exc:
        print("Failed to create admin:", exc, file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"Initial admin '{username}' created.")
    return 0


def reset_admin_password_cmd(username: str, new_password: str) -> int:
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        print(f"User '{username}' not found.", file=sys.stderr)
        conn.close()
        return 1
    pwd_hash = hash_password(new_password)
    try:
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pwd_hash, username))
        conn.commit()
    except Exception as exc:
        print("Failed to reset password:", exc, file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Password for '{username}' has been reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

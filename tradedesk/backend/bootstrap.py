from __future__ import annotations

import json
import secrets

from sqlalchemy import select

from .database import AsyncSessionLocal
from .models.account import AccountType, ChartOfAccount
from .models.user import User
from .security import hash_password
from .config import settings

DEFAULT_ACCOUNTS = [
    ("1000", "Cash in Hand", AccountType.asset),
    ("1100", "Bank Accounts", AccountType.asset),
    ("1200", "Inventory", AccountType.asset),
    ("1300", "Accounts Receivable", AccountType.asset),
    ("2000", "Accounts Payable", AccountType.liability),
    ("2100", "Loan", AccountType.liability),
    ("2200", "VAT Payable", AccountType.liability),
    ("3000", "Capital", AccountType.equity),
    ("3100", "Retained Earnings", AccountType.equity),
    ("4000", "Sales Revenue", AccountType.income),
    ("4100", "Service Income", AccountType.income),
    ("5000", "Salary", AccountType.expense),
    ("5100", "Office", AccountType.expense),
    ("5200", "Freight", AccountType.expense),
    ("5300", "Customs Duty", AccountType.expense),
    ("5400", "LC Charges", AccountType.expense),
    ("5500", "Insurance", AccountType.expense),
]


async def seed_defaults() -> None:
    async with AsyncSessionLocal() as session:
        users_q = await session.execute(select(User.id))
        has_users = users_q.first() is not None

        accounts_q = await session.execute(select(ChartOfAccount.id))
        has_accounts = accounts_q.first() is not None
        if not has_accounts:
            for code, name, account_type in DEFAULT_ACCOUNTS:
                session.add(
                    ChartOfAccount(
                        account_code=code,
                        account_name=name,
                        account_type=account_type,
                        parent_id=None,
                        is_system=True,
                    )
                )

        if not has_users:
            credentials_path = settings.initial_super_admin_credentials_path
            username = "superadmin"
            full_name = "Default Super Admin"
            email = None
            password = None

            if credentials_path.exists():
                try:
                    stored = json.loads(credentials_path.read_text(encoding="utf-8"))
                    username = stored.get("username") or username
                    full_name = stored.get("full_name") or full_name
                    email = stored.get("email") or email
                    password = stored.get("password")
                except Exception:
                    password = None

            if not password:
                password = secrets.token_urlsafe(18)
                credentials_path.parent.mkdir(parents=True, exist_ok=True)
                credentials_path.write_text(
                    json.dumps(
                        {
                            "username": username,
                            "full_name": full_name,
                            "email": email,
                            "password": password,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            session.add(
                User(
                    full_name=full_name,
                    username=username,
                    email=email,
                    password_hash=hash_password(password),
                    role="super_admin",
                    is_active=True,
                    failed_login_attempts=0,
                    locked_until=None,
                )
            )

        await session.commit()

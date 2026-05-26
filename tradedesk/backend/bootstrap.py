from sqlalchemy import select

from .database import AsyncSessionLocal
from .models.account import AccountType, ChartOfAccount
from .security import hash_password

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
        # NOTE: We intentionally do NOT create a default admin account here.
        # Initial admin creation must be performed via the first-run setup
        # flow or the CLI to avoid shipping default credentials in production.

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

        await session.commit()

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRADEDESK_")

    app_name: str = "TradeDesk ERP"
    environment: str = "development"
    enforce_startup_checks: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8742
    debug: bool = False

    # Small-team install settings
    # Maximum number of user accounts allowed (e.g., owner + 2 trusted people)
    max_users: int = 3
    # Toggle whether user management UI/API is enabled (installer may disable)
    enable_user_module: bool = True

    # Server-provided role definitions (key + label). Frontend should fetch /api/roles
    # to populate role dropdowns. Represented as list of dicts with 'key' and 'label'.
    roles: list[dict] = Field(default_factory=lambda: [
        {"key": "viewer", "label": "Viewer"},
        {"key": "sales_manager", "label": "Sales Manager"},
        {"key": "purchase_manager", "label": "Purchase Manager"},
        {"key": "accounts_manager", "label": "Accounts Manager"},
        {"key": "admin", "label": "Admin"},
        {"key": "super_admin", "label": "Super Admin"},
    ])

    base_dir: Path = Field(default_factory=lambda: Path.home() / "TradeDesk")
    data_dir: Path = Field(default_factory=lambda: Path.home() / "TradeDesk" / "data")
    backup_dir: Path = Field(default_factory=lambda: Path.home() / "TradeDesk" / "backups")
    logs_dir: Path = Field(default_factory=lambda: Path.home() / "TradeDesk" / "logs")

    db_file_name: str = "tradedesk.db"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    refresh_token_expire_days: int = 7

    bcrypt_rounds: int = 12
    failed_login_limit: int = 5
    lock_minutes: int = 15

    # Optional Sentry DSN for production error reporting (set in env: TRADEDESK_SENTRY_DSN)
    sentry_dsn: str | None = None

    # Diagnostics upload & storage configuration
    diagnostics_enabled: bool = False
    diagnostics_storage_dir: Path = Field(default_factory=lambda: Path.home() / "TradeDesk" / "diagnostics")
    diagnostics_max_bytes: int = 5_242_880  # 5 MB
    diagnostics_retention_days: int = 30
    diagnostics_signature_skew_seconds: int = 300
    # Allow clients to self-register to receive an install secret (for HMAC)
    diagnostics_allow_self_register: bool = False
    # Optional admin key that can be used to register installs via an admin call
    diagnostics_admin_key: str | None = None
    # Optional webhook to notify on new diagnostics uploads
    diagnostics_webhook_url: str | None = None
    # Optional local upload URL used by the desktop client
    diagnostics_upload_url: str | None = None
    # Nonce persistence: directory to store seen nonces
    diagnostics_nonces_dir: Path | None = Field(default=None)
    # How long to keep nonces (days) to prevent replays
    diagnostics_nonces_ttl_days: int = 7
    # Email notification settings
    diagnostics_notify_via_email: bool = False
    diagnostics_notify_email_from: str | None = None
    diagnostics_notify_email_to: str | None = None
    diagnostics_smtp_host: str | None = None
    diagnostics_smtp_port: int = 587
    diagnostics_smtp_user: str | None = None
    diagnostics_smtp_password: str | None = None
    # Admin UI session settings
    diagnostics_admin_session_ttl_seconds: int = 3600

    # Exchange rate auto-sync configuration
    exchange_rate_auto_sync: bool = False
    exchange_rate_sync_interval_minutes: int = 60
    exchange_rate_source_url: str = "https://api.exchangerate.host/latest?base={base}"
    exchange_rate_default_base: str = "USD"
    exchange_rate_default_targets: list[str] = Field(default_factory=lambda: ["USD", "EUR", "GBP", "CNY", "AED", "SGD", "JPY"]) 

    # SMS provider settings (console by default; Twilio optional)
    sms_provider: str | None = None
    sms_twilio_account_sid: str | None = None
    sms_twilio_auth_token: str | None = None
    sms_from_number: str | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_file_name

    @property
    def initial_super_admin_credentials_path(self) -> Path:
        return self.base_dir / "default-super-admin.json"

    @property
    def async_database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path.as_posix()}"


settings = Settings()


def ensure_runtime_dirs() -> None:
    for target in (settings.base_dir, settings.data_dir, settings.backup_dir, settings.logs_dir):
        target.mkdir(parents=True, exist_ok=True)

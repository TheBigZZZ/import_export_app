from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import httpx

from .api_client import ApiClient
from .error_messages import friendly_exception_message, friendly_http_error
from .live_updates import LiveUpdateMonitor
from .modules import (
    BanksModule,
    CashRegisterModule,
    ChartOfAccountsModule,
    CustomersModule,
    DashboardModule,
    ExpensesModule,
    ImportCostingModule,
    ProductsModule,
    PurchasesModule,
    ReportsModule,
    SalesModule,
    SettingsModule,
    SuppliersModule,
    UsersModule,
    VouchersModule,
)


@dataclass
class ModuleEntry:
    key: str
    label: str
    widget_cls: type


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Login")
        self.setModal(True)

        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Enter your password")
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)

        self.error = QLabel("")
        self.error.setStyleSheet("color: #E53935;")
        self.error.setWordWrap(True)

        self.help_button = QPushButton("Setup Help")
        self.help_button.clicked.connect(self._show_setup_help)

        buttons = QHBoxLayout()
        buttons.addWidget(self.help_button)
        buttons.addStretch(1)
        self.login_button = QPushButton("Login")
        self.cancel_button = QPushButton("Cancel")
        self.login_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.login_button)
        buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(buttons)

    def _show_setup_help(self) -> None:
        dialog = SetupHelpDialog(self)
        dialog.exec()

    def prefill(self, username: str | None = None, password: str | None = None) -> None:
        if username:
            self.username.setText(username)
        if password:
            self.password.setText(password)

    def clear_error(self) -> None:
        self.error.setText("")

    def show_error(self, message: str) -> None:
        self.error.setText(message)


class SetupHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Setup Guide")
        self.setModal(True)
        self.resize(780, 640)

        text = QTextBrowser(self)
        text.setOpenExternalLinks(True)
        text.setHtml(
            """
            <h2>Recommended setup for nontechnical users</h2>
            <p><b>Best simple choice:</b> use <a href="https://tailscale.com/download">Tailscale</a> on the host PC and on every client PC. It removes the need for port forwarding, firewall changes, or manual LAN configuration.</p>
            <p><b>If you need access from outside the office:</b> use <a href="https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/">Cloudflare Tunnel</a> or a similar HTTPS tunnel on the host.</p>

            <h3>Option A - Local setup on one PC</h3>
            <ol>
                <li>Install TradeDesk on the PC you want to use as the main machine.</li>
                <li>Open the app and click <b>Use Local Backend</b>.</li>
                <li>Leave the URL as <code>http://127.0.0.1:8742</code>.</li>
                <li>Log in with the admin account.</li>
                <li>Keep this app open; it will start and use the local backend automatically.</li>
            </ol>

            <h3>Option B - Shared setup using Tailscale</h3>
            <ol>
                <li>Pick one always-on PC to act as the host.</li>
                <li>Install TradeDesk on the host PC and open it once.</li>
                <li>On the host PC, click <b>Use Local Backend</b>.</li>
                <li>Install Tailscale on the host PC from <a href="https://tailscale.com/download">tailscale.com/download</a>.</li>
                <li>Sign in to Tailscale on the host PC.</li>
                <li>Install Tailscale on every client PC and sign in with the same account or invite the users.</li>
                <li>Find the host PC's Tailscale IP address, usually a <code>100.x.x.x</code> address.</li>
                <li>On every other PC, open TradeDesk and choose <b>Use Shared Backend</b>.</li>
                <li>Enter the host Tailscale URL exactly, for example <code>http://100.101.102.103:8742</code>.</li>
                <li>Leave <b>Remember this connection</b> checked if you want each PC to keep the setting.</li>
                <li>Log in normally on each client.</li>
            </ol>

            <h3>Option C - Shared setup with a public HTTPS URL</h3>
            <ol>
                <li>Run the backend on a server or always-on machine.</li>
                <li>Expose it through Cloudflare Tunnel or another public HTTPS tunnel.</li>
                <li>On each client, choose <b>Use Shared Backend</b>.</li>
                <li>Enter the public HTTPS URL exactly, such as <code>https://trade.example.com</code>.</li>
                <li>Log in after the connection is saved.</li>
            </ol>

            <h3>What to type in the URL field</h3>
            <ul>
                <li><b>Local:</b> <code>http://127.0.0.1:8742</code></li>
                <li><b>Tailscale host:</b> <code>http://100.x.x.x:8742</code></li>
                <li><b>Public host/tunnel:</b> <code>https://...</code></li>
            </ul>

            <h3>Recommended free path</h3>
            <ol>
                <li>Use one office PC as the host.</li>
                <li>Install Tailscale on the host and on every client.</li>
                <li>Point the clients to the host's Tailscale IP.</li>
            </ol>

            <h3>Quick start checklist</h3>
            <ol>
                <li>Host PC: install TradeDesk, click <b>Use Local Backend</b>, and log in once.</li>
                <li>Host PC: install Tailscale and sign in.</li>
                <li>Client PCs: install Tailscale and sign in.</li>
                <li>Client PCs: open TradeDesk, choose <b>Use Shared Backend</b>, and paste the host Tailscale URL.</li>
                <li>Test the setup by editing data on one PC and confirming another PC refreshes.</li>
            </ol>

            <p>If you need internet access outside the office, use Cloudflare Tunnel instead of LAN or Tailscale.</p>
            """
        )

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(close_button)
        layout.addLayout(footer)


class MainWindow(QMainWindow):
    def __init__(self, backend_url: str):
        super().__init__()
        self.setWindowTitle("TradeDesk ERP")
        self.resize(1400, 860)

        self.api_client = ApiClient(backend_url)
        self.live_monitor: LiveUpdateMonitor | None = None
        self.user_role: str | None = None
        self.current_module_key = "dashboard"
        self._pending_live_modules: set[str] = set()
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.timeout.connect(self._apply_live_refresh)

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        self.company_label = QLabel("TradeDesk ERP")
        self.company_label.setObjectName("titleLabel")
        self.user_label = QLabel("Not logged in")
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        top_layout.addWidget(self.company_label)
        top_layout.addStretch(1)
        self.connection_label = QLabel("Connection: unknown")
        self.connection_label.setObjectName("mutedLabel")
        top_layout.addWidget(self.connection_label)
        top_layout.addWidget(self.user_label)
        top_layout.addWidget(self.logout_button)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setAlignment(Qt.AlignTop)

        self.stack = QStackedWidget()
        self.module_buttons: dict[str, QPushButton] = {}
        self.module_widgets: dict[str, QWidget] = {}

        self._build_modules()

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack, 1)

        shell_layout.addWidget(top_bar)
        shell_layout.addWidget(body, 1)
        self.setCentralWidget(shell)

        status = QStatusBar()
        status.showMessage("Backend connected")
        self.setStatusBar(status)

        self._update_connection_indicator()

    def _build_modules(self) -> None:
        entries = [
            ModuleEntry("dashboard", "Dashboard", DashboardModule),
            ModuleEntry("users", "Users", UsersModule),
            ModuleEntry("accounts", "Chart of Accounts", ChartOfAccountsModule),
            ModuleEntry("banks", "Banks", BanksModule),
            ModuleEntry("cash", "Cash Register", CashRegisterModule),
            ModuleEntry("vouchers", "Vouchers", VouchersModule),
            ModuleEntry("customers", "Customers", CustomersModule),
            ModuleEntry("suppliers", "Suppliers", SuppliersModule),
            ModuleEntry("products", "Products", ProductsModule),
            ModuleEntry("imports", "Import Costing", ImportCostingModule),
            ModuleEntry("sales", "Sales", SalesModule),
            ModuleEntry("purchases", "Purchases", PurchasesModule),
            ModuleEntry("expenses", "Expenses", ExpensesModule),
            ModuleEntry("reports", "Reports", ReportsModule),
            ModuleEntry("settings", "Settings", SettingsModule),
        ]

        for index, entry in enumerate(entries):
            button = QPushButton(entry.label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, key=entry.key: self.switch_module(key))
            self.sidebar_layout.addWidget(button)
            self.module_buttons[entry.key] = button

            widget = entry.widget_cls(self.api_client)
            self.stack.addWidget(widget)
            self.module_widgets[entry.key] = widget

            if index == 0:
                button.setChecked(True)
                self.stack.setCurrentWidget(widget)

        users_button = self.module_buttons.get("users")
        if users_button is not None:
            users_button.hide()

        self.sidebar_layout.addStretch(1)

    def _apply_user_visibility(self) -> None:
        users_button = self.module_buttons.get("users")
        can_view_users = self.user_role == "super_admin"
        if users_button is not None:
            users_button.setVisible(can_view_users)
        self._update_connection_indicator(connected=True)

    def _on_live_disconnected(self, message: str) -> None:
        if message:
            self.statusBar().showMessage(f"Live sync reconnecting: {message}", 5000)
        self._update_connection_indicator(connected=False)

    def _update_connection_indicator(self, connected: bool = True) -> None:
        backend_url = self.api_client.base_url
        if backend_url.startswith("http://127.0.0.1") or backend_url.startswith("http://localhost"):
            mode = "Local"
        else:
            mode = "Shared"

        state = "Connected" if connected else "Reconnecting"
        self.connection_label.setText(f"Connection: {mode} {state} ({backend_url})")

    def _modules_for_live_event(self, payload: dict) -> set[str]:
        table_name = str(payload.get("payload", {}).get("table_name") or "").lower()
        modules = {"dashboard", "reports", self.current_module_key}
        if not table_name:
            return modules

        if "database" in table_name or "system" in table_name:
            return set(self.module_widgets.keys()) | {"dashboard", "reports"}

        if "user" in table_name:
            modules.add("users")
        if any(token in table_name for token in ("account", "transaction", "voucher", "bank", "cash")):
            modules.update({"accounts", "banks", "cash", "vouchers"})
        if "customer" in table_name:
            modules.add("customers")
        if "supplier" in table_name:
            modules.add("suppliers")
        if any(token in table_name for token in ("product", "stock", "inventory")):
            modules.update({"products", "imports"})
        if "import" in table_name:
            modules.update({"imports", "products"})
        if "sale" in table_name:
            modules.update({"sales", "customers", "products"})
        if "purchase" in table_name:
            modules.update({"purchases", "suppliers", "products"})
        if "expense" in table_name:
            modules.add("expenses")

        return modules

    def _on_live_event(self, payload: dict) -> None:
        event_name = payload.get("event_name")
        if event_name == "ready":
            return

        modules = self._modules_for_live_event(payload)
        self._pending_live_modules.update(modules)
        if not self._live_refresh_timer.isActive():
            self._live_refresh_timer.start(250)

    def _safe_refresh_widget(self, widget: QWidget) -> None:
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def _apply_live_refresh(self) -> None:
        modules = set(self._pending_live_modules)
        self._pending_live_modules.clear()

        for key in sorted(modules):
            widget = self.module_widgets.get(key)
            if widget is not None:
                self._safe_refresh_widget(widget)

        current_widget = self.stack.currentWidget()
        if current_widget is not None:
            self._safe_refresh_widget(current_widget)

    def _start_live_monitor(self) -> None:
        try:
            self._stop_live_monitor()
        except Exception:
            pass

        try:
            self.live_monitor = LiveUpdateMonitor(self.api_client)
            self.live_monitor.connected.connect(lambda: self.statusBar().showMessage("Live sync connected", 3000))
            self.live_monitor.disconnected.connect(self._on_live_disconnected)
            self.live_monitor.event_received.connect(self._on_live_event)
            self.live_monitor.start()
        except Exception:
            self.live_monitor = None

    def _stop_live_monitor(self) -> None:
        if self.live_monitor is None:
            return
        try:
            self.live_monitor.stop()
        except Exception:
            pass
        self.live_monitor = None

    def ensure_login(self, initial_credentials: dict[str, str] | None = None) -> bool:
        # Persistent loop until user authenticates or cancels
        while True:
            dialog = LoginDialog(self)
            if initial_credentials:
                dialog.prefill(username=initial_credentials.get("username"), password=initial_credentials.get("password"))
                initial_credentials = None

            res = dialog.exec()
            if res != QDialog.Accepted:
                return False

            username = dialog.username.text().strip()
            password = dialog.password.text()

            if not username or not password:
                dialog.show_error("Username and password are required")
                continue

            try:
                resp = httpx.post(f"{self.api_client.base_url}/api/auth/login", json={"username": username, "password": password}, timeout=10.0)
            except Exception as exc:
                dialog.show_error(friendly_exception_message(exc, "Login"))
                continue

            if resp.status_code != 200:
                dialog.show_error(friendly_http_error(resp, "Login"))
                continue

            try:
                body = resp.json()
            except Exception:
                dialog.show_error("Invalid response from server")
                continue

            access = body.get("access_token")
            refresh = body.get("refresh_token")
            if not access or not refresh:
                dialog.show_error("Login failed: missing tokens")
                continue

            try:
                self.api_client.set_tokens(access, refresh)
            except Exception:
                # tokens stored best-effort; continue
                pass

            # fetch current user
            try:
                me = httpx.get(f"{self.api_client.base_url}/api/auth/me", headers=self.api_client.auth_headers(), timeout=5.0)
            except Exception as exc:
                dialog.show_error(friendly_exception_message(exc, "Fetch user"))
                continue

            if me.status_code != 200:
                dialog.show_error(friendly_http_error(me, "Fetch user"))
                continue

            try:
                user = me.json()
            except Exception:
                dialog.show_error("Failed to parse user info")
                continue

            self.user_role = user.get("role")
            display_name = user.get("full_name") or user.get("username") or ""
            self.user_label.setText(display_name or "Logged in")
            self._apply_user_visibility()
            self._start_live_monitor()
            return True

    def logout(self) -> None:
        self._stop_live_monitor()
        self.api_client.clear_tokens()
        self.user_label.setText("Not logged in")
        self.user_role = None
        self._apply_user_visibility()
        self._update_connection_indicator(connected=False)
        if not self.ensure_login():
            self.close()

    def closeEvent(self, event):
        self._stop_live_monitor()
        self.api_client.close()
        super().closeEvent(event)

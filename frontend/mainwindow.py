from __future__ import annotations

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass

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
    QVBoxLayout,
    QWidget,
    QTextBrowser,
)

from .api_client import ApiClient
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
                dialog = QDialog(self)
                dialog.setWindowTitle("TradeDesk Setup Guide")
                dialog.setModal(True)
                dialog.resize(720, 520)

                text = QTextBrowser(dialog)
                text.setOpenExternalLinks(True)
                text.setHtml(
                        """
                        <h2>Setup Options</h2>
                        <p><b>Local mode</b>: this PC starts its own backend on <code>127.0.0.1:8742</code>.</p>
                        <p><b>LAN mode</b>: one office PC runs the backend and everyone uses that PC's LAN IP.</p>
                        <p><b>Online tunnel</b>: a tunnel service gives the host PC a public HTTPS URL that other devices can use.</p>
                        <p><b>Public host</b>: a VPS or cloud host runs the backend and exposes a public URL directly.</p>
                        <h3>Recommended free options</h3>
                        <ol>
                            <li>LAN host on one always-on office PC.</li>
                            <li>Free tunnel from that PC if you need internet access.</li>
                        </ol>
                        <h3>What to enter in this app</h3>
                        <ul>
                            <li>Local mode: keep the default localhost address.</li>
                            <li>LAN mode: enter the host PC's LAN IP address and port.</li>
                            <li>Online tunnel: enter the public HTTPS URL from the tunnel or host.</li>
                        </ul>
                        <p>The app remembers the chosen backend URL on this computer unless you turn that off.</p>
                        """
                )

                close_button = QPushButton("Close", dialog)
                close_button.clicked.connect(dialog.accept)

                layout = QVBoxLayout(dialog)
                layout.addWidget(text)
                footer = QHBoxLayout()
                footer.addStretch(1)
                footer.addWidget(close_button)
                layout.addLayout(footer)

                dialog.exec()


class MainWindow(QMainWindow):
    def __init__(self, backend_url: str):
        super().__init__()
        self.setWindowTitle("TradeDesk ERP")
        self.resize(1400, 860)

        self.api_client = ApiClient(backend_url)
        self.live_monitor: LiveUpdateMonitor | None = None
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

        self.ensure_login()

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
            # Respect server-side enable_user_module and role-based visibility later; widgets created now and adjusted after login
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

        self.sidebar_layout.addStretch(1)

    def switch_module(self, key: str) -> None:
        self.current_module_key = key
        for name, button in self.module_buttons.items():
            button.setChecked(name == key)

        widget = self.module_widgets[key]
        self.stack.setCurrentWidget(widget)
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()

    def ensure_login(self) -> None:
        dialog = LoginDialog(self)
        credentials_path = Path.home() / "TradeDesk" / "default-super-admin.json"
        if credentials_path.exists():
            try:
                creds = json.loads(credentials_path.read_text(encoding="utf-8"))
                dialog.username.setText(creds.get("username") or "")
                dialog.password.setText(creds.get("password") or "")
            except Exception:
                pass

        if dialog.exec() != QDialog.Accepted:
            self.close()
            return

        username = dialog.username.text().strip()
        password = dialog.password.text()

        try:
            response = asyncio.run(
                self.api_client.post(
                    "/api/auth/login",
                    json={"username": username, "password": password},
                    auth=False,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "Connection Error", str(exc))
            self.close()
            return

        if response.status_code != 200:
            QMessageBox.warning(self, "Login Failed", response.text)
            self.ensure_login()
            return

        payload = response.json()
        self.api_client.set_tokens(payload["access_token"], payload["refresh_token"])
        self.user_label.setText(f"Logged in: {username}")
        # Fetch current user to learn role and adjust UI
        try:
            me_resp = asyncio.run(self.api_client.get('/api/auth/me'))
            if me_resp.status_code == 200:
                me = me_resp.json()
                self.user_role = me.get('role')
            else:
                self.user_role = None
        except Exception:
            self.user_role = None

        # Hide the Users module unless the signed-in user is a super admin.
        try:
            # check server-side feature flag
            import requests
            root = self.api_client.base_url
            resp = requests.get(f"{root}/api/settings")
            if resp.ok:
                settings = resp.json()
                enable_users = settings.get('enable_user_module', True)
            else:
                enable_users = True
        except Exception:
            enable_users = True

        if not enable_users or getattr(self, 'user_role', None) != 'super_admin':
            btn = self.module_buttons.get('users')
            if btn:
                btn.hide()

        self._start_live_monitor()

    def _start_live_monitor(self) -> None:
        self._stop_live_monitor()
        self.live_monitor = LiveUpdateMonitor(self.api_client)
        self.live_monitor.connected.connect(self._on_live_connected)
        self.live_monitor.disconnected.connect(self._on_live_disconnected)
        self.live_monitor.event_received.connect(self._on_live_event)
        self.live_monitor.start()

    def _stop_live_monitor(self) -> None:
        if self.live_monitor is not None:
            self.live_monitor.stop()
            self.live_monitor = None

    def _on_live_connected(self) -> None:
        self.statusBar().showMessage("Live sync connected", 3000)
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

    def logout(self) -> None:
        self._stop_live_monitor()
        self.api_client.clear_tokens()
        self.user_label.setText("Not logged in")
        self._update_connection_indicator(connected=False)
        self.ensure_login()

    def closeEvent(self, event):
        self._stop_live_monitor()
        self.api_client.close()
        super().closeEvent(event)

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from PySide6.QtCore import Qt
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
)

from .api_client import ApiClient
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

        buttons = QHBoxLayout()
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


class MainWindow(QMainWindow):
    def __init__(self, backend_url: str):
        super().__init__()
        self.setWindowTitle("TradeDesk ERP")
        self.resize(1400, 860)

        self.api_client = ApiClient(backend_url)

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
        for name, button in self.module_buttons.items():
            button.setChecked(name == key)

        widget = self.module_widgets[key]
        self.stack.setCurrentWidget(widget)
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()

    def ensure_login(self) -> None:
        dialog = LoginDialog(self)
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

        # Hide users module if server disables it or if current role is viewer
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

        if not enable_users or (hasattr(self, 'user_role') and self.user_role == 'viewer'):
            # remove/hide Users button
            btn = self.module_buttons.get('users')
            if btn:
                btn.hide()

    def logout(self) -> None:
        self.api_client.clear_tokens()
        self.user_label.setText("Not logged in")
        self.ensure_login()

    def closeEvent(self, event):
        self.api_client.close()
        super().closeEvent(event)

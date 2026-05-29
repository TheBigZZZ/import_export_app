from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import (QEasingCurve, QEventLoop, QPropertyAnimation, Qt,
                            QThreadPool, QTimer, Signal)
from PySide6.QtWidgets import (QDialog, QFormLayout, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QPushButton, QStackedWidget, QStatusBar,
                               QTextBrowser, QVBoxLayout, QWidget)

from .api_client import ApiClient
from .error_messages import friendly_exception_message
from .live_updates import AsyncLiveUpdateMonitor, LiveUpdateMonitor
from .modules import (BanksModule, CashRegisterModule, ChartOfAccountsModule,
                      CustomersModule, DashboardModule, ExpensesModule,
                      ImportCostingModule, ProductsModule, PurchasesModule,
                      ReportsModule, SalesModule, SettingsModule,
                      SuppliersModule, UsersModule, VouchersModule)
from .workers import Worker


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
        text.setHtml("""
            <h2>Recommended setup for nontechnical users</h2>
            <p>
                <b>Best simple choice:</b> use
                <a href="https://tailscale.com/download">Tailscale</a> on the
                host PC and on every client PC.
                It removes the need for port forwarding, firewall changes, or
                manual LAN configuration.
            </p>
            <p>
                <b>If you need access from outside the office:</b> use
                (
                    '<a href="https://developers.cloudflare.com/cloudflare-one/'
                    'connections/connect-networks/get-started/create-remote-tunnel/">'
                    "Cloudflare Tunnel"
                    "</a>"
                )
                or a similar HTTPS tunnel on the host.
            </p>

            <h3>Option A - Local setup on one PC</h3>
            <ol>
                <li>
                    Install TradeDesk on the PC you want to use as the main
                    machine.
                </li>
                <li>Open the app and click <b>Use Local Backend</b>.</li>
                <li>
                    Leave the URL as <code>http://127.0.0.1:8742</code>.
                </li>
                <li>Log in with the admin account.</li>
                <li>
                    Keep this app open; it will start and use the local
                    backend automatically.
                </li>
            </ol>

            <h3>Option B - Shared setup using Tailscale</h3>
            <ol>
                <li>Pick one always-on PC to act as the host.</li>
                <li>Install TradeDesk on the host PC and open it once.</li>
                <li>On the host PC, click <b>Use Local Backend</b>.</li>
                <li>
                    Install Tailscale on the host PC from
                    <a href="https://tailscale.com/download">tailscale.com/download</a>.
                </li>
                <li>Sign in to Tailscale on the host PC.</li>
                <li>
                    Install Tailscale on every client PC and sign in with the
                    same account or invite the users.
                </li>
                <li>
                    Find the host PC's Tailscale IP address, usually a
                    <code>100.x.x.x</code> address.
                </li>
                <li>
                    On every other PC, open TradeDesk and choose
                    <b>Use Shared Backend</b>.
                </li>
                <li>
                    Enter the host Tailscale URL exactly, for example
                    <code>http://100.101.102.103:8742</code>.
                </li>
                <li>
                    Leave <b>Remember this connection</b> checked if you want
                    each PC to keep the setting.
                </li>
                <li>Log in normally on each client.</li>
            </ol>

            <h3>Option C - Shared setup with a public HTTPS URL</h3>
            <ol>
                <li>Run the backend on a server or always-on machine.</li>
                <li>Expose it through Cloudflare Tunnel or another public HTTPS
                    tunnel.</li>
                <li>On each client, choose <b>Use Shared Backend</b>.</li>
                <li>
                    Enter the public HTTPS URL exactly, such as
                    <code>https://trade.example.com</code>.
                </li>
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
                <li>
                    Host PC: install TradeDesk, click
                    <b>Use Local Backend</b>, and log in once.
                </li>
                <li>Host PC: install Tailscale and sign in.</li>
                <li>Client PCs: install Tailscale and sign in.</li>
                <li>
                    Client PCs: open TradeDesk, choose
                    <b>Use Shared Backend</b>, and paste the host Tailscale URL.
                </li>
                <li>
                    Test the setup by editing data on one PC and confirming
                    another PC refreshes.
                </li>
            </ol>

            <p>
                If you need internet access outside the office, use Cloudflare
                Tunnel instead of LAN or Tailscale.
            </p>
            """)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(close_button)
        layout.addLayout(footer)


class MainWindow(QMainWindow):
    # Signal to request a backend restart from the GUI thread.
    restart_requested = Signal()

    def __init__(self, backend_url: str, on_close=None, restart_local_backend=None):
        super().__init__()
        self.setWindowTitle("TradeDesk ERP")
        self.resize(1400, 860)
        self._on_close = on_close

        self.api_client = ApiClient(backend_url)
        # Optional callable provided by caller to restart a local backend (callable -> proc|None)
        self._restart_local_backend = restart_local_backend
        self.live_monitor: LiveUpdateMonitor | None = None
        self.user_role: str | None = None
        self.current_module_key = "dashboard"
        self._pending_live_modules: set[str] = set()
        self._refreshed_modules: set[str] = set()
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.timeout.connect(self._apply_live_refresh)
        self._module_transition: QPropertyAnimation | None = None

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(8, 8, 8, 8)
        shell_layout.setSpacing(8)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 8, 10, 8)
        top_layout.setSpacing(10)
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
        body_layout.setSpacing(8)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setAlignment(Qt.AlignTop)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)
        self.sidebar_layout.setSpacing(6)

        self.stack = QStackedWidget()
        self.module_buttons: dict[str, QPushButton] = {}
        self.module_widgets: dict[str, QWidget] = {}
        self.stack.setContentsMargins(0, 0, 0, 0)

        self._build_modules()
        QTimer.singleShot(0, self.refresh_current_module)

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack, 1)

        shell_layout.addWidget(top_bar)
        shell_layout.addWidget(body, 1)
        self.setCentralWidget(shell)

        status = QStatusBar()
        status.showMessage("Backend connected")
        self.setStatusBar(status)

        self._update_connection_indicator()

        # connect restart signal to handler
        self.restart_requested.connect(self._handle_restart_request)

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
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, key=entry.key: self.switch_module(key)
            )
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
        # If this is a local backend and a restart callback is available,
        # request a restart via a Qt signal (handler will run in GUI thread
        # and will offload the actual restart work to a worker thread).
        try:
            backend_url = self.api_client.base_url
            if backend_url.startswith("http://127.0.0.1") or backend_url.startswith(
                "http://localhost"
            ):
                if callable(self._restart_local_backend):
                    # emit signal to request restart; connected handler will do the work
                    self.restart_requested.emit()
        except Exception:
            pass

    def _update_connection_indicator(self, connected: bool = True) -> None:
        backend_url = self.api_client.base_url
        if backend_url.startswith("http://127.0.0.1") or backend_url.startswith(
            "http://localhost"
        ):
            mode = "Local"
        else:
            mode = "Shared"

        state = "Connected" if connected else "Reconnecting"
        self.connection_label.setText(f"Connection: {mode} {state} ({backend_url})")

    def _modules_for_live_event(self, payload: dict) -> set[str]:
        table_name = str(payload.get("payload", {}).get("table_name") or "").lower()
        modules = {"dashboard", "reports"}
        if not table_name:
            return modules

        if "database" in table_name or "system" in table_name:
            return set(self.module_widgets.keys()) | {"dashboard", "reports"}

        if "user" in table_name:
            modules.add("users")
        if any(
            token in table_name
            for token in ("account", "transaction", "voucher", "bank", "cash")
        ):
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

    def refresh_current_module(self) -> None:
        widget = self.stack.currentWidget()
        if widget is None:
            return
        key = self.current_module_key
        self._refreshed_modules.add(key)
        self._safe_refresh_widget(widget)

    def switch_module(self, key: str) -> None:
        widget = self.module_widgets.get(key)
        button = self.module_buttons.get(key)
        if widget is None or button is None:
            return

        self.current_module_key = key
        self.stack.setCurrentWidget(widget)

        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(140)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _clear_effect() -> None:
            widget.setGraphicsEffect(None)
            self._module_transition = None

        animation.finished.connect(_clear_effect)
        self._module_transition = animation
        animation.start()

        for module_key, module_button in self.module_buttons.items():
            module_button.setChecked(module_key == key)
        self.statusBar().showMessage(f"Opened {button.text()}", 2000)

    def _apply_live_refresh(self) -> None:
        modules = set(self._pending_live_modules)
        self._pending_live_modules.clear()

        for key in sorted(modules):
            widget = self.module_widgets.get(key)
            if widget is not None:
                self._safe_refresh_widget(widget)

    def _start_live_monitor(self) -> None:
        try:
            self._stop_live_monitor()
        except Exception:
            pass

        try:
            if self._use_async_live_monitor():
                self.live_monitor = AsyncLiveUpdateMonitor(self.api_client)
            else:
                self.live_monitor = LiveUpdateMonitor(self.api_client)
            self.live_monitor.connected.connect(
                lambda: self.statusBar().showMessage("Live sync connected", 3000)
            )
            self.live_monitor.disconnected.connect(self._on_live_disconnected)
            self.live_monitor.event_received.connect(self._on_live_event)
            self.live_monitor.start()
        except Exception:
            self.live_monitor = None

    def _use_async_live_monitor(self) -> bool:
        return str(os.environ.get("TRADEDESK_USE_QTASYNCIO", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _handle_restart_request(self) -> None:
        """Handle a restart request on the GUI thread: start a worker to perform the restart so
        the backend spawn runs off the main thread, but GUI updates remain in the main thread.
        """
        if not callable(self._restart_local_backend):
            return

        from PySide6.QtCore import QThreadPool

        from .workers import Worker

        self.statusBar().showMessage("Restarting local backend...", 5000)

        def _call_restart():
            try:
                return self._restart_local_backend()
            except Exception:
                raise

        worker = Worker(_call_restart)

        def _on_result(proc):
            if proc is not None:
                self.statusBar().showMessage("Local backend restarted", 3000)
                self._update_connection_indicator(connected=True)
            else:
                self.statusBar().showMessage("Failed to restart local backend", 5000)

        def _on_error(exc):
            try:
                self.statusBar().showMessage(
                    f"Failed to restart local backend: {exc}", 8000
                )
            except Exception:
                pass

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        QThreadPool.globalInstance().start(worker)

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
                dialog.prefill(
                    username=initial_credentials.get("username"),
                    password=initial_credentials.get("password"),
                )
                initial_credentials = None

            res = dialog.exec()
            if res != QDialog.Accepted:
                return False

            username = dialog.username.text().strip()
            password = dialog.password.text()

            if not username or not password:
                dialog.show_error("Username and password are required")
                continue

            # Run login in a worker and wait via a nested event loop so the modal dialog
            # remains responsive but we avoid blocking the main thread.
            login_result = {}

            def _do_login():
                resp = self.api_client.sync_post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                resp.raise_for_status()
                return resp.json()

            loop = QEventLoop()

            def _on_login(result):
                login_result["body"] = result
                loop.quit()

            def _on_login_error(exc):
                login_result["error"] = exc
                loop.quit()

            worker = Worker(_do_login)
            worker.signals.result.connect(_on_login)
            worker.signals.error.connect(_on_login_error)
            QThreadPool.globalInstance().start(worker)
            loop.exec()

            if "error" in login_result:
                dialog.show_error(
                    friendly_exception_message(login_result["error"], "Login")
                )
                continue

            body = login_result.get("body")
            if not body or not isinstance(body, dict):
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
                pass

            # fetch current user via worker as well
            me_result = {}

            def _do_me():
                resp = self.api_client.sync_get("/api/auth/me")
                resp.raise_for_status()
                return resp.json()

            loop2 = QEventLoop()

            def _on_me(result):
                me_result["user"] = result
                loop2.quit()

            def _on_me_error(exc):
                me_result["error"] = exc
                loop2.quit()

            worker2 = Worker(_do_me)
            worker2.signals.result.connect(_on_me)
            worker2.signals.error.connect(_on_me_error)
            QThreadPool.globalInstance().start(worker2)
            loop2.exec()

            if "error" in me_result:
                dialog.show_error(
                    friendly_exception_message(me_result["error"], "Fetch user")
                )
                continue

            user = me_result.get("user")
            if not user or not isinstance(user, dict):
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
        try:
            if callable(self._on_close):
                self._on_close()
        except Exception:
            pass
        self._stop_live_monitor()
        self.api_client.close()
        super().closeEvent(event)

from __future__ import annotations

import os
import re
from typing import Any

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from ..error_messages import friendly_exception_message, friendly_http_error
from ..widgets.data_table import DataTable
from ..workers import Worker
from .base import BaseModuleWidget


class UsersModule(BaseModuleWidget):
    module_title = "Users"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable(delete_callback=self.delete_selected)

        form_box = QGroupBox("Add User")
        form = QFormLayout(form_box)
        self.username_input = QLineEdit()
        self.fullname_input = QLineEdit()
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        # inline small labels to show field errors/icons
        self.username_error = QLabel("")
        self.fullname_error = QLabel("")
        self.email_error = QLabel("")
        self.password_error = QLabel("")
        self.role_error = QLabel("")
        # style inline error labels
        for lbl in (
            self.username_error,
            self.fullname_error,
            self.email_error,
            self.password_error,
            self.role_error,
        ):
            lbl.setStyleSheet("color: #E53935;")
        self.password_input.setPlaceholderText("Minimum 8 characters")
        # Role dropdown with canonical roles (seeded; refreshed from server on refresh())
        self.role_input = QComboBox()
        # seed with sensible defaults so UI is usable offline
        for r in [
            "viewer",
            "sales_manager",
            "purchase_manager",
            "accounts_manager",
            "admin",
            "super_admin",
        ]:
            self.role_input.addItem(r, r)
        create_btn = QPushButton("Create User")
        create_btn.clicked.connect(self.create_user)

        # wrap inputs with an icon label
        def wrap_with_icon(widget_input, icon_label):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(widget_input)
            h.addWidget(icon_label)
            return container

        form.addRow(
            "Username", wrap_with_icon(self.username_input, self.username_error)
        )
        form.addRow("", QLabel(""))
        form.addRow(
            "Full name", wrap_with_icon(self.fullname_input, self.fullname_error)
        )
        form.addRow("", QLabel(""))
        form.addRow("Email", wrap_with_icon(self.email_input, self.email_error))
        form.addRow("", QLabel(""))
        form.addRow(
            "Password", wrap_with_icon(self.password_input, self.password_error)
        )
        form.addRow("", QLabel(""))
        form.addRow("Role", wrap_with_icon(self.role_input, self.role_error))
        form.addRow("", QLabel(""))
        form.addRow("", create_btn)
        self.configure_form_layout(form)

        actions = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        actions.addWidget(reload_btn)
        actions.addStretch(1)

        # reuse base layout created by BaseModuleWidget (avoid duplicate layouts)
        layout = self.layout() or QVBoxLayout(self)
        layout.addWidget(form_box)
        layout.addLayout(actions)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        # Load roles and users via background workers to avoid blocking the UI
        try:
            # kick off roles loader but don't block on it
            if os.environ.get("TRADEDESK_USE_QTASYNCIO"):
                # run async roles loader in background
                self.run_async(
                    self._async_load_roles(),
                    on_result=lambda _: None,
                    on_error=lambda e: None,
                )
            else:
                roles_worker = Worker(self._load_roles)
                QThreadPool.globalInstance().start(roles_worker)
        except Exception:
            pass

        # Start worker to fetch users
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch_users():
                resp = await self.api_client.get("/api/users")
                return resp

            def _on_result(response: Any) -> None:
                try:
                    if response.status_code != 200:
                        QMessageBox.warning(
                            self, "Users", friendly_http_error(response, "Load users")
                        )
                        return

                    data = response.json()
                    rows = [
                        [
                            str(item["id"]),
                            item["username"],
                            item["full_name"],
                            item.get("email") or "",
                            item["role"],
                            str(item.get("is_active")),
                        ]
                        for item in data
                    ]
                    self.table.set_rows(
                        ["ID", "Username", "Full Name", "Email", "Role", "Active"],
                        rows,
                        stretch_columns={2, 3},
                    )
                    self._clear_icons()
                except Exception as exc:
                    QMessageBox.warning(
                        self, "Users", friendly_exception_message(exc, "Load users")
                    )

            def _on_error(exc: Exception) -> None:
                QMessageBox.warning(
                    self, "Users", friendly_exception_message(exc, "Load users")
                )

            self.run_async(
                _async_fetch_users(), on_result=_on_result, on_error=_on_error
            )
            return

        def _fetch_users() -> Any:
            return self.api_client.sync_get("/api/users")

        def _on_result(response: Any) -> None:
            try:
                if response.status_code != 200:
                    QMessageBox.warning(
                        self, "Users", friendly_http_error(response, "Load users")
                    )
                    return

                data = response.json()
                rows = [
                    [
                        str(item["id"]),
                        item["username"],
                        item["full_name"],
                        item.get("email") or "",
                        item["role"],
                        str(item.get("is_active")),
                    ]
                    for item in data
                ]
                self.table.set_rows(
                    ["ID", "Username", "Full Name", "Email", "Role", "Active"],
                    rows,
                    stretch_columns={2, 3},
                )
                self._clear_icons()
            except Exception as exc:
                QMessageBox.warning(
                    self, "Users", friendly_exception_message(exc, "Load users")
                )

        def _on_error(exc: Exception) -> None:
            QMessageBox.warning(
                self, "Users", friendly_exception_message(exc, "Load users")
            )

        worker = Worker(_fetch_users)
        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        QThreadPool.globalInstance().start(worker)

    def create_user(self) -> None:
        # Clear previous inline errors
        self.username_error.setText("")
        self.fullname_error.setText("")
        self.email_error.setText("")
        self.password_error.setText("")
        self.role_error.setText("")

        username = self.username_input.text().strip()
        full = self.fullname_input.text().strip()
        email = self.email_input.text().strip() or None
        password = self.password_input.text()
        # Prefer itemData (role key); fall back to visible text
        role = (
            self.role_input.currentData()
            or self.role_input.currentText().strip()
            or "viewer"
        )

        # Client-side validation
        has_error = False
        # reset icons
        for lbl in (
            self.username_error,
            self.fullname_error,
            self.email_error,
            self.password_error,
            self.role_error,
        ):
            lbl.setText("")

        if not username:
            self.username_error.setText("Username is required")
            has_error = True
        if not full:
            self.fullname_error.setText("Full name is required")
            has_error = True
        # basic email regex if provided
        if email:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                self.email_error.setText("Enter a valid email")
                has_error = True
        if password is None or len(password) < 8:
            self.password_error.setText("Password must be at least 8 characters")
            has_error = True
        if has_error:
            # show inline errors (styled); no emoji
            self._update_field_icons()
            return

        payload = {
            "username": username,
            "full_name": full,
            "email": email,
            "password": password,
            "role": role,
        }

        def _do_create() -> Any:
            return self.api_client.sync_post("/api/users", json=payload)

        def _on_result(response: Any) -> None:
            try:
                if response.status_code != 201:
                    try:
                        data = response.json()
                        if isinstance(data, dict) and "detail" in data:
                            detail = data["detail"]
                            if isinstance(detail, list):
                                for d in detail:
                                    loc = d.get("loc") or []
                                    if isinstance(loc, (list, tuple)) and len(loc) > 0:
                                        field = str(loc[-1])
                                    else:
                                        field = None
                                    msg = d.get("msg", "Invalid")
                                    if field == "username":
                                        self.username_error.setText(msg)
                                    elif field == "full_name":
                                        self.fullname_error.setText(msg)
                                    elif field == "email":
                                        self.email_error.setText(msg)
                                    elif field == "password":
                                        self.password_error.setText(msg)
                                    elif field == "role":
                                        self.role_error.setText(msg)
                                return
                            else:
                                QMessageBox.warning(
                                    self,
                                    "Create User",
                                    friendly_http_error(response, "Create user"),
                                )
                        else:
                            QMessageBox.warning(
                                self,
                                "Create User",
                                friendly_http_error(response, "Create user"),
                            )
                    except Exception:
                        QMessageBox.warning(
                            self,
                            "Create User",
                            friendly_http_error(response, "Create user"),
                        )
                    return

                # success
                self.username_input.clear()
                self.fullname_input.clear()
                self.email_input.clear()
                self.password_input.clear()
                idx = self.role_input.findData("viewer")
                if idx >= 0:
                    self.role_input.setCurrentIndex(idx)
                else:
                    self.role_input.setCurrentIndex(0)
                # refresh the table
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(
                    self, "Create User", friendly_exception_message(exc, "Create user")
                )

        def _on_error(exc: Exception) -> None:
            w = self.window()
            try:
                if w and hasattr(w, "statusBar"):
                    w.statusBar().showMessage(
                        friendly_exception_message(exc, "Create user"), 5000
                    )
                    return
            except Exception:
                pass
            QMessageBox.warning(
                self, "Create User", friendly_exception_message(exc, "Create user")
            )

        worker = Worker(_do_create)
        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        QThreadPool.globalInstance().start(worker)

    def _clear_icons(self) -> None:
        for lbl in (
            self.username_error,
            self.fullname_error,
            self.email_error,
            self.password_error,
            self.role_error,
        ):
            lbl.setText("")

    def _update_field_icons(self) -> None:
        # Prefix inline error messages with an SVG error icon
        from pathlib import Path

        icon = Path(__file__).resolve().parents[1] / "assets" / "icons" / "error.svg"
        for lbl in (
            self.username_error,
            self.fullname_error,
            self.email_error,
            self.password_error,
            self.role_error,
        ):
            txt = lbl.text().strip()
            if txt:
                lbl.setText(f"<img src='{icon.as_posix()}' width='14'/> {txt}")
            else:
                lbl.setText("")

    def delete_selected(self) -> None:
        # Bulk delete selected rows
        indexes = self.table.table.selectedIndexes()
        rows = sorted({idx.row() for idx in indexes})
        if not rows:
            QMessageBox.information(
                self, "Delete User", "Select one or more user rows to delete"
            )
            return

        ids = []
        for r in rows:
            item = self.table.table.item(r, 0)
            if item:
                ids.append(item.text())

        if not ids:
            QMessageBox.information(
                self, "Delete User", "Could not determine selected user ids"
            )
            return

        if (
            QMessageBox.question(
                self, "Delete User", f"Delete {len(ids)} users? This cannot be undone."
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        # placeholder for potential per-item errors; currently unused

        def _do_delete_all() -> Any:
            return self.api_client.sync_post("/api/users/bulk-delete", json=ids)

        def _do_delete_single(uid: str) -> Any:
            return self.api_client.sync_delete(f"/api/users/{uid}")

        def _on_result(response: Any) -> None:
            try:
                if isinstance(response, list):
                    # shouldn't happen; guard
                    pass
                elif hasattr(response, "status_code") and response.status_code in (
                    200,
                    204,
                    201,
                ):
                    # success path
                    self.refresh()
                else:
                    # try to extract details
                    try:
                        if hasattr(response, "json"):
                            data = response.json()
                            if isinstance(data, dict) and "failed" in data:
                                failed = data.get("failed", [])
                                if failed:
                                    QMessageBox.warning(
                                        self,
                                        "Delete User",
                                        "Some deletes failed:\n"
                                        + "\n".join([str(f) for f in failed]),
                                    )
                                    return
                    except Exception:
                        pass
                    QMessageBox.warning(
                        self,
                        "Delete User",
                        friendly_http_error(response, "Delete users"),
                    )
            except Exception as exc:
                QMessageBox.warning(
                    self, "Delete User", friendly_exception_message(exc, "Delete user")
                )

        def _on_error(exc: Exception) -> None:
            QMessageBox.warning(
                self, "Delete User", friendly_exception_message(exc, "Delete user")
            )

        if len(ids) > 1:
            worker = Worker(_do_delete_all)
            worker.signals.result.connect(_on_result)
            worker.signals.error.connect(_on_error)
            QThreadPool.globalInstance().start(worker)
        else:
            uid = ids[0]
            worker = Worker(lambda: _do_delete_single(uid))
            worker.signals.result.connect(_on_result)
            worker.signals.error.connect(_on_error)
            QThreadPool.globalInstance().start(worker)

    def _load_roles(self) -> None:
        """Fetch canonical roles from the backend and populate the combo box.

        Falls back to existing items if the request fails.
        """

        def _do_fetch():
            resp = self.api_client.sync_get("/api/roles")
            return resp

        def _on_result(resp):
            try:
                if resp.status_code != 200:
                    return
                body = resp.json()
                roles = body.get("roles", []) if isinstance(body, dict) else []
                default = body.get("default") if isinstance(body, dict) else None
            except Exception:
                return

            # repopulate combo preserving display labels and itemData=key
            self.role_input.clear()
            for r in roles:
                key = r.get("key") or r.get("name") or r.get("id") or r.get("label")
                label = r.get("label") or key
                self.role_input.addItem(label, key)

            # select default if provided
            if default:
                idx = self.role_input.findData(default)
                if idx >= 0:
                    self.role_input.setCurrentIndex(idx)

        def _on_error(exc):
            return

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

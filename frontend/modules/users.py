from __future__ import annotations

import asyncio

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QComboBox,
    QWidget,
)
import re

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class UsersModule(BaseModuleWidget):
    module_title = "Users"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

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
        for lbl in (self.username_error, self.fullname_error, self.email_error, self.password_error, self.role_error):
            lbl.setStyleSheet("color: #E53935;")
        self.password_input.setPlaceholderText("Minimum 8 characters")
        # Role dropdown with canonical roles (seeded; refreshed from server on refresh())
        self.role_input = QComboBox()
        # seed with sensible defaults so UI is usable offline
        for r in ["viewer", "sales_manager", "purchase_manager", "accounts_manager", "admin", "super_admin"]:
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

        form.addRow("Username", wrap_with_icon(self.username_input, self.username_error))
        form.addRow("", QLabel(""))
        form.addRow("Full name", wrap_with_icon(self.fullname_input, self.fullname_error))
        form.addRow("", QLabel(""))
        form.addRow("Email", wrap_with_icon(self.email_input, self.email_error))
        form.addRow("", QLabel(""))
        form.addRow("Password", wrap_with_icon(self.password_input, self.password_error))
        form.addRow("", QLabel(""))
        form.addRow("Role", wrap_with_icon(self.role_input, self.role_error))
        form.addRow("", QLabel(""))
        form.addRow("", create_btn)

        actions = QHBoxLayout()
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        actions.addWidget(delete_btn)
        actions.addWidget(reload_btn)
        actions.addStretch(1)

        # reuse base layout created by BaseModuleWidget (avoid duplicate layouts)
        layout = self.layout() or QVBoxLayout(self)
        layout.addWidget(form_box)
        layout.addLayout(actions)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        # Load roles from server (populate combo) — do this before loading users so role labels are available
        try:
            self._load_roles()
        except Exception:
            # non-fatal; continue to load users
            pass

        try:
            response = asyncio.run(self.api_client.get("/api/users"))
        except Exception as exc:
            QMessageBox.warning(self, "Users", str(exc))
            return

        if response.status_code != 200:
            QMessageBox.warning(self, "Users", f"Error: {response.status_code} {response.text}")
            return

        data = response.json()
        rows = [[str(item["id"]), item["username"], item["full_name"], item.get("email") or "", item["role"], str(item["is_active"])] for item in data]
        self.table.set_rows(["ID", "Username", "Full Name", "Email", "Role", "Active"], rows)
        # Reset icons after refresh
        self._clear_icons()

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
        role = self.role_input.currentData() or self.role_input.currentText().strip() or "viewer"

        # Client-side validation
        has_error = False
        # reset icons
        for lbl in (self.username_error, self.fullname_error, self.email_error, self.password_error, self.role_error):
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

        payload = {"username": username, "full_name": full, "email": email, "password": password, "role": role}
        try:
            response = asyncio.run(self.api_client.post("/api/users", json=payload))
        except Exception as exc:
            # show non-blocking status
            w = self.window()
            try:
                if w and hasattr(w, 'statusBar'):
                    w.statusBar().showMessage(str(exc), 5000)
                    return
            except Exception:
                pass
            QMessageBox.warning(self, "Create User", str(exc))
            return

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
                        QMessageBox.warning(self, "Create User", str(detail))
                else:
                    QMessageBox.warning(self, "Create User", str(data))
            except Exception:
                QMessageBox.warning(self, "Create User", f"Error: {response.status_code} {response.text}")
            return

        self.username_input.clear()
        self.fullname_input.clear()
        self.email_input.clear()
        self.password_input.clear()
        # reset to default viewer if present
        idx = self.role_input.findData("viewer")
        if idx >= 0:
            self.role_input.setCurrentIndex(idx)
        else:
            self.role_input.setCurrentIndex(0)
        self.refresh()

    def _clear_icons(self) -> None:
        for lbl in (self.username_error, self.fullname_error, self.email_error, self.password_error, self.role_error):
            lbl.setText("")

    def _update_field_icons(self) -> None:
        # Prefix inline error messages with an SVG error icon
        from pathlib import Path
        icon = Path(__file__).resolve().parents[1] / 'assets' / 'icons' / 'error.svg'
        for lbl in (self.username_error, self.fullname_error, self.email_error, self.password_error, self.role_error):
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
            QMessageBox.information(self, "Delete User", "Select one or more user rows to delete")
            return

        ids = []
        for r in rows:
            item = self.table.table.item(r, 0)
            if item:
                ids.append(item.text())

        if not ids:
            QMessageBox.information(self, "Delete User", "Could not determine selected user ids")
            return

        if QMessageBox.question(self, "Delete User", f"Delete {len(ids)} users? This cannot be undone.") != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for uid in ids:
            try:
                if len(ids) > 1:
                    resp = asyncio.run(self.api_client.post("/api/users/bulk-delete", json=ids))
                    if resp.status_code == 200:
                        failed = resp.json().get("failed", [])
                        if failed:
                            errors.extend([f"{f}: failed" for f in failed])
                    else:
                        errors.append(f"bulk-delete failed: {resp.status_code} {resp.text}")
                    break
                else:
                    response = asyncio.run(self.api_client.delete(f"/api/users/{uid}"))
                    if response.status_code not in (200, 204):
                        errors.append(f"{uid}: {response.status_code} {response.text}")
            except Exception as exc:
                errors.append(str(exc))

        if errors:
            QMessageBox.warning(self, "Delete User", "Some deletes failed:\n" + "\n".join(errors))

        self.refresh()
    def _load_roles(self) -> None:
        """Fetch canonical roles from the backend and populate the combo box.

        Falls back to existing items if the request fails.
        """
        try:
            resp = asyncio.run(self.api_client.get("/api/roles"))
        except Exception:
            return

        if resp.status_code != 200:
            return

        try:
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

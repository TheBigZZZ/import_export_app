from __future__ import annotations

import asyncio

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QWidget
import re

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class CustomersModule(BaseModuleWidget):
    module_title = "Customers"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        form_box = QGroupBox("Add Customer")
        form = QFormLayout(form_box)
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.opening_input = QLineEdit("0")
        create_btn = QPushButton("Create Customer")
        create_btn.clicked.connect(self.create_customer)
        # Inline error labels
        self.code_error = QLabel("")
        self.code_error.setStyleSheet("color: #E53935;")
        self.name_error = QLabel("")
        self.name_error.setStyleSheet("color: #E53935;")
        self.opening_error = QLabel("")
        self.opening_error.setStyleSheet("color: #E53935;")
        # wrap code and icon
        code_container = QWidget()
        h = QHBoxLayout(code_container)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.code_input)
        h.addWidget(self.code_error)
        form.addRow("Code", code_container)

        name_container = QWidget()
        h2 = QHBoxLayout(name_container)
        h2.setContentsMargins(0, 0, 0, 0)
        h2.addWidget(self.name_input)
        h2.addWidget(self.name_error)
        form.addRow("Name", name_container)
        form.addRow("Phone", self.phone_input)
        open_container = QWidget()
        h3 = QHBoxLayout(open_container)
        h3.setContentsMargins(0, 0, 0, 0)
        h3.addWidget(self.opening_input)
        h3.addWidget(self.opening_error)
        form.addRow("Opening Balance", open_container)
        form.addRow("", create_btn)

        actions = QHBoxLayout()
        self.ledger_id_input = QLineEdit()
        self.ledger_id_input.setPlaceholderText("Customer ID for ledger")
        ledger_btn = QPushButton("Load Ledger")
        ledger_btn.clicked.connect(self.load_ledger)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.ledger_summary = QLabel("Ledger: not loaded")
        actions.addWidget(self.ledger_id_input)
        actions.addWidget(ledger_btn)
        actions.addWidget(reload_btn)
        actions.addWidget(self.ledger_summary)
        actions.addStretch(1)

        self.layout().addWidget(form_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

        # Add delete button
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)
        self.layout().addWidget(delete_btn)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/customers"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Customers", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["customer_code"],
                item["customer_name"],
                item["phone"] or "",
                str(item["current_balance"]),
            ]
            for item in data
        ]
        self.table.set_rows(["ID", "Code", "Name", "Phone", "Balance"], rows)

    def create_customer(self) -> None:
        # Clear previous inline errors
        self.code_error.setText("")
        self.name_error.setText("")
        self.opening_error.setText("")

        # Clear and validate
        self.code_error.setText("")
        self.name_error.setText("")
        self.opening_error.setText("")
        has_error = False
        code = self.code_input.text().strip()
        name = self.name_input.text().strip()
        try:
            opening = float(self.opening_input.text())
        except Exception:
            opening = None

        if not code:
            self.code_error.setText("Code is required")
            has_error = True
        if not name:
            self.name_error.setText("Name is required")
            has_error = True
        if opening is None:
            self.opening_error.setText("Opening balance must be numeric")
            has_error = True
        if has_error:
            from pathlib import Path
            icon = Path(__file__).resolve().parents[1] / 'assets' / 'icons' / 'error.svg'
            for lbl in (self.code_error, self.name_error, self.opening_error):
                txt = lbl.text().strip()
                if txt:
                    lbl.setText(f"<img src='{icon.as_posix()}' width='14'/> {txt}")
            return

        payload = {
            "customer_code": code,
            "customer_name": name,
            "phone": self.phone_input.text().strip() or None,
            "opening_balance": opening,
        }

        try:
            response = asyncio.run(self.api_client.post("/api/customers", json=payload))
        except Exception as exc:
            QMessageBox.warning(self, "Create Customer", str(exc))
            return

        if response.status_code != 201:
            # Try to show structured validation or error details inline
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
                            if field == "customer_code":
                                self.code_error.setText(msg)
                            elif field == "customer_name":
                                self.name_error.setText(msg)
                            elif field == "opening_balance":
                                self.opening_error.setText(msg)
                        return
                    else:
                        QMessageBox.warning(self, "Create Customer", str(detail))
                else:
                    QMessageBox.warning(self, "Create Customer", str(data))
            except Exception:
                QMessageBox.warning(self, "Create Customer", f"Error: {response.status_code} {response.text}")
            return

        self.code_input.clear()
        self.name_input.clear()
        self.phone_input.clear()
        self.opening_input.setText("0")
        self.refresh()

    def delete_selected(self) -> None:
        # Support bulk delete for multiple selected rows
        indexes = self.table.table.selectedIndexes()
        rows = sorted({idx.row() for idx in indexes})
        if not rows:
            QMessageBox.information(self, "Delete Customer", "Select one or more customer rows to delete")
            return

        ids = []
        for r in rows:
            item = self.table.table.item(r, 0)
            if item:
                ids.append(item.text())

        if not ids:
            QMessageBox.information(self, "Delete Customer", "Could not determine selected customer ids")
            return

        if QMessageBox.question(self, "Delete Customer", f"Delete {len(ids)} customers? This cannot be undone.") != QMessageBox.StandardButton.Yes:
            return

        errors = []
        for cid in ids:
                    try:
                        # Use bulk-delete when multiple ids provided
                        if len(ids) > 1:
                            resp = asyncio.run(self.api_client.post("/api/customers/bulk-delete", json=ids))
                            if resp.status_code == 200:
                                failed = resp.json().get("failed", [])
                                if failed:
                                    errors.extend([f"{f}: failed" for f in failed])
                            else:
                                errors.append(f"bulk-delete failed: {resp.status_code} {resp.text}")
                            break
                        else:
                            response = asyncio.run(self.api_client.delete(f"/api/customers/{cid}"))
                            if response.status_code not in (200, 204):
                                errors.append(f"{cid}: {response.status_code} {response.text}")
                    except Exception as exc:
                        errors.append(str(exc))

        if errors:
            QMessageBox.warning(self, "Delete Customer", "Some deletes failed:\n" + "\n".join(errors))

        self.refresh()

    def load_ledger(self) -> None:
        customer_id = self.ledger_id_input.text().strip()
        if not customer_id.isdigit():
            QMessageBox.warning(self, "Customer Ledger", "Enter a valid numeric customer ID")
            return
        try:
            response = asyncio.run(self.api_client.get(f"/api/customers/{customer_id}/ledger"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Customer Ledger", str(exc))
            return

        self.ledger_summary.setText(
            f"Ledger debit: {data['total_debit']} | credit: {data['total_credit']} | balance: {data['current_balance']}"
        )

from __future__ import annotations

import os
from datetime import date

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton)

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class ExpensesModule(BaseModuleWidget):
    module_title = "Expenses"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        form_box = QGroupBox("Record Expense")
        form = QFormLayout(form_box)
        self.expense_no = QLineEdit()
        self.expense_no.setPlaceholderText("EXP-2026-0001")
        self.expense_account_id = QLineEdit()
        self.amount = QLineEdit()
        self.payment_method = QComboBox()
        self.payment_method.addItems(["cash", "bank"])
        self.bank_account_id = QLineEdit()
        self.bank_account_id.setPlaceholderText("Required when payment method is bank")
        self.description = QLineEdit()
        create_btn = QPushButton("Create Expense")
        create_btn.clicked.connect(self.create_expense)

        form.addRow("Expense No", self.expense_no)
        form.addRow("Expense Account ID", self.expense_account_id)
        form.addRow("Amount", self.amount)
        form.addRow("Payment Method", self.payment_method)
        form.addRow("Bank Account ID", self.bank_account_id)
        form.addRow("Description", self.description)
        form.addRow("", create_btn)
        self.configure_form_layout(form)

        actions = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.status_label = QLabel("Ready")
        actions.addWidget(reload_btn)
        actions.addWidget(self.status_label)
        actions.addStretch(1)

        self.layout().setSpacing(10)

        self.layout().addWidget(form_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch():
                resp = await self.api_client.get("/api/expenses")
                resp.raise_for_status()
                return resp.json()

            def _on_result(data):
                try:
                    rows = [
                        [
                            str(item["id"]),
                            item["expense_no"],
                            item["expense_date"],
                            str(item.get("account_id")),
                            str(item.get("amount")),
                            item["payment_method"],
                            str(item.get("bank_account_id") or ""),
                            item["description"] or "",
                        ]
                        for item in data
                    ]
                    self.table.set_rows(
                        [
                            "ID",
                            "No",
                            "Date",
                            "Account",
                            "Amount",
                            "Method",
                            "Bank",
                            "Description",
                        ],
                        rows,
                        stretch_columns={7},
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Expenses", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Expenses", str(exc))

            self.run_async(_async_fetch(), on_result=_on_result, on_error=_on_error)
            return

        def _do_fetch():
            resp = self.api_client.sync_get("/api/expenses")
            resp.raise_for_status()
            return resp.json()

        def _on_result(data):
            try:
                rows = [
                    [
                        str(item["id"]),
                        item["expense_no"],
                        item["expense_date"],
                        str(item.get("account_id")),
                        str(item.get("amount")),
                        item["payment_method"],
                        str(item.get("bank_account_id") or ""),
                        item["description"] or "",
                    ]
                    for item in data
                ]
                self.table.set_rows(
                    [
                        "ID",
                        "No",
                        "Date",
                        "Account",
                        "Amount",
                        "Method",
                        "Bank",
                        "Description",
                    ],
                    rows,
                    stretch_columns={7},
                )
            except Exception as exc:
                QMessageBox.warning(self, "Expenses", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Expenses", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

    def create_expense(self) -> None:
        method = self.payment_method.currentText()

        try:
            payload = {
                "expense_no": self.expense_no.text().strip(),
                "expense_date": date.today().isoformat(),
                "account_id": int(self.expense_account_id.text()),
                "amount": float(self.amount.text()),
                "payment_method": method,
                "bank_account_id": (
                    int(self.bank_account_id.text())
                    if self.bank_account_id.text().strip()
                    else None
                ),
                "description": self.description.text().strip() or None,
                "reference": None,
            }
        except ValueError:
            QMessageBox.warning(
                self,
                "Expenses",
                "Enter valid numeric account, amount and bank account IDs",
            )
            return

        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_create():
                resp = await self.api_client.post("/api/expenses", json=payload)
                resp.raise_for_status()
                return resp.json()

            def _on_result(data):
                try:
                    self.status_label.setText(f"Posted voucher: {data['voucher_no']}")
                except Exception:
                    pass
                self.expense_no.clear()
                self.expense_account_id.clear()
                self.amount.clear()
                self.bank_account_id.clear()
                self.description.clear()
                self.refresh()

            def _on_error(exc):
                QMessageBox.warning(self, "Create Expense", str(exc))

            self.run_async(_async_create(), on_result=_on_result, on_error=_on_error)
            return

        def _do_create():
            resp = self.api_client.sync_post("/api/expenses", json=payload)
            resp.raise_for_status()
            return resp.json()

        def _on_result(data):
            try:
                self.status_label.setText(f"Posted voucher: {data['voucher_no']}")
            except Exception:
                pass
            self.expense_no.clear()
            self.expense_account_id.clear()
            self.amount.clear()
            self.bank_account_id.clear()
            self.description.clear()
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Create Expense", str(exc))

        self.run_blocking(_do_create, on_result=_on_result, on_error=_on_error)

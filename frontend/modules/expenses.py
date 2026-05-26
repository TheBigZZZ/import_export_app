from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

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

        actions = QHBoxLayout()
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.status_label = QLabel("Ready")
        actions.addWidget(reload_btn)
        actions.addWidget(self.status_label)
        actions.addStretch(1)

        self.layout().addWidget(form_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/expenses"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Expenses", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["expense_no"],
                item["expense_date"],
                str(item["account_id"]),
                str(item["amount"]),
                item["payment_method"],
                str(item["bank_account_id"] or ""),
                item["description"] or "",
            ]
            for item in data
        ]
        self.table.set_rows(["ID", "No", "Date", "Account", "Amount", "Method", "Bank", "Description"], rows)

    def create_expense(self) -> None:
        method = self.payment_method.currentText()

        try:
            payload = {
                "expense_no": self.expense_no.text().strip(),
                "expense_date": date.today().isoformat(),
                "account_id": int(self.expense_account_id.text()),
                "amount": float(self.amount.text()),
                "payment_method": method,
                "bank_account_id": int(self.bank_account_id.text()) if self.bank_account_id.text().strip() else None,
                "description": self.description.text().strip() or None,
                "reference": None,
            }
        except ValueError:
            QMessageBox.warning(self, "Expenses", "Enter valid numeric account, amount and bank account IDs")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/expenses", json=payload))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Create Expense", str(exc))
            return

        self.status_label.setText(f"Posted voucher: {data['voucher_no']}")
        self.expense_no.clear()
        self.expense_account_id.clear()
        self.amount.clear()
        self.bank_account_id.clear()
        self.description.clear()
        self.refresh()

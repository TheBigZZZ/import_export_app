from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox, QPushButton

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class BanksModule(BaseModuleWidget):
    module_title = "Banks"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        create_box = QGroupBox("Add Bank")
        create_form = QFormLayout(create_box)
        self.bank_name = QLineEdit()
        self.account_name = QLineEdit()
        self.account_number = QLineEdit()
        self.opening_balance = QLineEdit("0")
        add_btn = QPushButton("Create Bank")
        add_btn.clicked.connect(self.create_bank)

        create_form.addRow("Bank", self.bank_name)
        create_form.addRow("Account Name", self.account_name)
        create_form.addRow("Account Number", self.account_number)
        create_form.addRow("Opening Balance", self.opening_balance)
        create_form.addRow("", add_btn)
        self.configure_form_layout(create_form)

        transfer_box = QGroupBox("Bank Transfer")
        transfer_form = QFormLayout(transfer_box)
        self.from_id = QLineEdit()
        self.to_id = QLineEdit()
        self.transfer_amount = QLineEdit()
        transfer_btn = QPushButton("Transfer")
        transfer_btn.clicked.connect(self.transfer)
        transfer_form.addRow("From Bank ID", self.from_id)
        transfer_form.addRow("To Bank ID", self.to_id)
        transfer_form.addRow("Amount", self.transfer_amount)
        transfer_form.addRow("", transfer_btn)
        self.configure_form_layout(transfer_form)

        top = QHBoxLayout()
        top.addWidget(create_box)
        top.addWidget(transfer_box)

        self.layout().setSpacing(10)

        self.layout().addLayout(top)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/banks"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Banks", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["bank_name"],
                item["account_name"],
                item["account_number"],
                str(item["current_balance"]),
                item["currency"],
            ]
            for item in data
        ]
        self.table.set_rows(["ID", "Bank", "Account", "Number", "Balance", "Currency"], rows, stretch_columns={2})

    def create_bank(self) -> None:
        try:
            balance = float(self.opening_balance.text())
        except ValueError:
            QMessageBox.warning(self, "Banks", "Opening balance must be numeric")
            return
        payload = {
            "bank_name": self.bank_name.text().strip(),
            "account_name": self.account_name.text().strip(),
            "account_number": self.account_number.text().strip(),
            "opening_balance": balance,
        }
        try:
            response = asyncio.run(self.api_client.post("/api/banks", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Bank", str(exc))
            return
        self.refresh()

    def transfer(self) -> None:
        try:
            payload = {
                "from_bank_account_id": int(self.from_id.text()),
                "to_bank_account_id": int(self.to_id.text()),
                "amount": float(self.transfer_amount.text()),
                "transaction_date": date.today().isoformat(),
            }
        except ValueError:
            QMessageBox.warning(self, "Transfer", "Enter valid numeric values")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/banks/transfer", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Transfer", str(exc))
            return
        self.transfer_amount.clear()
        self.refresh()

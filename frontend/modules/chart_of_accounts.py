from __future__ import annotations

import asyncio

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class ChartOfAccountsModule(BaseModuleWidget):
    module_title = "Chart Of Accounts"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        form_box = QGroupBox("Add Account")
        form = QFormLayout(form_box)
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.type_input = QComboBox()
        self.type_input.addItems(["asset", "liability", "equity", "income", "expense"])
        self.parent_input = QLineEdit()
        self.parent_input.setPlaceholderText("Optional parent account ID")
        self.add_button = QPushButton("Create Account")
        self.add_button.clicked.connect(self.create_account)

        form.addRow("Code", self.code_input)
        form.addRow("Name", self.name_input)
        form.addRow("Type", self.type_input)
        form.addRow("Parent ID", self.parent_input)
        form.addRow("", self.add_button)
        self.configure_form_layout(form)

        tree_refresh = QPushButton("Reload Tree")
        tree_refresh.clicked.connect(self.load_tree)
        self.tree_label = QLabel("Tree: not loaded")

        extra = QHBoxLayout()
        extra.addWidget(tree_refresh)
        extra.addWidget(self.tree_label)
        extra.addStretch(1)

        self.layout().setSpacing(10)

        self.layout().addWidget(form_box)
        self.layout().addLayout(extra)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        self.load_accounts()

    def load_accounts(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/accounts"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Accounts", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["account_code"],
                item["account_name"],
                item["account_type"],
                str(item["parent_id"] or ""),
                "Yes" if item["is_system"] else "No",
            ]
            for item in data
        ]
        self.table.set_rows(["ID", "Code", "Name", "Type", "Parent", "System"], rows, stretch_columns={2})

    def load_tree(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/accounts/tree"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Accounts Tree", str(exc))
            return
        self.tree_label.setText(f"Tree roots: {len(data)}")

    def create_account(self) -> None:
        payload = {
            "account_code": self.code_input.text().strip(),
            "account_name": self.name_input.text().strip(),
            "account_type": self.type_input.currentText(),
            "parent_id": int(self.parent_input.text()) if self.parent_input.text().strip() else None,
            "is_system": False,
        }
        try:
            response = asyncio.run(self.api_client.post("/api/accounts", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Account", str(exc))
            return

        self.code_input.clear()
        self.name_input.clear()
        self.parent_input.clear()
        self.refresh()

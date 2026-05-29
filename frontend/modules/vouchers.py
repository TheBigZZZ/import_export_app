from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLineEdit, QMessageBox, QPushButton)

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class VouchersModule(BaseModuleWidget):
    module_title = "Vouchers"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        form_box = QGroupBox("Create Voucher (2 Lines)")
        form = QFormLayout(form_box)
        self.v_type = QComboBox()
        self.v_type.addItems(["CPV", "CRV", "BPV", "BRV", "JV", "Contra"])
        self.debit_account = QLineEdit("1")
        self.credit_account = QLineEdit("2")
        self.amount = QLineEdit()
        self.description = QLineEdit()
        self.create_button = QPushButton("Post Voucher")
        self.create_button.clicked.connect(self.create_voucher)

        form.addRow("Type", self.v_type)
        form.addRow("Debit Account ID", self.debit_account)
        form.addRow("Credit Account ID", self.credit_account)
        form.addRow("Amount", self.amount)
        form.addRow("Description", self.description)
        form.addRow("", self.create_button)
        self.configure_form_layout(form)

        actions = QHBoxLayout()
        reload_button = QPushButton("Reload")
        reload_button.clicked.connect(self.refresh)
        actions.addWidget(reload_button)
        actions.addStretch(1)

        self.layout().setSpacing(10)

        self.layout().addWidget(form_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        def _do_fetch():
            resp = self.api_client.sync_get("/api/vouchers")
            resp.raise_for_status()
            return resp.json()["items"]

        def _on_result(data):
            try:
                rows = []
                for voucher in data:
                    debit_total = sum(float(line["debit"]) for line in voucher["lines"])
                    credit_total = sum(
                        float(line["credit"]) for line in voucher["lines"]
                    )
                    rows.append(
                        [
                            voucher["voucher_no"],
                            voucher["voucher_type"],
                            voucher["transaction_date"],
                            f"{debit_total:.2f}",
                            f"{credit_total:.2f}",
                            str(len(voucher["lines"])),
                        ]
                    )
                self.table.set_rows(
                    ["Voucher No", "Type", "Date", "Debit", "Credit", "Lines"],
                    rows,
                    stretch_columns={0},
                )
            except Exception as exc:
                QMessageBox.warning(self, "Vouchers", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Vouchers", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

    def create_voucher(self) -> None:
        try:
            amount = float(self.amount.text())
            debit_acc = int(self.debit_account.text())
            credit_acc = int(self.credit_account.text())
        except ValueError:
            QMessageBox.warning(self, "Voucher", "Enter valid numeric values")
            return

        payload = {
            "voucher_type": self.v_type.currentText(),
            "transaction_date": date.today().isoformat(),
            "description": self.description.text().strip() or None,
            "lines": [
                {
                    "account_id": debit_acc,
                    "debit": amount,
                    "credit": 0,
                    "description": self.description.text().strip(),
                },
                {
                    "account_id": credit_acc,
                    "debit": 0,
                    "credit": amount,
                    "description": self.description.text().strip(),
                },
            ],
        }

        def _do_post():
            resp = self.api_client.sync_post("/api/vouchers", json=payload)
            resp.raise_for_status()
            return resp

        def _on_result(_):
            self.amount.clear()
            self.description.clear()
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Post Voucher", str(exc))

        self.run_blocking(_do_post, on_result=_on_result, on_error=_on_error)

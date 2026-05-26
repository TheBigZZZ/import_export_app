from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class SalesModule(BaseModuleWidget):
    module_title = "Sales"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        create_box = QGroupBox("Create Sales Invoice")
        form = QFormLayout(create_box)
        self.invoice_no = QLineEdit()
        self.customer_id = QLineEdit()
        self.product_id = QLineEdit()
        self.quantity = QLineEdit()
        self.unit_price = QLineEdit()
        self.cost_price = QLineEdit("0")
        create_btn = QPushButton("Create Draft Invoice")
        create_btn.clicked.connect(self.create_invoice)
        form.addRow("Invoice No", self.invoice_no)
        form.addRow("Customer ID", self.customer_id)
        form.addRow("Product ID", self.product_id)
        form.addRow("Quantity", self.quantity)
        form.addRow("Unit Price", self.unit_price)
        form.addRow("Cost Price", self.cost_price)
        form.addRow("", create_btn)

        actions = QHBoxLayout()
        self.post_invoice_id = QLineEdit()
        self.post_invoice_id.setPlaceholderText("Invoice ID to post")
        post_btn = QPushButton("Post Invoice")
        post_btn.clicked.connect(self.post_invoice_action)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.result_label = QLabel("Ready")
        actions.addWidget(self.post_invoice_id)
        actions.addWidget(post_btn)
        actions.addWidget(reload_btn)
        actions.addWidget(self.result_label)
        actions.addStretch(1)

        self.layout().addWidget(create_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/sales"))
            response.raise_for_status()
            rows_data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Sales", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["invoice_no"],
                str(item["customer_id"]),
                str(item["total_amount"]),
                item["status"],
            ]
            for item in rows_data
        ]
        self.table.set_rows(["ID", "Invoice", "Customer", "Total", "Status"], rows)

    def create_invoice(self) -> None:
        try:
            payload = {
                "invoice_no": self.invoice_no.text().strip(),
                "customer_id": int(self.customer_id.text()),
                "invoice_date": date.today().isoformat(),
                "items": [
                    {
                        "product_id": int(self.product_id.text()),
                        "quantity": float(self.quantity.text()),
                        "unit_price": float(self.unit_price.text()),
                        "cost_price": float(self.cost_price.text()),
                    }
                ],
            }
        except ValueError:
            QMessageBox.warning(self, "Sales", "Enter valid numeric customer/product/quantity/prices")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/sales", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Sales Invoice", str(exc))
            return
        self.refresh()

    def post_invoice_action(self) -> None:
        invoice_id = self.post_invoice_id.text().strip()
        if not invoice_id.isdigit():
            QMessageBox.warning(self, "Sales", "Enter a valid invoice ID")
            return
        try:
            response = asyncio.run(self.api_client.post(f"/api/sales/{invoice_id}/post", json={}))
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Post Sales Invoice", str(exc))
            return
        self.result_label.setText(f"Posted voucher: {payload['voucher_no']}")
        self.refresh()

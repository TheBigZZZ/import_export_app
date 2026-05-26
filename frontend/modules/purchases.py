from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class PurchasesModule(BaseModuleWidget):
    module_title = "Purchases"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        create_box = QGroupBox("Create Purchase Order")
        form = QFormLayout(create_box)
        self.po_no = QLineEdit()
        self.supplier_id = QLineEdit()
        self.product_id = QLineEdit()
        self.quantity = QLineEdit()
        self.unit_price = QLineEdit()
        create_btn = QPushButton("Create Order")
        create_btn.clicked.connect(self.create_order)
        form.addRow("PO No", self.po_no)
        form.addRow("Supplier ID", self.supplier_id)
        form.addRow("Product ID", self.product_id)
        form.addRow("Quantity", self.quantity)
        form.addRow("Unit Price", self.unit_price)
        form.addRow("", create_btn)

        actions = QHBoxLayout()
        self.post_order_id = QLineEdit()
        self.post_order_id.setPlaceholderText("Order ID to post")
        post_btn = QPushButton("Post Order")
        post_btn.clicked.connect(self.post_order_action)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.result_label = QLabel("Ready")
        actions.addWidget(self.post_order_id)
        actions.addWidget(post_btn)
        actions.addWidget(reload_btn)
        actions.addWidget(self.result_label)
        actions.addStretch(1)

        self.layout().addWidget(create_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/purchases"))
            response.raise_for_status()
            rows_data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Purchases", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["po_no"],
                str(item["supplier_id"]),
                str(item["total_amount"]),
                item["status"],
            ]
            for item in rows_data
        ]
        self.table.set_rows(["ID", "PO", "Supplier", "Total", "Status"], rows)

    def create_order(self) -> None:
        try:
            payload = {
                "po_no": self.po_no.text().strip(),
                "supplier_id": int(self.supplier_id.text()),
                "order_date": date.today().isoformat(),
                "items": [
                    {
                        "product_id": int(self.product_id.text()),
                        "quantity": float(self.quantity.text()),
                        "unit_price": float(self.unit_price.text()),
                    }
                ],
            }
        except ValueError:
            QMessageBox.warning(self, "Purchases", "Enter valid numeric supplier/product/quantity/price")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/purchases", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Purchase", str(exc))
            return
        self.refresh()

    def post_order_action(self) -> None:
        order_id = self.post_order_id.text().strip()
        if not order_id.isdigit():
            QMessageBox.warning(self, "Purchases", "Enter a valid order ID")
            return
        try:
            response = asyncio.run(self.api_client.post(f"/api/purchases/{order_id}/post", json={}))
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Post Purchase", str(exc))
            return
        self.result_label.setText(f"Posted voucher: {payload['voucher_no']}")
        self.refresh()

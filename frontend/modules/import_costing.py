from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class ImportCostingModule(BaseModuleWidget):
    module_title = "Import Costing"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        create_box = QGroupBox("Create Import Shipment")
        form = QFormLayout(create_box)
        self.supplier_id = QLineEdit()
        self.lc_no = QLineEdit()
        self.product_id = QLineEdit()
        self.quantity = QLineEdit()
        self.unit_cost = QLineEdit("0")
        self.fob_cost = QLineEdit("0")
        self.freight_cost = QLineEdit("0")
        create_btn = QPushButton("Create Shipment")
        create_btn.clicked.connect(self.create_shipment)
        form.addRow("Supplier ID", self.supplier_id)
        form.addRow("LC No", self.lc_no)
        form.addRow("Product ID", self.product_id)
        form.addRow("Quantity", self.quantity)
        form.addRow("Unit Landed Cost", self.unit_cost)
        form.addRow("FOB Cost", self.fob_cost)
        form.addRow("Freight Cost", self.freight_cost)
        form.addRow("", create_btn)

        actions = QHBoxLayout()
        self.post_shipment_id = QLineEdit()
        self.post_shipment_id.setPlaceholderText("Shipment ID to post")
        post_btn = QPushButton("Post Shipment")
        post_btn.clicked.connect(self.post_shipment_action)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.result_label = QLabel("Ready")
        actions.addWidget(self.post_shipment_id)
        actions.addWidget(post_btn)
        actions.addWidget(reload_btn)
        actions.addWidget(self.result_label)
        actions.addStretch(1)

        self.layout().addWidget(create_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/imports"))
            response.raise_for_status()
            rows_data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Imports", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["lc_no"] or "",
                str(item["supplier_id"]),
                str(item["total_landed_cost"]),
                item["status"],
            ]
            for item in rows_data
        ]
        self.table.set_rows(["ID", "LC", "Supplier", "Landed Cost", "Status"], rows)

    def create_shipment(self) -> None:
        try:
            payload = {
                "supplier_id": int(self.supplier_id.text()),
                "lc_no": self.lc_no.text().strip() or None,
                "shipment_date": date.today().isoformat(),
                "arrival_date": date.today().isoformat(),
                "fob_cost": float(self.fob_cost.text()),
                "freight_cost": float(self.freight_cost.text()),
                "items": [
                    {
                        "product_id": int(self.product_id.text()),
                        "quantity": float(self.quantity.text()),
                        "unit": "pcs",
                        "fob_unit_cost": float(self.unit_cost.text()),
                        "total_landed_unit_cost": float(self.unit_cost.text()),
                    }
                ],
            }
        except ValueError:
            QMessageBox.warning(self, "Imports", "Enter valid numeric supplier/product/quantity/cost values")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/imports", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Import Shipment", str(exc))
            return
        self.refresh()

    def post_shipment_action(self) -> None:
        shipment_id = self.post_shipment_id.text().strip()
        if not shipment_id.isdigit():
            QMessageBox.warning(self, "Imports", "Enter a valid shipment ID")
            return
        try:
            response = asyncio.run(self.api_client.post(f"/api/imports/{shipment_id}/post", json={}))
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Post Import Shipment", str(exc))
            return
        self.result_label.setText(f"Posted voucher: {payload['voucher_no']}")
        self.refresh()

from __future__ import annotations

import asyncio
from datetime import date

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class ProductsModule(BaseModuleWidget):
    module_title = "Products"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()

        create_box = QGroupBox("Add Product")
        create_form = QFormLayout(create_box)
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.unit_input = QLineEdit("pcs")
        self.purchase_price_input = QLineEdit("0")
        self.selling_price_input = QLineEdit("0")
        create_btn = QPushButton("Create Product")
        create_btn.clicked.connect(self.create_product)
        create_form.addRow("Code", self.code_input)
        create_form.addRow("Name", self.name_input)
        create_form.addRow("Unit", self.unit_input)
        create_form.addRow("Purchase Price", self.purchase_price_input)
        create_form.addRow("Selling Price", self.selling_price_input)
        create_form.addRow("", create_btn)

        movement_box = QGroupBox("Stock Movement")
        movement_form = QFormLayout(movement_box)
        self.product_id_input = QLineEdit()
        self.movement_type = QComboBox()
        self.movement_type.addItems(["in", "out", "adjustment"])
        self.quantity_input = QLineEdit()
        self.unit_cost_input = QLineEdit("0")
        self.doc_no_input = QLineEdit()
        self.status_input = QLineEdit("posted")
        post_btn = QPushButton("Post Movement")
        post_btn.clicked.connect(self.post_movement)
        movement_form.addRow("Product ID", self.product_id_input)
        movement_form.addRow("Type", self.movement_type)
        movement_form.addRow("Quantity", self.quantity_input)
        movement_form.addRow("Unit Cost", self.unit_cost_input)
        movement_form.addRow("Document No", self.doc_no_input)
        movement_form.addRow("Document Status", self.status_input)
        movement_form.addRow("", post_btn)

        top = QHBoxLayout()
        top.addWidget(create_box)
        top.addWidget(movement_box)

        actions = QHBoxLayout()
        self.ledger_id_input = QLineEdit()
        self.ledger_id_input.setPlaceholderText("Product ID for ledger")
        ledger_btn = QPushButton("Load Stock Ledger")
        ledger_btn.clicked.connect(self.load_ledger)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.refresh)
        self.ledger_summary = QLabel("Stock ledger: not loaded")
        actions.addWidget(self.ledger_id_input)
        actions.addWidget(ledger_btn)
        actions.addWidget(reload_btn)
        actions.addWidget(self.ledger_summary)
        actions.addStretch(1)

        self.layout().addLayout(top)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/products"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Products", str(exc))
            return

        rows = [
            [
                str(item["id"]),
                item["product_code"],
                item["product_name"],
                item["unit"],
                str(item["current_stock"]),
                str(item["selling_price"]),
            ]
            for item in data
        ]
        self.table.set_rows(["ID", "Code", "Name", "Unit", "Stock", "Sell Price"], rows)

    def create_product(self) -> None:
        try:
            purchase_price = float(self.purchase_price_input.text())
            selling_price = float(self.selling_price_input.text())
        except ValueError:
            QMessageBox.warning(self, "Products", "Prices must be numeric")
            return

        payload = {
            "product_code": self.code_input.text().strip(),
            "product_name": self.name_input.text().strip(),
            "unit": self.unit_input.text().strip() or "pcs",
            "purchase_price": purchase_price,
            "selling_price": selling_price,
        }
        try:
            response = asyncio.run(self.api_client.post("/api/products", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Create Product", str(exc))
            return

        self.code_input.clear()
        self.name_input.clear()
        self.purchase_price_input.setText("0")
        self.selling_price_input.setText("0")
        self.refresh()

    def post_movement(self) -> None:
        try:
            payload = {
                "product_id": int(self.product_id_input.text()),
                "movement_type": self.movement_type.currentText(),
                "quantity": float(self.quantity_input.text()),
                "movement_date": date.today().isoformat(),
                "unit_cost": float(self.unit_cost_input.text()),
                "document_no": self.doc_no_input.text().strip() or None,
                "document_status": self.status_input.text().strip() or "posted",
            }
        except ValueError:
            QMessageBox.warning(self, "Stock Movement", "Enter valid numeric product, quantity, and cost")
            return

        try:
            response = asyncio.run(self.api_client.post("/api/products/movements", json=payload))
            response.raise_for_status()
        except Exception as exc:
            QMessageBox.warning(self, "Stock Movement", str(exc))
            return

        self.quantity_input.clear()
        self.unit_cost_input.setText("0")
        self.doc_no_input.clear()
        self.refresh()

    def load_ledger(self) -> None:
        product_id = self.ledger_id_input.text().strip()
        if not product_id.isdigit():
            QMessageBox.warning(self, "Stock Ledger", "Enter a valid numeric product ID")
            return
        try:
            response = asyncio.run(self.api_client.get(f"/api/products/{product_id}/ledger"))
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Stock Ledger", str(exc))
            return

        self.ledger_summary.setText(f"Current stock: {data['current_stock']} | Ledger lines: {len(data['entries'])}")

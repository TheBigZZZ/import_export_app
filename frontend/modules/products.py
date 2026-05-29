from __future__ import annotations

import os
from datetime import date

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton)

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
        self.configure_form_layout(create_form)

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
        self.configure_form_layout(movement_form)

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

        self.layout().setSpacing(10)

        self.layout().addLayout(top)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch():
                resp = await self.api_client.get("/api/products")
                resp.raise_for_status()
                return resp.json()

            def _on_result(data):
                try:
                    rows = [
                        [
                            str(item["id"]),
                            item["product_code"],
                            item["product_name"],
                            item["unit"],
                            str(item.get("current_stock")),
                            str(item.get("selling_price")),
                        ]
                        for item in data
                    ]
                    self.table.set_rows(
                        ["ID", "Code", "Name", "Unit", "Stock", "Sell Price"],
                        rows,
                        stretch_columns={2},
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Products", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Products", str(exc))

            self.run_async(_async_fetch(), on_result=_on_result, on_error=_on_error)
            return

        def _do_fetch():
            resp = self.api_client.sync_get("/api/products")
            resp.raise_for_status()
            return resp.json()

        def _on_result(data):
            try:
                rows = [
                    [
                        str(item["id"]),
                        item["product_code"],
                        item["product_name"],
                        item["unit"],
                        str(item.get("current_stock")),
                        str(item.get("selling_price")),
                    ]
                    for item in data
                ]
                self.table.set_rows(
                    ["ID", "Code", "Name", "Unit", "Stock", "Sell Price"],
                    rows,
                    stretch_columns={2},
                )
            except Exception as exc:
                QMessageBox.warning(self, "Products", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Products", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

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

        def _do_create():
            resp = self.api_client.sync_post("/api/products", json=payload)
            resp.raise_for_status()
            return resp

        def _on_result(_):
            self.code_input.clear()
            self.name_input.clear()
            self.purchase_price_input.setText("0")
            self.selling_price_input.setText("0")
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Create Product", str(exc))

        self.run_blocking(_do_create, on_result=_on_result, on_error=_on_error)

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
            QMessageBox.warning(
                self,
                "Stock Movement",
                "Enter valid numeric product, quantity, and cost",
            )
            return

        def _do_post():
            resp = self.api_client.sync_post("/api/products/movements", json=payload)
            resp.raise_for_status()
            return resp

        def _on_result(_):
            self.quantity_input.clear()
            self.unit_cost_input.setText("0")
            self.doc_no_input.clear()
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Stock Movement", str(exc))

        self.run_blocking(_do_post, on_result=_on_result, on_error=_on_error)

    def load_ledger(self) -> None:
        product_id = self.ledger_id_input.text().strip()
        if not product_id.isdigit():
            QMessageBox.warning(
                self, "Stock Ledger", "Enter a valid numeric product ID"
            )
            return
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_load():
                resp = await self.api_client.get(f"/api/products/{product_id}/ledger")
                resp.raise_for_status()
                return resp.json()

            def _on_result(data):
                try:
                    self.ledger_summary.setText(
                        f"Current stock: {data['current_stock']} | Ledger lines: {len(data['entries'])}"
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Stock Ledger", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Stock Ledger", str(exc))

            self.run_async(_async_load(), on_result=_on_result, on_error=_on_error)
            return

        def _do_load():
            resp = self.api_client.sync_get(f"/api/products/{product_id}/ledger")
            resp.raise_for_status()
            return resp.json()

        def _on_result(data):
            try:
                self.ledger_summary.setText(
                    f"Current stock: {data['current_stock']} | Ledger lines: {len(data['entries'])}"
                )
            except Exception as exc:
                QMessageBox.warning(self, "Stock Ledger", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Stock Ledger", str(exc))

        self.run_blocking(_do_load, on_result=_on_result, on_error=_on_error)

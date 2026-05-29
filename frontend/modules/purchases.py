from __future__ import annotations

import os
from datetime import date

from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton)

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
        self.configure_form_layout(form)

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

        self.layout().setSpacing(10)

        self.layout().addWidget(create_box)
        self.layout().addLayout(actions)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch():
                resp = await self.api_client.get("/api/purchases")
                resp.raise_for_status()
                return resp.json()

            def _on_result(rows_data):
                try:
                    rows = [
                        [
                            str(item["id"]),
                            item["po_no"],
                            str(item["supplier_id"]),
                            str(item.get("total_amount")),
                            item["status"],
                        ]
                        for item in rows_data
                    ]
                    self.table.set_rows(
                        ["ID", "PO", "Supplier", "Total", "Status"],
                        rows,
                        stretch_columns={1, 2},
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Purchases", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Purchases", str(exc))

            self.run_async(_async_fetch(), on_result=_on_result, on_error=_on_error)
            return

        def _do_fetch():
            resp = self.api_client.sync_get("/api/purchases")
            resp.raise_for_status()
            return resp.json()

        def _on_result(rows_data):
            try:
                rows = [
                    [
                        str(item["id"]),
                        item["po_no"],
                        str(item["supplier_id"]),
                        str(item.get("total_amount")),
                        item["status"],
                    ]
                    for item in rows_data
                ]
                self.table.set_rows(
                    ["ID", "PO", "Supplier", "Total", "Status"],
                    rows,
                    stretch_columns={1, 2},
                )
            except Exception as exc:
                QMessageBox.warning(self, "Purchases", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Purchases", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

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
            QMessageBox.warning(
                self, "Purchases", "Enter valid numeric supplier/product/quantity/price"
            )
            return

        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_create():
                resp = await self.api_client.post("/api/purchases", json=payload)
                resp.raise_for_status()
                return resp

            def _on_result(_):
                self.refresh()

            def _on_error(exc):
                QMessageBox.warning(self, "Create Purchase", str(exc))

            self.run_async(_async_create(), on_result=_on_result, on_error=_on_error)
            return

        def _do_create():
            resp = self.api_client.sync_post("/api/purchases", json=payload)
            resp.raise_for_status()
            return resp

        def _on_result(_):
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Create Purchase", str(exc))

        self.run_blocking(_do_create, on_result=_on_result, on_error=_on_error)

    def post_order_action(self) -> None:
        order_id = self.post_order_id.text().strip()
        if not order_id.isdigit():
            QMessageBox.warning(self, "Purchases", "Enter a valid order ID")
            return
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_post():
                resp = await self.api_client.post(
                    f"/api/purchases/{order_id}/post", json={}
                )
                resp.raise_for_status()
                return resp.json()

            def _on_result(payload):
                try:
                    self.result_label.setText(
                        f"Posted voucher: {payload['voucher_no']}"
                    )
                except Exception:
                    pass
                self.refresh()

            def _on_error(exc):
                QMessageBox.warning(self, "Post Purchase", str(exc))

            self.run_async(_async_post(), on_result=_on_result, on_error=_on_error)
            return

        def _do_post():
            resp = self.api_client.sync_post(f"/api/purchases/{order_id}/post", json={})
            resp.raise_for_status()
            return resp.json()

        def _on_result(payload):
            try:
                self.result_label.setText(f"Posted voucher: {payload['voucher_no']}")
            except Exception:
                pass
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Post Purchase", str(exc))

        self.run_blocking(_do_post, on_result=_on_result, on_error=_on_error)

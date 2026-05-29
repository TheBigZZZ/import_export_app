from __future__ import annotations

import os
from datetime import date

from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton)

from .base import BaseModuleWidget


class CashRegisterModule(BaseModuleWidget):
    module_title = "Cash Register"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        cash_box = QGroupBox("Cash Receipt / Payment")
        form = QFormLayout(cash_box)
        self.direction = QComboBox()
        self.direction.addItems(["in", "out"])
        self.account_id = QLineEdit("1")
        self.amount = QLineEdit()
        self.description = QLineEdit()
        post_btn = QPushButton("Post Cash Entry")
        post_btn.clicked.connect(self.post_cash)
        form.addRow("Direction", self.direction)
        form.addRow("Counter Account ID", self.account_id)
        form.addRow("Amount", self.amount)
        form.addRow("Description", self.description)
        form.addRow("", post_btn)

        close_box = QGroupBox("Daily Closing")
        close_form = QFormLayout(close_box)
        self.closing_label = QLabel(
            "Opening: 0.00 | Receipts: 0.00 | Payments: 0.00 | Closing: 0.00"
        )
        close_btn = QPushButton("Refresh Daily Closing")
        close_btn.clicked.connect(self.refresh)
        close_form.addRow(self.closing_label)
        close_form.addRow(close_btn)

        top = QHBoxLayout()
        top.addWidget(cash_box)
        top.addWidget(close_box)
        self.layout().addLayout(top)

    def refresh(self) -> None:
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch():
                resp = await self.api_client.get(
                    "/api/cash/daily-closing",
                    params={"for_date": date.today().isoformat()},
                )
                resp.raise_for_status()
                return resp.json()

            def _on_result(payload):
                try:
                    self.closing_label.setText(
                        "Opening: {opening} | Receipts: {receipts} | Payments: {payments} | Closing: {closing}".format(
                            **payload
                        )
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Cash Closing", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Cash Closing", str(exc))

            self.run_async(_async_fetch(), on_result=_on_result, on_error=_on_error)
            return

        def _do_fetch():
            resp = self.api_client.sync_get(
                "/api/cash/daily-closing", params={"for_date": date.today().isoformat()}
            )
            resp.raise_for_status()
            return resp.json()

        def _on_result(payload):
            try:
                self.closing_label.setText(
                    "Opening: {opening} | Receipts: {receipts} | Payments: {payments} | Closing: {closing}".format(
                        **payload
                    )
                )
            except Exception as exc:
                QMessageBox.warning(self, "Cash Closing", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Cash Closing", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

    def post_cash(self) -> None:
        try:
            payload = {
                "transaction_date": date.today().isoformat(),
                "amount": float(self.amount.text()),
                "direction": self.direction.currentText(),
                "account_id": int(self.account_id.text()),
                "description": self.description.text().strip() or None,
            }
        except ValueError:
            QMessageBox.warning(self, "Cash", "Enter valid numeric amount/account")
            return

        def _do_post():
            resp = self.api_client.sync_post("/api/cash", json=payload)
            resp.raise_for_status()
            return resp

        def _on_result(_):
            self.amount.clear()
            self.description.clear()
            self.refresh()

        def _on_error(exc):
            QMessageBox.warning(self, "Cash", str(exc))

        self.run_blocking(_do_post, on_result=_on_result, on_error=_on_error)

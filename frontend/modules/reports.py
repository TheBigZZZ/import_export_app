from __future__ import annotations

import csv
import os
from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton)

from ..widgets.data_table import DataTable
from .base import BaseModuleWidget


class ReportsModule(BaseModuleWidget):
    module_title = "Reports"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        self.table = DataTable()
        self.summary = QLabel("Select a report and click Load")
        self.current_headers: list[str] = []
        self.current_rows: list[list[str]] = []

        actions = QHBoxLayout()
        self.report_select = QComboBox()
        self.report_select.addItem("Trial Balance", "/api/reports/trial-balance")
        self.report_select.addItem("Stock Position", "/api/reports/stock-position")
        self.report_select.addItem("Profit & Loss", "/api/reports/profit-loss")
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.refresh)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        actions.addWidget(self.report_select)
        actions.addWidget(load_btn)
        actions.addWidget(export_btn)
        actions.addStretch(1)

        self.layout().setSpacing(10)

        self.layout().addLayout(actions)
        self.layout().addWidget(self.summary)
        self.layout().addWidget(self.table)

    def refresh(self) -> None:
        endpoint = self.report_select.currentData()
        if not endpoint:
            return
        if os.environ.get("TRADEDESK_USE_QTASYNCIO"):

            async def _async_fetch():
                resp = await self.api_client.get(endpoint)
                resp.raise_for_status()
                return resp.json()

            def _on_result(payload):
                try:
                    title = self.report_select.currentText()
                    if title == "Trial Balance":
                        rows = payload.get("rows", [])
                        self.current_headers = [
                            "Account ID",
                            "Code",
                            "Name",
                            "Debit",
                            "Credit",
                        ]
                        self.current_rows = [
                            [
                                str(row["account_id"]),
                                row["account_code"],
                                row["account_name"],
                                str(row["debit"]),
                                str(row["credit"]),
                            ]
                            for row in rows
                        ]
                        total_debit = payload.get("total_debit")
                        total_credit = payload.get("total_credit")
                        is_balanced = payload.get("is_balanced")
                        self.summary.setText(
                            (
                                "Total Debit: "
                                + str(total_debit)
                                + " | Total Credit: "
                                + str(total_credit)
                                + " | Balanced: "
                                + str(is_balanced)
                            )
                        )
                    elif title == "Stock Position":
                        rows = payload.get("rows", [])
                        self.current_headers = [
                            "Product ID",
                            "Code",
                            "Name",
                            "Stock",
                            "Unit Cost",
                            "Value",
                        ]
                        self.current_rows = [
                            [
                                str(row["product_id"]),
                                row["product_code"],
                                row["product_name"],
                                str(row["current_stock"]),
                                str(row["unit_cost"]),
                                str(row["stock_value"]),
                            ]
                            for row in rows
                        ]
                        self.summary.setText(
                            f"Total Stock Value: {payload.get('total_stock_value')}"
                        )
                    else:
                        self.current_headers = ["Metric", "Amount"]
                        self.current_rows = [
                            ["Income", str(payload.get("income_total"))],
                            ["Expenses", str(payload.get("expense_total"))],
                            ["Net Profit", str(payload.get("net_profit"))],
                        ]
                        self.summary.setText("Profit & Loss Summary")

                    self.table.set_rows(self.current_headers, self.current_rows)
                except Exception as exc:
                    QMessageBox.warning(self, "Reports", str(exc))

            def _on_error(exc):
                QMessageBox.warning(self, "Reports", str(exc))

            self.run_async(_async_fetch(), on_result=_on_result, on_error=_on_error)
            return

        def _do_fetch():
            resp = self.api_client.sync_get(endpoint)
            resp.raise_for_status()
            return resp.json()

        def _on_result(payload):
            try:
                title = self.report_select.currentText()
                if title == "Trial Balance":
                    rows = payload.get("rows", [])
                    self.current_headers = [
                        "Account ID",
                        "Code",
                        "Name",
                        "Debit",
                        "Credit",
                    ]
                    self.current_rows = [
                        [
                            str(row["account_id"]),
                            row["account_code"],
                            row["account_name"],
                            str(row["debit"]),
                            str(row["credit"]),
                        ]
                        for row in rows
                    ]
                    total_debit = payload.get("total_debit")
                    total_credit = payload.get("total_credit")
                    is_balanced = payload.get("is_balanced")
                    self.summary.setText(
                        (
                            "Total Debit: "
                            + str(total_debit)
                            + " | Total Credit: "
                            + str(total_credit)
                            + " | Balanced: "
                            + str(is_balanced)
                        )
                    )
                elif title == "Stock Position":
                    rows = payload.get("rows", [])
                    self.current_headers = [
                        "Product ID",
                        "Code",
                        "Name",
                        "Stock",
                        "Unit Cost",
                        "Value",
                    ]
                    self.current_rows = [
                        [
                            str(row["product_id"]),
                            row["product_code"],
                            row["product_name"],
                            str(row["current_stock"]),
                            str(row["unit_cost"]),
                            str(row["stock_value"]),
                        ]
                        for row in rows
                    ]
                    self.summary.setText(
                        f"Total Stock Value: {payload.get('total_stock_value')}"
                    )
                else:
                    self.current_headers = ["Metric", "Amount"]
                    self.current_rows = [
                        ["Income", str(payload.get("income_total"))],
                        ["Expenses", str(payload.get("expense_total"))],
                        ["Net Profit", str(payload.get("net_profit"))],
                    ]
                    self.summary.setText("Profit & Loss Summary")

                self.table.set_rows(self.current_headers, self.current_rows)
            except Exception as exc:
                QMessageBox.warning(self, "Reports", str(exc))

        def _on_error(exc):
            QMessageBox.warning(self, "Reports", str(exc))

        self.run_blocking(_do_fetch, on_result=_on_result, on_error=_on_error)

    def export_csv(self) -> None:
        if not self.current_headers:
            QMessageBox.information(self, "Reports", "Load a report first")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", str(Path.home()), "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8", newline="") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(self.current_headers)
                writer.writerows(self.current_rows)
        except Exception as exc:
            QMessageBox.warning(self, "Reports", str(exc))
            return

        QMessageBox.information(self, "Reports", f"Exported: {file_path}")

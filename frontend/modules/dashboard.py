from __future__ import annotations

import asyncio

from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QMessageBox, QPushButton

from .base import BaseModuleWidget


class DashboardModule(BaseModuleWidget):
    module_title = "Dashboard"

    def __init__(self, api_client, parent=None):
        super().__init__(api_client, parent)
        self.placeholder.hide()

        card = QGroupBox("Business Snapshot")
        grid = QGridLayout(card)

        self.kpi_labels: dict[str, QLabel] = {}
        items = [
            ("sales_month", "Sales (Month)"),
            ("purchases_month", "Purchases (Month)"),
            ("expenses_month", "Expenses (Month)"),
            ("open_receivables", "Open Receivables"),
            ("open_payables", "Open Payables"),
            ("inventory_value", "Inventory Value"),
            ("low_stock_count", "Low Stock Items"),
            ("draft_sales_count", "Draft Sales"),
            ("draft_purchases_count", "Draft Purchases"),
            ("draft_imports_count", "Pending Imports"),
        ]
        for idx, (key, title) in enumerate(items):
            row = idx // 2
            col = (idx % 2) * 2
            name_label = QLabel(title)
            value_label = QLabel("-")
            value_label.setObjectName("titleLabel")
            self.kpi_labels[key] = value_label
            grid.addWidget(name_label, row, col)
            grid.addWidget(value_label, row, col + 1)

        reload_btn = QPushButton("Reload KPIs")
        reload_btn.clicked.connect(self.refresh)

        self.layout().addWidget(card)
        self.layout().addWidget(reload_btn)

    def refresh(self) -> None:
        try:
            response = asyncio.run(self.api_client.get("/api/reports/dashboard"))
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            QMessageBox.warning(self, "Dashboard", str(exc))
            return

        for key, label in self.kpi_labels.items():
            value = payload.get(key, "-")
            label.setText(str(value))

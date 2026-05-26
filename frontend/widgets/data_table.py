from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)


class DataTable(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.export_button = QPushButton("Export to Excel")
        self.clear_button = QPushButton("Clear")
        top_bar = QHBoxLayout()
        top_bar.addWidget(self.search_box)
        top_bar.addWidget(self.export_button)
        top_bar.addWidget(self.clear_button)

        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        # Allow multi-row selection for bulk operations
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setAlternatingRowColors(True)
        self.search_box.textChanged.connect(self._apply_filter)
        self.clear_button.clicked.connect(self.clear)
        self._raw_rows: list[list[str]] = []

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self.table)

    def set_rows(self, headers: list[str], rows: list[list[str]]) -> None:
        self._raw_rows = rows
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self._render_rows(rows)

    def _render_rows(self, rows: list[list[str]]) -> None:
        self.table.setRowCount(len(rows))
        for r_index, row in enumerate(rows):
            for c_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                if value.replace(",", "").replace(".", "").isdigit():
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r_index, c_index, item)
        self.table.resizeColumnsToContents()

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self._render_rows(self._raw_rows)
            return
        filtered = [row for row in self._raw_rows if any(query in cell.lower() for cell in row)]
        self._render_rows(filtered)

    def clear(self) -> None:
        """Clear search and any selection in the table."""
        self.search_box.clear()
        self.table.clearSelection()
        # show non-blocking status via parent window if available
        try:
            w = self.window()
            if w and hasattr(w, 'statusBar'):
                w.statusBar().showMessage('Table cleared', 3000)
        except Exception:
            pass

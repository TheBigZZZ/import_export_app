from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DataTable(QWidget):
    def __init__(self, parent=None, delete_callback=None, delete_label: str = "Delete Selected"):
        super().__init__(parent)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.export_button = QPushButton("Export to Excel")
        self.clear_button = QPushButton("Clear")
        self.delete_button: QPushButton | None = None
        top_bar = QHBoxLayout()
        top_bar.addWidget(self.search_box, 1)
        top_bar.addWidget(self.export_button)
        top_bar.addWidget(self.clear_button)

        if delete_callback is not None:
            self.delete_button = QPushButton(delete_label)
            self.delete_button.clicked.connect(delete_callback)
            top_bar.addWidget(self.delete_button)

        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        # Allow multi-row selection for bulk operations
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setUniformRowHeights(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setMinimumSectionSize(72)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.search_box.textChanged.connect(self._apply_filter)
        self.clear_button.clicked.connect(self.clear)
        self._raw_rows: list[list[str]] = []
        self._headers: list[str] = []
        self._stretch_columns: set[int] = set()
        self._max_content_width = 280

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(top_bar)
        layout.addWidget(self.table)

    def set_rows(
        self,
        headers: list[str],
        rows: list[list[str]],
        stretch_columns: Iterable[int] | None = None,
    ) -> None:
        self._raw_rows = rows
        self._headers = headers
        self._stretch_columns = set(stretch_columns or self._infer_stretch_columns(headers))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self._render_rows(rows)

    def _render_rows(self, rows: list[list[str]]) -> None:
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r_index, row in enumerate(rows):
            for c_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                if value.replace(",", "").replace(".", "").isdigit():
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r_index, c_index, item)
        self._apply_column_sizing()
        self.table.setSortingEnabled(sorting)

    def _infer_stretch_columns(self, headers: list[str]) -> set[int]:
        keywords = ("description", "path", "full name", "account", "email", "name", "address", "remarks")
        lowered = [header.lower() for header in headers]
        for keyword in keywords:
            for index, header in enumerate(lowered):
                if keyword in header:
                    return {index}
        return {len(headers) - 1} if headers else set()

    def _apply_column_sizing(self) -> None:
        header = self.table.horizontalHeader()
        column_count = self.table.columnCount()
        if column_count == 0:
            return

        header.setStretchLastSection(False)
        for column in range(column_count):
            if column in self._stretch_columns:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
                continue

            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.resizeColumnToContents(column)
            current_width = self.table.columnWidth(column)
            self.table.setColumnWidth(column, min(max(current_width, 72), self._max_content_width))

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
        self.table.clearFocus()
        # show non-blocking status via parent window if available
        try:
            w = self.window()
            if w and hasattr(w, 'statusBar'):
                w.statusBar().showMessage('Table cleared', 3000)
        except Exception:
            pass

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class _ListTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str] | None = None, rows: list[list[str]] | None = None):
        super().__init__()
        self._headers = headers or []
        self._rows = rows or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            try:
                return self._rows[index.row()][index.column()]
            except Exception:
                return ""
        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
            return f"Column {section}"
        return QVariant()

    def flags(self, index: QModelIndex):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def set_rows(self, headers: list[str], rows: list[list[str]]):
        self.beginResetModel()
        self._headers = headers
        self._rows = rows
        self.endResetModel()


class _FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self.filterRegExp().isEmpty():
            pattern = self.filterRegExp().pattern().lower()
            model = self.sourceModel()
            cols = model.columnCount()
            for c in range(cols):
                idx = model.index(source_row, c)
                val = str(model.data(idx, Qt.DisplayRole) or "").lower()
                if pattern in val:
                    return True
            return False
        return True


class DataTable(QWidget):
    """Scalable data table backed by QAbstractTableModel and QSortFilterProxyModel.

    Public API kept minimal and compatible with previous widget:
    - `set_rows(headers, rows, stretch_columns=None)`
    - `table` attribute holds the `QTableView` for direct access where needed
    - `selected_row_indices()` helper returns source-model row indices of selection
    """

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

        # Use QTableView + model for scalability
        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setMinimumSectionSize(72)

        # Default uniform row height (pixels). Keep reasonable for compact lists.
        self._default_row_height = 28
        self.table.verticalHeader().setDefaultSectionSize(self._default_row_height)

        self._model = _ListTableModel([], [])
        self._proxy = _FilterProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table.setModel(self._proxy)

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
        self._model.set_rows(headers, rows)
        # Ensure row heights are uniform
        for r in range(len(rows)):
            try:
                self.table.setRowHeight(r, self._default_row_height)
            except Exception:
                pass
        # Apply column sizing after model update
        self._apply_column_sizing()

    def selected_row_indices(self) -> list[int]:
        """Return the selected rows as source-model indices."""
        res: list[int] = []
        for idx in self.table.selectionModel().selectedRows():
            src = self._proxy.mapToSource(idx)
            res.append(src.row())
        return sorted(set(res))

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
        column_count = self.table.model().columnCount()
        if column_count == 0:
            return

        header.setStretchLastSection(False)
        for column in range(column_count):
            if column in self._stretch_columns:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
                continue

            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            try:
                self.table.resizeColumnToContents(column)
                current_width = self.table.columnWidth(column)
                self.table.setColumnWidth(column, min(max(current_width, 72), self._max_content_width))
            except Exception:
                pass

    def _apply_filter(self, text: str) -> None:
        pattern = text.strip()
        if not pattern:
            self._proxy.setFilterRegExp("")
        else:
            self._proxy.setFilterRegExp(pattern)

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

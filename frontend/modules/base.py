from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget


class BaseModuleWidget(QWidget):
    module_title = "Module"
    form_label_width = 150

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self.title = QLabel(self.module_title)
        self.title.setObjectName("titleLabel")
        self.placeholder = QLabel("This module will be implemented in its dedicated phase.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.placeholder)

    def refresh(self) -> None:
        """Reload data for this module."""
        return None

    def configure_form_layout(self, form: QFormLayout, label_width: int | None = None) -> None:
        width = label_width or self.form_label_width
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label_item is None:
                continue
            label_widget = label_item.widget()
            if label_widget is None:
                continue
            label_widget.setMinimumWidth(width)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

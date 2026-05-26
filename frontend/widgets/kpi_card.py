from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class KpiCard(QWidget):
    def __init__(self, title: str, value: str = "0.00", parent=None):
        super().__init__(parent)
        self.title_label = QLabel(title)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("kpiValue")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

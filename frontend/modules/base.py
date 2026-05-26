from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class BaseModuleWidget(QWidget):
    module_title = "Module"

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self.title = QLabel(self.module_title)
        self.title.setObjectName("titleLabel")
        self.placeholder = QLabel("This module will be implemented in its dedicated phase.")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.placeholder)
        layout.addStretch(1)

    def refresh(self) -> None:
        """Reload data for this module."""
        return None

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout


class FormDialog(QDialog):
    def __init__(self, title: str, fields: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.inputs: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for field in fields:
            input_box = QLineEdit()
            self.inputs[field] = input_box
            form.addRow(field, input_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

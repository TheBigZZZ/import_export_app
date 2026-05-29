import asyncio

from PySide6.QtCore import QObject, Qt, QThreadPool, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from ..workers import Worker


class BaseModuleWidget(QWidget):
    module_title = "Module"
    form_label_width = 150

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self.title = QLabel(self.module_title)
        self.title.setObjectName("titleLabel")
        self.placeholder = QLabel(
            "This module will be implemented in its dedicated phase."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.placeholder)

    def refresh(self) -> None:
        """Reload data for this module."""
        return None

    def configure_form_layout(
        self, form: QFormLayout, label_width: int | None = None
    ) -> None:
        width = label_width or self.form_label_width
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
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
            label_widget.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

    def run_blocking(self, fn, on_result=None, on_error=None) -> None:
        """Run a blocking callable in a thread and call the provided callbacks in the GUI thread.

        fn: callable returning a result
        on_result: callable(result) -> None
        on_error: callable(exception) -> None
        """
        worker = Worker(fn)
        if on_result:
            worker.signals.result.connect(on_result)
        if on_error:
            worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def run_async(self, coro, on_result=None, on_error=None) -> None:
        """Run an async coroutine on the current asyncio event loop (qasync) and deliver
        results back to the GUI thread via Qt signals.
        """

        class _Runner(QObject):
            result = Signal(object)
            error = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)

            def run(self, coro):
                try:
                    task = asyncio.create_task(coro)
                except RuntimeError:
                    # No running loop
                    self.error.emit(RuntimeError("No running asyncio event loop"))
                    return

                def _done(fut):
                    try:
                        res = fut.result()
                    except Exception as exc:
                        self.error.emit(exc)
                    else:
                        self.result.emit(res)

                task.add_done_callback(_done)

        runner = _Runner(self)
        if on_result:
            runner.result.connect(on_result)
        if on_error:
            runner.error.connect(on_error)

        # Keep a reference so the runner isn't GC'd while the task runs.
        if not hasattr(self, "_async_runners"):
            self._async_runners = []
        self._async_runners.append(runner)

        runner.run(coro)

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(object)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    """Run a callable in a thread and emit signals for result or error.

    Usage:
        w = Worker(func, *args, **kwargs)
        w.signals.result.connect(on_result)
        QThreadPool.globalInstance().start(w)
    """

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

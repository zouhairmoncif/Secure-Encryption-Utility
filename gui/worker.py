"""Background worker so encryption/decryption never blocks the UI thread."""

from PyQt5.QtCore import QThread, pyqtSignal


class Worker(QThread):
    """Runs a callable on a dedicated thread and reports back via signals.

    `job` must be a zero-argument callable returning a dict of results.
    Only one job may run per Worker instance at a time.
    """

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job
        self._error = None

    def run(self):
        try:
            result = self._job()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self._error = str(exc)
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
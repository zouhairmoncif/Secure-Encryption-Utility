"""Session + persisted history of encrypt/decrypt operations."""

import json
import os
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

APP_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = APP_DIR / ".secure_encryption_history.json"
MAX_RECORDS = 200


class HistoryManager(QObject):
    """Owns the in-memory + on-disk record of operations."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._records = data[-MAX_RECORDS:]
        except (OSError, ValueError):
            self._records = []

    def _save(self):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._records, fh, indent=2)
        except OSError:
            pass  # history is best-effort; never block the app on IO

    def add(self, mode, input_path, output_path, size, ok=True):
        record = {
            "mode": mode,
            "input": input_path,
            "output": output_path,
            "size": size,
            "status": "ok" if ok else "error",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self._records.append(record)
        self._records = self._records[-MAX_RECORDS:]
        self._save()
        self.changed.emit()

    def records(self):
        return list(self._records)

    def clear(self):
        self._records = []
        self._save()
        self.changed.emit()
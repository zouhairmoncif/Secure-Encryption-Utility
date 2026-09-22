"""Operation log page: session history rendered as terminal log lines."""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..components import Btn
from ..icons import icon


def _human_size(num) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return "%.0f %s" % (num, unit) if unit == "B" else "%.1f %s" % (num, unit)
        num /= 1024
    return "%.1f TB" % num


class _HistoryRow(QFrame):
    """A single monospace activity line, e.g.: [23:54][ENC][OK] file -> out."""

    DIM = "#4F8A63"
    MID = "#3CCF6E"
    BRIGHT = "#86FFA6"
    BODY = "#A9E6B8"
    OK = "#63E67B"
    ERR = "#FF6B6B"

    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.setObjectName("historyRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 5, 12, 5)
        lay.setSpacing(8)

        mode = "ENC" if record["mode"] == "encrypt" else "DEC"
        status = "OK" if record["status"] == "ok" else "ERR"
        status_color = self.OK if record["status"] == "ok" else self.ERR
        base = os.path.basename(record["input"]) or record["input"]

        html = (
            '<span style="color:%s;">[%s]</span> '
            '<span style="color:%s; font-weight:600;">[%s]</span> '
            '<span style="color:%s; font-weight:600;">%s</span> '
            '<span style="color:%s;">-&gt;</span> '
            '<span style="color:%s;">%s</span> '
            '<span style="color:%s;">(%s)</span> '
            '<span style="color:%s; font-weight:700;">[%s]</span>'
        ) % (
            self.DIM, record["time"],
            self.MID, mode,
            self.BRIGHT, _html_escape(base),
            self.DIM,
            self.BODY, _html_escape(record["output"]),
            self.DIM, _human_size(record["size"]),
            status_color, status,
        )

        line = QLabel(html)
        line.setOpenExternalLinks(False)
        line.setTextFormat(Qt.RichText)
        line.setWordWrap(True)
        line.setToolTip(record["output"])
        lay.addWidget(line, 1)


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class HistoryPage(QWidget):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        heading_col = QVBoxLayout()
        heading_col.setSpacing(1)
        title = QLabel("OPERATION LOG")
        title.setObjectName("pageHeading")
        heading_col.addWidget(title)
        sub = QLabel("RECENT ENCRYPT / DECRYPT ACTIVITY")
        sub.setObjectName("statusText")
        heading_col.addWidget(sub)
        header.addLayout(heading_col)
        header.addStretch(1)
        self.empty_count = QLabel("")
        self.empty_count.setObjectName("statusText")
        header.addWidget(self.empty_count)

        self.clear_btn = Btn("CLEAR LOG", kind="ghost")
        self.clear_btn.set_icon("trash", size=12)
        self.clear_btn.setToolTip("ERASE ACTIVITY RECORD")
        header.addWidget(self.clear_btn)
        root.addLayout(header)

        self.clear_btn.clicked.connect(self._clear)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll, 1)

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch(1)
        scroll.setWidget(self.list_host)

        self._empty_widget = None
        self.history.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        records = self.history.records()
        if not records:
            self._show_empty()
        else:
            self._hide_empty()
            for record in reversed(records):
                self.list_layout.insertWidget(0, _HistoryRow(record))

        text = "" if not records else "%d EVENT%s CAPTURED" % (
            len(records),
            "" if len(records) == 1 else "S",
        )
        self.empty_count.setText(text)

    def _show_empty(self):
        if self._empty_widget is not None:
            return
        self._empty_widget = QWidget()
        lay = QVBoxLayout(self._empty_widget)
        lay.setContentsMargins(0, 50, 0, 0)
        lay.setSpacing(8)
        glyph = QLabel()
        glyph.setPixmap(icon("clock", 40, "#335040").pixmap(40, 40))
        glyph.setAlignment(Qt.AlignCenter)
        lay.addWidget(glyph)
        msg = QLabel("NO OPERATIONS RECORDED")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-weight: 700; color: #4F8A63;")
        lay.addWidget(msg)
        hint = QLabel("ENCRYPT OR DECRYPT A FILE TO BEGIN LOGGING")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #335040; font-size: 11px;")
        lay.addWidget(hint)
        self.list_layout.insertWidget(0, self._empty_widget)

    def _hide_empty(self):
        if self._empty_widget is not None:
            self._empty_widget.deleteLater()
            self._empty_widget = None

    def _clear(self):
        from ..components import ask_confirm

        if ask_confirm(self, "CLEAR LOG",
                       "ERASE THE ACTIVITY RECORD?\n\nTHIS ACTION CANNOT BE UNDONE."):
            self.history.clear()
"""Shared single-file encrypt/decrypt workflow page.

Both Encrypt and Decrypt use the exact same three-card flow
(file -> password -> action) with only wording and defaults differing.
"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from encryption import encrypt_data, decrypt_data
from file_manager import read_file, write_file, get_default_output_path

from ..components import (
    Btn,
    Card,
    PasswordField,
    StrengthBar,
    ask_confirm_overwrite,
)
from ..theme import ERROR, SUCCESS, TEXT_DIM, TEXT_FAINT
from ..icons import icon
from ..worker import Worker

STRENGTH_LABELS = ["", "Weak", "Fair", "Good", "Strong"]


def _password_score(password: str) -> int:
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    classes = 0
    if any(c.isupper() for c in password):
        classes += 1
    if any(c.isdigit() for c in password):
        classes += 1
    if any(not c.isalnum() for c in password):
        classes += 1
    if classes >= 2:
        score += 1
    return min(4, score)


class _DropRow(QWidget):
    """HBox row that accepts dropped files to auto-fill the input path."""

    dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.dropped.emit(urls[0].toLocalFile())


class FileOperationPage(QWidget):
    """Base class implementing the complete file encrypt/decrypt flow."""

    notify = pyqtSignal(str, str, str)   # kind, title, message
    status_changed = pyqtSignal(str, str)  # state, text

    MODE = "encrypt"
    ACTION_VERB = "Encrypt"
    ACTION_PAST = "encrypted"
    ACTION_ICON = "lock"
    RESULT_ICON = "checkCircle"

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history
        self._output_auto = True
        self.worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 30)
        layout.setSpacing(18)

        inner = QWidget()
        inner.setMaximumWidth(840)
        layout.addWidget(inner)
        layout.addStretch(1)
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(18)

        self._build_file_card()
        self._build_password_card()
        self._build_action_card()
        self._build_result_card()

    # ------------------------------------------------------------------ UI

    def _build_file_card(self):
        card = Card(title="INPUT FILE", icon_name="folder")
        body = card.body

        self.drop_row = _DropRow()
        row = QHBoxLayout(self.drop_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Drag & drop a file here, or browse…")
        self.input_field.setAcceptDrops(False)
        row.addWidget(self.input_field, 1)

        self.btn_browse = Btn("Browse…")
        self.btn_browse.setMinimumWidth(110)
        row.addWidget(self.btn_browse)
        body.addWidget(self.drop_row)

        output_row = QWidget()
        out = QHBoxLayout(output_row)
        out.setContentsMargins(0, 0, 0, 0)
        out.setSpacing(8)
        self.output_field = QLineEdit()
        self.output_field.setPlaceholderText("Destination file")
        self.output_field.setAcceptDrops(False)
        out.addWidget(self.output_field, 1)
        self.btn_save_as = Btn("Save as…")
        self.btn_save_as.setMinimumWidth(110)
        out.addWidget(self.btn_save_as)
        body.addWidget(output_row)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("hint")
        self.hint_label.setWordWrap(True)
        body.addWidget(self.hint_label)

        self.btn_browse.clicked.connect(self._browse_input)
        self.btn_save_as.clicked.connect(self._browse_output)
        self.output_field.textEdited.connect(self._on_output_edited)
        self.drop_row.dropped.connect(self._on_file_selected)

        self._layout.addWidget(card)

    def _build_password_card(self):
        card = Card(title="PASSPHRASE", icon_name="key")
        body = card.body

        self.password_field = PasswordField()
        body.addWidget(self.password_field)

        strength_row = QHBoxLayout()
        strength_row.setSpacing(10)
        self.strength_bar = StrengthBar()
        strength_row.addWidget(self.strength_bar, 1)
        self.strength_label = QLabel("")
        self.strength_label.setObjectName("hint")
        self.strength_label.setFixedWidth(90)
        self.strength_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        strength_row.addWidget(self.strength_label)
        body.addLayout(strength_row)

        self.password_field.line.textChanged.connect(self._on_password_changed)

        self._layout.addWidget(card)

    def _build_action_card(self):
        card = Card()
        body = card.body

        self.action_btn = Btn("%s File" % self.ACTION_VERB, kind="primary")
        self.action_btn.set_icon(self.ACTION_ICON, size=18, color="#FFFFFF")
        self.action_btn.setMinimumHeight(46)
        body.addWidget(self.action_btn)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(10)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        bar_row.addWidget(self.progress_bar, 1)

        self.progress_label = QLabel("Processing…")
        self.progress_label.setObjectName("hint")
        self.progress_label.hide()
        bar_row.addWidget(self.progress_label)
        body.addLayout(bar_row)

        opts = QHBoxLayout()
        opts.setSpacing(8)
        self.reset_btn = Btn("Clear fields", kind="ghost")
        self.reset_btn.set_icon("refresh", size=15)
        opts.addWidget(self.reset_btn)
        opts.addStretch(1)
        body.addLayout(opts)

        self.action_btn.clicked.connect(self._run_action)
        self.reset_btn.clicked.connect(self.reset_form)

        self._layout.addWidget(card)

    def _build_result_card(self):
        card = Card()
        self._result_card = card
        body = card.body

        row = QHBoxLayout()
        row.setSpacing(12)
        self._result_icon = QLabel()
        self._result_icon.setPixmap(icon(self.RESULT_ICON, 34, SUCCESS).pixmap(34, 34))
        row.addWidget(self._result_icon, 0, Qt.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(4)
        self._result_title = QLabel()
        self._result_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        texts.addWidget(self._result_title)
        self._result_detail = QLabel()
        self._result_detail.setWordWrap(True)
        self._result_detail.setStyleSheet("color: %s;" % TEXT_DIM)
        texts.addWidget(self._result_detail)
        row.addLayout(texts, 1)
        body.addLayout(row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_open_folder = Btn("Open folder", kind="ghost")
        self.btn_open_folder.set_icon("folder", size=15)
        actions.addWidget(self.btn_open_folder)
        self.btn_new_file = Btn("New operation", kind="ghost")
        self.btn_new_file.set_icon("refresh", size=15)
        actions.addWidget(self.btn_new_file)
        actions.addStretch(1)
        body.addLayout(actions)

        self.btn_open_folder.clicked.connect(self._open_output_folder)
        self.btn_new_file.clicked.connect(self.reset_form)
        card.hide()

        self._layout.addWidget(card)

    # ------------------------------------------------------------ behaviour

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to %s" % self.ACTION_VERB.lower())
        if path:
            self._on_file_selected(path)

    def _on_file_selected(self, path):
        self.input_field.setText(path)
        if self._output_auto:
            self.output_field.setText(get_default_output_path(path, self.MODE))
        verb = "encrypted" if self.MODE == "encrypt" else "decrypted"
        self.hint_label.setText(
            "%s will be %s and saved as a new file using the password below."
            % (os.path.basename(path), verb)
        )

    def _on_output_edited(self, _text):
        self._output_auto = False

    def _browse_output(self):
        initial = self.output_field.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save %s file as…" % self.ACTION_PAST,
            initial or get_default_output_path(self.input_field.text().strip() or "untitled", self.MODE),
        )
        if path:
            self.output_field.setText(path)
            self._output_auto = False

    def _on_password_changed(self, text):
        score = _password_score(text)
        self.strength_bar.set_score(score)
        if score == 0:
            self.strength_label.setText("")
        else:
            self.strength_label.setText(STRENGTH_LABELS[score])
        color = {1: ERROR, 2: "#F0A24A", 3: SUCCESS, 4: SUCCESS}.get(score, TEXT_FAINT)
        self.strength_label.setStyleSheet("color: %s;" % color)

    def reset_form(self):
        self.input_field.clear()
        self.output_field.clear()
        self.password_field.clear()
        self.hint_label.setText("")
        self._result_card.hide()
        self._output_auto = True
        self.strength_bar.set_score(0)
        self.strength_label.setText("")
        self._notify("Ready")

    def _notify(self, text):
        self.status_changed.emit("idle", text)

    # ------------------------------------------------------------ actions

    def _validate(self):
        src = self.input_field.text().strip()
        dst = self.output_field.text().strip()
        pwd = self.password_field.text()

        if not src:
            return None, "No input file selected."
        if not os.path.isfile(src):
            return None, "The selected input file does not exist."
        if not pwd:
            return None, "Password cannot be empty."
        if not dst:
            return None, "No destination file specified."
        return (src, dst, pwd), None

    def _run_action(self):
        if self.worker is not None and self.worker.isRunning():
            return
        values, error = self._validate()
        if error:
            self.notify.emit("err", self.ACTION_VERB + " failed", error)
            self.status_changed.emit("err", error)
            return

        src, dst, pwd = values
        if os.path.exists(dst) and not ask_confirm_overwrite(self, dst):
            return

        self._set_busy(True)
        mode = self.MODE

        def job():
            data = read_file(src)
            if mode == "encrypt":
                output = encrypt_data(data, pwd)
            else:
                output = decrypt_data(data, pwd)
            write_file(dst, output)
            return {"input": src, "output": dst, "size": len(output)}

        self.worker = Worker(job, parent=self)
        self.worker.succeeded.connect(self._on_success)
        self.worker.failed.connect(self._on_failure)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.status_changed.emit("busy", "%sing…" % self.ACTION_VERB)
        self.notify.emit("info", "%s in progress" % self.ACTION_VERB.title(), "Processing %s…" % os.path.basename(src))
        self.worker.start()

    def _set_busy(self, busy):
        self.action_btn.setEnabled(not busy)
        self.btn_browse.setEnabled(not busy)
        self.btn_save_as.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.password_field.setEnabled(not busy)
        if busy:
            self.progress_bar.show()
            self.progress_label.show()
        else:
            self.progress_bar.hide()
            self.progress_label.hide()

    def _on_success(self, result):
        self.history.add(self.MODE, result["input"], result["output"], result["size"], ok=True)
        name = os.path.basename(result["output"])
        self._result_title.setText("%s complete" % self.ACTION_VERB.title())
        self._result_detail.setText(
            "File saved to:\n%s" % result["output"]
        )
        self._result_icon.setPixmap(icon(self.RESULT_ICON, 34, SUCCESS).pixmap(34, 34))
        self._result_card.show()
        self.hint_label.setText("")
        self.status_changed.emit("ok", "%s file successfully %s." % (os.path.basename(result["input"]), self.ACTION_PAST))
        self.notify.emit(
            "ok",
            "%s complete" % self.ACTION_VERB.title(),
            "Saved:\n%s" % result["output"],
        )

    def _on_failure(self, message):
        self.history.add(self.MODE, self.input_field.text().strip(), self.output_field.text().strip(), 0, ok=False)
        self._result_title.setText("%s failed" % self.ACTION_VERB.title())
        self._result_detail.setText(message)
        self._result_icon.setPixmap(icon("xCircle", 34, ERROR).pixmap(34, 34))
        self._result_card.show()
        self.status_changed.emit("err", message)
        self.notify.emit("err", "%s failed" % self.ACTION_VERB.title(), message)

    def _open_output_folder(self):
        folder = os.path.dirname(self.output_field.text().strip()) or "."
        try:
            os.startfile(folder)  # noqa: S606
        except OSError:
            self.notify.emit("warn", "Cannot open folder", folder)

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(3000)
            self.worker = None
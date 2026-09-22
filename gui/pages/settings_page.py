"""Settings & about page: product information, security details, self-test."""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from encryption import encrypt_data, decrypt_data
from ..components import Btn, Card
from ..icons import icon
from ..worker import Worker
from ..theme import ERROR, SUCCESS, TEXT_DIM, TEXT_FAINT

VERSION = "2.0"


class SettingsPage(QWidget):
    notify = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 30)
        root.setSpacing(18)

        inner = QWidget()
        inner.setMaximumWidth(840)
        root.addWidget(inner)
        root.addStretch(1)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self._build_about(layout)
        self._build_security(layout)
        self._build_diagnostics(layout)

    # ------------------------------------------------------------------ UI

    def _build_about(self, layout):
        card = Card()
        body = card.body

        row = QHBoxLayout()
        row.setSpacing(14)
        brand = QLabel()
        brand.setPixmap(icon("shield", 46, "#86FFA6").pixmap(46, 46))
        row.addWidget(brand, 0, Qt.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel("Secure Encryption")
        title.setObjectName("brandName")
        texts.addWidget(title)
        version = QLabel("Version %s" % VERSION)
        version.setObjectName("statusText")
        texts.addWidget(version)
        desc = QLabel(
            "Password-based file encryption for safe storage and transfer. "
            "Every file is protected with a unique random salt and a "
            "cryptographically derived key."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: %s;" % TEXT_DIM)
        texts.addWidget(desc)
        row.addLayout(texts, 1)
        body.addLayout(row)
        layout.addWidget(card)

    def _build_security(self, layout):
        card = Card(title="SECURITY PARAMETERS", icon_name="lock")
        body = card.body
        facts = [
            ("Algorithm", "Fernet (AES-128-CBC + HMAC-SHA256)"),
            ("Key derivation", "PBKDF2-HMAC-SHA256"),
            ("Iterations", "480,000"),
            ("Salting", "16 random bytes per file"),
            ("Password storage", "Never stored, never transmitted"),
        ]
        for label, value in facts:
            row = QHBoxLayout()
            row.setSpacing(20)
            name = QLabel(label)
            name.setStyleSheet("color: %s; font-weight: 600;" % TEXT_DIM)
            name.setFixedWidth(150)
            row.addWidget(name)
            val = QLabel(value)
            row.addWidget(val, 1)
            body.addLayout(row)
        layout.addWidget(card)

    def _build_diagnostics(self, layout):
        card = Card(title="ENVIRONMENT SELF-TEST", icon_name="zap")
        body = card.body

        intro = QLabel(
            "Verifies that the installed cryptography stack can encrypt and "
            "decrypt correctly on this machine."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: %s;" % TEXT_DIM)
        body.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.test_btn = Btn("Run self-test", kind="secondary")
        self.test_btn.set_icon("refresh", size=15)
        row.addWidget(self.test_btn)
        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        row.addWidget(self.test_result, 1)
        body.addLayout(row)

        footer = QLabel("Built with PyQt5 + the cryptography library.")
        footer.setObjectName("versionLabel")
        layout.addWidget(footer)

        self.test_btn.clicked.connect(self._run_self_test)
        layout.addWidget(card)

    # ------------------------------------------------------------ self-test

    def _run_self_test(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.test_btn.setEnabled(False)
        self.test_result.setStyleSheet("color: %s;" % TEXT_FAINT)
        self.test_result.setText("Running…")
        self.notify.emit("info", "Self-test started", "Encrypting and decrypting a sample payload…")

        sample = os.urandom(64)

        def job():
            token = encrypt_data(sample, "self-test-password-123")
            back = decrypt_data(token, "self-test-password-123")
            return sample == back

        self.worker = Worker(job, parent=self)

        def _ok(result):
            if result:
                self.test_result.setStyleSheet("color: %s;" % SUCCESS)
                self.test_result.setText("All checks passed — round-trip verified.")
                self.notify.emit("ok", "Self-test passed", "Encryption/decryption is fully functional.")
            else:
                self.test_result.setStyleSheet("color: %s;" % ERROR)
                self.test_result.setText("Round-trip mismatch — cryptography stack is broken.")
                self.notify.emit("err", "Self-test failed", "Round-trip mismatch.")

        def _fail(message):
            self.test_result.setStyleSheet("color: %s;" % ERROR)
            self.test_result.setText("Self-test failed: %s" % message)
            self.notify.emit("err", "Self-test failed", message)

        self.worker.succeeded.connect(_ok)
        self.worker.failed.connect(_fail)
        self.worker.finished.connect(self._test_finished)
        self.worker.start()

    def _test_finished(self):
        self.test_btn.setEnabled(True)

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(3000)
            self.worker = None
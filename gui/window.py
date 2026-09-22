"""Application shell: retro sidebar, technical top bar, console, status bar."""

import random

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .components import (
    Btn,
    Card,
    CrtOverlay,
    Led,
    NavButton,
    StatusPill,
    TerminalView,
    ToastManager,
)
from .history import HistoryManager
from .icons import pixmap
from .pages import EncryptPage, DecryptPage, HistoryPage, SettingsPage, VERSION
from .theme import ACCENT_HOVER, TEXT_DIM, build_stylesheet

PAGE_META = {
    "Encrypt": ("ENCRYPT FILE", "LOCK FILE  ::  AES-128 / PBKDF2"),
    "Decrypt": ("DECRYPT FILE", "UNLOCK .ENC CIPHERTEXT"),
    "History": ("OPERATION LOG", "SESSION ACTIVITY RECORD"),
    "Settings": ("SYSTEM INFO", "CONFIGURATION & DIAGNOSTICS"),
}


class SecureEncryptionApp(QMainWindow):
    """Main window of the retro Secure Encryption console."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECURE ENCRYPTION :: SEC-ENC TERMINAL")
        self.resize(1150, 760)
        self.setMinimumSize(940, 620)
        self.setStyleSheet(build_stylesheet())

        self.history = HistoryManager(self)
        self.toasts = ToastManager(self)

        self._uptime = 0
        self._cpu = 8
        self._mem = 31

        self._build_ui()
        self._wire_signals()
        self._boot()

        self.encrypt_nav.setChecked(True)
        self.navigate("Encrypt")

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget(objectName="rootBg")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_main(), 1)

        # CRT layer sits above everything and passes clicks through.
        self.crt_overlay = CrtOverlay(central)
        self.crt_overlay.setGeometry(central.rect())
        self.crt_overlay.raise_()

    def _build_sidebar(self):
        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(196)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(2)

        brand = QHBoxLayout()
        brand.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(pixmap("shield", 26, ACCENT_HOVER))
        brand.addWidget(logo, 0, Qt.AlignTop)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("SEC-ENC")
        name.setObjectName("brandName")
        tagline = QLabel("ENCRYPTION UNIT v%s" % VERSION)
        tagline.setObjectName("brandTagline")
        brand_text.addWidget(name)
        brand_text.addWidget(tagline)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        layout.addLayout(brand)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #1A2026;")
        layout.addSpacing(10)
        layout.addWidget(line)
        layout.addSpacing(10)

        self.encrypt_nav = NavButton("lock", "Encrypt")
        self.decrypt_nav = NavButton("unlock", "Decrypt")
        self.history_nav = NavButton("clock", "Logs")
        self.settings_nav = NavButton("gear", "System")

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        for btn in (self.encrypt_nav, self.decrypt_nav,
                    self.history_nav, self.settings_nav):
            nav_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        self.about_btn = Btn("About", kind="ghost")
        self.about_btn.set_icon("info", size=13)
        layout.addWidget(self.about_btn)

        version = QLabel("AES-128 :: FERNET")
        version.setObjectName("versionLabel")
        version.setContentsMargins(6, 4, 0, 0)
        layout.addWidget(version)

        return sidebar

    def _build_top_bar(self):
        top_bar = QFrame(objectName="topBar")
        row = QHBoxLayout(top_bar)
        row.setContentsMargins(16, 6, 16, 6)
        row.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.top_title = QLabel()
        self.top_title.setObjectName("topTitle")
        self.top_subtitle = QLabel()
        self.top_subtitle.setObjectName("topSubtitle")
        titles.addWidget(self.top_title)
        titles.addWidget(self.top_subtitle)
        row.addLayout(titles)
        row.addStretch(1)

        self._led_system = self._make_led_row("SYS", "ONLINE", "green")
        self._led_conn = self._make_led_row("CONN", "SECURE", "green")
        self._led_enc = self._make_led_row("ENC", "ACTIVE", "green")
        row.addWidget(self._led_system)
        row.addWidget(self._led_conn)
        row.addWidget(self._led_enc)

        self.status_pill = StatusPill()
        row.addWidget(self.status_pill)
        return top_bar

    def _make_led_row(self, tag, text, color_name):
        frame = QWidget()
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        led = Led(color=color_name, radius=4)
        label = QLabel("%s:%s" % (tag, text))
        label.setObjectName("ledText")
        label.setStyleSheet("font-weight: 700; color: %s;" % TEXT_DIM)
        lay.addWidget(led)
        lay.addWidget(label)
        return frame

    def _build_console(self):
        panel = Card(title="SYSTEM CONSOLE", icon_name="zap")
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addStretch(1)
        self.console_clear = Btn("CLEAR", kind="ghost")
        self.console_clear.setMinimumHeight(22)
        self.console_clear.set_icon("trash", size=12)
        bar.addWidget(self.console_clear)
        panel.body.addLayout(bar)

        self.console = TerminalView()
        self.console.setFixedHeight(148)
        panel.body.addWidget(self.console)
        self.console_clear.clicked.connect(self.console.clear_log)
        return panel

    def _build_status_bar(self):
        status_bar = QFrame(objectName="statusBarQFrame")
        row = QHBoxLayout(status_bar)
        row.setContentsMargins(14, 4, 14, 4)
        row.setSpacing(14)

        self.status_text = QLabel("STATUS: READY")
        self.status_text.setObjectName("ledText")
        row.addWidget(self.status_text)

        self.cpu_label = QLabel("CPU: --")
        self.cpu_label.setObjectName("ledText")
        row.addWidget(self.cpu_label)
        self.mem_label = QLabel("MEM: --")
        self.mem_label.setObjectName("ledText")
        row.addWidget(self.mem_label)
        self.session_label = QLabel("SESSION: 00:00")
        self.session_label.setObjectName("ledText")
        row.addWidget(self.session_label)

        sec = QLabel("SECURITY: ACTIVE")
        sec.setObjectName("ledText")
        sec.setStyleSheet("color: %s; font-weight: 700;" % ACCENT_HOVER)
        row.addWidget(sec)

        row.addStretch(1)
        version = QLabel("VERSION %s" % VERSION)
        version.setObjectName("versionLabel")
        row.addWidget(version)
        return status_bar

    def _build_main(self):
        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_top_bar())

        self.encrypt_page = EncryptPage(self.history)
        self.decrypt_page = DecryptPage(self.history)
        self.history_page = HistoryPage(self.history)
        self.settings_page = SettingsPage()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.encrypt_page)
        self.stack.addWidget(self.decrypt_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)
        layout.addWidget(self.stack, 1)

        layout.addWidget(self._build_console())
        layout.addWidget(self._build_status_bar())
        return main

    # ------------------------------------------------------------- wiring

    def _wire_signals(self):
        self.encrypt_nav.clicked.connect(lambda: self.navigate("Encrypt"))
        self.decrypt_nav.clicked.connect(lambda: self.navigate("Decrypt"))
        self.history_nav.clicked.connect(lambda: self.navigate("History"))
        self.settings_nav.clicked.connect(lambda: self.navigate("Settings"))
        self.about_btn.clicked.connect(self.show_about)

        for page in (self.encrypt_page, self.decrypt_page):
            page.notify.connect(self.notify)
            page.status_changed.connect(self._on_status_changed)

        self.settings_page.notify.connect(self.notify)

        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._tick_status)
        self._sys_timer.start(1000)

    def navigate(self, name):
        pages = {
            "Encrypt": (self.encrypt_nav, self.encrypt_page),
            "Decrypt": (self.decrypt_nav, self.decrypt_page),
            "History": (self.history_nav, self.history_page),
            "Settings": (self.settings_nav, self.settings_page),
        }
        nav_btn, page = pages[name]
        if not nav_btn.isChecked():
            nav_btn.setChecked(True)
        self.stack.setCurrentWidget(page)
        title, subtitle = PAGE_META[name]
        self.top_title.setText("> " + title)
        self.top_subtitle.setText(subtitle)

    def _boot(self):
        self.console.write("sys", "[SYSTEM] SEC-ENC TERMINAL v%s" % VERSION)
        self.console.write("ok", "[OK] SECURITY MODULE LOADED")
        self.console.write("ok", "[OK] ENCRYPTION ENGINE READY (AES-128 / PBKDF2-SHA256)")
        self.console.write("info", "[INFO] AWAITING INPUT...")

    def _tick_status(self):
        self._uptime += 1
        m, s = divmod(self._uptime, 60)
        self.session_label.setText("SESSION: %02d:%02d" % (m, s))
        for label, attr, lo, hi, step in (
            (self.cpu_label, "_cpu", 4, 64, 4),
            (self.mem_label, "_mem", 18, 46, 2),
        ):
            value = getattr(self, attr) + random.randint(-step, step)
            setattr(self, attr, min(hi, max(lo, value)))
            label.setText("%s: %d%%" % ("CPU" if attr == "_cpu" else "MEM", getattr(self, attr)))

    # ----------------------------------------------------------- feedback

    def notify(self, kind, title, message="", log_only=False):
        """Public feedback entry: toasts + console logging."""
        if not log_only:
            if kind == "ok":
                self.console.write("ok", "[OK] " + title.upper() + (" -- " + message if message else ""))
            elif kind == "err":
                self.console.write("err", "[ERR] " + title.upper() + (" -- " + message if message else ""))
            elif kind == "warn":
                self.console.write("warn", "[WARN] " + title.upper() + (" -- " + message if message else ""))
            else:
                self.console.write("info", "[INFO] " + title.upper() + (" -- " + message if message else ""))
            self.toasts.push(kind, title, message)

    def _on_status_changed(self, state, text):
        if state == "idle":
            self.console.write("info", "[SYS] READY")
            self.status_pill.set_state("idle", "READY")
            self.status_text.setText("STATUS: READY")
        elif state == "busy":
            self.console.write("info", "[EXEC] " + text.upper())
            self.status_pill.set_state("busy", "BUSY")
            self.status_text.setText("STATUS: " + text.upper())
        elif state == "ok":
            self.console.write("ok", "[DONE] " + text.upper())
            self.status_pill.set_state("ok", "OK")
            self.status_text.setText("STATUS: COMPLETE")
        elif state == "err":
            self.console.write("err", "[FAIL] " + text.upper())
            self.status_pill.set_state("err", "ERROR")
            self.status_text.setText("STATUS: ERROR")

    # ----------------------------------------------------------- dialogs

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("ABOUT SEC-ENC")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(8)

        logo = QLabel()
        logo.setPixmap(pixmap("shield", 44, ACCENT_HOVER))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        name = QLabel("SEC-ENC :: ENCRYPTION UNIT")
        name.setObjectName("brandName")
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)

        sub = QLabel("SECURE ENCRYPTION TERMINAL  v%s" % VERSION)
        sub.setObjectName("statusText")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        desc = QLabel(
            "PASSWORD-BASED FILE ENCRYPTION UTILITY\n"
            "AES-128 (FERNET) :: PBKDF2-HMAC-SHA256 :: 480,000 ITERATIONS\n"
            "16-BYTE RANDOM SALT PER FILE"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: %s;" % TEXT_DIM)
        layout.addWidget(desc)
        layout.addSpacing(10)

        ok = Btn("OK", kind="primary")
        ok.setMinimumWidth(110)
        ok.clicked.connect(dialog.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(ok)
        row.addStretch(1)
        layout.addLayout(row)

        dialog.setMinimumWidth(420)
        dialog.exec_()

    # ---------------------------------------------------------- lifecycle

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.crt_overlay.setGeometry(self.centralWidget().rect())
        self.toasts.reflow()

    def closeEvent(self, event):
        self.encrypt_page.shutdown()
        self.decrypt_page.shutdown()
        self.settings_page.shutdown()
        super().closeEvent(event)
"""Reusable retro components for the Secure Encryption console.

The public API mirrors the previous iteration (Card, Btn, NavButton, toasts,
confirmation helpers) so the page logic stays untouched — only the look and
the new terminal / CRT primitives are added here.
"""

from PyQt5.QtCore import Qt, QTimer, QEvent, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QRadialGradient
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    ACCENT,
    ACCENT_HOVER,
    ERROR,
    INPUT_BG,
    LED,
    ON_ACCENT,
    SURFACE_2,
    TERM,
    TEXT,
    TEXT_DIM,
    TEXT_FAINT,
    WARNING,
)
from .icons import icon, pixmap


# --------------------------------------------------------------------------
# Buttons
# --------------------------------------------------------------------------

class Btn(QPushButton):
    """Beveled technical button; text is normalised to uppercase."""

    def __init__(self, text="", kind="secondary", parent=None):
        super().__init__(text.upper(), parent)
        self.setProperty("bt", kind)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(28)

    def setText(self, text):
        super().setText(text.upper())

    def set_icon(self, icon_name, size=14, color=ACCENT):
        self.setIcon(icon(icon_name, size, color))


class IconButton(QPushButton):
    """Small square button carrying only an icon."""

    def __init__(self, icon_name, tooltip="", size=15, color=TEXT_DIM, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.size = size
        self.color_default = color
        self.color_hover = ACCENT_HOVER
        self.setProperty("bt", "icon")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(24, 24)
        self._apply(color)
        if tooltip:
            self.setToolTip(tooltip)

    def _apply(self, color):
        self.setIcon(icon(self.icon_name, self.size, color))

    def enterEvent(self, event):
        self._apply(self.color_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply(self.color_default)
        super().leaveEvent(event)


class NavButton(QPushButton):
    """Sidebar navigation item with a green 'cursor' when active."""

    def __init__(self, icon_name, text, parent=None):
        super().__init__(text.upper(), parent)
        self.icon_name = icon_name
        self.setProperty("bt", "nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(32)
        self._icon_size = 13
        self._hovered = False
        self._apply_color()
        self.toggled.connect(lambda _: self._apply_color())

    def setText(self, text):
        super().setText(text.upper())

    def _color(self):
        if self.isChecked():
            return ACCENT_HOVER
        return ACCENT if not self._hovered else ACCENT_HOVER

    def _apply_color(self):
        self.setIcon(icon(self.icon_name, self._icon_size, self._color()))

    def enterEvent(self, event):
        self._hovered = True
        self._apply_color()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_color()
        super().leaveEvent(event)


# --------------------------------------------------------------------------
# Beveled panel
# --------------------------------------------------------------------------

class Card(QFrame):
    """Retro beveled panel with an `[ TITLE ]` header strip."""

    def __init__(self, title=None, icon_name=None, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if title:
            header = QFrame(objectName="panelHeader")
            head = QHBoxLayout(header)
            head.setContentsMargins(10, 4, 10, 4)
            head.setSpacing(8)
            if icon_name:
                glyph = QLabel()
                glyph.setPixmap(pixmap(icon_name, 13, ACCENT))
                head.addWidget(glyph)
            title_label = QLabel("[ %s ]" % title.upper())
            title_label.setObjectName("panelTitle")
            head.addWidget(title_label)
            head.addStretch(1)
            layout.addWidget(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(12, 10, 12, 10)
        self.body.setSpacing(9)
        layout.addLayout(self.body)


# --------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------

class FieldLabel(QLabel):
    def __init__(self, text):
        super().__init__(text.upper())
        self.setObjectName("fieldLabel")

    def setText(self, text):
        super().setText(text.upper())


class PasswordField(QWidget):
    """Password input with a built-in show/hide toggle."""

    toggled_visibility = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.line = QLineEdit()
        self.line.setEchoMode(QLineEdit.Password)
        self.line.setPlaceholderText("ENTER PASSPHRASE")
        layout.addWidget(self.line, 1)

        self._toggle = QPushButton(self.line)
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.setFixedSize(26, 26)
        self._toggle.setProperty("bt", "icon")
        self._hidden = True
        self.line.installEventFilter(self)
        self._update_eye()
        self._toggle.clicked.connect(self.toggle_visibility)

    def eventFilter(self, obj, event):
        if obj is self.line and event.type() == QEvent.Resize:
            self._position_toggle()
        return super().eventFilter(obj, event)

    def _position_toggle(self):
        x = self.line.width() - 32
        y = (self.line.height() - self._toggle.height()) // 2
        self._toggle.move(max(0, x), max(0, y))

    def _update_eye(self):
        name = "eyeOff" if self._hidden else "eye"
        self._toggle.setIcon(icon(name, 14, TEXT_DIM))
        self._toggle.setToolTip("SHOW PASSPHRASE" if self._hidden else "HIDE PASSPHRASE")

    def toggle_visibility(self):
        self._hidden = not self._hidden
        self.line.setEchoMode(QLineEdit.Password if self._hidden else QLineEdit.Normal)
        self._update_eye()
        self.toggled_visibility.emit(not self._hidden)

    def text(self):
        return self.line.text()

    def setText(self, value):
        self.line.setText(value)
        self.line.setEchoMode(QLineEdit.Password)
        if not self._hidden:
            self._hidden = True
            self._update_eye()

    def clear(self):
        self.line.clear()

    def setEnabled(self, enabled):
        self.line.setEnabled(enabled)
        self._toggle.setEnabled(enabled)
        super().setEnabled(enabled)


class StrengthBar(QWidget):
    """Four-segment password strength meter in terminal colours."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self._score = 0
        self._colors = [TEXT_FAINT, WARNING, ACCENT, ACCENT_HOVER, ACCENT_HOVER]

    def set_score(self, score):
        self._score = max(0, min(4, score))
        self.update()

    def paintEvent(self, event):
        if self._score <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        gap = 3
        seg_w = (w - gap * 3) / 4
        color = QColor(self._colors[self._score])
        for i in range(self._score):
            x = i * (seg_w + gap)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRect(int(x), 0, int(seg_w) + 1, self.height())
        painter.end()


class CheckBox(QCheckBox):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setCursor(Qt.PointingHandCursor)

    def setText(self, text):
        super().setText(text.upper())


# --------------------------------------------------------------------------
# LEDs and status pill
# --------------------------------------------------------------------------

class Led(QWidget):
    """Small status LED with a soft glow when lit."""

    def __init__(self, color="off", radius=5, parent=None):
        super().__init__(parent)
        self._lit = False
        self._color = QColor(LED.get(color, LED["off"]))
        self._dim = QColor(LED["off"])
        self._radius = radius
        d = radius * 2 + 4
        self.setFixedSize(d, d)
        self._blink = QTimer(self)
        self._blink.setSingleShot(True)
        self._blink.timeout.connect(self._toggle)

    def set_color(self, color, lit=True):
        self._color = QColor(LED.get(color, color))
        self._lit = bool(lit)
        self._blink.stop()
        self.update()

    def set_off(self):
        self._lit = False
        self._blink.stop()
        self.update()

    def blink(self, ms=450):
        self._lit = True
        self._blink.start(ms)

    def _toggle(self):
        self._lit = not self._lit
        self.update()
        self._blink.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        r = self._radius
        if self._lit:
            glow = QColor(self._color)
            glow.setAlpha(70)
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QRectF(c.x() - r - 2, c.y() - r - 2, 2 * r + 4, 2 * r + 4))
            painter.setBrush(self._color)
            painter.drawEllipse(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r))
        else:
            painter.setBrush(self._dim)
            painter.drawEllipse(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r))
        painter.end()


class StatusPill(QFrame):
    """LED + uppercase status readout (READY / BUSY / OK / ERR)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusLed")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(7)
        self.led = Led(radius=4)
        layout.addWidget(self.led)
        self.label = QLabel("READY")
        self.label.setObjectName("ledText")
        self.label.setStyleSheet("font-weight: 700; color: %s;" % TEXT_DIM)
        layout.addWidget(self.label)
        self.set_state("idle", "READY")

    def set_state(self, state, text):
        text = text.upper()
        if state == "busy":
            self.led.set_color("amber")
            self.label.setStyleSheet("color: %s;" % WARNING)
        elif state == "ok":
            self.led.set_color("green")
            self.label.setStyleSheet("color: %s;" % ACCENT_HOVER)
        elif state == "err":
            self.led.set_color("red")
            self.label.setStyleSheet("color: %s;" % ERROR)
        else:
            self.led.set_off()
            self.label.setStyleSheet("color: %s;" % TEXT_DIM)
        self.label.setText(text)


# --------------------------------------------------------------------------
# Terminal
# --------------------------------------------------------------------------

class TerminalView(QPlainTextEdit):
    """Black console with coloured log lines and a blinking block cursor."""

    _MAX_LINES = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("terminal")
        self.setReadOnly(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setCursorWidth(0)
        font = QFont("Consolas")
        font.setPointSize(12)
        self.setFont(font)
        self._lines = []          # [(color, text), ...]
        self._block_on = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._tick)
        self._cursor_timer.start(540)

    def write(self, kind, text):
        color = TERM.get(kind, TERM["info"])
        self._lines.append((color, text))
        if len(self._lines) > self._MAX_LINES:
            del self._lines[: len(self._lines) - self._MAX_LINES]
        self._render()

    def clear_log(self):
        self._lines = []
        self._render()

    def _tick(self):
        self._block_on = not self._block_on
        self._render()

    def _render(self):
        from PyQt5.QtGui import QTextCharFormat
        doc = self.document()
        doc.clear()
        cursor = self.textCursor()
        cursor.setPosition(0)
        for color, text in self._lines:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(text + "\n")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(TERM["echo"]))
        cursor.setCharFormat(fmt)
        cursor.insertText("[secenc]$ ")
        if self._block_on:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(TERM["sys"]))
            fmt.setBackground(QColor(ACCENT_HOVER))
            cursor.setCharFormat(fmt)
            cursor.insertText("\u2588")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


def make_log(console, kind, text):
    """Convenience: forward a line to a console widget if present."""
    if console is not None:
        console.write(kind, text)


# --------------------------------------------------------------------------
# CRT overlay (subtle scanlines, vignette, slow drift band)
# --------------------------------------------------------------------------

class CrtOverlay(QWidget):
    """Transparent, mouse-transparent layer painting CRT artefacts.

    Kept deliberately subtle: faint scanlines, a dark corner vignette and a
    slow-moving refresh band. Noise/grain is intentionally omitted to keep
    text fully readable and rendering cheap.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._band = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(42)

    def _step(self):
        self._band = (self._band + 1) % (self.height() + 260)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        # Scanlines every 3 px.
        y = 0
        while y < h:
            painter.fillRect(0, y, w, 1, QColor(0, 0, 0, 16))
            y += 3

        # Very faint refresh band drifting downward.
        band_pos = self._band - 240
        if 0 <= band_pos < h + 240:
            band = QRadialGradient(w / 2, band_pos, 260)
            band.setColorAt(0.0, QColor(140, 255, 170, 10))
            band.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, w, h, band)

        # Corner vignette (radial fade to black).
        vg = QRadialGradient(w / 2, h / 2, max(w, h) * 0.62)
        vg.setColorAt(0.0, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 46))
        painter.fillRect(0, 0, w, h, vg)

        painter.end()


# --------------------------------------------------------------------------
# Toasts
# --------------------------------------------------------------------------

_TOAST_WIDTH = 360
_TOAST_LIVE_MS = 3600


class Toast(QFrame):
    """Transient console notification box."""

    def __init__(self, kind, title, message, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setFixedWidth(_TOAST_WIDTH)

        accent = {
            "ok": ACCENT_HOVER,
            "warn": WARNING,
            "err": ERROR,
            "info": ACCENT,
        }[kind]
        licon = {
            "ok": "checkCircle",
            "warn": "alert",
            "err": "xCircle",
            "info": "info",
        }[kind]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        layout.setSpacing(8)

        glyph = QLabel()
        glyph.setPixmap(pixmap(licon, 16, accent))
        layout.addWidget(glyph, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_label = QLabel("[ %s ]" % title.upper())
        title_label.setStyleSheet("font-weight: 700; color: %s; font-size: 11px;" % accent)
        text_col.addWidget(title_label)
        if message:
            msg_label = QLabel(message)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet("color: %s; font-size: 11px;" % TEXT)
            text_col.addWidget(msg_label)
        layout.addLayout(text_col, 1)

        close_btn = IconButton("close", tooltip="DISMISS", size=12)
        close_btn.clicked.connect(self.close_toast)
        layout.addWidget(close_btn, 0, Qt.AlignTop)

        self.setWindowOpacity(0.0)
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._fade_out)

    def close_toast(self):
        self._fade_out()

    def _fade_out(self):
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(160)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self._cleanup)
        anim.start()
        self._anim = anim

    def _cleanup(self):
        self.setParent(None)
        self.deleteLater()


class ToastManager:
    """Stacks Toast instances in the top-right corner of the host window."""

    def __init__(self, host):
        self.host = host
        self.toasts = []

    def push(self, kind, title, message):
        toast = Toast(kind, title, message, self.host)
        self.toasts.append(toast)
        toast.destroyed.connect(lambda: self._prune(toast))
        toast.show()
        self.reflow()
        toast._fade_timer.start(_TOAST_LIVE_MS)

    def _prune(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
        self.reflow()

    def reflow(self):
        margin = 12
        x = self.host.width() - _TOAST_WIDTH - margin
        y = margin
        for toast in self.toasts:
            toast.adjustSize()
            toast.move(x, y)
            toast.raise_()
            y += toast.height() + 8


# --------------------------------------------------------------------------
# Dialogs
# --------------------------------------------------------------------------

def ask_confirm(parent, title, text) -> bool:
    """Dark-themed yes/no confirmation. Returns True when confirmed."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Warning)
    box.setText(text)
    confirm = box.addButton("CONFIRM", QMessageBox.AcceptRole)
    box.addButton("CANCEL", QMessageBox.RejectRole)
    box.setDefaultButton(confirm)
    box.exec_()
    return box.clickedButton() is confirm


def ask_confirm_overwrite(parent, path) -> bool:
    return ask_confirm(
        parent,
        "FILE EXISTS",
        "DESTINATION FILE ALREADY EXISTS:\n\n%s\n\nOVERWRITE IT?" % path,
    )
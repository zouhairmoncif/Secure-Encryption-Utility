"""Late-80s / early-90s BIOS boot-manager screen, painted pixel-exact."""

from collections import namedtuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt5.QtWidgets import QWidget

NAVY = QColor("#000080")
PALE = QColor("#C0C0C0")
HALO = QColor(120, 150, 255, 85)
TEAL = QColor("#008080")
INVERT = QColor("#2B2B2B")

TITLE = "Python Application Environment v0.9"

MENU_ITEMS = [
    "Launch Main Script (main_app.py)",
    "Run Full Test Suite (pytest)",
    "Generate Code Coverage Report",
    "Edit Environment Configuration (.env)",
    "Check and Install Dependencies",
    "Access Interactive Shell (REPL)",
    "Start in Debug Mode (ipdb)",
    "Open Sphinx Documentation (local)",
]

SYSTEM_ITEMS = [
    "View System Log",
    "Restore Factory Settings",
    "Shutdown/Exit",
]

DESCRIPTIONS = {
    0: "Execute the main entry point of the application. Will run with default profile",
    1: "Run the complete automated test suite through the pytest runner.",
    2: "Produce HTML and terminal coverage statistics for the codebase.",
    3: "Open the environment configuration file for manual editing.",
    4: "Verify required packages are present and install any missing dependencies.",
    5: "Launch a python interactive shell with the project context loaded.",
    6: "Run the main application under the ipdb interactive debugger.",
    7: "Build and open the locally generated Sphinx documentation.",
    8: "Display recent application and environment log entries.",
    9: "Reset all configuration and preferences to their default values.",
    10: "Power down the application environment and exit to the system.",
}

_AWAY = ((-1, 0), (1, 0), (0, -1), (0, 1))


class _Metrics(namedtuple("_Metrics", [
        "font", "fm", "margin", "top", "line",
        "sep_y", "menu_top", "menu_bottom", "rows",
        "pointer_x", "text_x", "panel_x", "panel_w",
        "panel_y", "panel_h"])):
    __slots__ = ()


class BiosBootScreen(QWidget):
    """A faithful emulation of a BIOS / boot manager text screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumSize(640, 480)
        self.setFocusPolicy(Qt.StrongFocus)

        self._labels = list(MENU_ITEMS) + list(SYSTEM_ITEMS)
        self._index = 0
        self._gap_index = len(MENU_ITEMS)

    # --------------------------------------------------------- metrics

    def _metrics(self):
        width = self.width()
        height = self.height()

        font = QFont()
        font.setFamilies(["Fixedsys", "Terminal", "Lucida Console", "Consolas",
                          "Courier New", "monospace"])
        font.setPixelSize(max(12, round(height * 0.021)))
        font.setStyleStrategy(QFont.NoAntialias)
        fm = QFontMetrics(font)

        margin = round(width * 0.05)
        top = round(height * 0.10)
        line = round(fm.height() * 1.25)
        sep_y = top + round(line * 1.45)
        rows = len(self._labels) + 1
        menu_top = sep_y + round(line * 1.15)
        menu_bottom = menu_top + rows * line

        pointer_x = margin
        text_x = margin + fm.horizontalAdvance("> ") + max(4, round(width * 0.006))
        panel_x = round(width * 0.60)
        panel_w = width - margin - panel_x
        panel_y = sep_y + round(line * 0.15)
        panel_h = menu_bottom - panel_y

        return _Metrics(font, fm, margin, top, line, sep_y, menu_top,
                        menu_bottom, rows, pointer_x, text_x, panel_x,
                        panel_w, panel_y, panel_h)

    # --------------------------------------------------------- keyboard

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Down:
            self._index = min(self._index + 1, len(self._labels) - 1)
            self.update()
        elif key == Qt.Key_Up:
            self._index = max(self._index - 1, 0)
            self.update()
        elif key == Qt.Key_Home:
            self._index = 0
            self.update()
        elif key == Qt.Key_End:
            self._index = len(self._labels) - 1
            self.update()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self._index == len(self._labels) - 1:
                self.window().close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        m = self._metrics()
        x = event.pos().x()
        if x < m.panel_x:
            row = (event.pos().y() - m.menu_top) // m.line
            if 0 <= row < len(self._labels):
                row = min(row, self._gap_index - 1) if row < self._gap_index else row - 1
                # correct for the blank gap row between the two groups
                if row < 0:
                    row = 0
                self._index = row
                self.update()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        target = round(width * 3 / 4)
        if abs(target - self.height()) > 1:
            self.resize(width, target)

    # ------------------------------------------------------------- paint

    def paintEvent(self, _event):
        painter = QPainter(self)
        dpr = self.devicePixelRatioF()
        if dpr > 1.0001:
            painter.scale(dpr, dpr)

        m = self._metrics()
        painter.fillRect(0, 0, self.width(), self.height(), NAVY)
        painter.setFont(m.font)

        self._text(painter, (self.width() - m.fm.horizontalAdvance(TITLE)) / 2,
                   m.top, TITLE, halo=True)

        painter.setPen(PALE)
        painter.drawLine(m.margin, m.sep_y, self.width() - m.margin, m.sep_y)

        self._draw_menu(painter, m)
        self._draw_panel(painter, m)

    def _draw_menu(self, painter, m):
        for row in range(len(self._labels)):
            y = m.menu_top + row * m.line
            if row >= self._gap_index:
                y += m.line
            label = self._labels[row]
            selected = row == self._index
            if selected:
                painter.fillRect(m.margin, y - round(m.line * 0.72),
                                 m.panel_x - m.margin - m.line, m.line, TEAL)
                painter.setPen(INVERT)
                painter.drawText(m.pointer_x, y, "> " + label)
            else:
                painter.setPen(PALE)
                self._text(painter, m.text_x, y, label, halo=True)

    def _draw_panel(self, painter, m):
        painter.setPen(PALE)
        painter.drawRect(m.panel_x, m.panel_y, m.panel_w, m.panel_h)
        painter.drawRect(m.panel_x + 2, m.panel_y + 2,
                         m.panel_w - 4, m.panel_h - 4)

        pad = round(m.line * 0.45)
        inner_w = m.panel_w - pad * 2
        lines = self._wrap(m.fm, DESCRIPTIONS[self._index], inner_w)
        ty = m.panel_y + pad + m.fm.ascent()
        for text in lines:
            self._text(painter, m.panel_x + pad, ty, text, halo=True)
            ty += m.line

    # ----------------------------------------------------------- helpers

    def _wrap(self, fm, text, width):
        words = text.split(" ")
        result = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if fm.horizontalAdvance(candidate) <= width:
                current = candidate
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
        return result

    def _text(self, painter, x, y, value, halo=True):
        ix = int(round(x))
        iy = int(round(y))
        if halo:
            painter.setPen(HALO)
            for dx, dy in _AWAY:
                painter.drawText(ix + dx, iy + dy, value)
        painter.setPen(PALE)
        painter.drawText(ix, iy, value)
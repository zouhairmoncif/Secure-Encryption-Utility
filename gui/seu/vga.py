""".-----------------------------------------------------------------------------.
| vga.py — 80x25 character-cell grid renderer for the BIOS-style SEU.          |
|                                                                              |
| A QWidget that paints a two dimensional cell array (char + fg token + bg     |
| token + optional blink color). The screen draws only intend to hit the       |
| public put/fill/box helpers. The widget owns font fallback, the 530 ms       |
| blink phase and the (togglable) CRT overlay.                                 |
`-----------------------------------------------------------------------------"""

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

PALETTE = {
    "bg": "#000080",          # BIOS_BG
    "text": "#C0C0C0",        # BIOS_TEXT
    "dim": "#808080",         # BIOS_TEXT_DIM
    "bright": "#FFFFFF",      # BIOS_TEXT_BRIGHT
    "hlb": "#008080",         # BIOS_HIGHLIGHT_BG (teal)
    "hlt": "#000000",         # BIOS_HIGHLIGHT_TEXT
    "border": "#C0C0C0",     # BIOS_BORDER
    "titlebg": "#808080",     # BIOS_TITLE_BG
    "titletext": "#000000",   # BIOS_TITLE_TEXT
    "warn": "#FFFF00",        # BIOS_WARN_TEXT
    "error": "#FF0000",       # BIOS_ERROR_TEXT
    "success": "#00FF00",     # BIOS_SUCCESS_TEXT
    "keyhint": "#00FFFF",     # BIOS_KEY_HINT
    "keyhintdesc": "#C0C0C0", # BIOS_KEY_HINT_DESC
    "inputbg": "#000080",     # BIOS_INPUT_BG
    "cursor": "#C0C0C0",      # BIOS_INPUT_CURSOR
    "panelbg": "#000080",     # BIOS_PANEL_BG
    "separator": "#C0C0C0",   # BIOS_SEPARATOR
}

FONT_STACK = [
    "Px437 IBM VGA 8x16",
    "Perfect DOS VGA 437",
    "Px437 IBM EGA 8x14",
    "Courier New",
    "Lucida Console",
    "Consolas",
    "monospace",
]

COLS = 80
ROWS = 25
BLINK_MS = 530


class Cell:
    __slots__ = ("char", "fg", "bg", "blink_color")

    def __init__(self, char=" ", fg="text", bg="bg", blink_color=None):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.blink_color = blink_color


class VGAGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cols = COLS
        self._rows = ROWS
        self._cells = [
            [Cell() for _ in range(COLS)] for _ in range(ROWS)
        ]
        self._col_w = 12
        self._row_h = 24
        self._font = None
        self._blink_on = True
        self.crt_scanlines = True
        self.crt_phosphor = True
        self.crt_curvature = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(BLINK_MS)
        self._blink_timer.timeout.connect(self._tick_blink)
        self._blink_timer.start()
        self.setFocusPolicy(Qt.StrongFocus)

    # ---------------------------------------------------------------- access

    def put(self, col, row, text, fg="text", bg="bg", blink=None):
        if row < 0 or row >= self._rows:
            return
        for i, ch in enumerate(text):
            c = col + i
            if c < 0 or c >= self._cols:
                continue
            cell = self._cells[row][c]
            cell.char = ch
            cell.fg = fg
            cell.bg = bg
            cell.blink_color = blink

    def put_char(self, col, row, ch, fg="text", bg="bg", blink=None):
        if 0 <= col < self._cols and 0 <= row < self._rows:
            cell = self._cells[row][col]
            cell.char = ch
            cell.fg = fg
            cell.bg = bg
            cell.blink_color = blink

    def hline(self, col, row, length, ch="─", fg="separator", bg="bg"):
        for i in range(max(0, col), min(self._cols, col + length)):
            cell = self._cells[row][i]
            cell.char = ch
            cell.fg = fg
            cell.bg = bg
            cell.blink_color = None

    def vline(self, col, row, height, ch="│", fg="border", bg="bg"):
        for r in range(row, min(self._rows, row + height)):
            cell = self._cells[r][col]
            cell.char = ch
            cell.fg = fg
            cell.bg = bg
            cell.blink_color = None

    def fill(self, col, row, width, height, ch=" ", fg="text", bg="bg"):
        for r in range(row, min(self._rows, row + height)):
            for i in range(max(0, col), min(self._cols, col + width)):
                cell = self._cells[r][i]
                cell.char = ch
                cell.fg = fg
                cell.bg = bg
                cell.blink_color = None

    def box(self, col, row, width, height, fg="border", bg="bg",
            corners=None, edges=None):
        b = edges or "│─"
        v, h = b[0], b[1]
        c0 = corners or "┌┐└┘"
        x2 = col + width - 1
        y2 = row + height - 1
        self.hline(col + 1, row, width - 2, h, fg, bg)
        self.hline(col + 1, y2, width - 2, h, fg, bg)
        self.vline(col, row + 1, height - 2, v, fg, bg)
        self.vline(x2, row + 1, height - 2, v, fg, bg)
        self.put_char(col, row, c0[0], fg, bg)
        self.put_char(x2, row, c0[1], fg, bg)
        self.put_char(col, y2, c0[2], fg, bg)
        self.put_char(x2, y2, c0[3], fg, bg)

    def clear(self):
        for row in self._cells:
            for cell in row:
                cell.char = " "
                cell.fg = "text"
                cell.bg = "bg"
                cell.blink_color = None

    @property
    def cols(self):
        return self._cols

    @property
    def rows(self):
        return self._rows

    # ---------------------------------------------------------------- blink

    def _tick_blink(self):
        self._blink_on = not self._blink_on
        self.update()

    # -------------------------------------------------------------- geometry

    def sizeHint(self):
        return QSize(self._cols * self._col_w, self._rows * self._row_h)

    def minimumSizeHint(self):
        return QSize(self._cols * 10, self._rows * 20)

    def cell_size(self):
        return self._col_w, self._row_h

    def recompute(self, width, height):
        col_w = max(10, width // self._cols)
        row_h = max(20, height // self._rows)
        used_w = col_w * self._cols
        used_h = row_h * self._rows
        self._col_w = col_w
        self._row_h = row_h
        self._font = self._build_font(col_w, row_h)
        self.update()
        return used_w, used_h

    def _build_font(self, col_w, row_h):
        size = max(8, int(row_h * 0.76))
        font = QFont()
        font.setFamilies(FONT_STACK)
        while size > 8:
            font.setPixelSize(size)
            fm = QFontMetrics(font)
            if fm.horizontalAdvance("W") <= col_w and fm.height() <= row_h:
                return font
            size -= 1
        return font

    # ---------------------------------------------------------------- paint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(PALETTE["bg"]))
        if self._font is None:
            self.recompute(self.width(), self.height())
        painter.setFont(self._font)
        col_w = self._col_w
        row_h = self._row_h
        bright = self._blink_on
        dpr = self.devicePixelRatioF()

        for r in range(self._rows):
            if r * row_h > self.height():
                break
            for c in range(self._cols):
                cell = self._cells[r][c]
                if cell.char == " " and cell.bg == "bg":
                    continue
                x = c * col_w
                y = r * row_h
                bg = cell.blink_color if (cell.blink_color and bright) else cell.bg
                if bg != "bg":
                    painter.fillRect(
                        x, y, col_w, row_h, QColor(PALETTE.get(bg, PALETTE["bg"]))
                    )
                if cell.char != " ":
                    painter.setPen(QColor(PALETTE.get(cell.fg, PALETTE["text"])))
                    px = int(round(x))
                    py = int(round(y))
                    painter.drawText(
                        px, py, col_w, row_h,
                        int(Qt.AlignHCenter | Qt.AlignVCenter), cell.char,
                    )
                    if self.crt_phosphor and cell.fg == "text":
                        painter.setPen(QColor(192, 192, 192, 22))
                        painter.drawText(
                            px, py + 1, col_w, row_h,
                            int(Qt.AlignHCenter | Qt.AlignVCenter), cell.char,
                        )

        if self.crt_scanlines:
            painter.fillRect(
                0, 0, int(self.width() * dpr), int(self.height() * dpr),
                QColor(0, 0, 0, 0),
            )
            pen = QPen(QColor(0, 0, 0, 20))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            y = 0
            while y < self.height():
                painter.drawLine(0, y, int(self.width() * dpr), y)
                y += 2

        if self.crt_curvature:
            w, h = self.width(), self.height()
            outer = QPainterPath()
            outer.addRect(0, 0, w, h)
            inner = QPainterPath()
            inner.addRoundedRect(6, 6, max(1, w - 12), max(1, h - 12), 6, 6)
            pen = QPen(QColor(0, 0, 0, 46), 6)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(outer.subtracted(inner))

        painter.end()
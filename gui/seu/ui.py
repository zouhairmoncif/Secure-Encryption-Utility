"""Screen-drawing primitives for the BIOS-style SEU (pure grid writes)."""

import datetime

COLS = 80
CONTENT_TOP = 2      # between title bar (row 0) and separator (row 1)
CONTENT_BOTTOM = 22  # footer separator sits on row 23, hints on row 24


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def title_bar(grid, title):
    grid.hline(0, 0, COLS, " ", "text", "titlebg")
    grid.fill(0, 0, COLS, 1, " ", "text", "titlebg")
    grid.put(2, 0, title.center(30), "titletext", "titlebg")
    # right-hand status area
    grid.put(60, 0, "SEU v1.0".center(18), "titletext", "titlebg")


def separator(grid):
    grid.hline(0, 1, COLS, "═", "separator", "bg")


def _footer_token(text, is_key):
    return {"t": text, "k": is_key}


def footer(grid):
    grid.hline(0, 23, COLS, "─", "separator", "bg")
    tokens = [
        _footer_token("↑↓ Navigate", False),
        _footer_token("  ", False),
        _footer_token("<Enter> Select", True),
        _footer_token("  ", False),
        _footer_token("<Esc> Back", True),
        _footer_token("  ", False),
        _footer_token("F1 Help", True),
        _footer_token("  ", False),
        _footer_token("F10 Exit", True),
    ]
    total = sum(len(t["t"]) for t in tokens)
    col = (COLS - total) // 2
    for t in tokens:
        grid.put(col, 24, t["t"], "keyhint" if t["k"] else "keyhintdesc", "bg")
        col += len(t["t"])


def wrap(text, width):
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = w
        elif cur:
            cur += " " + w
        else:
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def panel(grid, col, row, width, height, title=None, lines=None, fg="text"):
    grid.box(col, row, width, height, "border", "panelbg")
    if title:
        grid.put(col + 2, row, title, "bright", "panelbg")
        x = col + 2 + len(title)
        grid.put_char(x, row, "─", "border", "panelbg")
    if lines:
        for i, line in enumerate(lines[: height - 2]):
            for j, ch in enumerate(line[: width - 2]):
                grid.put_char(col + 1 + j, row + 1 + i, ch, fg, "panelbg")


def text_block(grid, col, row, text, width, max_lines, fg="text", bg="bg", wrap_=True):
    lines = wrap(text, width) if wrap_ else text.split("\n")
    r = row
    for i, line in enumerate(lines[:max_lines]):
        grid.put(col, r, line.ljust(width)[:width], fg, bg)
        r += 1
    return r


def cursor_date(fmt, when=None):
    dt = when or datetime.datetime.now()
    if fmt == "dot":
        return dt.strftime("%d.%m.%Y")
    return dt.strftime("%Y-%m-%d")


def button(grid, col, row, label, focused=False, enabled=True):
    text = "[ " + label + " ]"
    if not enabled:
        grid.put(col, row, text, "dim", "bg")
    elif focused:
        grid.put(col, row, text, "hlt", "hlb")
    else:
        grid.put(col, row, text, "text", "bg")
    return len(text)


def arrows(grid, col, row, up=True, down=True):
    grid.put_char(col, row, "▲", "bright" if up else "dim", "bg")
    grid.put_char(col + 2, row, "▼", "bright" if down else "dim", "bg")
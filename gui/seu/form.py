"""Generic BIOS-style form field engine (pure grid writes)."""

from . import ui


def _is_focusable(f):
    return f["kind"] in ("input", "toggle", "choice", "button")


def _toggle_value(f):
    f.setdefault("value", False)
    f["value"] = not f.get("value")


def _cycle(f, delta):
    opts = f.get("options") or [f.get("value")]
    idx = opts.index(f.get("value")) if f.get("value") in opts else 0
    idx = (idx + delta) % len(opts)
    f["value"] = opts[idx]


def render(grid, fields, focus, start_row):
    """Render the form starting at start_row; returns last used row + 1."""
    row = start_row
    for i, f in enumerate(fields):
        focused = f["kind"] in ("input", "toggle", "choice", "button") and i == focus
        col = 2
        label = f.get("label") or ""
        if label:
            grid.put(col, row, label[:18].ljust(18), "text", "bg")
            col += 18

        kind = f["kind"]
        if kind == "kv":
            grid.put(col + 2, row, str(f.get("value", "")), "dim", "bg")
        elif kind == "input":
            width = f.get("width", 44)
            value = str(f.get("value", ""))
            caret = min(f.get("caret", len(value)), len(value))
            visual = value
            end = ""
            if len(visual) > width - 2:
                visual = visual[: width - 2]
                end = "►"
            if focused:
                inner_col = col + caret + 1
                grid.put(col + 1, row, visual.ljust(width - 2), "text", "inputbg")
                if inner_col + 1 < col + width:
                    grid.put_char(inner_col, row, "█", "cursor", "inputbg", blink="cursor")
                grid.put(col + 1 + width - 2, row, end, "dim", "inputbg")
            else:
                grid.put(col + 1, row, visual.ljust(width - 2), "dim", "inputbg")
                grid.put(col + 1 + width - 2, row, end, "dim", "inputbg")
        elif kind == "toggle":
            value = "Yes" if f.get("value") else "No"
            if focused:
                grid.put(col + 1, row, "[" + value + "]", "hlt", "hlb")
            else:
                grid.put(col + 1, row, "[" + value + "]", "text", "bg")
        elif kind == "choice":
            value = str(f.get("value", ""))
            shown = f.get("names", {}).get(value, value)
            text = "[ " + shown + " ]"
            if focused:
                grid.put(col + 1, row, text, "hlt", "hlb")
            else:
                grid.put(col + 1, row, text, "text", "bg")
        elif kind == "button":
            text = "[ " + str(f.get("label2", f.get("value", "OK"))) + " ]"
            enabled = f.get("enabled", True)
            if focused:
                grid.put(col, row, text, "hlt" if enabled else "dim", "hlb" if enabled else "bg")
            else:
                grid.put(col, row, text, "text" if enabled else "dim", "bg")
        row += 1
    return row


def handle(grid, fields, focus, key, mods):
    """Returns (action, new_focus, event). event is None or a dict to callbacks."""
    n = len(fields)

    if key == "space" and fields[focus]["kind"] == "input":
        mods = dict(mods, text=" ")
        key = "type"

    def next_focus(i):
        for step in range(1, n + 1):
            j = (i + step) % n
            if fields[j]["kind"] in ("input", "toggle", "choice", "button"):
                return j
        return i

    def prev_focus(i):
        for step in range(1, n + 1):
            j = (i - step) % n
            if fields[j]["kind"] in ("input", "toggle", "choice", "button"):
                return j
        return i

    if key in ("tab", "down"):
        return "focus", next_focus(focus), None
    if key in ("shift_tab", "up"):
        return "focus", prev_focus(focus), None
    if key == "left":
        f = fields[focus]
        if f["kind"] == "input":
            caret = max(0, f.get("caret", 0) - 1)
            f["caret"] = caret
            return "changed", focus, None
        if f["kind"] == "toggle":
            _toggle_value(f)
            return "changed", focus, None
        if f["kind"] == "choice":
            _cycle(f, -1)
            return "changed", focus, None
        return "focus", prev_focus(focus), None
    if key == "right":
        f = fields[focus]
        if f["kind"] == "input":
            caret = min(len(str(f.get("value", ""))), f.get("caret", 0) + 1)
            f["caret"] = caret
            return "changed", focus, None
        if f["kind"] == "toggle":
            _toggle_value(f)
            return "changed", focus, None
        if f["kind"] == "choice":
            _cycle(f, 1)
            return "changed", focus, None
        return "focus", next_focus(focus), None
    if key == "space":
        f = fields[focus]
        if f["kind"] == "toggle":
            _toggle_value(f)
            return "changed", focus, None
        if f["kind"] == "button":
            return "activate", focus, f
        if f["kind"] == "choice":
            _cycle(f, 1)
            return "changed", focus, None
        return "focus", next_focus(focus), None
    if key == "enter":
        f = fields[focus]
        if f["kind"] == "button":
            return "activate", focus, f
        if f["kind"] == "toggle":
            _toggle_value(f)
            return "changed", focus, None
        if f["kind"] == "choice":
            return "focus", next_focus(focus), None
        return "focus", next_focus(focus), None
    if key == "home":
        f = fields[focus]
        if f["kind"] == "input":
            f["caret"] = 0
            return "changed", focus, None
    if key == "end":
        f = fields[focus]
        if f["kind"] == "input":
            f["caret"] = len(str(f.get("value", "")))
            return "changed", focus, None
    if key == "backspace":
        f = fields[focus]
        if f["kind"] == "input":
            value = str(f.get("value", ""))
            caret = f.get("caret", len(value))
            if caret > 0:
                f["value"] = value[: caret - 1] + value[caret:]
                f["caret"] = caret - 1
                return "changed", focus, f
        return "none", focus, None
    if key == "delete":
        f = fields[focus]
        if f["kind"] == "input":
            value = str(f.get("value", ""))
            caret = f.get("caret", len(value))
            if caret < len(value):
                f["value"] = value[:caret] + value[caret + 1:]
                return "changed", focus, f
        return "none", focus, None
    if key == "type":
        f = fields[focus]
        if f["kind"] == "input":
            value = str(f.get("value", ""))
            caret = f.get("caret", len(value))
            ch = mods.get("text", "")
            f["value"] = value[:caret] + ch + value[caret:]
            f["caret"] = caret + len(ch)
            return "changed", focus, f
        return "none", focus, None
    return "none", focus, None
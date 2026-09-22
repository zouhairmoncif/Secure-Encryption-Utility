"""Retro 2000s hacker / security-console design system.

Aesthetic target: an elite security utility running on a Windows XP-era
workstation. Near-black backgrounds, phosphor-green text, graphite bevels,
square corners and monospace typography — no gradients, no rounded "modern"
cards, no glass effects.
"""

# --------------------------------------------------------------------------
# Palette (restrained, terminal-authentic)
# --------------------------------------------------------------------------

BG = "#07080A"               # near-black with a cold graphite cast
BG_SIDEBAR = "#0E1014"       # graphite sidebar
FRAME_RAISED = "#2A3036"     # raised bevel highlight (top/left)
FRAME_DARK = "#000000"       # raised bevel shadow (bottom/right)
PANEL_HEADER = "#11151A"     # crowded panel title strip

SURFACE = "#0B0E10"          # panel interior
SURFACE_2 = "#0F131A"        # hovered surfaces / sunken fields
INPUT_BG = "#050606"         # sunken text fields (black)

TEXT = "#A9E6B8"             # body phosphor
TEXT_BRIGHT = "#86FFA6"      # headings / important output
TEXT_DIM = "#4F8A63"         # secondary text
TEXT_FAINT = "#335040"       # hints, placeholders

ACCENT = "#3CCF6E"           # mid phosphor (borders, icons)
ACCENT_HOVER = "#66FF99"     # hover / focused
ON_ACCENT = "#C6FFD4"

WARNING = "#FFB454"
WARNING_SOFT = "#241A0B"
ERROR = "#FF6B6B"
ERROR_SOFT = "#26110F"
SUCCESS = "#86FFA6"

# Terminal line colours keyed by log kind
TERM = {
    "sys": "#86FFA6",
    "ok": "#63E67B",
    "info": "#5F9E74",
    "warn": "#FFB454",
    "err": "#FF6B6B",
    "echo": "#A9E6B8",
}

LED = {
    "green": "#3CE86C",
    "amber": "#FFB454",
    "red": "#FF6B6B",
    "off": "#1C221E",
}

# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------

FAMILY = '"Consolas", "Lucida Console", "Courier New", monospace'
SIZE_BASE = 12
SIZE_SMALL = 11
SIZE_MICRO = 10
SIZE_TERMINAL = 12
SIZE_PANEL_TITLE = 12
SIZE_HEADING = 13

# --------------------------------------------------------------------------
# Shared QSS fragments
# --------------------------------------------------------------------------

# Raised (bevel up) and sunken (bevel down) 3D frame primitives.
_BEVEL_UP = (
    "border-top: 1px solid %s;\n"
    "border-left: 1px solid %s;\n"
    "border-bottom: 1px solid %s;\n"
    "border-right: 1px solid %s;"
) % (FRAME_RAISED, FRAME_RAISED, FRAME_DARK, FRAME_DARK)

_BEVEL_DOWN = (
    "border-top: 1px solid %s;\n"
    "border-left: 1px solid %s;\n"
    "border-bottom: 1px solid %s;\n"
    "border-right: 1px solid %s;"
) % (FRAME_DARK, FRAME_DARK, FRAME_RAISED, FRAME_RAISED)

BUTTON = f"""
QPushButton {{
    {_BEVEL_UP}
    background: {SURFACE_2};
    color: {ACCENT};
    padding: 5px 14px;
    font-size: {SIZE_SMALL}px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-top: 1px solid {ACCENT_HOVER};
    border-left: 1px solid {ACCENT_HOVER};
    border-bottom: 1px solid {FRAME_DARK};
    border-right: 1px solid {FRAME_DARK};
    background: #10161A;
    color: {ACCENT_HOVER};
}}
QPushButton:pressed {{
    {_BEVEL_DOWN}
    background: #07090B;
    color: {SUCCESS};
    padding: 6px 14px 4px 14px;
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background: {SURFACE};
    border: 1px solid #12161A;
}}
QPushButton:focus {{ outline: none; }}
"""

BUTTON_PRIMARY = f"""
QPushButton[bt="primary"] {{
    {_BEVEL_UP}
    background: #0F1D14;
    color: {TEXT_BRIGHT};
    border-left: 2px solid {FRAME_RAISED};
    border-top: 2px solid {FRAME_RAISED};
    font-weight: 700;
    padding: 6px 18px;
}}
QPushButton[bt="primary"]:hover {{
    background: #143020;
    border-top: 2px solid {ACCENT_HOVER};
    border-left: 2px solid {ACCENT_HOVER};
    color: {ON_ACCENT};
}}
QPushButton[bt="primary"]:pressed {{
    {_BEVEL_DOWN}
    background: {INPUT_BG};
    color: {TEXT_BRIGHT};
    padding: 8px 18px 4px 18px;
}}
QPushButton[bt="primary"]:disabled {{
    color: {TEXT_FAINT};
    background: {SURFACE};
    border: 1px solid #12161A;
}}
"""

BUTTON_AMBER = f"""
QPushButton[bt="amber"] {{
    {_BEVEL_UP}
    background: #171310;
    color: {WARNING};
    font-weight: 600;
}}
QPushButton[bt="amber"]:hover {{
    border-top: 1px solid {WARNING};
    border-left: 1px solid {WARNING};
    color: {WARNING};
    background: #1F1A12;
}}
QPushButton[bt="amber"]:pressed {{
    {_BEVEL_DOWN}
    background: #0C0A08;
}}
QPushButton[bt="amber"]:disabled {{ color: {TEXT_FAINT}; }}
"""

BUTTON_ICON = f"""
QPushButton[bt="icon"] {{
    background: transparent;
    border: none;
    padding: 0px;
}}
QPushButton[bt="icon"]:hover {{ background: {SURFACE_2}; }}
QPushButton[bt="icon"]:pressed {{ background: {INPUT_BG}; }}
QPushButton[bt="icon"]:disabled {{ background: transparent; }}
"""

BUTTON_NAV = f"""
QPushButton[bt="nav"] {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    color: {TEXT_DIM};
    text-align: left;
    padding: 7px 10px;
    font-size: {SIZE_SMALL}px;
    font-weight: 600;
}}
QPushButton[bt="nav"]:hover {{
    background: #0E1418;
    color: {ACCENT_HOVER};
}}
QPushButton[bt="nav"]:checked {{
    background: #10201A;
    border-left: 3px solid {ACCENT_HOVER};
    color: {TEXT_BRIGHT};
}}
"""

INPUT = f"""
QLineEdit, QTextEdit, QPlainTextEdit {{
    {_BEVEL_DOWN}
    background: {INPUT_BG};
    color: {ACCENT_HOVER};
    padding: 5px 9px;
    font-size: {SIZE_BASE}px;
    font-family: {FAMILY};
    selection-background-color: {ACCENT};
    selection-color: #07130B;
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-top: 1px solid {ACCENT};
    border-left: 1px solid {ACCENT};
    border-bottom: 1px solid {FRAME_RAISED};
    border-right: 1px solid {FRAME_RAISED};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT_HOVER};
    background: #08100A;
}}
QLineEdit:disabled {{
    color: {TEXT_FAINT};
    background: {SURFACE};
}}
QLineEdit[echoMode="2"] {{
    color: {ACCENT_HOVER};
    font-weight: 700;
    letter-spacing: 2px;
}}
"""

COMBO = f"""
QComboBox {{
    {_BEVEL_DOWN}
    background: {INPUT_BG};
    color: {ACCENT_HOVER};
    padding: 5px 10px;
    font-size: {SIZE_SMALL}px;
    font-family: {FAMILY};
}}
QComboBox:hover {{
    border-top: 1px solid {ACCENT};
    border-left: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {ACCENT};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {FRAME_RAISED};
    color: {ACCENT_HOVER};
    selection-background-color: {ACCENT};
    selection-color: #07130B;
    outline: 0;
    padding: 2px;
}}
"""

CHECKBOX = f"""
QCheckBox {{
    color: {TEXT};
    font-size: {SIZE_SMALL}px;
    font-family: {FAMILY};
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    {_BEVEL_DOWN}
    background: {INPUT_BG};
}}
QCheckBox::indicator:hover {{
    border-top: 1px solid {ACCENT};
    border-left: 1px solid {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT_HOVER};
}}
QCheckBox:disabled {{ color: {TEXT_FAINT}; }}
"""

PROGRESS = f"""
QProgressBar {{
    {_BEVEL_DOWN}
    background: {INPUT_BG};
    color: {TEXT_DIM};
    font-size: {SIZE_MICRO}px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-right: 1px solid {ACCENT_HOVER};
    margin: 0px;
}}
"""

SCROLLBAR = f"""
QScrollBar:vertical {{
    background: {SURFACE}
    width: 12px;
    border-left: 1px solid #13171B;
}}
QScrollBar::handle:vertical {{
    background: #1C2228;
    border: 1px solid {FRAME_RAISED};
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #24303A; }}
QScrollBar::handle:vertical:pressed {{ background: #12161A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 12px;
    background: #14181D;
    border: 1px solid {FRAME_RAISED};
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{
    background: {SURFACE};
    height: 12px;
    border-top: 1px solid #13171B;
}}
QScrollBar::handle:horizontal {{
    background: #1C2228;
    border: 1px solid {FRAME_RAISED};
    min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 12px;
    background: #14181D;
    border: 1px solid {FRAME_RAISED};
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
"""

TOOLTIP = f"""
QToolTip {{
    background: {INPUT_BG};
    color: {ACCENT_HOVER};
    border: 1px solid {ACCENT};
    padding: 4px 7px;
    font-size: {SIZE_SMALL}px;
    font-family: {FAMILY};
}}
"""


def build_stylesheet() -> str:
    return "\n".join([
        f"""
        * {{ font-family: {FAMILY}; }}
        QWidget {{ color: {TEXT}; font-size: {SIZE_BASE}px; background: transparent; }}
        QMainWindow, QWidget#rootBg {{ background: {BG}; }}

        QFrame#sidebar {{
            background: {BG_SIDEBAR};
            border-right: 1px solid {FRAME_DARK};
            border-left: 3px solid {FRAME_RAISED};
        }}
        QFrame#topBar {{
            background: {BG};
            border-bottom: 1px solid #12161A;
        }}
        QFrame#statusBarQFrame {{
            background: {BG_SIDEBAR};
            border-top: 1px solid #12161A;
        }}
        QFrame#panel {{
            {_BEVEL_UP}
            background: {SURFACE};
        }}
        QFrame#panelHeader {{
            background: {PANEL_HEADER};
            {_BEVEL_DOWN}
        }}
        QFrame#toast {{
            {_BEVEL_UP}
            background: {INPUT_BG};
        }}
        QFrame#historyRow {{
            background: {INPUT_BG};
            border-top: 1px solid #15191D;
            border-bottom: 1px solid #050607;
        }}
        QFrame#historyRow:hover {{ background: #0B110D; }}
        QWidget#statusLed {{ background: {SURFACE_2}; border: 1px solid #1A2026; }}

        QLabel {{ color: {TEXT}; }}
        QLabel[role="dim"] {{ color: {TEXT_DIM}; }}
        QLabel[role="faint"] {{ color: {TEXT_FAINT}; }}
        QLabel[role="bright"] {{ color: {TEXT_BRIGHT}; }}
        QLabel#topTitle {{ font-size: {SIZE_HEADING}px; font-weight: 700; color: {TEXT_BRIGHT}; }}
        QLabel#topSubtitle {{ font-size: {SIZE_MICRO}px; color: {TEXT_DIM}; }}
        QLabel#panelTitle {{ font-size: {SIZE_PANEL_TITLE}px; font-weight: 700; color: {ACCENT_HOVER}; }}
        QLabel#brandName {{ font-size: {SIZE_HEADING}px; font-weight: 700; color: {ACCENT_HOVER}; }}
        QLabel#brandTagline {{ font-size: {SIZE_MICRO}px; color: {TEXT_FAINT}; }}
        QLabel#hint {{ font-size: {SIZE_SMALL}px; color: {TEXT_FAINT}; }}
        QLabel#fieldLabel {{ font-size: {SIZE_SMALL}px; color: {TEXT_DIM}; font-weight: 600; }}
        QLabel#statusText {{ font-size: {SIZE_SMALL}px; color: {TEXT_DIM}; }}
        QLabel#versionLabel {{ font-size: {SIZE_MICRO}px; color: {TEXT_FAINT}; }}
        QLabel#ledText {{ font-size: {SIZE_MICRO}px; color: {TEXT_DIM}; }}
        QLabel#terminalPrompt {{ font-size: {SIZE_TERMINAL}px; color: {ACCENT_HOVER}; }}
        """,
        BUTTON,
        BUTTON_PRIMARY,
        BUTTON_AMBER,
        BUTTON_ICON,
        BUTTON_NAV,
        INPUT,
        COMBO,
        CHECKBOX,
        PROGRESS,
        SCROLLBAR,
        TOOLTIP,
        f"""
        QMessageBox {{ background: {SURFACE}; }}
        QMessageBox QLabel {{ color: {ACCENT_HOVER}; font-family: {FAMILY}; }}
        QMenu {{ background: {SURFACE_2}; border: 1px solid {FRAME_RAISED}; }}
        QMenu::item {{ padding: 5px 24px; color: {TEXT}; font-family: {FAMILY}; font-size: {SIZE_SMALL}px; }}
        QMenu::item:selected {{ background: {ACCENT}; color: #07130B; }}
        QHeaderView::section {{
            background: {PANEL_HEADER};
            border: none;
            border-right: 1px solid #1A2026;
            padding: 5px 8px;
            color: {ACCENT};
            font-weight: 600;
            font-family: {FAMILY};
        }}
        QTableWidget {{
            background: {INPUT_BG};
            border: 1px solid #15191D;
            gridline-color: #15191D;
            color: {TEXT};
            font-family: {FAMILY};
        }}
        QSplitter::handle {{ background: #12161A; }}
        QTextEdit#terminal, QPlainTextEdit#terminal {{
            background: #020302;
            border: none;
            color: {ACCENT};
            font-family: {FAMILY};
            font-size: {SIZE_TERMINAL}px;
            selection-background-color: {ACCENT};
            selection-color: #02100A;
        }}
        """,
    ])
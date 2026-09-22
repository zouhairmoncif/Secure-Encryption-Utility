"""Icon system.

Defines a small, consistent set of minimalist line icons (Feather style) as
SVG templates that are rendered on demand at any size and colour. This keeps
the interface crisp on high-DPI displays without shipping binary assets.
"""

import math

from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

_STROKE = (
    "stroke='{c}' stroke-width='1.8' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'"
)


def _gear_path(teeth=8, r_outer=9.8, r_inner=7.2):
    """Parametric star-gear outline so the gear keeps clean proportions."""
    pts = []
    n = teeth * 2
    step = math.pi / n
    ang = -math.pi / 2
    for i in range(n):
        r = r_outer if i % 2 == 0 else r_inner
        pts.append("12.0,12.0")
        pts.append(f"{12 + r * math.cos(ang):.2f},{12 + r * math.sin(ang):.2f}")
        ang += step
    return "M" + " L".join(pts[2::2]) + " Z"


_GEAR = _gear_path()

ICONS = {
    "shield": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M12 2.3L20 5.6v6.1c0 4.8-3.4 8.5-8 10-4.6-1.5-8-5.2-8-10V5.6l8-3.3z' "
        f"fill='{{c}}' opacity='0.22'/>"
        f"<path d='M12 2.3L20 5.6v6.1c0 4.8-3.4 8.5-8 10-4.6-1.5-8-5.2-8-10V5.6l8-3.3z' "
        f"fill='none' stroke='{{c}}' stroke-width='1.6' stroke-linejoin='round'/>"
        f"<path d='M8.4 12.1l2.4 2.4 4.8-4.8' stroke='{{c}}' stroke-width='2' "
        f"fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>"
    ),
    "lock": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<rect x='4.5' y='10.5' width='15' height='10' rx='2.6' {_STROKE}/>"
        f"<path d='M8 10.5V8a4 4 0 0 1 8 0v2.5' {_STROKE}/>"
        f"<path d='M12 13.8v2.6' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/>"
        f"<circle cx='12' cy='18.4' r='0.9' fill='{{c}}' stroke='none'/></svg>"
    ),
    "unlock": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<rect x='4.5' y='10.5' width='15' height='10' rx='2.6' {_STROKE}/>"
        f"<path d='M8 10.5V8a4 4 0 0 1 7.6-1.7' {_STROKE}/>"
        f"<path d='M12 13.8v2.6' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/>"
        f"<circle cx='12' cy='18.4' r='0.9' fill='{{c}}' stroke='none'/></svg>"
    ),
    "clock": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<circle cx='12' cy='12' r='8.5' {_STROKE}/>"
        f"<path d='M12 7.5V12l3 2' {_STROKE}/></svg>"
    ),
    "gear": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='{_GEAR}' stroke='{{c}}' stroke-width='1.5' fill='none' stroke-linejoin='round'/>"
        f"<circle cx='12' cy='12' r='3' stroke='{{c}}' stroke-width='1.6' fill='none'/></svg>"
    ),
    "info": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<circle cx='12' cy='12' r='8.5' {_STROKE}/>"
        f"<circle cx='12' cy='8.2' r='1.05' fill='{{c}}' stroke='none'/>"
        f"<path d='M12 11v5' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/></svg>"
    ),
    "alert": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M12 3.6L21.4 19.4H2.6L12 3.6z' {_STROKE}/>"
        f"<path d='M12 9.4v4.4' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/>"
        f"<circle cx='12' cy='17' r='1' fill='{{c}}' stroke='none'/></svg>"
    ),
    "check": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M4.5 12.6l4.6 4.6L19.5 6.8' stroke='{{c}}' stroke-width='2.2' "
        f"fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>"
    ),
    "checkCircle": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<circle cx='12' cy='12' r='8.5' {_STROKE}/>"
        f"<path d='M8.4 12.4l2.4 2.4 4.6-5' stroke='{{c}}' stroke-width='1.9' "
        f"fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>"
    ),
    "xCircle": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<circle cx='12' cy='12' r='8.5' {_STROKE}/>"
        f"<path d='M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6' stroke='{{c}}' stroke-width='1.9' "
        f"fill='none' stroke-linecap='round'/></svg>"
    ),
    "close": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M6 6l12 12M18 6L6 18' stroke='{{c}}' stroke-width='2' "
        f"fill='none' stroke-linecap='round'/></svg>"
    ),
    "folder": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M3.6 7.6a2 2 0 0 1 2-2h3.4l2 2.4h7.4a2 2 0 0 1 2 2v8.2a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V7.6z' {_STROKE}/>"
        f"<path d='M3.6 10.6h16.8' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/></svg>"
    ),
    "save": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M4.6 4.6h10.8l4 4v10.8h-14.8V4.6z' {_STROKE}/>"
        f"<path d='M8 4.6v4.4h6V4.6' {_STROKE}/>"
        f"<path d='M8 19.4v-5.8h8v5.8' {_STROKE}/></svg>"
    ),
    "eye": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M2.6 12S6 5.9 12 5.9 21.4 12 21.4 12 18 18.1 12 18.1 2.6 12 2.6 12z' {_STROKE}/>"
        f"<circle cx='12' cy='12' r='2.4' {_STROKE}/></svg>"
    ),
    "eyeOff": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M2.6 12S6 5.9 12 5.9c1.7 0 3.2.4 4.5 1.1' {_STROKE}/>"
        f"<path d='M21.4 12S18 18.1 12 18.1c-1.6 0-3-.4-4.2-1' {_STROKE}/>"
        f"<path d='M4 4l16 16' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/>"
        f"<path d='M10.5 10.6a2 2 0 0 0 2.8 2.8' {_STROKE}/></svg>"
    ),
    "refresh": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M20.4 12a8.4 8.4 0 1 1-2.5-5.9L20.4 8.6' {_STROKE}/>"
        f"<path d='M20.4 3.8v4.8h-4.8' {_STROKE}/></svg>"
    ),
    "zap": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M13 2.5L4.5 13.5h6.5l-1 8L18.5 10.5H12l1-8z' stroke='{{c}}' stroke-width='1.7' "
        f"fill='none' stroke-linejoin='round'/></svg>"
    ),
    "trash": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<path d='M4.5 6.5h15' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/>"
        f"<path d='M9 6.5V5.2A1.6 1.6 0 0 1 10.6 3.6h2.8A1.6 1.6 0 0 1 15 5.2v1.3' {_STROKE}/>"
        f"<path d='M6.6 6.5L7.5 19a1.5 1.5 0 0 0 1.5 1.4h6A1.5 1.5 0 0 0 16.5 19l.9-12.5' {_STROKE}/>"
        f"<path d='M10 10.5v6M14 10.5v6' stroke='{{c}}' stroke-width='1.8' stroke-linecap='round'/></svg>"
    ),
    "key": (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
        f"<circle cx='7.4' cy='15.6' r='3.7' {_STROKE}/>"
        f"<path d='M10.2 12.8L20.5 4.5' {_STROKE}/>"
        f"<path d='M15.8 7.4l2.8 2.8M18.6 4.6l2 2' {_STROKE}/></svg>"
    ),
}


def pixmap(name, size, color, dpr=1.0):
    """Render an icon as a transparent QPixmap at the requested size/colour."""
    template = ICONS[name]
    svg = template.replace("{c}", QColor(color).name())
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixel_size = int(round(size * dpr))
    pm = QPixmap(pixel_size, pixel_size)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def icon(name, size, color):
    """Return a themed QIcon for the given icon name."""
    return QIcon(pixmap(name, size, color))
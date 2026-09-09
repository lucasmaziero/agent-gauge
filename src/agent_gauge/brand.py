"""The marks this app wears: one per agent it can watch, plus its own.

Each agent's mark carries its own colour and its own size correction, because
the header's whole job is saying the two apart. Grey overrides both when the
agent is unwell: an indicator outranks a logo.

`gauge()` is the app's own mark. Paths are embedded as strings so there is no
data file for PyInstaller to miss.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import paint, theme

# The official Claude Code mark, with the fill parameterized. The two holes in
# the path (x 6..7.5 and 16.5..18) are its eyes.
_CLAWD = (
    "M20.998 10.949H24v3.102h-3v3.028h-1.487V20H18v-2.921h-1.487V20H15v-2.921H9V20"
    "H7.488v-2.921H6V20H4.487v-2.921H3V14.05H0V10.95h3V5h17.998v5.949zM6 10.949h1."
    "488V8.102H6v2.847zm10.51 0H18V8.102h-1.49v2.847z"
)

# Kept verbatim from installer/codex-mark.svg.
_CODEX = (
    "M8.086.457a6.105 6.105 0 013.046-.415c1.333.153 2.521.72 3.564 1.7a.117."
    "117 0 00.107.029c1.408-.346 2.762-.224 4.061.366l.063.03.154.076c1.357.7"
    "03 2.33 1.77 2.918 3.198.278.679.418 1.388.421 2.126a5.655 5.655 0 01-.1"
    "8 1.631.167.167 0 00.04.155 5.982 5.982 0 011.578 2.891c.385 1.901-.01 3"
    ".615-1.183 5.14l-.182.22a6.063 6.063 0 01-2.934 1.851.162.162 0 00-.108."
    "102c-.255.736-.511 1.364-.987 1.992-1.199 1.582-2.962 2.462-4.948 2.451-"
    "1.583-.008-2.986-.587-4.21-1.736a.145.145 0 00-.14-.032c-.518.167-1.04.1"
    "91-1.604.185a5.924 5.924 0 01-2.595-.622 6.058 6.058 0 01-2.146-1.781c-."
    "203-.269-.404-.522-.551-.821a7.74 7.74 0 01-.495-1.283 6.11 6.11 0 01-.0"
    "17-3.064.166.166 0 00.008-.074.115.115 0 00-.037-.064 5.958 5.958 0 01-1"
    ".38-2.202 5.196 5.196 0 01-.333-1.589 6.915 6.915 0 01.188-2.132c.45-1.4"
    "84 1.309-2.648 2.577-3.493.282-.188.55-.334.802-.438.286-.12.573-.22.861"
    "-.304a.129.129 0 00.087-.087A6.016 6.016 0 015.635 2.31C6.315 1.464 7.13"
    "2.846 8.086.457zm-.804 7.85a.848.848 0 00-1.473.842l1.694 2.965-1.688 2."
    "848a.849.849 0 001.46.864l1.94-3.272a.849.849 0 00.007-.854l-1.94-3.393z"
    "m5.446 6.24a.849.849 0 000 1.695h4.848a.849.849 0 000-1.696h-4.848z"
)

_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">{defs}'
    '<path clip-rule="evenodd" fill-rule="evenodd" fill="{fill}" d="{path}"/></svg>'
)

# The gradient runs down the ink itself, not the viewBox: a mark inset in its
# box would otherwise start partway along the ramp and lose one end of it.
_DEFS = (
    '<defs><linearGradient id="g" gradientUnits="userSpaceOnUse"'
    ' x1="12" y1="{top}" x2="12" y2="{bottom}">{stops}</linearGradient></defs>'
)
_STOP = '<stop offset="{at}" stop-color="{color}"/>'


@dataclass(frozen=True)
class Mark:
    """One agent's mark, and how much of the viewBox its ink actually fills.

    The two differ - Clawd draws in the y 5..20 band, Codex fills all 24 - so
    each carries its own, measured rather than read off the file. One shared
    number would make one of them half again too big.
    """

    path: str
    ink_height: float
    ink: str | tuple[tuple[float, str], ...] = theme.ACCENT.name()   # flat, or gradient stops
    tint: str = theme.ACCENT.name()      # one solid colour, for text beside the mark
    optical: float = 1.0                 # how big it *looks*, not how tall it is


# The tint is the ramp's middle stop: the solid blue at its foot measures 2.8:1
# against the panel, unreadable as small caps, where this one measures 6.7:1.
# The 1.15 is optical - at the same asked height Clawd is 20.8pt wide and Codex
# a 13pt square, two thirds the ink. Parity would need 1.25, which makes Codex
# the taller mark and overcorrects.
MARKS = {
    "claude": Mark(_CLAWD, 15.0, theme.ACCENT.name(), theme.ACCENT.name()),
    "codex": Mark(_CODEX, 24.0,
                  ((0.0, "#B1A7FF"), (0.5, "#7A9DFF"), (1.0, "#3941FF")),
                  "#7A9DFF", 1.15),
}
FALLBACK = "claude"

_VIEWBOX = 24.0
_cache: dict[tuple[str, int, str, float], QPixmap] = {}


def tint(key: str) -> QColor:
    """The agent's one solid colour, for text that sits beside its mark."""
    return QColor(MARKS.get(key, MARKS[FALLBACK]).tint)


def _fill(chosen: Mark, color: QColor | None) -> tuple[str, str]:
    """The `fill` attribute for this mark, and any `<defs>` it needs."""
    if color is not None:
        return color.name(), ""
    if isinstance(chosen.ink, str):
        return chosen.ink, ""

    top = (_VIEWBOX - chosen.ink_height) / 2
    stops = "".join(_STOP.format(at=at, color=c) for at, c in chosen.ink)
    return "url(#g)", _DEFS.format(top=top, bottom=top + chosen.ink_height, stops=stops)


def mark(key: str, height: int, color: QColor | None = None,
         dpr: float = 1.0) -> QPixmap:
    """The named agent's mark, measured on its drawn band, not its viewBox.

    `color` forces a flat tint - the grey an unwell agent wears. Left out, the
    mark keeps its own. The pixmap comes out taller than asked because the
    viewBox has empty rows above and below, and that slack is what centres the
    mark on a text line. Pass devicePixelRatioF to stay crisp above 100%.
    """
    cache_key = (key, height, color.name() if color is not None else "own", dpr)
    if cache_key in _cache:
        return _cache[cache_key]

    chosen = MARKS.get(key, MARKS[FALLBACK])
    box = height * chosen.optical * _VIEWBOX / chosen.ink_height
    pm = QPixmap(int(box * dpr), int(box * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    fill, defs = _fill(chosen, color)
    svg = _SVG.format(fill=fill, defs=defs, path=chosen.path)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p, QRectF(0, 0, box, box))
    p.end()

    _cache[cache_key] = pm
    return pm


# Far enough round to read as a measurement, short of the gap closing. The icon
# generator imports it so the About card and the taskbar cannot drift apart.
ARC_PCT = 72.0


def gauge(height: int, color: QColor = theme.ACCENT, dpr: float = 1.0) -> QPixmap:
    """This project's own mark - the ring, not a mascot.

    The app watches more than one agent, so no agent's face can stand for it.
    Drawn rather than embedded: tools/gen_icon.py already draws it this way for
    every icon size, and an SVG would be a third description of one shape.
    """
    box = float(height)
    pm = QPixmap(int(box * dpr), int(box * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)

    # The stroke is centred on the radius, so half of it falls outside: without
    # the inset the ring is clipped flat at four points.
    thickness = max(box * 0.20, 2.0)
    radius = (box - thickness) / 2
    center = QPointF(box / 2, box / 2)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # A ring with a gap and nothing behind it reads as a loading spinner. The
    # full track is what makes it a gauge - something measured against a whole.
    paint.ring(p, center, radius, thickness, 100.0, color=theme.BORDER, track=None)
    paint.ring(p, center, radius, thickness, ARC_PCT, color=color, track=None)
    p.end()
    return pm

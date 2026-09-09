"""The marks this app wears: one per agent it can watch, plus its own.

`gauge()` is the app's - the ring, drawn here and shared with the icon
generator. The two below are the agents' and stand only for whose numbers are
on screen.

Both are the agents' official marks, drawn from their own SVGs, and each wears
its own colour: Anthropic's coral, and the blue-violet gradient OpenAI gives
Codex. They used to share the theme accent, which made the two agents look
alike in the one place whose entire job is saying them apart - a Codex user
glancing at the header saw Claude's colour over Codex's numbers.

The colour gives way to grey when the agent is unwell, because that signal
matters more than the branding: a mark that stayed on-brand through an outage
would be a logo, not an indicator.

Both are embedded as strings so there is no data file for PyInstaller to miss.
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

# The official Codex mark, kept verbatim from installer/codex-mark.svg. Used the
# same way Clawd is: to say whose numbers are on screen. Neither is this
# project's own mark - the app's is the gauge, in gauge() below.
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

    The height matters because the two differ: Clawd is drawn in the y 5..20
    band and the Codex mark fills the whole 24, both measured rather than read
    off the file. Sizing every mark as though it filled the box would have made
    Clawd two thirds the height it was asked for; sizing them all as though they
    were Clawd would have made Codex half again too big.
    """

    path: str
    ink_height: float
    # The mark's own colour: one value, or the stops of a vertical gradient as
    # (offset, colour). Used whenever the caller does not force a flat tint.
    ink: str | tuple[tuple[float, str], ...] = theme.ACCENT.name()
    # One solid colour standing for this agent in text beside the mark. A
    # gradient cannot letter a word, so this is picked, not derived.
    tint: str = theme.ACCENT.name()
    # Correction for how big the mark *looks* rather than how tall it is. See
    # `mark()`: matching height alone leaves a compact shape reading small.
    optical: float = 1.0


MARKS = {
    "claude": Mark(_CLAWD, 15.0, theme.ACCENT.name(), theme.ACCENT.name()),
    # OpenAI's own ramp for Codex, top to bottom, taken from the official SVG.
    # The tint is the middle stop, not the solid blue at the foot of it: that
    # one measures 2.8:1 against the panel and is unreadable as small caps,
    # where this one measures 6.7:1 - better than the coral it replaces.
    # Drawn 15% over its asked height. Matching height alone left it reading
    # small beside Clawd: at 13pt both are 13pt tall, but Clawd is 20.8pt wide
    # and Codex 13pt square - 123 square points of ink against 192, two thirds
    # the visual mass. Full parity would need 1.25, and that makes Codex the
    # taller mark, which overcorrects into looking bigger. Measured, then
    # chosen by looking at the two side by side.
    "codex": Mark(_CODEX, 24.0,
                  ((0.0, "#B1A7FF"), (0.5, "#7A9DFF"), (1.0, "#3941FF")),
                  "#7A9DFF", 1.15),
}


def tint(key: str) -> QColor:
    """The agent's one solid colour, for text that sits beside its mark."""
    return QColor(MARKS.get(key, MARKS[FALLBACK]).tint)
FALLBACK = "claude"

_VIEWBOX = 24.0

_cache: dict[tuple[str, int, str, float], QPixmap] = {}


def _fill(chosen: Mark, color: QColor | None) -> tuple[str, str]:
    """How to paint this mark: the `fill` attribute, and any `<defs>` it needs.

    A colour forces a flat tint - that is the grey an unwell agent wears, and it
    has to beat the branding. Without one the mark uses its own ink, which for
    Codex is a gradient and so needs a definition alongside it.
    """
    if color is not None:
        return color.name(), ""
    if isinstance(chosen.ink, str):
        return chosen.ink, ""

    top = (_VIEWBOX - chosen.ink_height) / 2
    stops = "".join(_STOP.format(at=at, color=c) for at, c in chosen.ink)
    return "url(#g)", _DEFS.format(top=top, bottom=top + chosen.ink_height, stops=stops)


def mark(key: str, height: int, color: QColor | None = None,
         dpr: float = 1.0) -> QPixmap:
    """The named agent's mark, `height` pixels tall, measured on the drawn band.

    `color` forces a flat tint and is how an unwell agent goes grey. Left out,
    the mark wears its own colour - which is the point of having two.

    The pixmap comes out taller than requested because the viewBox has empty
    rows above and below; that transparent slack is what centers the mascot on a
    text line. Pass the window's devicePixelRatioF so it stays crisp when
    Windows scaling is above 100%.
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



# How far round the gauge goes when it stands for the app rather than a reading.
# Far enough to read as a measurement, short of the point where the gap closes.
# The icon generator imports this: the mark on the About card and the mark on
# the taskbar are the same object, and drifting apart would make the app look
# like two products.
ARC_PCT = 72.0


def gauge(height: int, color: QColor = theme.ACCENT, dpr: float = 1.0) -> QPixmap:
    """This project's own mark - the ring, not a mascot.

    Clawd and the Codex mark say whose numbers are on screen. Neither can stand
    for the app: it watches more than one agent, and wearing one agent's face
    while showing the other's numbers is a plain untruth. The About card is
    about Agent Gauge, so it wears the gauge.

    Drawn rather than embedded because it is two arcs, and because
    tools/gen_icon.py already draws it this way for every icon size - a shared
    SVG would be a third description of the same shape.
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

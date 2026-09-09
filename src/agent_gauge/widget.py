"""The floating bar.

Each block answers a different question, so no number appears twice: the ring
says how much of the 5h window is spent, the first row says how long until it
resets, and the second row covers the weekly window.

Frameless, always on top, kept off the taskbar (Qt.Tool) and dragged with the
left button. A click without a drag opens the panel.

The saved position is honoured everywhere except a Wayland session, where the
protocol gives a window no say in where it is placed; `app.prefer_x11` steers
Linux onto XWayland for that reason.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from . import brand, paint, providers, theme
from .i18n import t
from .poller import Snapshot
from .theme import LG, SM

# The ring is sized so the percent sign fits beside the number. Measured at the
# text's own height (a circle is narrower there than at its equator), the inner
# radius has to clear "38%" at 19.5px and "100%" at 20.4px; R=27 with a 6px
# stroke leaves 3.4px and 2.9px of air. The card keeps its height, so the gauge
# simply runs closer to the edges - 9px of padding instead of 16.
RING_R, RING_T = 27.0, 6.0
CARD_H = 78
CARD_FULL = 246                         # pays for the ring growth and the separator column
CARD_COMPACT = CARD_H                   # ring only
M = 12                                  # transparent margin reserved for the shadow

RING_C = QPointF(M + LG + RING_R, M + CARD_H / 2)   # full layout only
ORBIT_R = RING_R + RING_T / 2 + 3.5     # refresh ring, outside the gauge
ORBIT_T = 2.5
COL_X = M + LG + RING_R * 2 + LG        # text column
MENU_W = 32             # right column: mascot on top, menu dots below
ROW_H = 24
LABEL_W = 36            # label, then air, the dot, air again
RING_TEXT_PT = (15, 8)  # number, unit: up to two digits
RING_TEXT_PT_WIDE = (12, 7)   # 100 needs a step down to keep its air
RING_TEXT_MIN = 9       # below this the number stops being readable at a glance
MASCOT_PT = 11          # badge in the top-right corner
ICON_HIT = 26           # hit area of each button in the right column
ICON_R = 4.6            # circular arrow, sized against the menu dots
SPIN_MS = 40                            # spinner frame while a fetch is in flight
SPIN_STEP = 9.0                         # degrees per frame


def ring_text_fits(number: str, size: int, unit_size: int) -> bool:
    """Whether "38%" at these sizes clears the ring's inner edge, with air.

    Measured at the text's own height rather than at the circle's equator: a
    circle is narrower where the digits actually are. Shared with the tests and
    with tools/measure_font.py so all three ask the same question.
    """
    w_num = paint.width(number, size, QFont.Weight.DemiBold)
    w_unit = paint.width("%", unit_size)
    half = (w_num + w_unit * 0.35) / 2
    right = -half + w_num + 1 + w_unit

    inner = RING_R - RING_T / 2
    clearance = math.sqrt(inner**2 - (size * 0.95 / 2) ** 2) - 2
    return right < clearance and half < clearance


def ring_text_pt(number: str) -> tuple[int, int]:
    """Point sizes for the gauge number, stepped down until it clears the stroke
    it sits inside.

    The table is what the design was drawn against and is only ever made smaller
    here, so on a font where it already fits nothing moves. Other faces set the
    same digits wider - Inter runs "38%" almost two pixels past the stroke at
    these sizes - and the choice there is between digits crossing the gauge and
    digits a point smaller. Smaller wins.
    """
    size, unit = RING_TEXT_PT_WIDE if len(number) > 2 else RING_TEXT_PT
    while size > RING_TEXT_MIN and not ring_text_fits(number, size, unit):
        size -= 1
        unit = max(unit - 1, 6)
    return size, unit


class FloatingWidget(QWidget):
    clicked = Signal()                  # plain click: toggles the panel
    menu_requested = Signal(QPoint)
    refresh_requested = Signal()        # the button in the right column

    def __init__(self, settings) -> None:
        super().__init__(None)
        self.settings = settings
        self.snap: Snapshot | None = None
        self._drag_from: QPoint | None = None
        self._moved = False
        self._hover_menu = False
        self._hover_refresh = False
        self._hover_card = False
        self._busy = False
        self._spin = 0.0
        self._spinner = QTimer(self)      # only runs while a fetch is in flight
        self._spinner.setInterval(SPIN_MS)
        self._spinner.timeout.connect(self._advance_spin)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool                 # keeps it out of the taskbar
            | Qt.WindowType.NoDropShadowWindowHint
        )
        # macOS hides tool windows whenever the app is deactivated, which for a
        # widget whose whole job is to be visible while you work in something
        # else means it is never on screen. A no-op on the other platforms.
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setWindowTitle("Agent Gauge")
        self.setWindowOpacity(float(settings["opacity"]))

        self.apply_size()
        self.restore_position()

    # ---------------------------------------------------------------- layout
    def apply_size(self) -> None:
        card = CARD_COMPACT if self.settings["compact"] else CARD_FULL
        self.setFixedSize(card + M * 2, CARD_H + M * 2)

    def card(self) -> QRectF:
        """The visible rectangle, shadow margin already removed."""
        return QRectF(M, M, self.width() - M * 2, self.height() - M * 2)

    def ring_center(self) -> QPointF:
        """Compact is a square with nothing else in it, so the gauge belongs in
        the middle. Reusing the full layout's constant left it 4px off center
        and clipped the refresh ring against the right edge.
        """
        if self.settings["compact"]:
            return self.card().center()
        return RING_C

    def restore_position(self) -> None:
        x, y = self.settings["pos_x"], self.settings["pos_y"]
        if x is None or y is None:
            geo = self.screen().availableGeometry()
            x = geo.right() - self.width() - (LG - M)
            y = geo.bottom() - self.height() - (LG - M)
        self.move(self._clamp(QPoint(int(x), int(y))))

    def _clamp(self, pos: QPoint) -> QPoint:
        """Keep the window inside the work area of whichever screen holds it."""
        screen = self.screen()
        for sibling in screen.virtualSiblings():
            if sibling.availableGeometry().contains(pos):
                screen = sibling
                break
        geo = screen.availableGeometry()
        x = min(max(pos.x(), geo.left()), geo.right() - self.width())
        y = min(max(pos.y(), geo.top()), geo.bottom() - self.height())
        return QPoint(x, y)

    def _refresh_zone(self) -> QRectF:
        """Middle of the right column: refresh now."""
        if self.settings["compact"]:
            return QRectF()
        card = self.card()
        return QRectF(card.right() - MENU_W, card.center().y() - ICON_HIT / 2,
                      MENU_W, ICON_HIT)

    def _menu_zone(self) -> QRectF:
        """Bottom of the right column: the menu."""
        if self.settings["compact"]:
            return QRectF()
        card = self.card()
        return QRectF(card.right() - MENU_W, card.bottom() - ICON_HIT, MENU_W, ICON_HIT)

    # ------------------------------------------------------------------ data
    def set_snapshot(self, snap: Snapshot | None) -> None:
        """None means "nothing to show yet", which is a real state: it is what
        the app is in before the first cycle and again after switching agents."""
        self.snap = snap
        self.setToolTip(self._tooltip(snap))
        self.update()

    def set_busy(self, busy: bool) -> None:
        """Fetch in flight: the refresh ring spins instead of counting down."""
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            self._spin = 0.0
            self._spinner.start()
        else:
            self._spinner.stop()
        self.update()

    def _advance_spin(self) -> None:
        self._spin = (self._spin + SPIN_STEP) % 360.0
        self.update()

    def _tooltip(self, snap: Snapshot | None) -> str:
        if snap is None:
            return t("tray.collecting")
        if not snap.ok:
            return t("widget.tooltip_error", error=snap.error or t("widget.no_data"))
        u, now = snap.usage, time.time()
        return t("widget.tooltip", h5=u.h5, d7=u.d7,
                 h5_clock=theme.fmt_clock(u.h5_reset),
                 d7_clock=theme.fmt_clock(u.d7_reset),
                 h5_left=theme.fmt_countdown(u.h5_reset, now),
                 d7_left=theme.fmt_countdown(u.d7_reset, now))

    # -------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        card = self.card()
        paint.shadow(p, card, 16.0, spread=M - 1)
        paint.surface(p, card, radius=16.0,
                      fill=theme.hover(theme.SURFACE) if self._hover_card else theme.SURFACE)

        snap = self.snap
        live = bool(snap and snap.ok)
        self._paint_ring(p, snap, live)

        if not self.settings["compact"]:
            if snap and not snap.ok:
                self._paint_error(p, card, snap)
            else:
                self._paint_rows(p, snap, live)
            self._paint_mascot(p, card, snap)
            paint.refresh_icon(p, self._refresh_zone().center(), ICON_R,
                               theme.MUTED if self._hover_refresh else theme.FAINT)
            paint.dots(p, self._menu_zone().center(),
                       theme.MUTED if self._hover_menu else theme.FAINT)

        self._paint_refresh_ring(p, snap)
        p.end()

    def _paint_mascot(self, p: QPainter, card: QRectF, snap: Snapshot | None) -> None:
        """The watched agent's mark, as a badge in the top-right corner.

        It goes gray when a fetch failed or an incident is open, the same signal
        the panel header gives, and it is the only thing on the widget that says
        which agent these numbers belong to - the rows and the ring look
        identical either way.
        """
        unwell = bool(snap and (snap.error or snap.incidents))
        # The snapshot's own agent, not the setting: the two differ for as long
        # as a cycle that started before the switch is still in flight.
        key = providers.get(
            snap.provider if snap and snap.provider else str(self.settings["provider"])).key
        # None means the mark's own colour. Grey still wins when the agent is
        # unwell: the indicator outranks the branding.
        icon = brand.mark(key, MASCOT_PT, theme.FAINT if unwell else None,
                          self.devicePixelRatioF())
        w = icon.width() / icon.devicePixelRatio()
        p.drawPixmap(QPointF(card.right() - MENU_W / 2 - w / 2, card.top() + SM), icon)

    def _paint_ring(self, p: QPainter, snap: Snapshot | None, live: bool) -> None:
        center = self.ring_center()
        h5 = snap.usage.h5 if live else 0.0
        paint.ring(p, center, RING_R, RING_T, h5, color=None if live else theme.TRACK)
        if live:
            number = f"{h5:.0f}"
            size, unit_size = ring_text_pt(number)
            paint.numeric(p, center, number, "%", theme.TEXT, size, unit_size,
                          unit_color=theme.MUTED)
            return
        inner = QRectF(center.x() - RING_R, center.y() - RING_R, RING_R * 2, RING_R * 2)
        paint.text(p, inner, theme.NO_DATA, theme.FAINT, 13, QFont.Weight.DemiBold,
                   Qt.AlignmentFlag.AlignCenter)

    def row_columns(self, value: str, tail: str) -> tuple[str, float, float]:
        """Split a row into label | value | tail without letting them touch.

        Measured, not assumed: "56min" is half again as wide as "2h13", and a
        fixed value offset put it underneath the tail.
        """
        col_w = self.card().right() - MENU_W - SM - COL_X
        tail_w = paint.width(tail, 8)
        budget = col_w - LABEL_W - tail_w - SM
        return paint.elide(value, budget, 11, QFont.Weight.DemiBold), tail_w, col_w

    def _paint_rows(self, p: QPainter, snap: Snapshot | None, live: bool) -> None:
        """Two rows of identical structure: label | value | supporting value."""
        card = self.card()
        col_w = card.right() - MENU_W - SM - COL_X
        top = card.center().y() - ROW_H
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        if not live:
            paint.text(p, QRectF(COL_X, card.top(), col_w, card.height()),
                       t("widget.collecting") if snap is None else t("widget.no_data"),
                       theme.MUTED, 9)
            return

        u = snap.usage
        now = time.time()
        rows = (
            # label, value,                                  color,           tail
            ("5h", theme.fmt_countdown(u.h5_reset, now), theme.TEXT,
             theme.fmt_clock(u.h5_reset)),
            ("7d", f"{u.d7:.0f}%", theme.grad_color(u.d7),
             theme.fmt_countdown(u.d7_reset, now)),
        )
        for i, (label, value, color, tail) in enumerate(rows):
            row = QRectF(COL_X, top + i * ROW_H, col_w, ROW_H)
            shown, tail_w, _ = self.row_columns(value, tail)
            paint.text(p, row, label, theme.MUTED, 8)

            # A drawn dot, the same one the menu is made of: as text it would
            # scale with the font and never quite match. Centered in the gap so
            # it separates the two sides instead of hanging off the label.
            label_w = paint.width(label, 8)
            paint.dot(p, QPointF(row.x() + (label_w + LABEL_W) / 2, row.center().y()),
                      theme.MUTED)

            paint.text(p, row.adjusted(LABEL_W, 0, -(tail_w + SM), 0), shown, color, 11,
                       QFont.Weight.DemiBold)
            paint.text(p, row, tail, theme.FAINT, 8, align=right)

    def _paint_error(self, p: QPainter, card: QRectF, snap: Snapshot) -> None:
        col_w = card.right() - MENU_W - SM - COL_X
        msg = paint.elide(snap.error or t("widget.no_data"), col_w, 9)
        # Muted, not red, when nothing is actually wrong: an expired token
        # after a night away is the app's normal resting state, and alarming
        # about it teaches the user to ignore the colour that means trouble.
        color = theme.MUTED if snap.waiting else theme.BAD
        paint.text(p, QRectF(COL_X, card.top(), col_w, card.height()), msg, color, 9)

    def _paint_refresh_ring(self, p: QPainter, snap: Snapshot | None) -> None:
        """Outer ring: a fixed track plus an arc counting down to the next fetch,
        which becomes a spinner while the fetch runs.

        Gray, not the brand coral: at high usage the gauge turns orange or red
        and a concentric coral arc melts into it.
        """
        if snap is None and not self._busy:
            return
        center = self.ring_center()

        track = QColor(theme.MUTED)
        track.setAlpha(34)                # the track is what makes the arc readable
        paint.ring(p, center, ORBIT_R, ORBIT_T, 0.0, color=track, track=track)

        if self._busy:
            # Verde, nao o coral da marca: coral perto do vermelho da rampa
            # parecia alarme justamente quando o app esta so trabalhando.
            spin = QColor(theme.OK)
            spin.setAlpha(230)
            paint.arc(p, center, ORBIT_R, ORBIT_T, self._spin, 80.0, spin)
            return

        # The poller stretches its wait while nothing moves, so counting
        # down from the chosen interval would empty the arc early and
        # leave it sitting at zero.
        interval = max(snap.interval or int(self.settings["poll_sec"]), 1)
        left = 1.0 - min(max((time.time() - snap.at) / interval, 0.0), 1.0)
        if left <= 0.005:
            return
        arc_color = QColor(theme.MUTED)
        arc_color.setAlpha(170)
        paint.ring(p, center, ORBIT_R, ORBIT_T, left * 100.0, color=arc_color, track=None)

    # ----------------------------------------------------------------- mouse
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # The column's buttons come first, and none of them starts a drag.
            if self._refresh_zone().contains(event.position()):
                self.refresh_requested.emit()
                return
            if self._menu_zone().contains(event.position()):
                self.menu_requested.emit(event.globalPosition().toPoint())
                return
            self._drag_from = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        menu = self._menu_zone().contains(event.position())
        refresh = self._refresh_zone().contains(event.position())
        if (menu, refresh) != (self._hover_menu, self._hover_refresh):
            self._hover_menu, self._hover_refresh = menu, refresh
            self.setCursor(Qt.CursorShape.PointingHandCursor if refresh
                           else Qt.CursorShape.ArrowCursor)
            self.update()

        if self._drag_from is None or self.settings["locked"]:
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            target = event.globalPosition().toPoint() - self._drag_from
            if (target - self.pos()).manhattanLength() > 3:
                self._moved = True
            self.move(self._clamp(target))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_from is None:
            return
        self._drag_from = None
        if self._moved:
            self.settings["pos_x"], self.settings["pos_y"] = self.x(), self.y()
            self.settings.save()
        else:
            self.clicked.emit()

    def enterEvent(self, _event) -> None:
        self._hover_card = True
        self.update()

    def leaveEvent(self, _event) -> None:
        self._hover_card = False
        self._hover_menu = False
        self._hover_refresh = False
        self.update()

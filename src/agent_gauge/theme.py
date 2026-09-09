"""Palette, spacing scale and formatters.

Built for a dark desktop surface: one brand accent, three state colors, and a
neutral ramp for everything else. Formatter output is pt-BR: it is rendered in
the UI.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QColor

from .i18n import decimal_separator, t, weekdays

BG = QColor("#0F0F12")
SURFACE = QColor("#1A1A20")
SURFACE2 = QColor("#24242C")
TRACK = QColor("#26262E")
BORDER = QColor("#30303A")
TEXT = QColor("#F2F0EC")
# Only the tray uses this: the app's own surfaces are always dark, but the
# taskbar, menu bar or panel the icon sits on may not be.
INK_LIGHT = QColor("#17171C")
MUTED = QColor("#8C8C98")
FAINT = QColor("#5C5C68")
ACCENT = QColor("#D97757")   # Claude coral
# Anything the pointer can act on: links, and a label under the cursor. One
# name so the panel and the about card cannot drift, and deliberately not the
# accent - in coral an ordinary link read as an agent's branding.
INTERACTIVE = TEXT
OK = QColor("#4ADE80")
WARN = QColor("#FBBF24")
BAD = QColor("#F87171")

# 4pt spacing scale: every padding, row height and column offset comes from here.
XS, SM, MD, LG, XL, XXL = 4, 8, 12, 16, 24, 32

NO_DATA = "--"          # one placeholder, so the widget and the panel agree


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    """t=0 yields a, t=1 yields b."""
    t = min(max(t, 0.0), 1.0)
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def hover(color: QColor, amount: float = 0.05) -> QColor:
    """Lift a surface toward the text color for the hover state."""
    return _mix(color, TEXT, amount)


def grad_color(pct: float) -> QColor:
    """Continuous green -> amber -> red ramp as a window fills."""
    pct = min(max(pct, 0.0), 100.0)
    if pct <= 50.0:
        return _mix(WARN, OK, 1.0 - pct / 50.0)
    return _mix(BAD, WARN, 1.0 - (pct - 50.0) / 50.0)


def window_elapsed(reset_epoch: int, span: float, now: float) -> float:
    """Fraction of a window already spent, 0-1."""
    if not reset_epoch:
        return 0.0
    return min(max(1.0 - (reset_epoch - now) / span, 0.0), 1.0)


def status_label(usage) -> tuple[str, QColor]:
    """Aggregate status chip: the header wins, the percentage decides ties."""
    s = (usage.status_overall or "").lower()
    if not usage.ok:
        return t("status.no_data"), FAINT
    if "reject" in s or usage.worst >= 100:
        return t("status.blocked"), BAD
    if "warning" in s or usage.worst >= 90:
        return t("status.warning"), WARN
    return t("status.ok"), OK


def fmt_countdown(epoch: int, now: float) -> str:
    """Time left until a reset: 2d14h / 2h14 / 47min / 38s / --."""
    if not epoch:
        return NO_DATA
    left = int(epoch - now)
    if left <= 0:
        return t("time.now")
    if left >= 86400:
        return f"{left // 86400}d{(left % 86400) // 3600:02d}h"
    if left >= 3600:
        return f"{left // 3600}h{(left % 3600) // 60:02d}"
    if left >= 60:
        return f"{left // 60}min"
    return f"{left}s"


def fmt_clock(epoch: int) -> str:
    if not epoch:
        return "--:--"
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def fmt_weekday(epoch: int) -> str:
    """Abbreviated weekday. Not strftime("%a"): that follows the Windows locale,
    which is a different setting from the one the user picked in this app."""
    if not epoch:
        return ""
    return weekdays()[datetime.fromtimestamp(epoch).weekday()]


def fmt_tokens(n: int) -> str:
    """Compact token count: 512 / 24k / 6.0M, with the language's decimal mark."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".", decimal_separator())
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)

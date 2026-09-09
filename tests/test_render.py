"""Offscreen render smoke tests.

They do not assert on pixels; they assert that every painting path runs without
raising, across the states the UI actually reaches (no data yet, live values,
error, busy, compact).
"""
from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent

from agent_gauge import api, brand, paint, theme
from agent_gauge import app as app_module
from agent_gauge.panel import Panel
from agent_gauge.poller import Snapshot
from agent_gauge.settings import Settings
from agent_gauge.theme import SM
from agent_gauge.widget import (
    LABEL_W,
    ORBIT_R,
    ORBIT_T,
    RING_TEXT_MIN,
    FloatingWidget,
    ring_text_fits,
    ring_text_pt,
)


def render(widget) -> QImage:
    img = QImage(widget.width(), widget.height(), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(1.0)
    img.fill(QColor("#000000"))
    widget.render(img)
    return img


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "settings.json")


def live_snapshot() -> Snapshot:
    now = time.time()
    return Snapshot(
        usage=api.Usage(h5=71, d7=34, h5_reset=int(now + 8040), d7_reset=int(now + 169200),
                        status_overall="allowed", claim="five_hour", ok=True),
        subscription="max",
    )


def error_snapshot() -> Snapshot:
    return Snapshot(usage=api.Usage(ok=False), error="token recusado (401)")


@pytest.mark.parametrize("snap", [None, live_snapshot(), error_snapshot()])
def test_widget_paints_in_every_state(qapp, settings, snap):
    w = FloatingWidget(settings)
    if snap is not None:
        w.set_snapshot(snap)
    assert not render(w).isNull()


@pytest.mark.parametrize(
    ("value", "tail"),
    [
        ("2h13", "19:50"),      # the common case
        ("56min", "19:50"),     # minutes are half again as wide as hours
        ("38s", "1d22h"),
        ("100%", "6d23h"),      # widest value and widest tail together
    ],
)
def test_row_value_never_reaches_the_tail(qapp, real_fonts, settings, value, tail):
    """The row is measured, not laid out at a fixed offset.

    Gated on the real font: eliding is the correct answer when the text genuinely
    does not fit, and the offscreen fallback runs about 1.8x wider than Segoe UI,
    so under it the widget rightly truncates and the assertion below is false.
    """
    w = FloatingWidget(settings)
    shown, tail_w, col_w = w.row_columns(value, tail)

    # Fitting is not enough: the value must arrive whole. Eliding it to "33..."
    # would satisfy a pure overlap check while destroying the reading.
    assert shown == value
    used = LABEL_W + paint.width(shown, 11, QFont.Weight.DemiBold) + SM + tail_w
    assert used <= col_w + 0.5


@pytest.mark.parametrize("pct", [0, 7, 38, 99, 100])
def test_ring_number_stays_clear_of_the_stroke(qapp, real_fonts, pct):
    """The gauge number must not touch the ring it sits inside.

    Geometry, not eyeballing: the widest point of the ink has to clear the
    stroke's inner edge, measured at the text's own height (a circle is
    narrower there than at its equator). This is why the ring carries no
    The ring was widened (R 23 -> 27, stroke 7 -> 6) precisely so the percent
    sign fits: at the old size "38%" ran 1.4px past the stroke and "100%" 6px.
    """
    number = f"{pct:.0f}"
    size, unit_size = ring_text_pt(number)

    # The widget picks the size by asking this, so the assertion is that the
    # answer it settled on genuinely fits - not that a fixed size happens to.
    assert ring_text_fits(number, size, unit_size)
    assert size >= RING_TEXT_MIN


def test_widget_paints_while_busy(qapp, settings):
    w = FloatingWidget(settings)
    w.set_snapshot(live_snapshot())
    w.set_busy(True)
    assert not render(w).isNull()
    w.set_busy(False)


def test_compact_widget_is_square(qapp, settings):
    settings["compact"] = True
    w = FloatingWidget(settings)
    assert w.width() == w.height()
    assert not render(w).isNull()


@pytest.mark.parametrize("compact", [False, True])
def test_refresh_ring_fits_inside_the_card(qapp, settings, compact):
    """Pure geometry, so it runs under any font.

    Compact reused the full layout's ring center, which sits 16px from the left
    edge; in a square card that pushed the refresh ring past the right side and
    clipped it.
    """
    settings["compact"] = compact
    w = FloatingWidget(settings)
    card, center = w.card(), w.ring_center()
    outer = ORBIT_R + ORBIT_T / 2
    assert center.x() - outer >= card.left()
    assert center.x() + outer <= card.right()
    assert center.y() - outer >= card.top()
    assert center.y() + outer <= card.bottom()


@pytest.mark.parametrize("snap", [None, live_snapshot(), error_snapshot()])
def test_panel_paints_in_every_state(qapp, settings, snap):
    p = Panel(settings)
    if snap is not None:
        p.set_snapshot(snap, "~1h40")
    assert not render(p).isNull()


def test_right_column_buttons_are_separate_and_wired(qapp, settings):
    """Refresh and menu share a 32px column; overlapping hit areas would make
    one of them unreachable."""
    w = FloatingWidget(settings)
    assert not w._refresh_zone().intersects(w._menu_zone())

    fired = []
    w.refresh_requested.connect(lambda: fired.append(True))
    where = w._refresh_zone().center()
    press = QMouseEvent(QEvent.Type.MouseButtonPress, where,        # local
                        QPointF(w.mapToGlobal(where.toPoint())),    # global
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    w.mousePressEvent(press)
    assert fired, "clicking the refresh icon must ask for a new cycle"


def test_panel_swallows_the_click_that_closed_it(qapp, settings):
    p = Panel(settings)
    assert not p.just_closed()      # never shown, so nothing to swallow
    p.show()
    p.hide()
    assert p.just_closed()


@pytest.mark.parametrize("size", app_module.TRAY_SIZES)
@pytest.mark.parametrize("pct", [7, 71, 100])
def test_tray_pixmap_renders_at_every_size(qapp, size, pct):
    pm = app_module.tray_pixmap(Snapshot(usage=api.Usage(h5=pct, ok=True)), size)
    assert not pm.isNull()
    assert pm.width() == size


def test_tray_icon_offers_all_sizes(qapp):
    """The shell picks from what the icon carries; a single large pixmap left
    Windows to shrink it, which smeared the stroke and the digits."""
    icon = app_module.tray_icon(Snapshot(usage=api.Usage(h5=42, ok=True)))
    available = {size.width() for size in icon.availableSizes()}
    assert set(app_module.TRAY_SIZES) <= available
    assert not app_module.tray_icon(None).isNull()


def test_tray_number_fits_the_small_icon(qapp, real_fonts):
    """The number is measured against the space it has, not a fraction of the
    icon: as a fixed fraction it grew wider than the ring and the stroke cut
    straight through the digits."""
    for label in ("7", "16", "100"):
        pt = app_module._fit_in_square(label, 16)
        w, h = paint.ink(label, pt, QFont.Weight.DemiBold)
        assert w <= 14 and h <= 14


def test_clawd_is_cached_per_size_and_color(qapp):
    first = brand.mark("claude", 13, theme.ACCENT)
    assert first is brand.mark("claude", 13, theme.ACCENT)
    assert first is not brand.mark("claude", 13, theme.FAINT)
    assert not first.isNull()


@pytest.mark.parametrize("surface", ["widget", "panel"])
def test_a_surface_accepts_having_nothing_to_show(qapp, settings, surface):
    """None is a real state, not a mistake: it is what the app is in before the
    first cycle and again the moment the user switches agents.

    The widget's tooltip did not accept it, so switching raised inside the menu
    handler - before the line that told the poller. Qt swallowed that into
    stderr, and the visible result was an app whose label changed while its
    numbers went on coming from the agent the user had just left.
    """
    view = FloatingWidget(settings) if surface == "widget" else Panel(settings)
    view.set_snapshot(None)
    assert not render(view).isNull()


def test_elide_backs_off_to_a_whole_word(qapp, real_fonts):
    """Qt fills the width and stops wherever it lands, which inside a sentence
    means stopping inside a word - and the word it cut was usually the agent's
    name, the one thing the reader needed."""
    long = "sign in to Claude Code again - token refused (401)"
    cut = paint.elide(long, 120, 9)

    assert cut.endswith(paint.ELLIPSIS)
    assert not cut[: -len(paint.ELLIPSIS)].endswith(" ")   # no dangling space
    # what survives is whole words, not a fragment of one
    assert all(word in long.split() for word in
               cut[: -len(paint.ELLIPSIS)].split())


def test_elide_leaves_a_single_token_alone(qapp, real_fonts):
    """A countdown or a percentage has no word to fall back to, and must come
    out exactly as Qt would have left it."""
    for token in ("2h13", "100%", "1d22h"):
        assert paint.elide(token, 200, 11) == token


def test_elide_returns_short_text_untouched(qapp, real_fonts):
    assert paint.elide("OK", 200, 9) == "OK"


# ------------------------------------------------------- the status page link
def _click(widget, where):
    event = QMouseEvent(QEvent.Type.MouseButtonRelease, where,
                        QPointF(widget.mapToGlobal(where.toPoint())),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    widget.mouseReleaseEvent(event)


def test_the_status_line_opens_the_status_page(qapp, settings):
    """The incident is elided to fit a 280px column, so the one thing the line
    cannot do is tell the whole story. The link is where the rest of it is."""
    p = Panel(settings)
    p.set_snapshot(live_snapshot(), "~1h40")

    fired = []
    p.status_requested.connect(lambda: fired.append(True))
    _click(p, p._status_zone().center())
    assert fired


def test_an_app_side_error_is_not_offered_as_a_status_link(qapp, settings):
    """A refused token and a dead network land in the same slot, and neither is
    something status.claude.com answers. Sending someone there would be a
    wrong answer wearing the shape of help."""
    p = Panel(settings)
    p.set_snapshot(error_snapshot(), "")
    assert p._status_zone().isEmpty()

    fired = []
    p.status_requested.connect(lambda: fired.append(True))
    _click(p, QPointF(p.width() / 2, p.height() / 2))
    assert not fired


def test_the_link_zone_covers_the_text_it_names(qapp, settings):
    """Measured off the painted string: a full-width zone would put the hand
    cursor over empty card, and a stale one would miss the text entirely."""
    p = Panel(settings)
    p.set_snapshot(live_snapshot(), "~1h40")
    zone = p._status_zone()
    width, _ = paint.ink(p._status_line(), 8)
    assert zone.width() <= width + 6
    assert zone.height() > 0


def test_the_link_follows_the_agent_on_screen(qapp, settings):
    """It is built from the host the line just named, so the address opened and
    the address shown cannot disagree."""
    from agent_gauge import providers

    p = Panel(settings)
    for key in ("claude", "codex"):
        snap = live_snapshot()
        snap.provider = key
        p.set_snapshot(snap, "")
        assert p._status_host() == providers.get(key).status_host
        assert providers.get(key).status_host in p._status_line()


def test_an_open_incident_is_the_link_that_matters_most(qapp, settings):
    """The case the link was asked for: the incident text is cut to fit, so the
    line names a problem it cannot describe."""
    snap = live_snapshot()
    snap.incidents = ["Elevated error rates on the Messages API affecting a "
                      "subset of requests in us-east"]
    p = Panel(settings)
    p.set_snapshot(snap, "~1h40")

    assert p._status_line().startswith("! ")
    assert not p._status_zone().isEmpty()

    fired = []
    p.status_requested.connect(lambda: fired.append(True))
    _click(p, p._status_zone().center())
    assert fired


def test_a_long_incident_keeps_the_arrow(qapp, settings):
    """Eliding to the full column and then appending would push the arrow off
    the card - dropping the only mark that says the line can be clicked, in
    exactly the case where clicking it matters most."""
    from agent_gauge.panel import COL, STATUS_ARROW

    snap = live_snapshot()
    snap.incidents = ["Elevated error rates affecting a subset of requests "
                      "across several regions, with degraded latency " * 3]
    p = Panel(settings)
    p.set_snapshot(snap, "~1h40")

    line = p._status_line()
    assert line.endswith(STATUS_ARROW)
    width, _ = paint.ink(line, 8)
    assert width <= COL, f"{width} > {COL}: the line overflows the card"


# ------------------------------------------------- one colour for what you click
def test_every_interactive_thing_shares_one_colour(qapp, settings):
    """Refresh, setup, the status line and the about card's links used to be
    coral apiece, which read as an agent's branding on things that have nothing
    to do with an agent. They now come from one name, so they cannot drift."""
    from agent_gauge import about, theme

    assert theme.INTERACTIVE != theme.ACCENT
    assert theme.INTERACTIVE == theme.TEXT
    assert theme.INTERACTIVE.name() in about.link("https://example.com", "x")


def test_the_plan_is_not_painted_in_an_agent_colour(qapp, settings, monkeypatch):
    """It sits beside the mark, and two coloured things in one header compete.

    Read off the request rather than the pixels: a band of the rendered image
    would be found empty on a runner whose stub font draws no opaque text, and
    an empty band satisfies "the accent is not in here" by saying nothing.
    """
    from agent_gauge import paint as paint_module
    from agent_gauge import theme

    drawn = {}
    real = paint_module.text

    def spy(painter, rect, s, color, size, *args, **kwargs):
        drawn[s] = color.name()
        return real(painter, rect, s, color, size, *args, **kwargs)

    monkeypatch.setattr(paint_module, "text", spy)
    p = Panel(settings)
    p.set_snapshot(live_snapshot(), "~1h40")
    render(p)

    assert "MAX" in drawn, f"the plan label was never drawn: {list(drawn)}"
    assert drawn["MAX"] == theme.TEXT.name()
    assert drawn["MAX"] != theme.ACCENT.name()


@pytest.mark.parametrize("state", ["_hover_refresh", "_hover_setup", "_hover_status"])
def test_hover_lifts_text_to_the_interactive_colour(qapp, settings, monkeypatch, state):
    """Grey to white, not grey to coral.

    Read off the colour handed to paint.text rather than off the pixels. An
    earlier version counted rasterised pixels and passed here while failing on
    Linux, where the offscreen plugin's stub font draws no opaque text at all -
    46 pixels with the pointer on it and 46 with it off. Asking what colour was
    requested is both the actual claim and the same answer on every platform.
    """
    from agent_gauge import paint as paint_module
    from agent_gauge import theme

    def asked_for(hovering):
        drawn = []
        real = paint_module.text

        def spy(painter, rect, s, color, size, *args, **kwargs):
            drawn.append(color.name())
            return real(painter, rect, s, color, size, *args, **kwargs)

        monkeypatch.setattr(paint_module, "text", spy)
        p = Panel(settings)
        snap = live_snapshot()
        snap.setup = "signin"
        p.set_snapshot(snap, "~1h40")
        setattr(p, state, hovering)
        render(p)
        monkeypatch.undo()
        return drawn.count(theme.INTERACTIVE.name())

    assert asked_for(True) == asked_for(False) + 1


def test_published_screenshots_do_not_inherit_this_machine(qapp, tmp_path):
    """tools/preview.py used to build its Settings from the real config, so the
    picture on the site showed whichever agent the person generating it had
    selected - it came within a commit of shipping a Codex panel as the app's
    own screenshot."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    try:
        import preview
    finally:
        sys.path.pop(0)

    from agent_gauge.settings import DEFAULTS

    settings = preview.fixed_settings()
    assert settings["provider"] == DEFAULTS["provider"]
    assert settings["language"] == DEFAULTS["language"]
    assert settings["compact"] is False

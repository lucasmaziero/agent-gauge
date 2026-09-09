"""Application wiring: tray icon, widget, panel and the collection cycle."""
from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import autostart, i18n, paint, paths, providers, signin, theme
from .about import About
from .i18n import t
from .panel import Panel
from .poller import Poller, Snapshot
from .settings import Settings
from .widget import FloatingWidget

APP_ID = autostart.APP_ID
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DEBUG = bool(os.environ.get("AGENT_GAUGE_DEBUG"))
TICK_MS = 1000              # reset countdowns advance between polls
# The Windows shell asks for the small-icon metric times the display scale, so
# 20px at 125% becomes a request for 25. Without those in-between sizes Qt hands
# over a larger pixmap and Windows shrinks it, which is what smeared the icon.
# macOS asks for 22pt at 1x and 2x, and Linux panels pick from the same set.
TRAY_SIZES = (16, 20, 22, 24, 25, 30, 32, 40, 44, 48)
POLL_CHOICES = (30, 60, 120, 300, 900)
ALERT_CHOICES = (0, 50, 70, 80, 90)     # 0 is off
ALERT_MS = 12000                        # long enough to read, short enough to ignore


def poll_label(seconds: int) -> str:
    if seconds < 60:
        return t("menu.seconds", n=seconds)
    minutes = seconds // 60
    return t("menu.minute") if minutes == 1 else t("menu.minutes", n=minutes)


def _fit_in_square(label: str, side: float) -> int:
    """Largest point size whose ink fits a square icon, with a pixel of air."""
    for pt in range(16, 4, -1):
        w, h = paint.ink(label, pt, QFont.Weight.DemiBold)
        if w <= side - 2 and h <= side - 2:
            return pt
    return 5


def alert_due(snap: Snapshot, at: int, alerted_for: int) -> bool:
    """Whether this snapshot is the first of its window to cross the threshold.

    Keyed on the window's own reset time rather than a flag, so the alert fires
    once per window and rearms by itself when the window rolls over - including
    across a restart, since a fresh process has announced nothing.
    """
    usage = snap.usage
    return bool(at and snap.ok and usage.h5 >= at and usage.h5_reset != alerted_for)


def tray_surface_is_light() -> bool:
    """Whether the surface behind the tray icon is light.

    Not the same question as the app theme. Windows keeps two settings, and the
    one that governs the taskbar is SystemUsesLightTheme; Qt's colorScheme()
    reports the other one (AppsUseLightTheme), so a light-apps/dark-taskbar
    setup would come back inverted. Everywhere else the two are one setting and
    Qt's answer is the right one.
    """
    if paths.WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
                return bool(winreg.QueryValueEx(key, "SystemUsesLightTheme")[0])
        except OSError:
            return False              # the taskbar's default, and the old behaviour
    hints = QApplication.styleHints()
    scheme = getattr(hints, "colorScheme", lambda: Qt.ColorScheme.Dark)()
    return scheme == Qt.ColorScheme.Light


def tray_ink() -> QColor:
    """Digit color for the tray, legible on whatever it is sitting on.

    Unlike the widget, the tray icon sits on a surface this app does not paint:
    the Windows taskbar, the macOS menu bar, a Linux panel. Each inverts with
    the system theme, and the near-white the widget uses disappears on the light
    one. The ring keeps its usage color either way - that is the signal, and it
    reads on both.
    """
    return theme.INK_LIGHT if tray_surface_is_light() else theme.TEXT


def tray_pixmap(snap: Snapshot | None, size: int = TRAY_SIZES[-1],
                ink: QColor | None = None) -> QPixmap:
    """The 5h ring with the number inside, drawn for one exact icon size.

    The ring is kept thin and pushed to the edge, and the number is fitted to
    the square it encloses rather than to the circle. Fitting to the circle is
    what a strict reading would ask for, but at tray sizes it costs five point
    sizes - digits have empty corners, so the square is the honest bound.
    """
    ink = ink or theme.TEXT
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    live = bool(snap and snap.ok)
    pct = snap.usage.h5 if live else 0.0
    radius = size * 0.45
    thickness = max(size * 0.09, 1.6)
    idle = QColor(ink)
    idle.setAlpha(80)                    # a track, not a reading
    paint.ring(p, QPointF(size / 2, size / 2), radius, thickness, pct,
               color=None if live else idle)

    label = f"{pct:.0f}" if live else "-"
    inner_side = size - thickness * 2 - 2
    paint.text(p, QRectF(0, 0, size, size), label, ink,
               _fit_in_square(label, inner_side), QFont.Weight.DemiBold,
               Qt.AlignmentFlag.AlignCenter)
    p.end()
    return pm


def tray_icon(snap: Snapshot | None) -> QIcon:
    """One pixmap per size Windows asks for.

    A single large pixmap scaled down by the shell smears the stroke and the
    digits; drawing each size means the 16px icon is laid out for 16px.
    """
    icon = QIcon()
    ink = tray_ink()
    for size in TRAY_SIZES:
        icon.addPixmap(tray_pixmap(snap, size, ink))
    return icon


class App(QObject):
    """Owns the windows and the poller.

    Must be a QObject: the poller's signals are emitted from its own thread, and
    only a QObject receiver turns those connections into queued ones.
    """

    def __init__(self, qapp: QApplication) -> None:
        super().__init__(qapp)
        self.qapp = qapp
        self.settings = Settings()
        self.snap: Snapshot | None = None
        self._alerted_for = -1                # the window reset already announced
        self.about: About | None = None       # built on first use, dropped on a
                                              # language change so it rebuilds
        self._retired_about: list[About] = []
        i18n.set_language(self.settings["language"])

        self.widget = FloatingWidget(self.settings)
        self.panel = Panel(self.settings)
        self.tray = QSystemTrayIcon(tray_icon(None))
        self.provider = providers.get(str(self.settings["provider"]))
        self.poller = Poller(int(self.settings["poll_sec"]), self.provider)

        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip(t("tray.collecting"))
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.widget.clicked.connect(self.toggle_panel)
        self.widget.menu_requested.connect(self._popup_menu)
        self.widget.refresh_requested.connect(self.refresh)
        self.panel.refresh_requested.connect(self.refresh)
        self.panel.setup_requested.connect(
            lambda: signin.open_help(self.provider))
        self.panel.status_requested.connect(
            lambda: signin.open_status(self.provider))
        self.poller.updated.connect(self.on_update)
        self.poller.busy.connect(self.widget.set_busy)

        # Without a tray the widget is the only way to reach the menu, so a
        # stored "hidden" would leave the app running with no way to drive or
        # quit it. GNOME ships no tray unless an AppIndicator extension is on.
        if self.settings["widget_visible"] or not QSystemTrayIcon.isSystemTrayAvailable():
            self.widget.show()

        self.tick = QTimer(self)
        self.tick.timeout.connect(self._tick)
        self.tick.start(TICK_MS)

        # The tray icon is drawn against the system's surface, so it has to be
        # redrawn when the user switches between the light and dark themes.
        hints = qapp.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda _scheme: self._repaint_tray())

        self.poller.start()
        qapp.aboutToQuit.connect(self._shutdown)

    # ------------------------------------------------------------------ menu
    def _build_menu(self) -> None:
        self.menu = QMenu()
        self.menu.setStyleSheet(
            f"QMenu {{ background:{theme.SURFACE.name()}; color:{theme.TEXT.name()};"
            f" border:1px solid {theme.BORDER.name()}; border-radius:10px; padding:6px; }}"
            f"QMenu::item {{ padding:6px 22px 6px 14px; border-radius:6px; }}"
            f"QMenu::item:selected {{ background:{theme.SURFACE2.name()}; }}"
            f"QMenu::separator {{ height:1px; background:{theme.BORDER.name()}; margin:5px 8px; }}"
        )

        act_refresh = QAction(t("menu.refresh_now"), self.menu)
        act_refresh.triggered.connect(self.refresh)
        self.menu.addAction(act_refresh)

        act_panel = QAction(t("menu.open_panel"), self.menu)
        act_panel.triggered.connect(self.toggle_panel)
        self.menu.addAction(act_panel)
        self.menu.addSeparator()

        self.act_visible = self._check(t("menu.show_widget"), self.settings["widget_visible"],
                                       self._toggle_widget)
        self.act_compact = self._check(t("menu.compact"), self.settings["compact"],
                                       self._toggle_compact)
        self.act_locked = self._check(t("menu.lock"), self.settings["locked"],
                                      self._toggle_locked)

        self._submenu(t("menu.provider"), [p.key for p in providers.ALL],
                      lambda key: providers.get(key).label,
                      self.provider.key, self._set_provider)
        self._submenu(t("menu.interval"), POLL_CHOICES, poll_label,
                      int(self.settings["poll_sec"]), self._set_interval)
        self._submenu(t("menu.alert"), ALERT_CHOICES,
                      lambda pct: t("menu.alert_off") if pct == 0 else f"{pct}%",
                      int(self.settings["alert_at"]), self._set_alert)
        self._submenu(t("menu.language"), ["auto", *i18n.LANGUAGES],
                      lambda code: t("menu.language_auto") if code == "auto"
                      else i18n.LANGUAGES[code],
                      self.settings["language"], self._set_language)

        self.menu.addSeparator()
        self.act_autostart = self._check(t("menu.autostart", os=paths.os_name()),
                                         autostart.enabled(), self._toggle_autostart)

        self.menu.addSeparator()
        act_updates = QAction(t("menu.check_updates"), self.menu)
        act_updates.triggered.connect(lambda: self.show_about(check=True))
        self.menu.addAction(act_updates)

        act_about = QAction(t("menu.about"), self.menu)
        act_about.triggered.connect(lambda: self.show_about())
        self.menu.addAction(act_about)

        self.menu.addSeparator()
        act_quit = QAction(t("menu.quit"), self.menu)
        act_quit.triggered.connect(self.qapp.quit)
        self.menu.addAction(act_quit)

    def _submenu(self, title: str, values, label, current, slot) -> None:
        """A radio group: interval and language are both one-of-many."""
        sub = self.menu.addMenu(title)
        sub.setStyleSheet(self.menu.styleSheet())
        group = QActionGroup(sub)
        group.setExclusive(True)
        for value in values:
            act = QAction(label(value), sub, checkable=True)
            act.setChecked(value == current)
            act.triggered.connect(lambda _checked=False, v=value: slot(v))
            group.addAction(act)
            sub.addAction(act)

    def _popup_menu(self, where) -> None:
        # Not connected straight to self.menu.popup: the menu object is replaced
        # when the language changes, and the old connection would outlive it.
        self.menu.popup(where)

    def _set_language(self, code: str) -> None:
        self.settings["language"] = code
        self.settings.save()
        i18n.set_language(code)
        if self.about is not None:         # its labels were built once, in the old language
            retired = self.about
            self._retired_about.append(retired)
            retired.destroyed.connect(lambda: self._retired_about.remove(retired))
            retired.dispose()
            self.about = None
        self._build_menu()                 # labels live in the actions themselves
        self.tray.setContextMenu(self.menu)
        if self.snap:
            self.on_update(self.snap)      # tooltips and painted strings
        else:
            self.tray.setToolTip(t("tray.collecting"))
        self.widget.update()
        self.panel.update()

    def _check(self, label: str, checked: bool, slot) -> QAction:
        act = QAction(label, self.menu, checkable=True)
        act.setChecked(bool(checked))
        act.toggled.connect(slot)
        self.menu.addAction(act)
        return act

    # --------------------------------------------------------------- actions
    def refresh(self) -> None:
        self.poller.refresh()

    def toggle_panel(self) -> None:
        if self.panel.isVisible():
            self.panel.hide()
            return
        if self.panel.just_closed():
            return                    # this click is the one that closed it
        anchor = QRectF(self.widget.geometry()) if self.widget.isVisible() else None
        screen = self.widget.screen() if self.widget.isVisible() else self.qapp.primaryScreen()
        self.panel.popup_at(anchor, screen)

    def show_about(self, check: bool = False) -> None:
        """Open the about card, optionally running the update check on the way in
        so the menu's two entries land in the same place."""
        if self.about is None:
            self.about = About()
        if self.about.isVisible():
            self.about.hide()
            return
        anchor = QRectF(self.widget.geometry()) if self.widget.isVisible() else None
        screen = self.widget.screen() if self.widget.isVisible() else self.qapp.primaryScreen()
        self.about.popup_at(anchor, screen)
        if check:
            self.about.check()

    def _toggle_widget(self, on: bool) -> None:
        if not on and not QSystemTrayIcon.isSystemTrayAvailable():
            on = True
            self.act_visible.blockSignals(True)
            self.act_visible.setChecked(True)
            self.act_visible.blockSignals(False)
        self.settings["widget_visible"] = on
        self.settings.save()
        self.widget.setVisible(on)

    def _toggle_compact(self, on: bool) -> None:
        self.settings["compact"] = on
        self.settings.save()
        self.widget.apply_size()
        self.widget.restore_position()
        self.widget.update()

    def _toggle_locked(self, on: bool) -> None:
        self.settings["locked"] = on
        self.settings.save()

    def _toggle_autostart(self, on: bool) -> None:
        autostart.set_enabled(on)
        self.act_autostart.setChecked(autostart.enabled())

    def _set_alert(self, percent: int) -> None:
        self.settings["alert_at"] = percent
        self.settings.save()
        # A threshold just lowered past where usage already is should fire now,
        # not at the next window.
        self._alerted_for = -1
        if self.snap:
            self._maybe_alert(self.snap)

    def _maybe_alert(self, snap: Snapshot) -> None:
        """One notification per window, when the 5h number first crosses the
        threshold.

        The widget is a display, and a display only works if you look at it.
        This is the one place the app speaks first, so it says the thing worth
        acting on: not that you are at 80%, but how long that leaves you.
        """
        u = snap.usage
        if not alert_due(snap, int(self.settings["alert_at"]), self._alerted_for):
            return
        self._alerted_for = u.h5_reset

        projection = self.poller.projection(u)
        clock = theme.fmt_clock(u.h5_reset)
        body = (t("alert.body_rate", projection=projection.lstrip("~"), clock=clock)
                if projection else t("alert.body", clock=clock))
        self.tray.showMessage(t("alert.title", pct=u.h5), body,
                              tray_icon(snap), ALERT_MS)

    def _set_provider(self, key: str) -> None:
        """Switch which agent is watched. The old snapshot goes with it: leaving
        one agent's numbers on screen under another's name is the one thing this
        must never do.

        The poller is told first, and deliberately. This method used to end with
        that line, after four calls that repaint the UI - and one of them raised,
        so the setting changed, the label changed, and the poller went on reading
        the agent the user had just switched away from. Qt swallowed the
        exception into stderr, which a windowed app has nobody watching.
        """
        if key == self.provider.key:
            return
        self.provider = providers.get(key)
        self.poller.set_provider(self.provider)

        self.settings["provider"] = key
        self.settings.save()

        self.snap = None
        self._alerted_for = -1
        self.widget.set_snapshot(None)
        self.panel.set_snapshot(None)
        self.tray.setIcon(tray_icon(None))
        self.tray.setToolTip(t("tray.collecting"))

    def _set_interval(self, seconds: int) -> None:
        self.settings["poll_sec"] = seconds
        self.settings.save()
        self.poller.set_interval(seconds)

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_panel()

    # ----------------------------------------------------------------- cycle
    def on_update(self, snap: Snapshot) -> None:
        if snap.provider and snap.provider != self.provider.key:
            # In flight when the user switched. Drawing it would put one agent's
            # numbers under the other's name, which is the single thing this
            # must never do.
            return
        self.snap = snap
        if DEBUG:
            u = snap.usage
            print(f"[{time.strftime('%H:%M:%S')}] ok={snap.ok} 5h={u.h5:.1f} "
                  f"7d={u.d7:.1f} err={snap.error!r}", flush=True)
        self.widget.set_snapshot(snap)
        self.panel.set_snapshot(snap, self.poller.projection(snap.usage))
        self._maybe_alert(snap)
        self.tray.setIcon(tray_icon(snap))
        if snap.ok:
            u = snap.usage
            self.tray.setToolTip(t("tray.tooltip", h5=u.h5, d7=u.d7,
                                   h5_clock=theme.fmt_clock(u.h5_reset),
                                   d7_clock=theme.fmt_clock(u.d7_reset)))
        else:
            self.tray.setToolTip(t("widget.tooltip_error",
                                   error=snap.error or t("widget.no_data")))

    def _repaint_tray(self) -> None:
        self.tray.setIcon(tray_icon(self.snap))

    def _tick(self) -> None:
        if self.widget.isVisible():
            self.widget.update()
        if self.panel.isVisible():
            self.panel.update()

    def _shutdown(self) -> None:
        self.poller.stop()
        if self.about is not None:
            self.about.close()
            self.about.wait_for_check()
        for retired in self._retired_about:
            retired.wait_for_check()
        self.poller.wait()
        self.tray.hide()


def _already_running() -> bool:
    """Single instance: a second launch notices the first and exits."""
    probe = QLocalSocket()
    probe.connectToServer(APP_ID)
    if probe.waitForConnected(200):
        probe.disconnectFromServer()
        return True
    QLocalServer.removeServer(APP_ID)     # clears a socket left by a crash
    server = QLocalServer()
    server.listen(APP_ID)
    _already_running.server = server      # kept alive for the life of the process
    return False


def prefer_x11() -> None:
    """Steer a Linux Wayland session onto XWayland, before Qt reads the choice.

    Wayland gives a window no say in its own position: `move()` is silently
    ignored, and a widget that cannot be parked where the user left it is a
    different product. XWayland has no such rule.

    Only when the user has not picked a plugin themselves, and only when an X
    server is actually reachable - forcing xcb without one would stop the app
    from starting at all.
    """
    if not paths.LINUX or os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main() -> int:
    prefer_x11()                 # must precede the QApplication
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Agent Gauge")
    qapp.setQuitOnLastWindowClosed(False)

    if _already_running():
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(t("error.no_tray"), file=sys.stderr)

    app = App(qapp)          # the local reference keeps it alive during exec
    return qapp.exec() if app else 1


if __name__ == "__main__":
    raise SystemExit(main())

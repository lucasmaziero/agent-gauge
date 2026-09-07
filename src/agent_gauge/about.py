"""Who made this, which version it is, and whether there is a newer one.

Painted differently from the rest of the app on purpose. The widget and the
panel lay out every glyph by hand because they are instruments: numbers that
must not jitter, columns that must not collide. This is prose and two links, so
Qt lays it out, and the only hand-painted part is the card underneath - the
same shadow and surface the panel draws, so it reads as the same object.

The update check runs only when asked. There is no background poll and no
auto-update: the app tells you a newer tag exists and hands you the release
page, and what happens next is yours.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import brand, paint, release, theme
from .i18n import t
from .theme import LG, MD, SM

W = 312                      # visible card width; the height follows the layout
M = 16                       # transparent margin reserved for the shadow
APP_NAME = "Agent Gauge"
AUTHOR = "Lucas Maziero"

# What each way of failing is called on screen. Anything unrecognised falls back
# to the vague one, which is at least not a claim.
FAILURES = {
    "offline": "about.unreachable",
    "rate_limited": "about.rate_limited",
    "malformed": "about.unreadable",
    "untagged": "about.unreadable",
}


def link(href: str, text: str) -> str:
    """An anchor the app's colour actually reaches.

    A QSS rule for `QLabel a` is silently ignored - Qt styles rich-text anchors
    from the document, not the stylesheet - so without this every link in here
    renders in the default blue with an underline.
    """
    return (f'<a href="{href}" style="color:{theme.ACCENT.name()};'
            f' text-decoration:none;">{text}</a>')


class _Check(QThread):
    """One request, off the UI thread, then done.

    A QThread rather than QNetworkAccessManager so the request is the same
    urllib call the rest of the app makes and can be tested without Qt.
    """

    finished_with = Signal(object)       # a release.Latest

    def run(self) -> None:
        self.finished_with.emit(release.fetch_latest())


class About(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._check: _Check | None = None

        self.setWindowFlags(
            Qt.WindowType.Popup                 # closes itself on an outside click
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(W + M * 2)
        self._build()

    # ---------------------------------------------------------------- layout
    def _build(self) -> None:
        self.setStyleSheet(f"""
            QLabel {{ color: {theme.MUTED.name()}; }}
            QLabel#title {{ color: {theme.TEXT.name()}; }}
            QLabel#version, QLabel#status {{ color: {theme.FAINT.name()}; }}
            QPushButton {{
                color: {theme.TEXT.name()};
                background: {theme.SURFACE2.name()};
                border: 1px solid {theme.BORDER.name()};
                border-radius: 8px; padding: 7px 14px;
            }}
            QPushButton:hover {{ border-color: {theme.FAINT.name()}; }}
            QPushButton:disabled {{ color: {theme.FAINT.name()}; }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(M + LG, M + LG, M + LG, M + LG)
        outer.setSpacing(MD)

        head = QHBoxLayout()
        head.setSpacing(SM)
        mark = QLabel()
        mark.setPixmap(brand.clawd(13, theme.ACCENT, self.devicePixelRatioF()))
        head.addWidget(mark)

        title = QLabel(APP_NAME.upper(), objectName="title")
        title.setFont(paint.font(9, QFont.Weight.DemiBold))
        head.addWidget(title)
        head.addStretch(1)

        version = QLabel(f"v{release.__version__}", objectName="version")
        version.setFont(paint.font(8))
        head.addWidget(version)
        outer.addLayout(head)

        outer.addWidget(self._rule())

        body = QLabel(
            f'{AUTHOR}<br>{t("about.license")}<br><br>'
            + link(f"https://github.com/{release.REPO}", f"github.com/{release.REPO}")
        )
        body.setFont(paint.font(9))
        body.setOpenExternalLinks(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        outer.addWidget(body)

        outer.addWidget(self._rule())

        row = QHBoxLayout()
        row.setSpacing(MD)
        self.button = QPushButton(t("about.check"))
        self.button.setFont(paint.font(9))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.check)
        row.addWidget(self.button)

        self.status = QLabel("", objectName="status")
        self.status.setFont(paint.font(8))
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        row.addWidget(self.status, 1)
        outer.addLayout(row)

    def _rule(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER.name()}; border: none;")
        return line

    # ------------------------------------------------------------- placement
    def popup_at(self, anchor: QRectF | None, screen) -> None:
        """Same rule as the panel: open against the widget, flip below it when
        there is no room above, and never leave the work area."""
        geo = screen.availableGeometry()
        w, h = self.width(), self.sizeHint().height()
        self.setFixedHeight(h)
        if anchor is None:
            x, y = geo.right() - w, geo.bottom() - h
        else:
            x = int(anchor.center().x() - w / 2)
            y = int(anchor.top() - h + M)
            if y < geo.top():
                y = int(anchor.bottom() - M)
        x = min(max(x, geo.left() - M), geo.right() - w + M)
        y = min(max(y, geo.top() - M), geo.bottom() - h + M)
        self.move(QPoint(x, y))
        self.show()

    # ---------------------------------------------------------------- update
    def check(self) -> None:
        """Ask GitHub for the latest tag. Never runs on its own."""
        if self._check and self._check.isRunning():
            return
        self.button.setEnabled(False)
        self.status.setText(t("about.checking"))

        self._check = _Check(self)
        self._check.finished_with.connect(self._checked)
        self._check.start()

    def _checked(self, latest) -> None:
        """None of the failures may be worded as a pass, and they must not be
        worded as each other either: "could not reach GitHub" sent at least one
        person looking at their network when GitHub was rate limiting them."""
        self.button.setEnabled(True)
        if not latest.ok:
            self.status.setText(t(FAILURES.get(latest.problem, "about.unreachable")))
        elif release.is_newer(latest.tag):
            self.status.setText(
                link(release.DOWNLOAD_URL, t("about.available", version=latest.tag)))
        else:
            self.status.setText(t("about.current"))

    def closeEvent(self, event) -> None:
        if self._check and self._check.isRunning():
            self._check.wait(2000)
        super().closeEvent(event)

    # -------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = QRectF(M, M, self.width() - M * 2, self.height() - M * 2)
        paint.shadow(p, card, 18.0, spread=M - 2, alpha=64, dy=4.0)
        paint.surface(p, card, radius=18.0)
        p.end()

"""Who made this, which version it is, and whether there is a newer one.

Laid out by Qt, unlike the rest of the app: the widget and panel place every
glyph by hand because they are instruments, but this is prose and two links.
Only the card underneath is painted, with the panel's shadow and surface so it
reads as the same object.

The update check runs only when asked - no background poll, no auto-update.
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

# Hair spaces: a plain "  ·  " collapses to one in rich text and the dot
# crowds the word before it. No colour of its own, so it stays punctuation
# rather than reading as a third thing to click.
SEP = "&#8202;&#8202;·&#8202;&#8202;"

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
    return (f'<a href="{href}" style="color:{theme.INTERACTIVE.name()};'
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
        # The gauge, not an agent's mascot: this card is about the app, which
        # watches either. It wore Clawd here while showing Codex numbers.
        mark.setPixmap(brand.gauge(14, theme.ACCENT, self.devicePixelRatioF()))
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

        # A bare repository URL asked the reader to already know what this was.
        tagline = QLabel(t("about.tagline"))
        tagline.setFont(paint.font(9))
        tagline.setWordWrap(True)
        outer.addWidget(tagline)

        body = QLabel(
            f'{AUTHOR} · {t("about.license")}<br><br>'
            + link(release.SITE_URL, t("about.site"))
            + SEP
            + link(release.SOURCE_URL, t("about.source"))
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
        """No failure may be worded as a pass, or as another failure: "could
        not reach GitHub" sent someone hunting a network fault that was a rate
        limit."""
        self.button.setEnabled(True)
        if not latest.ok:
            self.status.setText(t(FAILURES.get(latest.problem, "about.unreachable")))
        elif release.is_newer(latest.tag):
            self.status.setText(
                link(release.DOWNLOAD_URL, t("about.available", version=latest.tag)))
        else:
            self.status.setText(t("about.current"))

    def dispose(self) -> None:
        """Retire a translated card without destroying a running child thread."""
        self.close()
        if self._check:
            self._check.finished.connect(self.deleteLater)
        if not self._check or not self._check.isRunning():
            self.deleteLater()

    def wait_for_check(self) -> None:
        """Keep the thread alive until its request finishes during shutdown."""
        if self._check:
            self._check.wait()

    # -------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = QRectF(M, M, self.width() - M * 2, self.height() - M * 2)
        paint.shadow(p, card, 18.0, spread=M - 2, alpha=64, dy=4.0)
        paint.surface(p, card, radius=18.0)
        p.end()

"""Render the widget and the panel to PNGs.

    uv run python tools/preview.py [out.png]        # contact sheet, every state
    uv run python tools/preview.py --shots docs     # one file each, at 2x

No network and no visible windows: the widgets are painted without ever being
shown. It runs on the normal Windows platform plugin on purpose: under
QT_QPA_PLATFORM=offscreen Qt loses the system font database and every glyph
renders as a box.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from agent_gauge import api, i18n, paint, theme, tokens
from agent_gauge.panel import Panel
from agent_gauge.poller import Snapshot
from agent_gauge.settings import DEFAULTS, Settings
from agent_gauge.widget import FloatingWidget

GAP = 20
BACKDROP = QColor("#08080A")


def snapshot(h5: float, d7: float, incidents: tuple[str, ...] = (), error: str = "") -> Snapshot:
    now = time.time()
    usage = api.Usage(
        h5=h5, d7=d7,
        h5_reset=int(now + 8040), d7_reset=int(now + 169200),
        status_overall=("rejected" if h5 >= 100 else
                        "allowed_warning" if h5 >= 90 else "allowed"),
        claim="five_hour", ok=not error, error=error,
    )
    return Snapshot(
        usage=usage,
        totals=tokens.TokenTotals(input=202_040, output=31_283,
                                  cache_read=6_029_281, sessions=2),
        incidents=list(incidents), subscription="max", error=error,
    )


def fixed_settings() -> Settings:
    """Defaults only, never this machine's preferences.

    A published screenshot must not depend on which agent happens to be
    selected wherever it was generated - that is how the site came within one
    commit of offering a Codex panel as its picture of the app.
    """
    settings = Settings()
    settings.update(DEFAULTS)
    settings["compact"] = False
    return settings


def render(widget, scale: float = 1.0) -> QImage:
    """Paint a widget offscreen, transparent background.

    `scale` above 1 renders for a high-density display: the pixmap is that many
    times larger and Qt lays the drawing out at the bigger size rather than
    scaling a small one up, so hairlines and text stay sharp.
    """
    img = QImage(round(widget.width() * scale), round(widget.height() * scale),
                 QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(scale)
    img.fill(Qt.GlobalColor.transparent)
    widget.render(img)
    return img


def tray_strip(out_dir: Path, scale: float = 2.0,
               percents: tuple[int, ...] = (6, 47, 83, 100)) -> None:
    """The tray icon at four fills, on the dark strip a taskbar actually is.

    The only doc image that keeps a background, and deliberately: the glyph is
    drawn in whatever colour reads against the surface it sits on, so a
    transparent PNG of it would be invisible against half the pages that embed
    it. The ink is pinned rather than read from this machine's theme, so the
    picture does not change depending on who regenerates it.
    """
    from agent_gauge import app as app_module

    size, pad = 32, 22
    width = len(percents) * (size + pad) + pad
    height = size + pad * 2
    sheet = QImage(int(width * scale), int(height * scale), QImage.Format.Format_ARGB32)
    sheet.setDevicePixelRatio(scale)
    sheet.fill(QColor(theme.SURFACE))

    p = QPainter(sheet)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    x = pad
    for pct in percents:
        icon = app_module.tray_pixmap(snapshot(pct, pct / 2), size, theme.TEXT)
        p.drawPixmap(x, pad, icon)
        x += size + pad
    p.end()

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(str(out_dir / "tray.png"))
    print(f"{out_dir / 'tray.png'} ({sheet.width()}x{sheet.height()} @{scale:g}x)")


def shots(out_dir: Path, scale: float = 2.0) -> None:
    """The two surfaces as separate files, for the web page.

    Transparent rather than on a backdrop: the page's own background is the
    same near-black the app is designed against, so the card sits on it
    directly instead of on a rectangle of a slightly different colour.

    The widget carries no translatable text - "5h", "2h13", "16:33" read the
    same in both - so it is rendered once. The panel is rendered per language,
    because the page offers the same switch the app does and a Portuguese
    screenshot under English copy would be the one thing on the page that
    contradicts itself.
    """
    settings = fixed_settings()
    out_dir.mkdir(parents=True, exist_ok=True)

    before = i18n.language()
    try:
        i18n.set_language("en")
        widget = FloatingWidget(settings)
        widget.set_snapshot(snapshot(37, 8))
        img = render(widget, scale)
        img.save(str(out_dir / "shot-widget.png"))
        print(f"{out_dir / 'shot-widget.png'} ({img.width()}x{img.height()} @{scale:g}x)")

        for code in ("en", "pt_BR"):
            i18n.set_language(code)
            panel = Panel(settings)
            panel.set_snapshot(
                snapshot(71, 34, ("Elevated error rates on the API",)), "~1h40")
            img = render(panel, scale)
            name = f"shot-panel-{code.split('_')[0]}.png"
            img.save(str(out_dir / name))
            print(f"{out_dir / name} ({img.width()}x{img.height()} @{scale:g}x)")
    finally:
        i18n.set_language(before)


def main() -> None:
    QApplication(sys.argv[:1])

    if "--shots" in sys.argv:
        where = sys.argv[sys.argv.index("--shots") + 1:]
        target = Path(where[0]) if where else Path("docs")
        shots(target)
        tray_strip(target)
        return

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "preview.png")
    settings = fixed_settings()

    states = (
        snapshot(12, 4),
        snapshot(71, 34),
        snapshot(96, 88, ("Elevated error rates on the API",)),
        snapshot(0, 0, error="token recusado (401): rode `claude` para renovar"),
    )

    settings["compact"] = False
    frames = []
    for snap in states:
        widget = FloatingWidget(settings)
        widget.set_snapshot(snap)
        frames.append(render(widget))

    settings["compact"] = True
    compact_widget = FloatingWidget(settings)
    compact_widget.set_snapshot(snapshot(71, 34))
    compact = render(compact_widget)
    settings["compact"] = False

    panel = Panel(settings)
    panel.set_snapshot(snapshot(71, 34, ("Elevated error rates on the API",)), "~1h40")
    panel_img = render(panel)

    column_w = frames[0].width() + compact.width() + GAP
    column_h = sum(f.height() + GAP for f in frames)
    width = GAP + column_w + GAP + panel_img.width() + GAP
    height = GAP + max(column_h, panel_img.height() + GAP) + GAP

    sheet = QImage(width, height, QImage.Format.Format_ARGB32)
    sheet.fill(BACKDROP)
    p = QPainter(sheet)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    y = GAP
    for frame in frames:
        p.drawImage(GAP, y, frame)
        y += frame.height() + GAP
    p.drawImage(GAP + frames[0].width() + GAP, GAP, compact)
    p.drawImage(GAP + column_w + GAP, GAP, panel_img)
    paint.text(p, QRectF(0, height - 20, width, 16), "preview offline · dados sintéticos",
               theme.FAINT, 8, align=Qt.AlignmentFlag.AlignHCenter)
    p.end()

    sheet.save(str(out))
    print(f"{out} ({width}x{height})")


if __name__ == "__main__":
    main()

"""Interface strings, one dictionary per language.

Dictionaries rather than Qt Linguist or gettext: at this size (some thirty
strings, two languages) a .ts/.po pipeline would add a compile step to the build
and data files for PyInstaller to carry, for tooling nobody here needs. Adding a
language is one dictionary and one entry in LANGUAGES; a test keeps the keys in
step.

Only what a person reads lives here. Keys, header names and log lines stay in
English in the code.
"""
from __future__ import annotations

DEFAULT = "en"
LANGUAGES = {"en": "English", "pt_BR": "Português"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # widget
        "widget.collecting": "collecting…",
        "widget.no_data": "no data",
        "widget.tooltip": ("5h: {h5:.0f}%  resets {h5_clock} (in {h5_left})\n"
                           "7d: {d7:.0f}%  resets {d7_clock} (in {d7_left})"),
        "widget.tooltip_error": "Agent Gauge: {error}",
        # panel
        "panel.window_5h": "5-hour window",
        "panel.window_7d": "7-day window",
        "panel.waiting": "waiting for the first fetch",
        "panel.resets": "resets {clock} · in {left}",
        "panel.resets_on": "resets {weekday} {clock} · in {left}",
        "panel.overflows": "hits 100% {projection}",
        "panel.bottleneck": "the binding limit",
        "panel.no_transcripts": "no transcripts in this window",
        "panel.tokens_one": "{total} tokens · {cache} cache · {n} session",
        "panel.tokens_other": "{total} tokens · {cache} cache · {n} sessions",
        "panel.no_incidents": "{host} reports no incidents",
        "panel.updated": "updated {stamp} · every {cadence}",
        "panel.updated_idle": "updated {stamp} · every {cadence}, idle",
        "panel.refresh_now": "refresh now",
        # status chip
        "status.ok": "OK",
        "status.warning": "WARNING",
        "status.blocked": "BLOCKED",
        "status.no_data": "NO DATA",
        # menu
        "menu.refresh_now": "Refresh now",
        "menu.open_panel": "Open panel",
        "menu.show_widget": "Show widget",
        "menu.compact": "Compact mode",
        "menu.lock": "Lock position",
        "menu.interval": "Interval",
        "menu.language": "Language",
        "menu.language_auto": "Automatic",
        "menu.autostart": "Start with {os}",
        "menu.alert": "Alert at",
        "menu.alert_off": "Off",
        "alert.title": "{pct:.0f}% of the 5-hour window",
        "alert.body": "Resets at {clock}.",
        "alert.body_rate": "At this rate it hits 100% in {projection}. Resets at {clock}.",
        "panel.get_agent": "Get {agent}",
        # about
        "menu.about": "About",
        "menu.check_updates": "Check for updates",
        "about.tagline": "Your coding agent's limits, where you can see them.",
        "about.license": "MIT License",
        "about.source": "Source",
        "about.site": "Website",
        "about.check": "Check for updates",
        "about.checking": "Checking…",
        "about.current": "This is the latest version",
        "about.available": "{version} is available →",
        "about.unreachable": "could not reach GitHub",
        "about.rate_limited": "GitHub is rate limiting; try again later",
        "about.unreadable": "GitHub answered something unexpected",
        "panel.how_signin": "How to sign in",
        "menu.quit": "Quit",
        "menu.seconds": "{n} seconds",
        "menu.minute": "1 minute",
        "menu.minutes": "{n} minutes",
        # tray
        "tray.collecting": "Agent Gauge: collecting…",
        "tray.tooltip": ("Claude · 5h {h5:.0f}% (resets {h5_clock})\n"
                         "7d {d7:.0f}% (resets {d7_clock})"),
        # time
        "time.now": "now",
        # errors, all user facing
        # What to do comes first in every one of these: the panel elides a
        # long line, and the tail is the half that tells the user what to do.
        "error.no_credentials": "sign in to {agent} - {path} not found",
        "error.no_claude": "no sign of {agent} on this machine",
        "error.no_windows": "the usage reply carried no rate-limit windows",
        "menu.provider": "Watching",
        # Kept short on purpose: the widget's error column is 120px at 9pt,
        # and "waiting for Claude Code" runs 127. An elided reassurance is
        # not reassuring.
        "error.waiting": "waiting for {agent}",
        "error.no_keychain": "sign in to {agent} - no token in the login keychain",
        "error.unreadable": "could not read {path}: {reason}",
        "error.no_token": "sign in to {agent} again - credentials carry no accessToken",
        "error.unauthorized": "sign in to {agent} again - token refused (401)",
        "error.no_headers": "HTTP {code} response carried no usage headers",
        "error.network": "network: {reason}",
        "error.collection": "could not read usage; retrying next cycle",
        "error.no_tray": "system tray unavailable",
    },
    "pt_BR": {
        # widget
        "widget.collecting": "coletando…",
        "widget.no_data": "sem dados",
        "widget.tooltip": ("5h: {h5:.0f}%  reseta {h5_clock} (em {h5_left})\n"
                           "7d: {d7:.0f}%  reseta {d7_clock} (em {d7_left})"),
        "widget.tooltip_error": "Agent Gauge: {error}",
        # panel
        "panel.window_5h": "Janela de 5 horas",
        "panel.window_7d": "Janela de 7 dias",
        "panel.waiting": "aguardando primeira coleta",
        "panel.resets": "reseta {clock} · em {left}",
        "panel.resets_on": "reseta {weekday} {clock} · em {left}",
        "panel.overflows": "estoura {projection}",
        "panel.bottleneck": "é o gargalo agora",
        "panel.no_transcripts": "sem transcripts nesta janela",
        "panel.tokens_one": "{total} tokens · {cache} cache · {n} sessão",
        "panel.tokens_other": "{total} tokens · {cache} cache · {n} sessões",
        "panel.no_incidents": "{host} sem incidentes",
        "panel.updated": "atualizado {stamp} · a cada {cadence}",
        "panel.updated_idle": "atualizado {stamp} · a cada {cadence}, ocioso",
        "panel.refresh_now": "atualizar agora",
        # status chip
        "status.ok": "OK",
        "status.warning": "ATENÇÃO",
        "status.blocked": "BLOQUEADO",
        "status.no_data": "SEM DADOS",
        # menu
        "menu.refresh_now": "Atualizar agora",
        "menu.open_panel": "Abrir painel",
        "menu.show_widget": "Mostrar widget",
        "menu.compact": "Modo compacto",
        "menu.lock": "Travar posição",
        "menu.interval": "Intervalo",
        "menu.language": "Idioma",
        "menu.language_auto": "Automático",
        "menu.autostart": "Iniciar com o {os}",
        "menu.alert": "Alertar em",
        "menu.alert_off": "Desligado",
        "alert.title": "{pct:.0f}% da janela de 5 horas",
        "alert.body": "Reseta às {clock}.",
        "alert.body_rate": "Nesse ritmo estoura em {projection}. Reseta às {clock}.",
        "panel.get_agent": "Instalar o {agent}",
        # sobre
        "menu.about": "Sobre",
        "menu.check_updates": "Verificar atualizações",
        "about.tagline": "Os limites do seu agente, onde dá para ver.",
        "about.license": "Licença MIT",
        "about.source": "Código",
        "about.site": "Site",
        "about.check": "Verificar atualizações",
        "about.checking": "Verificando…",
        "about.current": "Esta é a versão mais recente",
        "about.available": "{version} disponível →",
        "about.unreachable": "não consegui alcançar o GitHub",
        "about.rate_limited": "GitHub limitou as consultas; tente mais tarde",
        "about.unreadable": "o GitHub respondeu algo inesperado",
        "panel.how_signin": "Como fazer login",
        "menu.quit": "Sair",
        "menu.seconds": "{n} segundos",
        "menu.minute": "1 minuto",
        "menu.minutes": "{n} minutos",
        # tray
        "tray.collecting": "Agent Gauge: coletando…",
        "tray.tooltip": ("Claude · 5h {h5:.0f}% (reseta {h5_clock})\n"
                         "7d {d7:.0f}% (reseta {d7_clock})"),
        # time
        "time.now": "agora",
        # errors, all user facing
        "error.no_credentials": "faça login no {agent} - {path} não existe",
        "error.no_claude": "nenhum sinal do {agent} nesta máquina",
        "error.no_windows": "a resposta de uso não trouxe janelas de limite",
        "menu.provider": "Monitorando",
        "error.waiting": "esperando o {agent}",
        "error.no_keychain": "faça login no {agent} - sem token no chaveiro",
        "error.unreadable": "não consegui ler {path}: {reason}",
        "error.no_token": "refaça o login no {agent} - credenciais sem accessToken",
        "error.unauthorized": "refaça o login no {agent} - token recusado (401)",
        "error.no_headers": "resposta HTTP {code} sem headers de uso",
        "error.network": "rede: {reason}",
        "error.collection": "não foi possível ler o uso; nova tentativa no próximo ciclo",
        "error.no_tray": "bandeja do sistema indisponível",
    },
}

WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "pt_BR": ("seg", "ter", "qua", "qui", "sex", "sáb", "dom"),
}
DECIMAL = {"en": ".", "pt_BR": ","}

_current: str | None = None


def system_language() -> str:
    """What the system is set to, narrowed to what this app speaks.

    Imported lazily so the pure-stdlib modules that raise user-facing errors do
    not pull Qt in at import time.
    """
    from PySide6.QtCore import QLocale

    return "pt_BR" if QLocale.system().name().startswith("pt") else DEFAULT


def set_language(code: str | None) -> str:
    """Pin a language, or pass None/"auto" to follow the system."""
    global _current
    _current = code if code in STRINGS else system_language()
    return _current


def language() -> str:
    global _current
    if _current is None:
        _current = system_language()
    return _current


def t(key: str, **fields) -> str:
    """A translated string. Missing keys fall back to English, never to a crash
    in front of the user."""
    text = STRINGS[language()].get(key) or STRINGS[DEFAULT][key]
    return text.format(**fields) if fields else text


def tn(n: int, singular: str, plural: str, **fields) -> str:
    """Plural by count. Both languages here split at one, which is why this is
    six lines instead of a plural-forms engine."""
    return t(singular if n == 1 else plural, n=n, **fields)


def weekdays() -> tuple[str, ...]:
    return WEEKDAYS.get(language(), WEEKDAYS[DEFAULT])


def decimal_separator() -> str:
    return DECIMAL.get(language(), DECIMAL[DEFAULT])

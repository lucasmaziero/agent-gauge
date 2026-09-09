"""What to offer when there is no token to read.

Two different dead ends hide behind one red line, and they want different
answers: never installed here, or installed and signed out. `Provider.home()`
says which, and why it is the directory rather than a PATH lookup.

Nothing here installs anything. Piping an install script into a shell on the
user's behalf is not a thing a monitoring widget should do, and a link cannot
rot into running the wrong command.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

INSTALL = "install"      # no sign of this agent on the machine
SIGNIN = "signin"        # it has been used here, but there is no usable token


def needed(provider) -> str:
    """Which dead end the user is at, as INSTALL or SIGNIN."""
    return SIGNIN if provider.home().exists() else INSTALL


def open_help(provider) -> None:
    """Hand the agent's setup page to the user's browser."""
    QDesktopServices.openUrl(QUrl(provider.help_url))


def open_status(provider) -> None:
    """Hand the agent's status page to the user's browser.

    Built from status_host so the address opened is the one the panel named; a
    constant of its own could disagree with the label.
    """
    QDesktopServices.openUrl(QUrl(f"https://{provider.status_host}"))

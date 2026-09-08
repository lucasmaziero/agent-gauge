"""What to offer when there is no token to read.

Without credentials the widget has nothing to show and, until now, nothing to
suggest either: it painted a line of red text and left the user to work out the
rest. There are two different dead ends behind that one message, and they want
different answers.

The signal is `~/.claude`, not the `claude` binary. A PATH lookup is the obvious
test and the wrong one: Claude Code is also used through the desktop app and the
IDE extensions, which never put a CLI on PATH, so plenty of active users would
be told they have not installed it. The directory is written by all of them.

Nothing here installs anything. Piping an install script into a shell on the
user's behalf is not a thing a monitoring widget should do, and the script is
not ours to keep working; a link to the page that documents both installing and
signing in costs one click and cannot rot into running the wrong command.
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

    Built from status_host rather than a URL of its own, so the address opened
    is the one the panel just named. A separate constant could disagree with
    the label, and a link that goes somewhere other than where it says is worse
    than no link.
    """
    QDesktopServices.openUrl(QUrl(f"https://{provider.status_host}"))

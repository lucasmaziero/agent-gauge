"""What the widget needs from whatever it is watching.

The fit is closer than it has any right to be: both agents meter a rolling
five-hour window and a weekly one, at 18000 and 604800 seconds exactly, both
reporting a percentage and a reset time. So `Usage` did not have to change and
neither did any of the drawing - the seam is here, and it is thin.

They differ in what a reading costs: Anthropic publishes no usage endpoint for
subscription accounts, so that provider spends an output token per cycle
reading the headers of a reply it discards, where Codex spends nothing. Hence
`fetch` takes the whole credentials object rather than a token - what a
provider needs to ask its own question is its own business.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..api import Usage
from ..credentials import Credentials
from ..tokens import TokenTotals


class Provider(ABC):
    """One source of usage numbers."""

    key: str            # stored in settings; never shown
    label: str          # shown in the menu and the panel header
    short: str          # every message the widget's 120px error column shows
    help_url: str       # where someone with no credentials should be sent
    status_host: str    # the status page this agent's outages are reported on

    @abstractmethod
    def home(self) -> Path:
        """The agent's own directory. Its existence is what tells "never
        installed here" apart from "installed but signed out" - a PATH lookup
        would not, since both of these ship editor extensions that never put a
        binary on PATH."""

    @abstractmethod
    def credentials(self) -> Credentials:
        """Raises CredentialsError, translated, when there is nothing usable."""

    @abstractmethod
    def fetch(self, creds: Credentials) -> Usage:
        """Never raises: failures come back as ok=False."""

    def incidents(self) -> list[str]:
        """Open incidents on this agent's own status page.

        Per provider because the panel names the host it checked, and telling
        someone watching Codex that status.claude.com is quiet answers a
        question they did not ask about a service they are not using.
        """
        return []

    def totals(self, since: float) -> TokenTotals:
        """Absolute token counts for the window, when the agent keeps
        transcripts this can read. Empty is a valid answer and the panel
        already renders it as "no transcripts in this window"."""
        return TokenTotals()

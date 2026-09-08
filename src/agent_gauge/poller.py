"""Collection thread: token -> API -> local transcripts -> signal to the UI."""
from __future__ import annotations

import contextlib
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from . import api, credentials, diag, paths, providers, signin, tokens
from .i18n import t

HISTORY_FILE = paths.config_dir() / "history.json"


@dataclass
class Snapshot:
    """Everything the UI needs to paint one cycle."""

    usage: api.Usage = field(default_factory=api.Usage)
    totals: tokens.TokenTotals = field(default_factory=tokens.TokenTotals)
    incidents: list[str] = field(default_factory=list)
    subscription: str = ""
    error: str = ""
    setup: str = ""            # signin.INSTALL or signin.SIGNIN, else empty
    waiting: bool = False      # no data, but nothing is wrong: see _collect
    interval: int = 0          # seconds until the next fetch, backoff included
    provider: str = ""         # whose numbers these are; see App.on_update
    at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return self.usage.ok and not self.error


class Poller(QThread):
    """Polls every `interval` seconds; refresh() wakes it immediately.

    Receivers must be QObjects: connected to a plain Python callable the
    connection becomes direct and painting would run on this thread.
    """

    updated = Signal(object)   # Snapshot
    busy = Signal(bool)        # True while a cycle is in flight

    STATUS_EVERY = 300         # incidents move slowly; every 5 min is plenty
    HISTORY_MAX = 180          # more than a 5h window holds at any interval

    # Polling every two minutes while the number does not move buys nothing and
    # still costs a request each time. After this many identical readings the
    # wait stretches, up to this multiple of the interval the user chose; any
    # movement, any error, or a manual refresh puts it straight back.
    IDLE_AFTER = 3
    IDLE_MAX = 4

    # While the token is expired the only thing that can change the answer is
    # Claude Code rewriting the credentials, so the file is watched instead of
    # the clock. A stat every few seconds costs nothing and turns a two-minute
    # wait into about five - which is the difference between the widget coming
    # back as you type and you noticing it was ever out.
    CREDS_POLL = 5

    def __init__(self, interval: int, provider=None, parent=None) -> None:
        super().__init__(parent)
        self._interval = interval
        self.provider = provider or providers.get(providers.DEFAULT)
        self._wake = threading.Event()
        self._stop = False
        self._last_status = 0.0
        self._incidents: list[str] = []
        self._idle = 0                       # consecutive readings that did not move
        self._last_h5: float | None = None
        self._last_ok = 0.0                  # epoch of the last successful cycle
        self._watching = False               # waiting on the agent, not on the clock
        self._pending: object | None = None   # a switch waiting for a safe moment
        self.history: deque[tuple[float, float]] = deque(maxlen=self.HISTORY_MAX)
        self._load_history()

    def set_interval(self, seconds: int) -> None:
        self._interval = seconds
        self._wake.set()

    def refresh(self) -> None:
        self._idle = 0                       # asking by hand means asking now
        self._wake.set()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    def run(self) -> None:
        while not self._stop:
            self.busy.emit(True)
            snap = self._collect()
            # Stamped here rather than inside _collect so the number the UI
            # counts down from is the one this loop actually waits.
            snap.interval = self._effective_interval()
            # Stamped so the UI can tell whose numbers these are. A cycle that
            # was already in flight when the user switched still lands, and
            # without this it would be drawn under the new agent's name.
            snap.provider = self.provider.key
            self.updated.emit(snap)   # data first, so the spinner stops on fresh values
            self.busy.emit(False)
            self._sleep(snap.interval)
            self._wake.clear()

    def _creds_mtime(self) -> float:
        try:
            return paths.credentials_file().stat().st_mtime
        except OSError:
            return 0.0

    def _sleep(self, seconds: float) -> None:
        """Wait for the next cycle, but come back the moment Claude Code writes
        a new token - only while there is nothing else worth waiting for."""
        if not self._watching:
            self._wake.wait(seconds)
            return

        before = self._creds_mtime()
        deadline = time.monotonic() + seconds
        while not self._stop:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            if self._wake.wait(min(self.CREDS_POLL, left)):
                return                       # refresh() or stop()
            if self._creds_mtime() != before:
                return

    def _since_ok(self) -> str | None:
        """Minutes since the last cycle that worked, for the log."""
        if not self._last_ok:
            return None
        return f"{(time.time() - self._last_ok) / 60:.0f}"

    def _effective_interval(self) -> int:
        """The chosen interval while anything is moving, stretched while nothing
        is. Never longer than IDLE_MAX times what the user asked for."""
        if self._idle < self.IDLE_AFTER:
            return self._interval
        factor = min(2 ** (self._idle - self.IDLE_AFTER + 1), self.IDLE_MAX)
        return self._interval * factor

    def set_provider(self, provider) -> None:
        """Switch what is being watched, at the next safe moment.

        Nothing is changed here. This is called from the UI thread and the
        collection thread may be inside a fetch, so the switch is left as a note
        and applied at the top of the next cycle - otherwise clearing the
        history races with the append that ends that fetch.
        """
        self._pending = provider
        self._wake.set()

    def _apply_pending(self) -> None:
        """Take up a queued switch. Runs on the collection thread only.

        The history goes with the old agent: a burn rate computed across two
        agents' windows would be a fiction, not a mix.

        So do the incidents, and for the same reason. They are read from each
        agent's own status page - status.claude.com or status.openai.com - and
        cached for five minutes, because incidents move slowly. Left alone
        across a switch, that cache kept serving the previous agent's outages
        under the new agent's name: switch away from Codex and the panel went
        on reporting OpenAI's incident while every number on it was Anthropic's.
        Clearing the clock too is what makes the next cycle ask, rather than
        showing nothing for the rest of the five minutes.
        """
        if self._pending is None:
            return
        self.provider, self._pending = self._pending, None
        self.history.clear()
        self._save_history()
        self._last_h5 = None
        self._idle = 0
        self._incidents = []
        self._last_status = 0.0

    def _collect(self) -> Snapshot:
        self._apply_pending()
        self._watching = False
        try:
            creds = self.provider.credentials()
            if creds.expired:
                # Not a fault. The token lives eight hours and Claude Code
                # only renews it while running, so an overnight gap ends here
                # every time. Painting that red made the widget cry wolf about
                # its own normal condition; it waits instead, and watches the
                # file so it comes back seconds after you next use Claude Code.
                self._idle = 0
                self._watching = True
                diag.record("expired", **diag.credentials_context())
                return Snapshot(error=t("error.waiting", agent=self.provider.short),
                                waiting=True)
        except credentials.CredentialsError as exc:
            # Two dead ends wear the same exception. "Run `claude` to sign in"
            # is wrong advice for someone who has never installed it, so the
            # message is chosen here rather than where the file was missed.
            need = signin.needed(self.provider)
            message = (t("error.no_claude", agent=self.provider.label)
                       if need == signin.INSTALL else str(exc))
            self._idle = 0
            diag.record(need, **diag.credentials_context())
            return Snapshot(error=message, setup=need)

        usage = self.provider.fetch(creds)
        snap = Snapshot(usage=usage, subscription=usage.plan or creds.subscription,
                        error="" if usage.ok else usage.error)

        if usage.ok:
            moved = self._last_h5 is None or abs(usage.h5 - self._last_h5) >= 0.05
            self._idle = 0 if moved else self._idle + 1
            self._last_h5 = usage.h5

            start = tokens.window_start(usage.h5_reset)
            self.history.append((time.time(), usage.h5))
            # Samples from before this window describe a different one. Left in,
            # they made burn_rate see the percentage fall and report zero for
            # hours after every reset.
            while self.history and self.history[0][0] < start:
                self.history.popleft()
            self._save_history()

            with contextlib.suppress(OSError):
                snap.totals = self.provider.totals(start)
        else:
            self._idle = 0                   # a failure is no reason to look away
            # The one that matters: an HTTP 401 here means the server refused a
            # token the file still calls valid, which is a different fault from
            # one that simply ran out.
            diag.record("api", code=usage.code or None,
                        since_ok_min=self._since_ok(),
                        **diag.credentials_context())

        if usage.ok:
            self._last_ok = time.time()

        now = time.time()
        if now - self._last_status >= self.STATUS_EVERY:
            self._incidents = self.provider.incidents()
            self._last_status = now
        snap.incidents = list(self._incidents)
        return snap

    # ------------------------------------------------------------- history
    def _load_history(self) -> None:
        """Samples from the last run, so the projection is not blank for the
        first three minutes of every session - which, for an app that starts
        with the session, is exactly when it is wanted."""
        try:
            stored = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        cutoff = time.time() - tokens.WINDOW_SECONDS
        for item in stored[-self.HISTORY_MAX:]:
            try:
                when, pct = float(item[0]), float(item[1])
            except (TypeError, ValueError, IndexError):
                continue                     # one bad row must not lose the rest
            if when >= cutoff:
                self.history.append((when, pct))

    def _save_history(self) -> None:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            HISTORY_FILE.write_text(
                json.dumps([[round(w, 1), round(p, 2)] for w, p in self.history]),
                encoding="utf-8")
        except OSError:
            pass                             # a lost baseline must never take the app down

    def burn_rate(self) -> float:
        """Percentage points per hour on the 5h window.

        Samples survive a restart and are pruned to the current window, so this
        answers within a cycle of starting rather than after a fresh baseline.
        Returns 0 with no baseline, or if the percentage fell.
        """
        if len(self.history) < 2:
            return 0.0
        t0, p0 = self.history[0]
        t1, p1 = self.history[-1]
        dt = (t1 - t0) / 3600.0
        if dt < 0.05 or p1 < p0:      # under 3 min of baseline, or the window reset
            return 0.0
        return (p1 - p0) / dt

    def projection(self, usage: api.Usage) -> str:
        """When usage would hit 100% at the current rate: '~1h40', or '' if the
        answer would be noise: no baseline, or the window resets first."""
        rate = self.burn_rate()
        if rate <= 0.1 or usage.h5 >= 100:
            return ""
        hours = (100.0 - usage.h5) / rate
        left = (usage.h5_reset - time.time()) / 3600.0 if usage.h5_reset else 0
        if left and hours > left:
            return ""
        if hours >= 1:
            return f"~{int(hours)}h{int((hours % 1) * 60):02d}"
        return f"~{int(hours * 60)}min"

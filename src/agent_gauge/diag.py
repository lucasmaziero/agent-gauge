"""A short record of failed cycles, for the bugs that only happen at 3am.

A widget that goes red while nobody is watching leaves nothing behind: the
message is on screen until the next cycle overwrites it, and by the time anyone
looks the app has recovered and the evidence is gone. This keeps the last few
hundred failures on disk with the context that tells them apart.

What it deliberately does not write: the access token, the refresh token, or
anything derived from either. Only whether a token had expired, and by how
long - which is the question, and is answerable from a timestamp.

Successes are not logged. The file should stay empty on a healthy machine, so
its size is itself a signal.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import paths

LOG_FILE = paths.config_dir() / "errors.log"
MAX_LINES = 200          # a few weeks of an occasional blip, a day of a bad one


def _format(kind: str, fields: dict) -> str:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    parts = " ".join(f"{key}={value}" for key, value in fields.items()
                     if value is not None and value != "")
    return f"{stamp} {kind} {parts}".rstrip()


# Fields that say which failure this is, rather than how it is going. A run
# collapses only across records that agree on all of them: keyed on the kind
# alone, a rate-limited update check and an offline one folded into one line
# and the first was lost - in the file whose whole job is telling them apart.
DISCRIMINATORS = ("problem", "code", "reason", "past_expiry")


def _signature(kind: str, fields: dict) -> str:
    marks = [f"{name}={fields[name]}" for name in DISCRIMINATORS
             if fields.get(name) not in (None, "")]
    return " ".join([kind, *marks])


def _signature_of(line: str) -> str:
    parts = line.split()
    if len(parts) < 3:
        return ""
    kind = parts[2]
    found = {}
    for part in parts[3:]:
        name, _, value = part.partition("=")
        if name in DISCRIMINATORS:
            found[name] = value
    return _signature(kind, found)


def _run_of(line: str, signature: str) -> tuple[int, str] | None:
    """If `line` closes a run of this same failure, how long that run already is
    and when it started. None means a different one, which starts a new line."""
    if _signature_of(line) != signature:
        return None
    parts = line.split()
    count, since = 1, parts[1]
    for part in parts[3:]:
        if part.startswith("repeat=") and part[7:].isdigit():
            count = int(part[7:])
        elif part.startswith("since="):
            since = part[6:]
    return count, since


def record(kind: str, **fields) -> None:
    """Note one failed cycle, collapsing a run of the same kind into one line.

    An outage repeats itself. An expired token failed every two minutes for
    four hours and wrote 130 identical lines, which pushed the beginning of
    that very outage out of the file - the one part worth having. A run is now
    a single line carrying the newest values, how many times it has happened
    and when it started, which is everything those 130 said.

    Never raises: diagnostics must not be the thing that takes the app down.
    """
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        previous = (LOG_FILE.read_text(encoding="utf-8").splitlines()
                    if LOG_FILE.exists() else [])

        line = _format(kind, fields)
        run = _run_of(previous[-1], _signature(kind, fields)) if previous else None
        if run is None:
            kept = [*previous, line]
        else:
            count, since = run
            kept = [*previous[:-1], f"{line} repeat={count + 1} since={since}"]

        LOG_FILE.write_text("\n".join(kept[-MAX_LINES:]) + "\n", encoding="utf-8")
    except (OSError, ValueError):
        pass


def credentials_context() -> dict:
    """When the token expires and when Claude Code last rewrote the file.

    Both are the crux of the question this exists to answer: whether a failure
    is a token that genuinely ran out, or one the server rejected while the
    file still called it valid.
    """
    context: dict = {}
    try:
        stat = paths.credentials_file().stat()
    except OSError:
        return {"creds": "missing"}
    context["creds_age_min"] = f"{(time.time() - stat.st_mtime) / 60:.0f}"

    try:
        import json

        oauth = json.loads(
            paths.credentials_file().read_text(encoding="utf-8")).get("claudeAiOauth") or {}
        expires_at = float(oauth.get("expiresAt") or 0) / 1000.0
    except (OSError, ValueError, AttributeError):
        return context

    if expires_at:
        left = expires_at - time.time()
        context["expires_in_min"] = f"{left / 60:.0f}"
        context["past_expiry"] = "yes" if left <= 0 else "no"
    return context


def path() -> Path:
    return LOG_FILE

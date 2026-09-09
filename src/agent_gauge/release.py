"""Is there a newer build than this one?

No updater and no background check: this reads the latest tag GitHub publishes
and compares it with the version this build was cut from, and only when asked.

Apart from api.py on purpose - that module talks to Anthropic wearing Claude
Code's User-Agent, this one talks to GitHub as itself.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import NamedTuple

from . import __version__, diag, net

REPO = "lucasmaziero/agent-gauge"
LATEST_ENDPOINT = f"https://api.github.com/repos/{REPO}/releases/latest"
# The project page, not the release page: it names the file for each platform,
# where the release page is eight files and leaves the reader to sort them.
SITE_URL = "https://lucasmaziero.github.io/agent-gauge/"
DOWNLOAD_URL = f"{SITE_URL}#downloads"
SOURCE_URL = f"https://github.com/{REPO}"
USER_AGENT = f"agent-gauge/{__version__}"
TIMEOUT = 10


def parse(text: str) -> tuple[int, ...]:
    """"v1.2.0" -> (1, 2, 0).

    Anything after a dash or a plus is a pre-release or build marker and is
    dropped; anything that will not parse yields an empty tuple, which every
    comparison below treats as "do not claim anything".
    """
    core = text.strip().lstrip("vV").split("-")[0].split("+")[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except ValueError:
        return ()


def is_newer(latest: str, current: str = __version__) -> bool:
    """Whether `latest` is ahead of `current`, padding the shorter one with
    zeros so 1.2 and 1.2.0 compare equal.

    False whenever either side is unreadable. Telling a user an update exists
    when it does not is worse than staying quiet.
    """
    new, have = parse(latest), parse(current)
    if not new or not have:
        return False
    width = max(len(new), len(have))
    return new + (0,) * (width - len(new)) > have + (0,) * (width - len(have))


class Latest(NamedTuple):
    """The newest tag, or why there isn't one.

    Never "" alone: an empty tag is not "you are up to date", and the reason it
    is empty is the only thing that tells someone what to do about it.
    """

    tag: str = ""
    problem: str = ""          # "", "offline", "rate_limited", "http:<code>"

    @property
    def ok(self) -> bool:
        return bool(self.tag)


def _reason(exc: Exception) -> str:
    """One log-safe token describing why a connection failed.

    The log is space-separated key=value, so whitespace would break the line it
    is meant to explain; it is squeezed out rather than quoted.
    """
    detail = getattr(exc, "reason", None)
    text = str(detail if detail is not None else exc).strip()
    return "_".join(text.split())[:80] or type(exc).__name__


def fetch_latest() -> Latest:
    """Ask GitHub for the newest published tag.

    Each failure is named, because HTTPError subclasses URLError and a 403 for
    the rate limit used to report itself as a dead network. The sixty requests
    an hour are counted per IP, so an office can exhaust them without this
    machine making one - "your network is down" is then a wrong answer, not a
    vague one.
    """
    request = urllib.request.Request(
        LATEST_ENDPOINT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT,
                                    context=net.context()) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        exc.close()
        if exc.code in (403, 429) and remaining == "0":
            diag.record("update", problem="rate_limited")
            return Latest(problem="rate_limited")
        diag.record("update", problem=f"http:{exc.code}")
        return Latest(problem=f"http:{exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        # The reason, not the class name: "URLError" says nothing a user or a
        # maintainer can act on, while "certificate_verify_failed",
        # "getaddrinfo_failed" and "timed_out" each point somewhere different.
        diag.record("update", problem="offline", reason=_reason(exc))
        return Latest(problem="offline")
    except json.JSONDecodeError:
        diag.record("update", problem="malformed")
        return Latest(problem="malformed")

    if not isinstance(data, dict):
        return Latest(problem="malformed")
    tag = data.get("tag_name") or ""
    if not isinstance(tag, str):
        return Latest(problem="malformed")
    if not tag:
        diag.record("update", problem="untagged")
        return Latest(problem="untagged")
    return Latest(tag=tag)

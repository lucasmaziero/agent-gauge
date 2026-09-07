"""Usage lookup against the Anthropic API.

The API exposes no usage endpoint for subscription accounts: utilization rides
along in the `anthropic-ratelimit-unified-*` headers of any response. So this
sends the smallest possible request - a POST to /v1/messages with max_tokens=1 -
purely to read them.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import net
from .i18n import t

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
STATUS_ENDPOINT = "https://status.claude.com/api/v2/incidents/unresolved.json"
ANTHROPIC_VERSION = "2023-06-01"
PROBE_MODEL = "claude-haiku-4-5-20251001"
USER_AGENT = "claude-code/2.1.5"
TIMEOUT = 15
RETRIES = 1          # one more go before calling it a failure
RETRY_WAIT = 1.5

H5U = "anthropic-ratelimit-unified-5h-utilization"
H5R = "anthropic-ratelimit-unified-5h-reset"
H5S = "anthropic-ratelimit-unified-5h-status"
D7U = "anthropic-ratelimit-unified-7d-utilization"
D7R = "anthropic-ratelimit-unified-7d-reset"
D7S = "anthropic-ratelimit-unified-7d-status"
UST = "anthropic-ratelimit-unified-status"
URS = "anthropic-ratelimit-unified-reset"
URC = "anthropic-ratelimit-unified-representative-claim"
UFB = "anthropic-ratelimit-unified-fallback-percentage"
UOS = "anthropic-ratelimit-unified-overage-status"
UOR = "anthropic-ratelimit-unified-overage-disabled-reason"


@dataclass
class Usage:
    """One reading of the unified rate-limit headers."""

    h5: float = 0.0                 # 5h utilization, 0-100
    d7: float = 0.0                 # 7d utilization, 0-100
    h5_reset: int = 0               # epoch of the 5h window reset
    d7_reset: int = 0
    unified_reset: int = 0
    status_overall: str = ""        # allowed | allowed_warning | rejected
    status_5h: str = ""
    status_7d: str = ""
    claim: str = ""                 # five_hour | seven_day: which window binds
    fallback_pct: float = 0.0
    overage_status: str = ""
    overage_reason: str = ""
    fetched_at: float = field(default_factory=time.time)
    ok: bool = False
    error: str = ""                 # user-facing, translated
    code: int = 0                   # HTTP status, when there was one
    plan: str = ""                  # when the reading carries it, as Codex's does

    @property
    def worst(self) -> float:
        return max(self.h5, self.d7)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "oauth-2025-04-20",
        "content-type": "application/json",
        "User-Agent": USER_AGENT,
    }


def _num(headers, name: str, scale: float = 1.0) -> float:
    """Header as float; missing or malformed reads as 0."""
    try:
        return float(headers.get(name)) * scale
    except (TypeError, ValueError):
        return 0.0


def parse(headers, code: int) -> Usage:
    """Build a Usage out of response headers. Split from the request so the
    header contract can be tested without touching the network."""
    if headers.get(H5U) is None and headers.get(D7U) is None:
        if code == 401:
            return Usage(ok=False, code=code,
                         error=t("error.unauthorized", agent="Claude"))
        return Usage(ok=False, code=code, error=t("error.no_headers", code=code))

    return Usage(
        h5=_num(headers, H5U, 100.0),
        d7=_num(headers, D7U, 100.0),
        h5_reset=int(_num(headers, H5R)),
        d7_reset=int(_num(headers, D7R)),
        unified_reset=int(_num(headers, URS)),
        status_overall=headers.get(UST, "") or "",
        status_5h=headers.get(H5S, "") or "",
        status_7d=headers.get(D7S, "") or "",
        claim=headers.get(URC, "") or "",
        fallback_pct=_num(headers, UFB, 100.0),
        overage_status=headers.get(UOS, "") or "",
        overage_reason=headers.get(UOR, "") or "",
        ok=True,
    )


def _probe(req) -> tuple:
    """One round trip, reduced to the headers and the status code.

    An HTTP error is an answer, not a failure: 429 and friends still carry the
    rate-limit headers, which is the whole point of the request. Only the
    network-level exceptions escape, for the caller to retry.
    """
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=net.context()) as resp:
            headers, code = resp.headers, resp.status
            resp.read()
    except urllib.error.HTTPError as exc:
        headers, code = exc.headers, exc.code
        exc.read()
    return headers, code


def fetch_usage(token: str) -> Usage:
    """The probe request, retried once. Never raises: failures come back as
    ok=False.

    Without the retry a single dropped packet paints the widget red until the
    next cycle, which at the longest interval is fifteen minutes of showing a
    failure that lasted a second.
    """
    body = json.dumps(
        {
            "model": PROBE_MODEL,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "."}],
        }
    ).encode()
    req = urllib.request.Request(
        MESSAGES_ENDPOINT, data=body, headers=_headers(token), method="POST"
    )

    problem: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            return parse(*_probe(req))
        except (urllib.error.URLError, OSError) as exc:
            # HTTPError is a URLError subclass but _probe has already turned it
            # into headers, so anything caught here is the connection itself.
            problem = exc
            if attempt < RETRIES:
                time.sleep(RETRY_WAIT)

    reason = getattr(problem, "reason", problem)
    return Usage(ok=False, error=t("error.network", reason=reason))



def fetch_incidents() -> list[str]:
    """Open incident titles from status.claude.com; empty list means all clear."""
    req = urllib.request.Request(STATUS_ENDPOINT, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=net.context()) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []
    return [i.get("name", "") for i in data.get("incidents", []) if i.get("name")]

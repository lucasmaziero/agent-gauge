"""Codex, read from the endpoint the CLI itself uses.

Two things are better here than on the Claude side and one is worse.

Better: there is a usage endpoint, so a reading costs no quota at all rather
than the one output token the Claude probe spends. And the access token is
minted for ten days rather than eight hours, so the overnight gap that leaves
the Claude side waiting does not arise.

Worse, and it is the thing to keep in mind: `backend-api/wham/usage` is an
internal endpoint of the ChatGPT web backend, not a published API. It has no
contract and no deprecation policy, and the day it changes shape this provider
stops working with no warning. Every field is read defensively for that reason,
and a response that does not carry the two windows is reported as a failure
rather than guessed at.

The response also carries the account's email and ids. None of it is kept: only
the four numbers and the plan name leave this module, so nothing identifying
can reach the error log or a screenshot of the panel.
"""
from __future__ import annotations

import base64
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import net
from ..api import Usage
from ..credentials import Credentials, CredentialsError
from ..i18n import t
from ..paths import home
from .base import Provider

USAGE_ENDPOINT = "https://chatgpt.com/backend-api/wham/usage"
# Statuspage, and public. Unlike Anthropic's it publishes no unresolved-
# incidents list, so the overall indicator is what there is to read.
STATUS_ENDPOINT = "https://status.openai.com/api/v2/status.json"
TIMEOUT = 15
RETRIES = 1
RETRY_WAIT = 1.5


def _claims(token: str) -> dict:
    """The JWT payload, unverified.

    Read for one field: `exp`. Verification would need OpenAI's signing keys and
    would prove nothing useful - the server is the one that decides whether a
    token is good, and this only avoids asking when it already knows the answer.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, json.JSONDecodeError):
        return {}


def _window(block: dict) -> tuple[float, int]:
    """(percent, reset epoch) out of one of the two rate-limit windows."""
    percent = float(block["used_percent"])
    reset = block.get("reset_at")
    if reset is None and block.get("reset_after_seconds") is not None:
        reset = time.time() + float(block["reset_after_seconds"])
    reset = float(reset)
    if (isinstance(block["used_percent"], bool) or not math.isfinite(percent)
            or not 0 <= percent <= 100 or not math.isfinite(reset) or reset <= 0):
        raise ValueError("Invalid rate-limit window")
    return percent, int(reset)


def _claim(data: dict) -> str:
    """Which window is the binding one, or "" for no opinion.

    Anthropic publishes this per reply, as representative-claim. This API does
    not: the only thing close is rate_limit_reached_type, which stays null until
    a limit is actually hit, so most of the time the honest answer is silence.

    It said "seven_day" whenever the weekly percentage merely exceeded the
    five-hour one, which put "hits the ceiling first" on the panel at 3% of a
    week - a claim about the future read off two numbers that cannot support
    one. Which window binds depends on burn rate against time remaining, and
    nothing here measures the weekly rate.

    The vocabulary below is a guess, because the field is null on a healthy
    account and there was nothing to read. Anything unrecognised falls through
    to no claim, which is the same as saying nothing.
    """
    reached = str(data.get("rate_limit_reached_type") or "").lower()
    if not reached:
        return ""
    if "second" in reached or "week" in reached:
        return "seven_day"
    if "primary" in reached or "hour" in reached:
        return "five_hour"
    return ""


class Codex(Provider):
    key = "codex"
    label = "Codex"
    short = "Codex"
    help_url = "https://github.com/openai/codex"
    status_host = "status.openai.com"

    def incidents(self) -> list[str]:
        """The page's own description, and only when it is not "operational"."""
        request = urllib.request.Request(
            STATUS_ENDPOINT, headers={"User-Agent": "agent-gauge"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT,
                                        context=net.context()) as response:
                status = json.loads(
                    response.read().decode("utf-8", "replace")).get("status") or {}
        except (urllib.error.URLError, OSError, json.JSONDecodeError, AttributeError):
            return []
        if (status.get("indicator") or "none") == "none":
            return []
        description = str(status.get("description") or "").strip()
        return [description] if description else []

    def home(self) -> Path:
        return home() / ".codex"

    def auth_file(self) -> Path:
        return self.home() / "auth.json"

    # ------------------------------------------------------------ credentials
    def credentials(self) -> Credentials:
        path = self.auth_file()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise CredentialsError(
                t("error.no_credentials", agent=self.short, path=path)) from None
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialsError(t("error.unreadable", path=path, reason=exc)) from None

        token = (raw.get("tokens") or {}).get("access_token")
        if not token:
            raise CredentialsError(t("error.no_token", agent=self.short))

        return Credentials(
            token=token,
            expires_at=float(_claims(token).get("exp") or 0),
            subscription="",            # the plan comes back with the usage
            tier="",
            account=str((raw.get("tokens") or {}).get("account_id") or ""),
        )

    # ------------------------------------------------------------------ fetch
    def fetch(self, creds: Credentials) -> Usage:
        request = urllib.request.Request(
            USAGE_ENDPOINT,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "chatgpt-account-id": creds.account,
                "Accept": "application/json",
                "User-Agent": "agent-gauge",
            },
        )

        problem: Exception | None = None
        for attempt in range(RETRIES + 1):
            try:
                return self._read(request)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                return Usage(ok=False, error=t("error.no_windows"))
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                if code == 401:
                    return Usage(ok=False, code=code,
                                 error=t("error.unauthorized", agent=self.short))
                return Usage(ok=False, code=code, error=t("error.no_headers", code=code))
            except (urllib.error.URLError, OSError) as exc:
                problem = exc
                if attempt < RETRIES:
                    time.sleep(RETRY_WAIT)

        reason = getattr(problem, "reason", problem)
        return Usage(ok=False, error=t("error.network", reason=reason))

    def _read(self, request) -> Usage:
        with urllib.request.urlopen(request, timeout=TIMEOUT,
                                    context=net.context()) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))

        limits = data.get("rate_limit") or {}
        primary, secondary = limits.get("primary_window"), limits.get("secondary_window")
        if not isinstance(primary, dict) or not isinstance(secondary, dict):
            # The shape changed, or this account has no windows. Either way the
            # honest answer is that the reading failed.
            return Usage(ok=False, error=t("error.no_windows"))

        h5, h5_reset = _window(primary)
        d7, d7_reset = _window(secondary)
        blocked = bool(limits.get("limit_reached")) or not limits.get("allowed", True)

        return Usage(
            h5=h5, d7=d7,
            h5_reset=h5_reset, d7_reset=d7_reset,
            status_overall="rejected" if blocked else "allowed",
            claim=_claim(data),
            plan=str(data.get("plan_type") or ""),
            code=200,
            ok=True,
        )

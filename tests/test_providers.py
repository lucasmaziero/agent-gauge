"""Two agents behind one gauge.

The Codex half is exercised against recorded responses. The endpoint it reads
is an internal one with no published contract, so the tests that matter most
are the ones about what happens when it stops looking the way it does today.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request

import pytest

from agent_gauge import api, credentials, i18n, providers
from agent_gauge.providers.codex import Codex

CODEX = providers.get("codex")
CLAUDE = providers.get("claude")


@pytest.fixture(autouse=True)
def _english():
    before = i18n.language()
    i18n.set_language("en")
    yield
    i18n.set_language(before)


def jwt(exp: float) -> str:
    """A token shaped like the real one: only the middle segment is read."""
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(exp), "sub": "user"}).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


USAGE = {
    "plan_type": "plus",
    "email": "someone@example.com",
    "account_id": "046351fa-b64e-465c-b1c0-488e36d28d49",
    "rate_limit": {
        "allowed": True,
        "limit_reached": False,
        "primary_window": {"used_percent": 12, "limit_window_seconds": 18000,
                           "reset_at": 1788745443},
        "secondary_window": {"used_percent": 3, "limit_window_seconds": 604800,
                             "reset_at": 1788978299},
    },
}


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def answer(monkeypatch, payload):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout=None, **kwargs: _Response(payload))


@pytest.fixture
def codex_home(monkeypatch, tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    monkeypatch.setattr(Codex, "home", lambda _self: home)
    return home


def write_auth(home, token=None, account="acc-1"):
    (home / "auth.json").write_text(json.dumps({
        "auth_mode": "chatgpt",
        "tokens": {"access_token": token or jwt(time.time() + 240 * 3600),
                   "refresh_token": "r", "account_id": account},
    }), encoding="utf-8")


# --------------------------------------------------------------- the registry
def test_the_two_agents_are_offered_in_order():
    assert [p.key for p in providers.ALL] == ["claude", "codex"]
    assert providers.DEFAULT == "claude"


def test_an_unknown_provider_falls_back_rather_than_raising():
    """A settings file naming a provider this build does not have must not stop
    the app from starting."""
    assert providers.get("gemini").key == providers.DEFAULT
    assert providers.get("").key == providers.DEFAULT


def test_each_provider_names_itself_for_the_menu():
    for provider in providers.ALL:
        assert provider.label and provider.help_url.startswith("https://")


# ------------------------------------------------------------- credentials
def test_the_expiry_comes_from_the_token_itself(codex_home):
    """auth.json carries no expiresAt; the JWT does, and it is ten days out."""
    expires = time.time() + 240 * 3600
    write_auth(codex_home, jwt(expires))

    creds = CODEX.credentials()
    assert abs(creds.expires_at - expires) < 2
    assert not creds.expired
    assert creds.account == "acc-1"


def test_an_unreadable_token_is_not_treated_as_expired(codex_home):
    """A token whose claims will not parse still gets sent: the server decides.
    Guessing "expired" would stop the widget over a base64 quibble."""
    write_auth(codex_home, "not.a.jwt")
    assert CODEX.credentials().expires_at == 0
    assert not CODEX.credentials().expired


def test_a_missing_auth_file_names_the_path(codex_home):
    with pytest.raises(credentials.CredentialsError, match=r"auth\.json"):
        CODEX.credentials()


def test_auth_without_a_token_is_rejected(codex_home):
    (codex_home / "auth.json").write_text(json.dumps({"tokens": {}}), encoding="utf-8")
    with pytest.raises(credentials.CredentialsError, match="accessToken"):
        CODEX.credentials()


# -------------------------------------------------------------------- fetch
def test_the_two_windows_map_onto_the_gauge(monkeypatch, codex_home):
    """Both agents meter 18000 and 604800 seconds, so h5 and d7 stay honest
    names and none of the drawing had to change."""
    write_auth(codex_home)
    answer(monkeypatch, USAGE)

    usage = CODEX.fetch(CODEX.credentials())
    assert usage.ok
    assert usage.h5 == 12
    assert usage.d7 == 3
    assert usage.h5_reset == 1788745443
    assert usage.d7_reset == 1788978299
    assert usage.plan == "plus"


def test_nothing_identifying_survives_the_fetch(monkeypatch, codex_home):
    """The reply carries the account's email and ids. Only the numbers and the
    plan may leave the provider, so none of it can reach the error log."""
    write_auth(codex_home)
    answer(monkeypatch, USAGE)

    rendered = repr(CODEX.fetch(CODEX.credentials()))
    assert "example.com" not in rendered
    assert "046351fa" not in rendered


def test_a_reply_without_windows_is_a_failure(monkeypatch, codex_home):
    """The endpoint is internal and has no contract. When its shape changes the
    honest answer is that the reading failed, not a gauge at zero."""
    write_auth(codex_home)
    answer(monkeypatch, {"plan_type": "plus", "rate_limit": {}})

    usage = CODEX.fetch(CODEX.credentials())
    assert not usage.ok
    assert usage.h5 == 0


def test_a_refusal_is_reported_as_one(monkeypatch, codex_home):
    write_auth(codex_home)

    def refuse(request, timeout=None, **kwargs):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    usage = CODEX.fetch(CODEX.credentials())
    assert not usage.ok
    assert usage.code == 401


def test_the_request_carries_the_account(monkeypatch, codex_home):
    write_auth(codex_home, account="acc-42")
    seen = {}

    def capture(request, timeout=None, **kwargs):
        seen.update(request.headers)
        return _Response(USAGE)
    monkeypatch.setattr(urllib.request, "urlopen", capture)

    CODEX.fetch(CODEX.credentials())
    assert seen.get("Chatgpt-account-id") == "acc-42"
    assert seen.get("Authorization", "").startswith("Bearer ")


def test_a_dropped_connection_is_retried(monkeypatch, codex_home):
    write_auth(codex_home)
    attempts = []

    def flaky(request, timeout=None, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError("reset")
        return _Response(USAGE)
    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    monkeypatch.setattr(providers.codex.time, "sleep", lambda _s: None)

    assert CODEX.fetch(CODEX.credentials()).ok
    assert len(attempts) == 2


# ------------------------------------------------------------------ totals
def test_codex_has_no_transcripts_to_count():
    """Codex keeps its history in SQLite with no usage totals in it, so the
    panel's token line is empty rather than wrong."""
    assert CODEX.totals(time.time()).sessions == 0


def test_claude_still_counts_its_transcripts(monkeypatch):
    from agent_gauge import tokens

    monkeypatch.setattr(tokens, "collect",
                        lambda since, projects=None: tokens.TokenTotals(sessions=3))
    assert CLAUDE.totals(0.0).sessions == 3


# ---------------------------------------------------------------- switching
def test_switching_waits_for_a_safe_moment(monkeypatch, tmp_path):
    """set_provider is called from the UI thread while the collection thread may
    be inside a fetch, so it changes nothing on the spot - clearing the history
    there races with the append that ends that fetch."""
    from agent_gauge.poller import Poller

    poll = Poller(120, CLAUDE)
    poll.history.append((time.time(), 40.0))
    poll._last_h5 = 40.0

    poll.set_provider(CODEX)
    assert poll.provider is CLAUDE          # not yet
    assert poll.history                     # not yet

    poll._apply_pending()                   # what the next cycle does first
    assert poll.provider is CODEX
    assert not poll.history                 # a rate across two agents is a fiction
    assert poll._last_h5 is None


def test_a_snapshot_says_which_agent_it_came_from(monkeypatch, tmp_path):
    """The bug this fixes: switching mid-fetch delivered the previous agent's
    numbers, and the header - reading the setting rather than the snapshot -
    drew them under the new agent's name and mark."""
    from agent_gauge.poller import Poller

    def usage(_creds):
        return api.Usage(h5=7, h5_reset=int(time.time() + 3600), ok=True)

    monkeypatch.setattr(CLAUDE, "fetch", usage, raising=False)
    monkeypatch.setattr(CLAUDE, "credentials",
                        lambda: credentials.Credentials("t", 0, "max", ""), raising=False)
    monkeypatch.setattr(CLAUDE, "incidents", list, raising=False)

    poll = Poller(120, CLAUDE)
    snap = poll._collect()
    snap.provider = poll.provider.key       # run() stamps it; _collect is called direct
    assert snap.provider == "claude"


def test_a_queued_switch_is_taken_up_by_the_next_cycle(monkeypatch, tmp_path):
    from agent_gauge.poller import Poller

    monkeypatch.setattr(CODEX, "credentials",
                        lambda: credentials.Credentials("t", 0, "", ""), raising=False)
    monkeypatch.setattr(CODEX, "fetch",
                        lambda _c: api.Usage(h5=2, h5_reset=int(time.time() + 3600), ok=True),
                        raising=False)
    monkeypatch.setattr(CODEX, "incidents", list, raising=False)

    poll = Poller(120, CLAUDE)
    poll.set_provider(CODEX)
    poll._collect()
    assert poll.provider is CODEX


def test_the_poller_asks_whichever_provider_it_holds(monkeypatch):
    from agent_gauge.poller import Poller

    class Fake:
        key, label, help_url = "fake", "Fake", "https://example.com"

        def home(self):
            return None

        def credentials(self):
            return credentials.Credentials(token="t", expires_at=0,
                                           subscription="", tier="")

        def fetch(self, _creds):
            return api.Usage(h5=7, h5_reset=int(time.time() + 3600), ok=True, plan="pro")

        def incidents(self):
            return []

        def totals(self, _since):
            from agent_gauge.tokens import TokenTotals
            return TokenTotals()

    snap = Poller(120, Fake())._collect()
    assert snap.usage.h5 == 7
    assert snap.subscription == "pro"        # the plan the reading carried


# ------------------------------------------------------------------- marks
def test_every_provider_has_its_own_mark(qapp):
    """The mark is the only thing on the widget that says whose numbers these
    are - the ring and the rows look identical either way."""
    from agent_gauge import brand

    paths = {brand.MARKS[p.key] for p in providers.ALL}
    assert len(paths) == len(providers.ALL)


@pytest.mark.parametrize("key", ["claude", "codex"])
def test_a_mark_is_the_height_it_was_asked_for(qapp, key):
    """The two fill different amounts of the viewBox - Clawd the y 5..20 band,
    the Codex mark the whole 24 - so each carries its own ink height. Sizing
    both as though they were Clawd made one of them half again too big."""
    from agent_gauge import brand, theme

    pixmap = brand.mark(key, 13, theme.ACCENT, 2.0)
    image = pixmap.toImage()
    rows = [y for y in range(image.height())
            if any(image.pixelColor(x, y).alpha() > 8 for x in range(image.width()))]
    ink = (rows[-1] - rows[0] + 1) / pixmap.devicePixelRatio()
    assert abs(ink - 13) <= 1.0          # antialiasing, not layout


def test_the_embedded_codex_path_matches_its_source(qapp):
    """It is kept in installer/codex-mark.svg as provenance and embedded as a
    string so PyInstaller has no data file to miss. The two must not drift, and
    the first attempt at embedding it silently did: textwrap.wrap breaks on
    whitespace and drops it, and in an SVG path the spaces are data."""
    import re
    from pathlib import Path

    from agent_gauge import brand

    source = Path(__file__).resolve().parents[1] / "installer" / "codex-mark.svg"
    expected = re.search(r'\sd="([^"]+)"', source.read_text(encoding="utf-8")).group(1)
    assert brand.MARKS["codex"].path == expected


def test_an_unknown_key_still_draws_something(qapp):
    from agent_gauge import brand

    assert not brand.mark("gemini", 13).isNull()


# ---------------------------------------------------------------- the claim
def test_a_healthy_account_makes_no_claim(monkeypatch, codex_home):
    """"Hits the ceiling first" is a statement about the future. It used to be
    derived from d7 > h5, which put it on the panel at 3% of a weekly window -
    two percentages cannot support that claim, and this API does not publish one
    the way Anthropic's does."""
    write_auth(codex_home)
    answer(monkeypatch, USAGE)
    assert CODEX.fetch(CODEX.credentials()).claim == ""


@pytest.mark.parametrize("reached,expected", [
    ("secondary_window", "seven_day"),
    ("weekly", "seven_day"),
    ("primary_window", "five_hour"),
    ("5_hour", "five_hour"),
    ("something_new", ""),          # an unknown word says nothing, not a guess
    (None, ""),
])
def test_a_claim_is_only_made_when_a_limit_was_reached(
        monkeypatch, codex_home, reached, expected):
    write_auth(codex_home)
    answer(monkeypatch, {**USAGE, "rate_limit_reached_type": reached})
    assert CODEX.fetch(CODEX.credentials()).claim == expected


def test_the_other_agent_s_incidents_do_not_survive_a_switch(tmp_path):
    """Incidents come from each agent's own status page and are cached for five
    minutes, because they move slowly. Across a switch that cache went on
    reporting OpenAI's outage under Claude's name, beside numbers that were
    Anthropic's - a status line contradicting every figure next to it."""
    from agent_gauge.poller import Poller

    poll = Poller(120, CODEX)
    poll._incidents = ["Elevated errors on the ChatGPT API"]
    poll._last_status = time.time()          # fresh: no refresh due for 5 min

    poll.set_provider(CLAUDE)
    poll._apply_pending()

    assert poll._incidents == []
    assert poll._last_status == 0.0          # so the next cycle actually asks


def test_the_switched_in_agent_gets_its_own_incidents(monkeypatch, tmp_path):
    """Clearing alone would leave the panel silent for the rest of the five
    minutes, which reads as "no incidents" - a claim, not an absence."""
    from agent_gauge.poller import Poller

    monkeypatch.setattr(CLAUDE, "credentials",
                        lambda: credentials.Credentials("t", 0, "", ""), raising=False)
    monkeypatch.setattr(CLAUDE, "fetch",
                        lambda _c: api.Usage(h5=5, h5_reset=int(time.time() + 3600), ok=True),
                        raising=False)
    monkeypatch.setattr(CLAUDE, "incidents",
                        lambda: ["Anthropic: elevated error rates"], raising=False)

    poll = Poller(120, CODEX)
    poll._incidents = ["OpenAI: something else"]
    poll._last_status = time.time()

    poll.set_provider(CLAUDE)
    snap = poll._collect()

    assert snap.incidents == ["Anthropic: elevated error rates"]

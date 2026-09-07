"""The failure log: what it records, and what it must never record."""
from __future__ import annotations

import json
import time

import pytest

from agent_gauge import api, credentials, diag, paths, poller
from agent_gauge.poller import Poller

SECRET = "sk-ant-oat-do-not-log-me"


@pytest.fixture(autouse=True)
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(diag, "LOG_FILE", tmp_path / "errors.log")
    monkeypatch.setattr(poller, "HISTORY_FILE", tmp_path / "history.json")
    creds = tmp_path / ".credentials.json"
    creds.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": SECRET,
        "refreshToken": SECRET + "-refresh",
        "expiresAt": int((time.time() + 8 * 3600) * 1000),
    }}), encoding="utf-8")
    monkeypatch.setattr(paths, "credentials_file", lambda: creds)
    return tmp_path


def lines():
    return diag.LOG_FILE.read_text(encoding="utf-8").splitlines()


def _refused(monkeypatch, code=401):
    monkeypatch.setattr(credentials, "load", lambda *a, **k: credentials.Credentials(
        token=SECRET, expires_at=time.time() + 8 * 3600, subscription="max", tier="x"))
    monkeypatch.setattr(api, "fetch_usage",
                        lambda _t: api.Usage(ok=False, code=code, error="refused"))
    monkeypatch.setattr(api, "fetch_incidents", list)


def test_a_refusal_is_recorded_with_its_status_code(monkeypatch):
    """The line that tells the two faults apart: a 401 while the file still
    calls the token valid is not the same as a token that ran out."""
    _refused(monkeypatch)
    Poller(120)._collect()

    assert len(lines()) == 1
    assert "api" in lines()[0]
    assert "code=401" in lines()[0]
    assert "past_expiry=no" in lines()[0]


def test_no_token_ever_reaches_the_file(monkeypatch):
    """The whole file is read back and searched, not just the line we wrote."""
    _refused(monkeypatch)
    Poller(120)._collect()
    written = diag.LOG_FILE.read_text(encoding="utf-8")
    assert SECRET not in written
    assert "accessToken" not in written
    assert "refreshToken" not in written


def test_success_writes_nothing(monkeypatch):
    monkeypatch.setattr(credentials, "load", lambda *a, **k: credentials.Credentials(
        token=SECRET, expires_at=time.time() + 3600, subscription="max", tier="x"))
    monkeypatch.setattr(api, "fetch_usage",
                        lambda _t: api.Usage(h5=10, h5_reset=int(time.time() + 3600), ok=True))
    monkeypatch.setattr(api, "fetch_incidents", list)
    Poller(120)._collect()
    assert not diag.LOG_FILE.exists()


def test_an_expired_token_is_recorded_as_expired(monkeypatch):
    monkeypatch.setattr(credentials, "load", lambda *a, **k: credentials.Credentials(
        token=SECRET, expires_at=time.time() - 60, subscription="max", tier="x"))
    Poller(120)._collect()
    assert lines()[0].split()[2] == "expired"


def test_the_log_is_bounded(monkeypatch):
    """Alternating kinds, because the same kind in a row is now one line."""
    monkeypatch.setattr(diag, "MAX_LINES", 5)
    for n in range(12):
        diag.record("api" if n % 2 else "network", n=n)
    kept = lines()
    assert len(kept) == 5
    assert "n=11" in kept[-1]          # the newest survives
    assert "n=7" in kept[0]            # the seven before it are gone


def test_a_run_of_the_same_failure_is_one_line():
    """An expired token failed every two minutes for four hours and wrote 130
    identical lines, which pushed the start of that outage out of the file."""
    for n in range(130):
        diag.record("expired", expires_in_min=-(2 + 2 * n))

    assert len(lines()) == 1
    only = lines()[0]
    assert "repeat=130" in only
    assert "since=" in only
    assert "expires_in_min=-260" in only        # the newest values, not the first


def test_a_different_failure_starts_a_new_line():
    diag.record("expired", past_expiry="yes")
    diag.record("api", code=401)
    diag.record("expired", past_expiry="yes")
    assert len(lines()) == 3
    assert "repeat" not in "".join(lines())


def test_a_run_keeps_the_time_it_started():
    diag.record("network", reason="timeout")
    first = lines()[0].split()[1]
    diag.record("network", reason="timeout")
    assert f"since={first}" in lines()[0]


def test_a_missing_credentials_file_is_still_recorded(monkeypatch, sandbox):
    monkeypatch.setattr(paths, "credentials_file", lambda: sandbox / "gone.json")
    assert diag.credentials_context() == {"creds": "missing"}


def test_an_unwritable_log_never_takes_the_app_down(monkeypatch, sandbox):
    monkeypatch.setattr(diag, "LOG_FILE", sandbox / "nope" / "errors.log")
    monkeypatch.setattr(diag.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError("read-only")))
    diag.record("api", code=500)       # must not raise


def test_different_failures_of_one_kind_stay_apart():
    """Keyed on the kind alone, a rate-limited update check and an offline one
    folded into a single line and the first was lost - in the file whose whole
    job is telling causes apart."""
    for _ in range(3):
        diag.record("update", problem="rate_limited")
    for _ in range(2):
        diag.record("update", problem="offline")

    kept = lines()
    assert len(kept) == 2
    assert "problem=rate_limited repeat=3" in kept[0]
    assert "problem=offline repeat=2" in kept[1]


def test_the_same_failure_still_collapses():
    for _ in range(5):
        diag.record("api", code=500)
    assert len(lines()) == 1
    assert "repeat=5" in lines()[0]


def test_two_status_codes_are_two_failures():
    diag.record("api", code=401)
    diag.record("api", code=500)
    assert len(lines()) == 2

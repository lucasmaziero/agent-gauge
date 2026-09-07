"""Version comparison, and the one request that feeds it.

The comparison is the part worth guarding: getting it wrong either hides a real
update or, worse, tells everyone an update exists that does not.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from agent_gauge import release


@pytest.mark.parametrize("text,expected", [
    ("v1.2.0", (1, 2, 0)),
    ("1.2.0", (1, 2, 0)),
    ("V1.2.0", (1, 2, 0)),
    ("  v1.2.0  ", (1, 2, 0)),
    ("1.2", (1, 2)),
    ("v2.0.0-rc1", (2, 0, 0)),        # a pre-release marker is not part of the number
    ("v2.0.0+build7", (2, 0, 0)),
    ("", ()),
    ("latest", ()),
    ("v1.2.x", ()),
])
def test_parse(text, expected):
    assert release.parse(text) == expected


@pytest.mark.parametrize("latest,current", [
    ("v1.2.0", "1.1.0"),
    ("v1.1.1", "1.1.0"),
    ("v2.0.0", "1.9.9"),
    ("v1.10.0", "1.9.0"),            # ten is after nine; a string compare says otherwise
    ("v1.2", "1.1.9"),
])
def test_newer_is_recognised(latest, current):
    assert release.is_newer(latest, current)


@pytest.mark.parametrize("latest,current", [
    ("v1.1.0", "1.1.0"),
    ("v1.1", "1.1.0"),               # padded with zeros, so these are the same version
    ("v1.0.9", "1.1.0"),
    ("v1.1.0", "1.2.0"),
    ("v2.0.0-rc1", "2.0.0"),         # a candidate for what you already have is not an update
])
def test_not_newer(latest, current):
    assert not release.is_newer(latest, current)


@pytest.mark.parametrize("latest,current", [
    ("", "1.1.0"),
    ("nightly", "1.1.0"),
    ("v1.2.0", ""),
    ("v1.2.0", "unreleased"),
])
def test_unreadable_versions_never_claim_an_update(latest, current):
    """Silence beats announcing a release that may not exist."""
    assert not release.is_newer(latest, current)


# --------------------------------------------------------------- the request
class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _answer(monkeypatch, payload: bytes):
    def fake(request, timeout=None, **kwargs):
        assert request.full_url == release.LATEST_ENDPOINT
        # As itself, not as Claude Code: this call is to GitHub.
        assert request.get_header("User-agent").startswith("agent-gauge/")
        return _Response(payload)
    monkeypatch.setattr(urllib.request, "urlopen", fake)


def test_reads_the_tag(monkeypatch):
    _answer(monkeypatch, json.dumps({"tag_name": "v1.4.0"}).encode())
    latest = release.fetch_latest()
    assert latest.ok
    assert latest.tag == "v1.4.0"
    assert latest.problem == ""


def test_a_release_without_a_tag_says_so(monkeypatch):
    _answer(monkeypatch, json.dumps({"name": "untagged"}).encode())
    assert release.fetch_latest().problem == "untagged"


def test_malformed_json_says_so(monkeypatch):
    _answer(monkeypatch, b"<html>rate limited</html>")
    assert release.fetch_latest().problem == "malformed"


def test_a_network_failure_is_a_problem_not_an_exception(monkeypatch):
    def boom(request, timeout=None, **kwargs):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    latest = release.fetch_latest()
    assert not latest.ok
    assert latest.problem == "offline"


def _http_error(monkeypatch, code, headers=None):
    def refuse(request, timeout=None, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url, code, "no", headers or {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def test_the_rate_limit_is_not_reported_as_a_dead_network(monkeypatch):
    """Sixty requests an hour is per IP, so an office or anything behind CGNAT
    can exhaust it without this machine having made one. Saying "could not reach
    GitHub" sent a real person looking at their network."""
    _http_error(monkeypatch, 403, {"X-RateLimit-Remaining": "0"})
    assert release.fetch_latest().problem == "rate_limited"


def test_a_forbidden_that_is_not_the_rate_limit_keeps_its_code(monkeypatch):
    _http_error(monkeypatch, 403, {"X-RateLimit-Remaining": "42"})
    assert release.fetch_latest().problem == "http:403"


def test_a_missing_repository_keeps_its_code(monkeypatch):
    """What a rename would look like if the constant were left behind."""
    _http_error(monkeypatch, 404)
    assert release.fetch_latest().problem == "http:404"


def test_the_repo_constants_agree():
    assert release.REPO in release.LATEST_ENDPOINT


def test_the_download_link_goes_to_the_project_page():
    """Not the release page: that is eight files with no indication of which
    two are yours, and the project page has a card per platform."""
    assert release.DOWNLOAD_URL.startswith("https://")
    assert release.DOWNLOAD_URL.endswith("#downloads")

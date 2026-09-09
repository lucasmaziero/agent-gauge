"""Failures at the network, persistence and Qt lifecycle boundaries."""
from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSystemTrayIcon, QWidget
from shiboken6 import isValid

from agent_gauge import api, i18n, poller, release, storage
from agent_gauge.about import About
from agent_gauge.app import App
from agent_gauge.credentials import Credentials
from agent_gauge.poller import Poller
from agent_gauge.providers.codex import Codex
from agent_gauge.settings import DEFAULTS, Settings


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


@pytest.mark.parametrize("body", [
    b"<html>unavailable</html>", b"[]", b"null",
    b'{"rate_limit": [1]}',
    b'{"rate_limit": {"primary_window": {}, "secondary_window": {}}}',
])
def test_invalid_usage_is_a_recoverable_failure(monkeypatch, body):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(body))
    assert not Codex().fetch(Credentials("fake", 0, "", "")).ok


@pytest.mark.parametrize("field,value", [
    ("used_percent", None), ("used_percent", "bad"), ("used_percent", True),
    ("used_percent", float("nan")), ("used_percent", float("inf")),
    ("used_percent", -1), ("used_percent", 101),
    ("reset_at", None), ("reset_at", "bad"), ("reset_at", float("inf")),
])
def test_invalid_window_numbers_are_not_displayed(monkeypatch, field, value):
    window = {"used_percent": 0, "reset_at": int(time.time()) + 3600}
    body = json.dumps({"rate_limit": {
        "primary_window": {**window, field: value}, "secondary_window": window,
    }}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(body))
    assert not Codex().fetch(Credentials("fake", 0, "", "")).ok


def test_real_zero_and_relative_reset_are_valid(monkeypatch):
    window = {"used_percent": 0, "reset_after_seconds": 3600}
    body = json.dumps({"rate_limit": {
        "primary_window": window, "secondary_window": window,
    }}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(body))
    usage = Codex().fetch(Credentials("fake", 0, "", ""))
    assert usage.ok and usage.h5 == 0
    assert usage.h5_reset > time.time()


@pytest.mark.parametrize("stored", [None, [], 4, "text", {"poll_sec": None},
                                         {"poll_sec": "bad"}, {"opacity": float("nan")},
                                         {"locked": "false"}, {"pos_x": []}])
def test_bad_preferences_fall_back_to_defaults(tmp_path, stored):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(stored), encoding="utf-8")
    assert Settings(path) == DEFAULTS


@pytest.mark.parametrize("stored", [None, {}, 42, "text"])
def test_invalid_history_root_is_ignored(stored):
    poller.HISTORY_FILE.write_text(json.dumps(stored), encoding="utf-8")
    assert not Poller(120).history


def test_bad_history_rows_do_not_discard_good_samples():
    now = time.time()
    rows = [{}, [now, float("nan")], [now, float("inf")], [now + 100, 50],
            [now - 60, 20], [now - 120, 10], [now, -1]]
    poller.HISTORY_FILE.write_text(json.dumps(rows), encoding="utf-8")
    assert list(Poller(120).history) == [(now - 120, 10), (now - 60, 20)]


def test_failed_atomic_replace_preserves_previous_data(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(storage.os, "replace", Mock(side_effect=PermissionError))
    with pytest.raises(PermissionError):
        storage.atomic_write(path, "replacement")
    assert path.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_watcher_tracks_selected_provider(monkeypatch, tmp_path):
    path = tmp_path / "codex-auth.json"
    path.write_text("{}", encoding="utf-8")
    provider = Codex()
    monkeypatch.setattr(provider, "auth_file", lambda: path)
    assert Poller(120, provider)._creds_mtime() == path.stat().st_mtime_ns


def test_collection_thread_recovers_after_an_unexpected_failure(monkeypatch, qapp):
    worker = Poller(30)
    calls, snapshots, busy = [], [], []

    def collect():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("private response must not appear in logs")
        worker.stop()
        return poller.Snapshot(usage=api.Usage(ok=True))

    monkeypatch.setattr(worker, "_collect", collect)
    monkeypatch.setattr(worker, "_sleep", lambda seconds: None)
    worker.updated.connect(snapshots.append, Qt.ConnectionType.DirectConnection)
    worker.busy.connect(busy.append, Qt.ConnectionType.DirectConnection)
    worker.start()
    assert worker.wait(3000)
    assert len(snapshots) == 2
    assert not snapshots[0].ok and snapshots[1].ok
    assert busy == [True, False, True, False]
    from agent_gauge import diag
    assert "private response" not in diag.LOG_FILE.read_text(encoding="utf-8")


def test_retired_about_survives_until_check_finishes(monkeypatch, tmp_path, qapp):
    entered, finish = threading.Event(), threading.Event()

    def check():
        entered.set()
        finish.wait(10)
        return release.Latest(tag="v2.0.7")

    monkeypatch.setattr(release, "fetch_latest", check)
    card = About()
    state = SimpleNamespace(about=card, _retired_about=[],
                            settings=Settings(tmp_path / "settings.json"),
                            _build_menu=Mock(), tray=Mock(), menu=Mock(), snap=None,
                            widget=Mock(), panel=Mock())
    card.check()
    try:
        assert entered.wait(2)
        App._set_language(state, i18n.language())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert isValid(card) and card._check.isRunning()
        assert state.about is None and state._retired_about == [card]
    finally:
        finish.set()
        card.wait_for_check()
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(card)
    assert state._retired_about == []


def test_shutdown_waits_for_inflight_collection(monkeypatch, qapp):
    entered, finish = threading.Event(), threading.Event()
    worker = Poller(30)

    def collect():
        entered.set()
        finish.wait(10)
        return poller.Snapshot()

    monkeypatch.setattr(worker, "_collect", collect)
    state = SimpleNamespace(poller=worker, about=None, _retired_about=[], tray=Mock())
    worker.start()
    timer = threading.Timer(3.2, finish.set)
    timer.start()
    try:
        assert entered.wait(2)
        App._shutdown(state)
        assert not worker.isRunning()
    finally:
        finish.set()
        worker.stop()
        worker.wait()
        timer.cancel()


@pytest.mark.parametrize("tray_available", [False, True])
def test_widget_can_only_be_hidden_with_a_tray(monkeypatch, tmp_path, qapp, tray_available):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: tray_available)
    widget = QWidget()
    action = QAction(checkable=True)
    state = SimpleNamespace(settings=Settings(tmp_path / "settings.json"),
                            widget=widget, act_visible=action)
    try:
        App._toggle_widget(state, False)
        assert widget.isVisible() == (not tray_available)
        assert state.settings["widget_visible"] == (not tray_available)
    finally:
        widget.close()

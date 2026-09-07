"""Whose certificates the app trusts.

One machine reported "unable to get local issuer certificate" from the update
check while its browser opened the same URL and the gauge itself read Anthropic
fine. Windows keeps a small set of roots on disk and fetches the rest on demand
through CryptoAPI; OpenSSL, which is what Python verifies with, only sees what
is already cached. Handing verification to the OS is what closes that gap.
"""
from __future__ import annotations

import ssl

from agent_gauge import net


def test_a_context_is_returned():
    assert isinstance(net.context(), ssl.SSLContext)


def test_it_is_built_once():
    """Every request shares it: building one per call would re-read the store
    on a timer, for no gain."""
    assert net.context() is net.context()


def test_it_verifies():
    """Whatever it ends up being, it must not be the one that trusts anything."""
    context = net.context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_it_falls_back_when_the_os_layer_is_unavailable(monkeypatch):
    """A build that did not bundle truststore, or a platform where it raises,
    still gets a working context - refusing to connect would be worse than
    verifying the older way."""
    import builtins

    real_import = builtins.__import__

    def no_truststore(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("not bundled")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_truststore)
    monkeypatch.setattr(net, "_context", None)

    fallback = net._build()
    assert isinstance(fallback, ssl.SSLContext)
    assert fallback.verify_mode == ssl.CERT_REQUIRED


def test_the_fallback_leaves_a_line_behind(monkeypatch):
    """Silence here is what let the original bug hide. If the OS layer is not
    in play, the log has to say so - otherwise the next report of "unable to
    get local issuer certificate" is unanswerable all over again."""
    import builtins

    from agent_gauge import diag

    real_import = builtins.__import__

    def no_truststore(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("not bundled")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_truststore)
    monkeypatch.setattr(net, "_context", None)
    net._build()

    assert "tls" in diag.LOG_FILE.read_text(encoding="utf-8")
    assert "problem=fallback" in diag.LOG_FILE.read_text(encoding="utf-8")


def test_a_healthy_machine_writes_nothing(monkeypatch):
    """Successes stay unlogged: diag's whole premise is that an empty file
    means nothing went wrong."""
    from agent_gauge import diag

    monkeypatch.setattr(net, "_context", None)
    net._build()

    written = diag.LOG_FILE.read_text(encoding="utf-8") if diag.LOG_FILE.exists() else ""
    assert "tls" not in written

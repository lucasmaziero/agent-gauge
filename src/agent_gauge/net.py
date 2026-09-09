"""One place that decides whose certificates to trust.

Windows ships a small set of root certificates and fetches the rest on demand
through CryptoAPI. OpenSSL, which is what Python verifies with, sees only what
is already cached - so an ordinary host fails with "unable to get local issuer
certificate" on one machine and works on the next. truststore hands the
question to the OS instead, matching what everything else on that machine
believes, a corporate proxy's own CA included.

Every HTTPS call goes through here. Before, one of five passed a context and
four did not, which is why the difference stayed invisible for so long.
"""
from __future__ import annotations

import ssl

_context: ssl.SSLContext | None = None


def context() -> ssl.SSLContext:
    """The TLS context every request in this app should use, built once."""
    global _context
    if _context is None:
        _context = _build()
    return _context


def _build() -> ssl.SSLContext:
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception as exc:
        # A working connection beats the better verifier, so this falls back
        # rather than refuse to run - but never silently: without the record,
        # the next "unable to get local issuer certificate" gives no way to
        # tell whether the fix was even in play.
        from . import diag

        diag.record("tls", problem="fallback", reason=type(exc).__name__)
        return ssl.create_default_context()

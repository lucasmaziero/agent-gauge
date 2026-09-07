"""One place that decides whose certificates to trust.

Every HTTPS call in the app comes through here, which is the point: before
this, one of the five passed an SSL context and the other four did not, and the
difference was invisible until a machine turned up where it mattered.

What it fixes. Windows does not keep every root certificate on disk; it ships a
small set and fetches the rest on demand, through CryptoAPI, the first time a
chain needs one. Browsers get that for free. OpenSSL - which is what Python
verifies with - only sees what happens to be cached already, so a perfectly
ordinary site fails with "unable to get local issuer certificate" on one
machine and works on the next. That is exactly what was reported: the gauge
read Anthropic fine, the browser opened api.github.com fine, and the update
check inside the same app could not.

truststore hands verification to the operating system - CryptoAPI on Windows,
Security on macOS - so the answer matches what everything else on that machine
believes, including a corporate proxy's own CA. Where it is unavailable the
plain OpenSSL context still works for the common case, which is better than
refusing to run.
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
        # ImportError on a build that did not bundle it, and anything else the
        # platform layer raises: truststore reaches CryptoAPI through ctypes,
        # which is exactly the sort of thing freezing can break. A working
        # connection matters more than using the better verifier, so we fall
        # back rather than refuse to run.
        #
        # But this line has to exist. Falling back silently is how the bug this
        # module was written for would come back wearing the same face: the
        # same "unable to get local issuer certificate", and no way to tell
        # from the log whether the fix was even in play. Successes stay
        # unlogged - an empty file still means a healthy machine.
        from . import diag

        diag.record("tls", problem="fallback", reason=type(exc).__name__)
        return ssl.create_default_context()

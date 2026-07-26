"""zOS#9 — the last-resort WSGI 500 page carries the security header SSOT.

The hand-built fallback in lifecycle/wsgi_app.py used to ship bare
(Content-Type + Content-Length only) — no X-Content-Type-Options,
X-Frame-Options, or CSP. It now appends build_response_headers() (same-origin
form: an error page negotiates no CORS).
"""
from types import SimpleNamespace

from zOS.L4_Orchestration.r_zServer.zServer_modules.lifecycle.wsgi_app import (
    zServerWSGIApp,
)
from zOS.L4_Orchestration.r_zServer.zServer_modules.routing.http_headers import (
    SECURITY_RESPONSE_HEADERS,
)


def test_fallback_500_carries_security_headers():
    # A zserver stub whose bridge construction/dispatch cannot succeed —
    # any exception lands in the last-resort except branch we're testing.
    zserver = SimpleNamespace(
        logger=None, router=None, mount_manager=None,
        cache_manager=None, config_manager=None,
    )
    app = zServerWSGIApp(zserver)

    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = app({}, start_response)  # empty environ → bridge blows up → fallback

    assert captured["status"].startswith("500")
    assert b"500" in b"".join(body)
    for name, value in SECURITY_RESPONSE_HEADERS:
        assert captured["headers"].get(name) == value, f"missing {name}"
    assert "Content-Security-Policy" in captured["headers"]
    # Error pages are same-origin only — no CORS grants on the fallback.
    assert "Access-Control-Allow-Origin" not in captured["headers"]

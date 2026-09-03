# tests/test_rate_limit.py
"""
zOS#8 — declarative per-route rate limiting.

Covers the grammar (parse_rate/is_opt_out), the sliding-window limiter, the
client key extraction, and the dispatcher seam (_check_rate_limit): budget
resolution (route > zAPI meta default > nothing), the loud-but-open malformed
spec path, and the 429 response shape.
"""

import time
from types import SimpleNamespace

import pytest

from zOS.L4_Orchestration.r_zServer.zServer_modules.routing.rate_limiter import (
    RateLimiter, client_key, is_opt_out, parse_rate,
)
from zOS.L4_Orchestration.r_zServer.zServer_modules.routing import rate_limiter as rl_mod
from zOS.L4_Orchestration.r_zServer.zServer_modules.routing.route_dispatcher import (
    RouteDispatcher,
)


# ── grammar ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec,expected", [
    ("10/min", (10, 60.0)),
    ("5/sec", (5, 1.0)),
    ("100/hour", (100, 3600.0)),
    ("30/5min", (30, 300.0)),
    ("2/10sec", (2, 10.0)),
    (" 10 / min ", (10, 60.0)),
    ("10/MIN", (10, 60.0)),
    ("10/mins", (10, 60.0)),
])
def test_parse_rate_valid(spec, expected):
    assert parse_rate(spec) == expected


@pytest.mark.parametrize("spec", [
    None, True, False, "", "off", "none", "0",
    "ten/min", "10", "10/fortnight", "10/min/sec", "-5/min", "0/min",
])
def test_parse_rate_invalid(spec):
    assert parse_rate(spec) is None


def test_opt_out_values():
    for spec in (None, False, "off", "false", "none", "0", ""):
        assert is_opt_out(spec) is True
    for spec in ("10/min", "banana", True):
        assert is_opt_out(spec) is False


# ── limiter mechanics ────────────────────────────────────────────────────────

def test_admits_up_to_budget_then_refuses():
    lim = RateLimiter()
    for _ in range(3):
        allowed, _, _ = lim.check("k", 3, 60.0)
        assert allowed
    allowed, retry_after, first = lim.check("k", 3, 60.0)
    assert not allowed and retry_after >= 1 and first is True


def test_first_rejection_flag_fires_once_per_window():
    lim = RateLimiter()
    lim.check("k", 1, 60.0)
    _, _, first1 = lim.check("k", 1, 60.0)
    _, _, first2 = lim.check("k", 1, 60.0)
    assert first1 is True and first2 is False


def test_window_slides_open_again():
    lim = RateLimiter()
    lim.check("k", 1, 0.05)
    allowed, _, _ = lim.check("k", 1, 0.05)
    assert not allowed
    time.sleep(0.08)
    allowed, _, _ = lim.check("k", 1, 0.05)
    assert allowed


def test_keys_are_independent():
    lim = RateLimiter()
    lim.check(("r", "1.1.1.1"), 1, 60.0)
    allowed, _, _ = lim.check(("r", "2.2.2.2"), 1, 60.0)
    assert allowed  # a second caller has their own budget


# ── client key ───────────────────────────────────────────────────────────────

def _handler(headers=None, peer="9.9.9.9"):
    return SimpleNamespace(headers=headers or {}, client_address=(peer, 12345))


def test_client_key_prefers_first_xff_hop():
    h = _handler({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    assert client_key(h) == "203.0.113.7"


def test_client_key_falls_back_to_peer():
    assert client_key(_handler()) == "9.9.9.9"


# ── dispatcher seam ──────────────────────────────────────────────────────────

class _Log:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)

    def debug(self, *a, **k):
        pass


class _Wire:
    """Just enough handler surface for the 429 write path."""

    def __init__(self):
        self.status = None
        self.headers = {}
        self.body = b""
        self.client_address = ("6.6.6.6", 1)

    def get(self, *_):  # headers.get on the handler.headers dict
        return None

    def send_response(self, code):
        self.status = code

    def send_header(self, key, val):
        self.headers[key] = val

    def end_headers(self):
        pass

    @property
    def wfile(self):
        outer = self

        class _W:
            def write(self, b):
                outer.body += b
        return _W()


def _dispatcher(route_meta=None):
    disp = RouteDispatcher.__new__(RouteDispatcher)
    handler = _Wire()
    handler.headers = {}
    disp.handler = handler
    disp.logger = _Log()
    disp.router = SimpleNamespace(meta=route_meta or {})
    return disp


@pytest.fixture(autouse=True)
def _fresh_counters():
    rl_mod.get_limiter().reset()
    yield
    rl_mod.get_limiter().reset()


def test_route_without_rate_is_open():
    disp = _dispatcher()
    route = {"type": "zAPI"}
    for _ in range(50):
        assert disp._check_rate_limit(route, "/api/x") is None


def test_route_rate_enforced_with_429_shape():
    disp = _dispatcher()
    route = {"type": "zAPI", "rate": "2/min"}
    assert disp._check_rate_limit(route, "/api/zlogin") is None
    assert disp._check_rate_limit(route, "/api/zlogin") is None
    denied = disp._check_rate_limit(route, "/api/zlogin")
    assert denied is not None
    h = disp.handler
    assert h.status == 429
    assert h.headers.get("Retry-After") and int(h.headers["Retry-After"]) >= 1
    assert b"Too many requests" in h.body
    # One [SECURITY] warning for the window, not one per rejection.
    disp._check_rate_limit(route, "/api/zlogin")
    security = [w for w in disp.logger.warnings if "[SECURITY]" in w]
    assert len(security) == 1


def test_meta_default_applies_to_zapi_only():
    disp = _dispatcher(route_meta={"rate": "1/min"})
    api_route = {"type": "zAPI"}
    page_route = {"type": "zWalker"}
    assert disp._check_rate_limit(api_route, "/api/x") is None
    assert disp._check_rate_limit(api_route, "/api/x") is not None
    for _ in range(5):  # pages never inherit the meta default
        assert disp._check_rate_limit(page_route, "/home") is None


def test_route_off_opts_out_of_meta_default():
    disp = _dispatcher(route_meta={"rate": "1/min"})
    route = {"type": "zAPI", "rate": "off"}
    for _ in range(5):
        assert disp._check_rate_limit(route, "/api/open") is None


def test_malformed_spec_warns_once_and_stays_open():
    disp = _dispatcher()
    route = {"type": "zAPI", "rate": "10/fortnight"}
    for _ in range(5):
        assert disp._check_rate_limit(route, "/api/x") is None
    bad = [w for w in disp.logger.warnings if "Unreadable rate" in w]
    assert len(bad) == 1


def test_parametrized_urls_share_one_bucket():
    disp = _dispatcher()
    route = {"type": "zLoom", "rate": "2/min"}  # same dict = same table entry
    assert disp._check_rate_limit(route, "/report/1") is None
    assert disp._check_rate_limit(route, "/report/2") is None
    assert disp._check_rate_limit(route, "/report/3") is not None

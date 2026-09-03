# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/rate_limiter.py

"""
Rate Limiter — declarative per-route request budgets (zOS#8).

The framework seam for throttling: a route in any zServer.*.zolo blueprint
declares its budget with one key —

    /api/zlogin:
        type:    zAPI
        kind:    zFunc
        method:  POST
        handler: &.registrar.zlogin
        rate:    10/min

and the dispatcher refuses request N+1 inside the window with ``429 Too Many
Requests`` + a ``Retry-After`` header, before RBAC, before the handler, before
any password hashing or DB read spends a cycle. A blueprint can also set a
server-wide default for MACHINE doors via its meta block::

    zMeta:
        rate: 60/min        # default budget for every zAPI route

Page/static routes are never throttled by default (a stylesheet fetch is not
an attack surface); the meta default applies to ``type: zAPI`` routes only.
An explicit per-route ``rate:`` wins over the meta default; ``rate: off`` on
a route opts it out of the default.

Grammar: ``<count>/<window>`` where window is ``sec`` | ``min`` | ``hour``
with an optional multiplier — ``10/min``, ``100/hour``, ``30/5min``, ``5/sec``.
A malformed spec is a LOUD no-op (warning naming the route and the grammar,
route stays open) — a typo must never take a production door offline.

Mechanics: sliding-window over per-(route, client) timestamp deques,
thread-safe (waitress is multi-threaded), in-memory per process. Counters
reset on restart/reload — by design for the brute-force case: an attacker
does not control your restarts. The client key is the first hop of
``X-Forwarded-For`` when present (prod sits behind Caddy/nginx; same trust
posture as the existing X-Forwarded-Proto cookie logic), else the socket
peer. Rejections log ONE ``[SECURITY]`` warning per window per client — an
attack must not also be a log-flood attack.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Optional, Tuple

# ``rate: off`` (or false/none) opts a route out of a blueprint-meta default.
_OFF_VALUES = {"off", "false", "none", "0", ""}

_SPEC_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d*)\s*(sec|min|hour)s?\s*$", re.IGNORECASE)

_UNIT_SECONDS = {"sec": 1, "min": 60, "hour": 3600}


def parse_rate(spec) -> Optional[Tuple[int, float]]:
    """``"10/min"`` → ``(10, 60.0)``; ``"30/5min"`` → ``(30, 300.0)``.

    Returns None for anything that isn't a valid, positive budget — including
    the explicit opt-outs (off/false/none). The CALLER decides whether a
    non-parse deserves a warning (an opt-out doesn't; a typo does — see
    :func:`is_opt_out`).
    """
    if spec is None or isinstance(spec, bool):
        return None
    text = str(spec).strip().lower()
    if text in _OFF_VALUES:
        return None
    match = _SPEC_RE.match(text)
    if not match:
        return None
    count = int(match.group(1))
    multiplier = int(match.group(2) or 1)
    window = multiplier * _UNIT_SECONDS[match.group(3).lower()]
    if count <= 0 or window <= 0:
        return None
    return count, float(window)


def is_opt_out(spec) -> bool:
    """True when the spec EXPLICITLY disables limiting (never warn on these)."""
    if spec is None or spec is False:
        return True
    return str(spec).strip().lower() in _OFF_VALUES


class RateLimiter:
    """Sliding-window counters keyed by (route identity, client key).

    One instance lives for the process (module singleton below); the window
    deques are pruned inline on every check, and a periodic sweep drops
    whole idle buckets so a scan across many IPs can't grow memory forever.
    """

    _SWEEP_EVERY = 60.0  # seconds between idle-bucket sweeps

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict = {}          # key -> deque[timestamps]
        self._warned: dict = {}           # key -> window-start we last warned for
        self._last_sweep = time.monotonic()

    def check(self, key, max_requests: int, window_seconds: float):
        """Admit or refuse one request.

        Returns
        -------
        (allowed: bool, retry_after: int, first_rejection: bool)
            ``retry_after`` is the whole-second wait until the oldest counted
            request leaves the window (min 1). ``first_rejection`` is True only
            for the first refusal of this key in the current window — the
            caller's log gate.
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = deque()
            floor = now - window_seconds
            while bucket and bucket[0] <= floor:
                bucket.popleft()

            if len(bucket) < max_requests:
                bucket.append(now)
                self._warned.pop(key, None)
                self._maybe_sweep(now, window_seconds)
                return True, 0, False

            retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
            first = self._warned.get(key) != bucket[0]
            if first:
                self._warned[key] = bucket[0]
            return False, retry_after, first

    def _maybe_sweep(self, now: float, window_seconds: float) -> None:
        """Drop buckets whose newest entry is older than its window (idle)."""
        if now - self._last_sweep < self._SWEEP_EVERY:
            return
        self._last_sweep = now
        # A bucket's own window isn't stored; use the largest plausible bound
        # (1 hour) so a slow-window bucket is never dropped mid-window.
        horizon = now - max(window_seconds, 3600.0)
        for key in [k for k, b in self._buckets.items()
                    if not b or b[-1] <= horizon]:
            self._buckets.pop(key, None)
            self._warned.pop(key, None)

    def reset(self) -> None:
        """Test seam — drop all counters."""
        with self._lock:
            self._buckets.clear()
            self._warned.clear()


_LIMITER = RateLimiter()


def get_limiter() -> RateLimiter:
    """The process-wide limiter (route tables swap on reload; counters persist)."""
    return _LIMITER


def client_key(handler) -> str:
    """The caller's identity for counting: first X-Forwarded-For hop, else peer.

    Trusting the header mirrors the existing X-Forwarded-Proto posture: in
    production zServer sits behind a proxy that SETS it; on a directly-exposed
    dev box a spoofed XFF only ever splits the attacker's own budget across
    made-up names, it can never consume another caller's.
    """
    try:
        forwarded = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    except Exception:  # pylint: disable=broad-except
        pass
    try:
        return handler.client_address[0]
    except Exception:  # pylint: disable=broad-except
        return "unknown"

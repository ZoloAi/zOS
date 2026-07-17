# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/reload_gate.py
"""
Reload/request quiescence gate — reloads never race in-flight requests.

THE COLLISION THIS KILLS: ``z reload`` (SIGHUP) runs in the MAIN thread while
requests are served in the server thread (dev http.server daemon thread, or
waitress's pool). The reload's first act busts the loader's parsed-file cache
and rebuilds the route table — the exact shared state a long in-flight request
(a ``zolo push`` mid-zRelease, a zProxy wake holding the thread for seconds)
is standing on. Unsynchronized, the request thread wedges on half-swapped
state and, on the single-threaded dev server, every later request queues
behind it forever.

MODEL: readers-writer. Every routed request holds a READ slot for its whole
dispatch; a reload takes the WRITE side — it blocks NEW requests, waits
(bounded) for in-flight ones to drain, does its work alone, then releases.
Never races: if the drain window expires (a wedged/very long request), the
reload ABORTS with "busy" rather than proceeding concurrently — a skipped
reload is retryable, a corrupted route table is not.

One gate per process (module singleton): one server per process is the zOS
posture, and even co-hosted servers share the loader they'd be racing on.
"""

from __future__ import annotations

import contextlib
import threading

__all__ = ["ReloadGate", "get_gate"]

# How long a request arriving DURING a reload waits for it to finish before
# giving up (reloads are normally sub-second; this is generous).
DEFAULT_REQUEST_WAIT = 30.0
# How long a reload waits for in-flight requests to drain before aborting
# (a push mid-zRelease can legitimately hold the gate for tens of seconds).
DEFAULT_DRAIN_WAIT = 45.0


class ReloadGate:
    """Readers (requests) / writer (reload) synchronization for zServer."""

    def __init__(self):
        self._cond = threading.Condition()
        self._readers = 0
        # Thread idents currently holding a read slot — lets quiesce() detect a
        # self-deadlock (reload invoked FROM a request thread) and refuse fast.
        self._reader_threads: set = set()
        self._writer_pending = False

    # -- request (reader) side -------------------------------------------------

    @contextlib.contextmanager
    def request(self, wait: float = DEFAULT_REQUEST_WAIT):
        """Hold a read slot for one request dispatch.

        Yields True when the slot was acquired; False when a reload held the
        gate past ``wait`` (caller should answer 503-retry, never dispatch).
        Re-entrant per thread: a nested dispatch on a thread that already holds
        a slot passes straight through (it cannot deadlock the writer it is
        already excluding).
        """
        ident = threading.get_ident()
        with self._cond:
            if ident in self._reader_threads:
                yield True  # nested dispatch on an already-counted thread
                return
            if self._writer_pending and not self._cond.wait_for(
                    lambda: not self._writer_pending, timeout=wait):
                yield False
                return
            self._readers += 1
            self._reader_threads.add(ident)
        try:
            yield True
        finally:
            with self._cond:
                self._readers -= 1
                self._reader_threads.discard(ident)
                self._cond.notify_all()

    # -- reload (writer) side --------------------------------------------------

    @contextlib.contextmanager
    def quiesce(self, drain_wait: float = DEFAULT_DRAIN_WAIT):
        """Exclusive window for a reload/swap: block new requests, drain old.

        Yields True when the server is quiescent (proceed); False when it never
        drained inside ``drain_wait`` OR the caller is itself a request thread
        (proceeding would self-deadlock) — in both cases the caller must SKIP
        the mutation and report busy. New requests blocked during a failed
        drain are released on exit either way.
        """
        ident = threading.get_ident()
        with self._cond:
            if ident in self._reader_threads:
                yield False  # reload from within a request thread — refuse
                return
            if self._writer_pending:
                yield False  # another reload already holds/awaits the gate
                return
            self._writer_pending = True
            drained = self._cond.wait_for(lambda: self._readers == 0,
                                          timeout=drain_wait)
        try:
            yield drained
        finally:
            with self._cond:
                self._writer_pending = False
                self._cond.notify_all()

    @property
    def in_flight(self) -> int:
        with self._cond:
            return self._readers


_GATE = ReloadGate()


def get_gate() -> ReloadGate:
    """The process-wide gate shared by request dispatch and reload/swap."""
    return _GATE

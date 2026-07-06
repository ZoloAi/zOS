# zSys/shutdown/signals.py
"""
Signal handling for graceful shutdown.
"""

from __future__ import annotations

from .shutdown_constants import (
    ERROR_RELOAD_SIGNAL,
    ERROR_SHUTDOWN_SIGNAL,
    ERROR_SIGNAL_RECEIVED,
    ERROR_SWAP_SIGNAL,
    ERROR_VISITORS_SIGNAL,
    LOG_DEBUG_RELOAD_HANDLER,
    LOG_DEBUG_SIGNAL_HANDLERS,
    LOG_DEBUG_SIGNAL_SKIP_NONMAIN,
    LOG_DEBUG_SWAP_HANDLER,
    LOG_DEBUG_VISITORS_HANDLER,
    LOG_RELOAD_SIGNAL_RECEIVED,
    LOG_SWAP_SIGNAL_RECEIVED,
    LOG_VISITORS_SIGNAL_RECEIVED,
    LOG_WARN_SIGNAL_DUPLICATE,
    SIGNAL_HUP,
    SIGNAL_INT,
    SIGNAL_TERM,
    SIGNAL_USR1,
    SIGNAL_USR2,
)


def register_signal_handlers(zos) -> None:
    """
    Register SIGINT/SIGTERM handlers for graceful shutdown.

    Prevents duplicate attempts via _shutdown_in_progress flag.
    Exit codes: 0 (clean) | 1 (error).
    """
    import signal
    import sys
    import threading

    def signal_handler(signum, frame):  # pylint: disable=unused-argument
        """Handle SIGINT (Ctrl+C) and SIGTERM gracefully."""
        import os as _os  # pylint: disable=import-outside-toplevel

        signal_name = SIGNAL_INT if signum == signal.SIGINT else SIGNAL_TERM

        if zos._shutdown_in_progress:  # pylint: disable=protected-access
            zos.logger.warning(LOG_WARN_SIGNAL_DUPLICATE, signal_name)
            return

        zos.logger.info(ERROR_SIGNAL_RECEIVED, signal_name)
        zos._shutdown_requested = True  # pylint: disable=protected-access

        # When this process IS the zRaven runner (not the test-target subprocess),
        # do NOT sys.exit() after shutdown. The runner owns post-run work (hints,
        # data teardown) that must execute after zcli.run() returns. Exiting here
        # via SystemExit would bypass all of that.
        is_runner = _os.environ.get("ZRAVEN_RUNNER") == "1"

        try:
            zos.shutdown()
            if not is_runner:
                sys.exit(0)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            zos.zTraceback.log_exception(
                exc,
                message=ERROR_SHUTDOWN_SIGNAL % signal_name,
                context={"signal": signum},
            )
            if not is_runner:
                sys.exit(1)

    def reload_handler(signum, frame):  # pylint: disable=unused-argument
        """Handle SIGHUP — hot-reload the served app WITHOUT stopping the process.

        Unix convention: SIGHUP = "reload your config". For zServer that means
        re-scan routes/zAPIs + bust the parsed-file cache in place. Never exits;
        the socket, WS bridge, and live sessions are preserved.
        """
        zos.logger.info(LOG_RELOAD_SIGNAL_RECEIVED, SIGNAL_HUP)
        try:
            zos.reload_server(source=SIGNAL_HUP)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            zos.zTraceback.log_exception(
                exc,
                message=ERROR_RELOAD_SIGNAL % SIGNAL_HUP,
                context={"signal": signum},
            )

    def swap_handler(signum, frame):  # pylint: disable=unused-argument
        """Handle SIGUSR2 — zero-downtime self-replace (blue-green).

        Spawns a fresh copy of this app on the SAME port, waits for it to go ready,
        then drains and exits this process — leaving the new code live. Unlike SIGHUP
        (in-place re-scan), this picks up new Python / a patched zGuard binary. On a
        successful handoff the process exits inside this call. Fail-safe: if the new
        instance never goes ready, we keep serving.
        """
        zos.logger.info(LOG_SWAP_SIGNAL_RECEIVED, SIGNAL_USR2)
        try:
            zos.swap_server(source=SIGNAL_USR2)
        except SystemExit:
            raise  # successful handoff exits the process — let it propagate
        except Exception as exc:  # pylint: disable=broad-exception-caught
            zos.zTraceback.log_exception(
                exc,
                message=ERROR_SWAP_SIGNAL % SIGNAL_USR2,
                context={"signal": signum},
            )

    def visitors_handler(signum, frame):  # pylint: disable=unused-argument
        """Handle SIGUSR1 — print this PID's live zVisitors table to the console.

        Read-only: renders the in-process session registry (the visitors this zOS
        instance currently holds) for the zOwner. Triggered by `z visitors` from
        another shell; the snapshot prints on THIS server's console — the same
        "watch the server console" model as `z reload`. Never exits or mutates.
        """
        zos.logger.info(LOG_VISITORS_SIGNAL_RECEIVED, SIGNAL_USR1)
        try:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session.visitor_view import (  # pylint: disable=import-outside-toplevel
                render_visitor_table,
            )
        except ImportError:  # dev / alternate package root
            from L1_Foundation.a_zConfig.zConfig_modules.session.visitor_view import (  # pylint: disable=import-outside-toplevel
                render_visitor_table,
            )
        try:
            spark = getattr(zos, "spark", None) or {}
            if isinstance(spark, dict) and isinstance(spark.get("zSpark"), dict):
                spark = spark["zSpark"]
            title = (spark.get("title") or spark.get("zTitle")
                     if isinstance(spark, dict) else None) or "zVisitors"
            print(render_visitor_table(title=title), flush=True)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            zos.zTraceback.log_exception(
                exc,
                message=ERROR_VISITORS_SIGNAL % SIGNAL_USR1,
                context={"signal": signum},
            )

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        zos.logger.framework.debug(LOG_DEBUG_SIGNAL_HANDLERS)
        # SIGHUP is POSIX-only (absent on Windows) — register the reload hook
        # only where the platform provides it.
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, reload_handler)
            zos.logger.framework.debug(LOG_DEBUG_RELOAD_HANDLER)
        # SIGUSR2 → self-replace (blue-green). POSIX-only.
        if hasattr(signal, "SIGUSR2"):
            signal.signal(signal.SIGUSR2, swap_handler)
            zos.logger.framework.debug(LOG_DEBUG_SWAP_HANDLER)
        # SIGUSR1 → zVisitors snapshot (read-only console dump). POSIX-only.
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, visitors_handler)
            zos.logger.framework.debug(LOG_DEBUG_VISITORS_HANDLER)
    else:
        zos.logger.framework.debug(LOG_DEBUG_SIGNAL_SKIP_NONMAIN)


__all__ = ["register_signal_handlers"]

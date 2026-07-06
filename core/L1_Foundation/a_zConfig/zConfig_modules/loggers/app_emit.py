# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/app_emit.py
"""
App-level log emission — SSOT for zos.log() and the zLogger app event.

This is the runtime emit orchestrator that sits on top of the configured
``AppLogger`` (same package). It owns the cross-cutting routing concerns:

    zLog: PROD          → always print to console (app logs bypass framework silence)
    zLog: DEBUG/INFO/…  → standard Python level filtering applies
    zLogPath set        → always written to file via the app logger
    zRaven capture      → buffered instead of printed
    zBifrost mode       → broadcast as a WS ``app_log`` event

The public handle is :class:`AppLog`, bound on the instance as ``zos.log``.
"""
from __future__ import annotations

from typing import Optional

_LOG_LEVEL_PROD = "PROD"
_DEFAULT_LEVEL  = "INFO"
_VALID_LEVELS   = {"DEBUG", "SESSION", "INFO", "WARNING", "ERROR", "CRITICAL"}

# ── CLI app-log wire format (SSOT) ─────────────────────────────────────────────
# A machine-readable line emitted to stdout in CLI mode so the zRaven CLI runner
# can capture app logs without confusing them for normal output. The tag is
# NUL-prefixed so ordinary output never collides; fields are unit-separated.
CLI_APP_LOG_TAG = "\x00ZLOG"
CLI_APP_LOG_SEP = "\x1f"
# WS event name used to broadcast the same app log in Bifrost mode.
APP_LOG_EVENT   = "app_log"

# Backward-compatible private alias (was the only definition before SSOT split).
_CLI_APP_LOG_TAG = CLI_APP_LOG_TAG


def format_cli_log_line(level: str, tag, message: str) -> str:
    """Build the NUL-tagged, unit-separated CLI app-log line (emit side)."""
    return f"{CLI_APP_LOG_TAG}{CLI_APP_LOG_SEP}{level}{CLI_APP_LOG_SEP}{tag or ''}{CLI_APP_LOG_SEP}{message}"


def parse_cli_log_line(line: str):
    """Parse a CLI app-log line back into {message, level, tag} (capture side).

    Returns None when *line* is not a tagged app-log line.
    """
    if not line.startswith(CLI_APP_LOG_TAG + CLI_APP_LOG_SEP):
        return None
    parts = line.split(CLI_APP_LOG_SEP, 3)
    return {
        "message": parts[3] if len(parts) > 3 else "",
        "level":   parts[1] if len(parts) > 1 else "INFO",
        "tag":     parts[2] if (len(parts) > 2 and parts[2]) else None,
    }


class AppLog:
    """Public app-level logging handle, exposed as ``zos.log``.

    Callable for the common case, with ``.log`` / ``.event`` aliases:

        zos.log("Order saved", tag="crm.orders")
        zos.log.event("User signed in", tag="auth")
    """

    __slots__ = ("_zos",)

    def __init__(self, zos: object) -> None:
        self._zos = zos

    def __call__(self, message: str, level: str = _DEFAULT_LEVEL, tag: Optional[str] = None) -> None:
        emit_app_log(self._zos, message, level, tag)

    def log(self, message: str, level: str = _DEFAULT_LEVEL, tag: Optional[str] = None) -> None:
        emit_app_log(self._zos, message, level, tag)

    def event(self, message: str, tag: Optional[str] = None) -> None:
        """Convenience shorthand — always INFO level, PROD-safe."""
        emit_app_log(self._zos, message, _DEFAULT_LEVEL, tag)


def emit_app_log(zos: object, message: str, level: str = _DEFAULT_LEVEL, tag: Optional[str] = None) -> None:
    """Emit an app-level log event.

    Args:
        zos:     zOS instance (provides session + logger access)
        message: Log message string
        level:   Log level — DEBUG/SESSION/INFO/WARNING/ERROR/CRITICAL/PROD
        tag:     Optional namespace tag shown as prefix (e.g. "crm.orders")
    """
    level = str(level).upper() if level else _DEFAULT_LEVEL

    prefix = f"[{tag}] " if tag else ""
    line   = f"{prefix}{message}"

    # zRaven capture mode: write to buffer instead of printing
    buf = getattr(zos, "_app_log_buffer", None)
    if buf is not None:
        buf.append({"message": message, "level": level, "tag": tag})
        return

    # Bifrost: broadcast WS event; CLI: emit a machine-readable tagged line for zRaven
    _broadcast_app_log(zos, message, level, tag)
    _print_cli_log_tag(zos, message, level, tag)

    # Resolve current zLog mode from session
    zlog = ""
    try:
        zlog = str(zos.session.get("zLogger", "")).upper()  # type: ignore[attr-defined]
    except Exception:
        pass

    if zlog == _LOG_LEVEL_PROD:
        # PROD mode: bypass framework logger, always print to console
        print(line)
        _write_to_file(zos, message, level, tag)
        return

    # Standard mode: route through Python logger at the requested level
    effective = level if level in _VALID_LEVELS else _DEFAULT_LEVEL
    try:
        logger = zos.logger._app_logger  # type: ignore[attr-defined]
        getattr(logger, effective.lower(), logger.info)(line)
    except Exception:
        print(line)


def _print_cli_log_tag(zos: object, message: str, level: str, tag: Optional[str]) -> None:
    """Print a machine-readable line to stdout in CLI mode so zRaven CLI runner can capture it."""
    try:
        mode = str(getattr(zos, "session", {}).get("zMode", "")).strip()  # type: ignore[attr-defined]
        if mode not in ("zCLI", "", None):
            return
    except Exception:
        return
    print(format_cli_log_line(level, tag, message), flush=True)


def _broadcast_app_log(zos: object, message: str, level: str, tag: Optional[str]) -> None:
    """Broadcast app_log WS event when running in Bifrost mode (for zRaven capture)."""
    try:
        mode = str(getattr(zos, "session", {}).get("zMode", "")).strip()  # type: ignore[attr-defined]
        if mode != "zBifrost":
            return
        events = zos.comm.websocket_events  # type: ignore[attr-defined]
        events.send_event({"event": APP_LOG_EVENT, "message": message, "level": level, "tag": tag})
    except Exception:
        pass


def _write_to_file(zos: object, message: str, level: str, tag: Optional[str]) -> None:
    """Write to file logger if available (respects zLogPath)."""
    try:
        logger = zos.logger._app_logger  # type: ignore[attr-defined]
        prefix = f"[{tag}] " if tag else ""
        effective = level if level in _VALID_LEVELS else _DEFAULT_LEVEL
        getattr(logger, effective.lower(), logger.info)(f"{prefix}{message}")
    except Exception:
        pass

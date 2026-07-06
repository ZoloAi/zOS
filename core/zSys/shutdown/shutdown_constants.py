# zSys/shutdown/shutdown_constants.py
"""
Shutdown constants shared across signal handling and cleanup.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Signal Names (2) - For signal handler logging
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_INT: str = "SIGINT"
SIGNAL_TERM: str = "SIGTERM"
SIGNAL_HUP: str = "SIGHUP"  # reload (not shutdown) — re-scan routes/zAPIs in place
SIGNAL_USR2: str = "SIGUSR2"  # self-replace (blue-green) — spawn new code, hand off, exit
SIGNAL_USR1: str = "SIGUSR1"  # zVisitors snapshot — print this PID's live session table

# ─────────────────────────────────────────────────────────────────────────────
# Shutdown Component Keys (4) - For status tracking dict
# ─────────────────────────────────────────────────────────────────────────────
SHUTDOWN_WEBSOCKET: str = "websocket"
SHUTDOWN_HTTP_SERVER: str = "http_server"
SHUTDOWN_DATABASE: str = "database"
SHUTDOWN_LOGGER: str = "logger"

# ─────────────────────────────────────────────────────────────────────────────
# Shutdown Status Symbols (2) - For status display
# ─────────────────────────────────────────────────────────────────────────────
SHUTDOWN_STATUS_SUCCESS: str = "[ok]"
SHUTDOWN_STATUS_FAIL: str = "✗"

# ─────────────────────────────────────────────────────────────────────────────
# Console Prints (6) - User-facing stdout lines (SSOT; reuse the success glyph)
# ─────────────────────────────────────────────────────────────────────────────
SHUTDOWN_PRINT_INITIATED: str = "\nzCLI: Graceful shutdown initiated..."
SHUTDOWN_PRINT_WEBSOCKET: str = f"   {SHUTDOWN_STATUS_SUCCESS} Closing WebSocket connections..."
SHUTDOWN_PRINT_HTTP: str = f"   {SHUTDOWN_STATUS_SUCCESS} Stopping HTTP server..."
SHUTDOWN_PRINT_DB: str = f"   {SHUTDOWN_STATUS_SUCCESS} Closing database connections..."
SHUTDOWN_PRINT_LOGGER: str = f"   {SHUTDOWN_STATUS_SUCCESS} Flushing logs..."
SHUTDOWN_PRINT_COMPLETE: str = f"{SHUTDOWN_STATUS_SUCCESS} Graceful shutdown complete\n"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Info (2)
# ─────────────────────────────────────────────────────────────────────────────
LOG_SHUTDOWN_START: str = "[Shutdown] Initiating graceful shutdown..."
LOG_SHUTDOWN_COMPLETE: str = "[Shutdown] Graceful shutdown complete"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Warning (4)
# ─────────────────────────────────────────────────────────────────────────────
LOG_WARN_SHUTDOWN_IN_PROGRESS: str = "[Shutdown] Shutdown already in progress"
LOG_WARN_WEBSOCKET_ERROR: str = "[Shutdown] WebSocket cleanup error: %s"
LOG_WARN_SIGNAL_DUPLICATE: str = "[%s] Shutdown already in progress..."
LOG_WARN_ASYNC_SHUTDOWN_SKIPPED: str = "[Shutdown] Async shutdown skipped (loop running)"

# ─────────────────────────────────────────────────────────────────────────────
# Logger Messages - Debug (7)
# ─────────────────────────────────────────────────────────────────────────────
LOG_DEBUG_SIGNAL_HANDLERS: str = "Signal handlers registered (SIGINT, SIGTERM)"
LOG_DEBUG_SIGNAL_SKIP_NONMAIN: str = "[zCLI] Skipping signal handlers (not main thread)"
LOG_DEBUG_RELOAD_HANDLER: str = "Reload handler registered (SIGHUP)"
LOG_DEBUG_WEBSOCKET_NOT_RUNNING: str = "[Shutdown] WebSocket server not running"
LOG_DEBUG_WEBSOCKET_NOT_INIT: str = "[Shutdown] WebSocket server not initialized"
LOG_DEBUG_HTTP_NOT_RUNNING: str = "[Shutdown] HTTP server not running"
LOG_DEBUG_HTTP_NOT_INIT: str = "[Shutdown] HTTP server not initialized"
LOG_DEBUG_DB_NOT_CONNECTED: str = "[Shutdown] No active database connections"
LOG_DEBUG_DB_NOT_INIT: str = "[Shutdown] Database subsystem not initialized"

# ─────────────────────────────────────────────────────────────────────────────
# Shutdown Messages (6)
# ─────────────────────────────────────────────────────────────────────────────
SHUTDOWN_MSG_WEBSOCKET_CLOSE: str = "[Shutdown] Closing WebSocket server..."
SHUTDOWN_MSG_HTTP_STOP: str = "[Shutdown] Stopping HTTP server..."
SHUTDOWN_MSG_DB_CLOSE: str = "[Shutdown] Closing database connections..."
SHUTDOWN_MSG_LOGGER_FLUSH: str = "[Shutdown] Flushing logger..."
SHUTDOWN_MSG_STATUS_REPORT: str = "[Shutdown] Cleanup Status:"
SHUTDOWN_MSG_COMPONENT_STATUS: str = "  %s %s"

# ─────────────────────────────────────────────────────────────────────────────
# Shutdown Separators (1)
# ─────────────────────────────────────────────────────────────────────────────
SHUTDOWN_SEPARATOR: str = "=" * 70

# ─────────────────────────────────────────────────────────────────────────────
# Error Messages (6)
# ─────────────────────────────────────────────────────────────────────────────
ERROR_SHUTDOWN_SIGNAL: str = "Error during %s shutdown"
ERROR_WEBSOCKET_SHUTDOWN: str = "WebSocket shutdown"
ERROR_HTTP_SHUTDOWN: str = "HTTP server shutdown"
ERROR_DB_SHUTDOWN: str = "Database connection cleanup"
ERROR_LOGGER_SHUTDOWN: str = "Logger cleanup"
ERROR_SIGNAL_RECEIVED: str = "[%s] Received shutdown signal"
ERROR_RELOAD_SIGNAL: str = "Error during %s reload"
LOG_RELOAD_SIGNAL_RECEIVED: str = "[%s] Received reload signal"
ERROR_SWAP_SIGNAL: str = "Error during %s self-replace"
LOG_SWAP_SIGNAL_RECEIVED: str = "[%s] Received self-replace signal"
LOG_DEBUG_SWAP_HANDLER: str = "Self-replace handler registered (SIGUSR2)"
LOG_DEBUG_VISITORS_HANDLER: str = "zVisitors handler registered (SIGUSR1)"
LOG_VISITORS_SIGNAL_RECEIVED: str = "[%s] Received zVisitors snapshot request"
ERROR_VISITORS_SIGNAL: str = "Error rendering zVisitors on %s"


__all__ = [
    "SIGNAL_INT",
    "SIGNAL_TERM",
    "SIGNAL_HUP",
    "SIGNAL_USR2",
    "SIGNAL_USR1",
    "SHUTDOWN_WEBSOCKET",
    "SHUTDOWN_HTTP_SERVER",
    "SHUTDOWN_DATABASE",
    "SHUTDOWN_LOGGER",
    "SHUTDOWN_STATUS_SUCCESS",
    "SHUTDOWN_STATUS_FAIL",
    "SHUTDOWN_PRINT_INITIATED",
    "SHUTDOWN_PRINT_WEBSOCKET",
    "SHUTDOWN_PRINT_HTTP",
    "SHUTDOWN_PRINT_DB",
    "SHUTDOWN_PRINT_LOGGER",
    "SHUTDOWN_PRINT_COMPLETE",
    "LOG_SHUTDOWN_START",
    "LOG_SHUTDOWN_COMPLETE",
    "LOG_WARN_SHUTDOWN_IN_PROGRESS",
    "LOG_WARN_WEBSOCKET_ERROR",
    "LOG_WARN_SIGNAL_DUPLICATE",
    "LOG_WARN_ASYNC_SHUTDOWN_SKIPPED",
    "LOG_DEBUG_SIGNAL_HANDLERS",
    "LOG_DEBUG_SIGNAL_SKIP_NONMAIN",
    "LOG_DEBUG_RELOAD_HANDLER",
    "LOG_DEBUG_WEBSOCKET_NOT_RUNNING",
    "LOG_DEBUG_WEBSOCKET_NOT_INIT",
    "LOG_DEBUG_HTTP_NOT_RUNNING",
    "LOG_DEBUG_HTTP_NOT_INIT",
    "LOG_DEBUG_DB_NOT_CONNECTED",
    "LOG_DEBUG_DB_NOT_INIT",
    "SHUTDOWN_MSG_WEBSOCKET_CLOSE",
    "SHUTDOWN_MSG_HTTP_STOP",
    "SHUTDOWN_MSG_DB_CLOSE",
    "SHUTDOWN_MSG_LOGGER_FLUSH",
    "SHUTDOWN_MSG_STATUS_REPORT",
    "SHUTDOWN_MSG_COMPONENT_STATUS",
    "SHUTDOWN_SEPARATOR",
    "ERROR_SHUTDOWN_SIGNAL",
    "ERROR_WEBSOCKET_SHUTDOWN",
    "ERROR_HTTP_SHUTDOWN",
    "ERROR_DB_SHUTDOWN",
    "ERROR_LOGGER_SHUTDOWN",
    "ERROR_SIGNAL_RECEIVED",
    "ERROR_RELOAD_SIGNAL",
    "LOG_RELOAD_SIGNAL_RECEIVED",
    "ERROR_SWAP_SIGNAL",
    "LOG_SWAP_SIGNAL_RECEIVED",
    "LOG_DEBUG_SWAP_HANDLER",
    "LOG_DEBUG_VISITORS_HANDLER",
    "LOG_VISITORS_SIGNAL_RECEIVED",
    "ERROR_VISITORS_SIGNAL",
]

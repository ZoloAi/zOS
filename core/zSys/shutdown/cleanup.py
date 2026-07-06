# zSys/shutdown/cleanup.py
"""
Subsystem cleanup for graceful shutdown.
"""

from __future__ import annotations

from typing import Dict, Optional

from .shutdown_constants import (
    ERROR_DB_SHUTDOWN,
    ERROR_HTTP_SHUTDOWN,
    ERROR_LOGGER_SHUTDOWN,
    ERROR_WEBSOCKET_SHUTDOWN,
    LOG_DEBUG_DB_NOT_CONNECTED,
    LOG_DEBUG_DB_NOT_INIT,
    LOG_DEBUG_HTTP_NOT_INIT,
    LOG_DEBUG_HTTP_NOT_RUNNING,
    LOG_DEBUG_WEBSOCKET_NOT_INIT,
    LOG_DEBUG_WEBSOCKET_NOT_RUNNING,
    LOG_SHUTDOWN_COMPLETE,
    LOG_SHUTDOWN_START,
    LOG_WARN_ASYNC_SHUTDOWN_SKIPPED,
    LOG_WARN_SHUTDOWN_IN_PROGRESS,
    LOG_WARN_WEBSOCKET_ERROR,
    SHUTDOWN_DATABASE,
    SHUTDOWN_HTTP_SERVER,
    SHUTDOWN_LOGGER,
    SHUTDOWN_PRINT_COMPLETE,
    SHUTDOWN_PRINT_DB,
    SHUTDOWN_PRINT_HTTP,
    SHUTDOWN_PRINT_INITIATED,
    SHUTDOWN_PRINT_LOGGER,
    SHUTDOWN_PRINT_WEBSOCKET,
    SHUTDOWN_MSG_COMPONENT_STATUS,
    SHUTDOWN_MSG_DB_CLOSE,
    SHUTDOWN_MSG_HTTP_STOP,
    SHUTDOWN_MSG_LOGGER_FLUSH,
    SHUTDOWN_MSG_STATUS_REPORT,
    SHUTDOWN_MSG_WEBSOCKET_CLOSE,
    SHUTDOWN_SEPARATOR,
    SHUTDOWN_STATUS_FAIL,
    SHUTDOWN_STATUS_SUCCESS,
    SHUTDOWN_WEBSOCKET,
)

# pylint: disable=protected-access


def perform_shutdown(zos) -> Optional[Dict[str, bool]]:
    """
    Gracefully shutdown all subsystems in reverse init order.

    Cleanup: WebSocket → HTTP → Database → Logger. Each wrapped in ExceptionContext
    (failures don't halt shutdown). Idempotent via _shutdown_in_progress flag.

    Returns Dict[str, bool] with component status, or None if already in progress.
    """
    from zSys.errors import ExceptionContext

    if zos._shutdown_in_progress:
        zos.logger.warning(LOG_WARN_SHUTDOWN_IN_PROGRESS)
        return None

    zos._shutdown_in_progress = True
    print(SHUTDOWN_PRINT_INITIATED)
    zos.logger.framework.debug(LOG_SHUTDOWN_START)

    cleanup_status = {
        SHUTDOWN_WEBSOCKET: False,
        SHUTDOWN_HTTP_SERVER: False,
        SHUTDOWN_DATABASE: False,
        SHUTDOWN_LOGGER: False,
    }

    with ExceptionContext(
        zos.zTraceback, operation=ERROR_WEBSOCKET_SHUTDOWN, default_return=None
    ):
        if zos.comm and hasattr(zos.comm, "websocket") and zos.comm.websocket:
            if zos.comm.websocket._running:  # pylint: disable=protected-access
                print(SHUTDOWN_PRINT_WEBSOCKET)
                zos.logger.framework.debug(SHUTDOWN_MSG_WEBSOCKET_CLOSE)

                import asyncio

                try:
                    try:
                        loop = asyncio.get_running_loop()
                        if hasattr(zos.comm.websocket, "_sync_shutdown"):
                            zos.comm.websocket._sync_shutdown()  # pylint: disable=protected-access
                        else:
                            zos.logger.warning(LOG_WARN_ASYNC_SHUTDOWN_SKIPPED)
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(zos.comm.websocket.shutdown())
                        loop.close()

                    cleanup_status[SHUTDOWN_WEBSOCKET] = True
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    zos.logger.warning(LOG_WARN_WEBSOCKET_ERROR, exc)
            else:
                zos.logger.debug(LOG_DEBUG_WEBSOCKET_NOT_RUNNING)
                cleanup_status[SHUTDOWN_WEBSOCKET] = True
        else:
            zos.logger.debug(LOG_DEBUG_WEBSOCKET_NOT_INIT)
            cleanup_status[SHUTDOWN_WEBSOCKET] = True

    with ExceptionContext(
        zos.zTraceback, operation=ERROR_HTTP_SHUTDOWN, default_return=None
    ):
        if zos.server:
            if zos.server.is_running():
                print(SHUTDOWN_PRINT_HTTP)
                zos.logger.framework.debug(SHUTDOWN_MSG_HTTP_STOP)
                zos.server.stop()
                cleanup_status[SHUTDOWN_HTTP_SERVER] = True
            else:
                zos.logger.debug(LOG_DEBUG_HTTP_NOT_RUNNING)
                cleanup_status[SHUTDOWN_HTTP_SERVER] = True
        else:
            zos.logger.debug(LOG_DEBUG_HTTP_NOT_INIT)
            cleanup_status[SHUTDOWN_HTTP_SERVER] = True

    with ExceptionContext(
        zos.zTraceback, operation=ERROR_DB_SHUTDOWN, default_return=None
    ):
        if hasattr(zos, "data") and zos.data:
            if hasattr(zos.data, "adapter") and zos.data.adapter:
                print(SHUTDOWN_PRINT_DB)
                zos.logger.framework.debug(SHUTDOWN_MSG_DB_CLOSE)
                if hasattr(zos.data.adapter, "disconnect"):
                    zos.data.adapter.disconnect()
                elif hasattr(zos.data.adapter, "close"):
                    zos.data.adapter.close()
                cleanup_status[SHUTDOWN_DATABASE] = True
            else:
                zos.logger.debug(LOG_DEBUG_DB_NOT_CONNECTED)
                cleanup_status[SHUTDOWN_DATABASE] = True
        else:
            zos.logger.debug(LOG_DEBUG_DB_NOT_INIT)
            cleanup_status[SHUTDOWN_DATABASE] = True

    with ExceptionContext(
        zos.zTraceback, operation=ERROR_LOGGER_SHUTDOWN, default_return=None
    ):
        if zos.logger:
            print(SHUTDOWN_PRINT_LOGGER)
            zos.logger.framework.debug(SHUTDOWN_MSG_LOGGER_FLUSH)
            if hasattr(zos.logger, "logger"):
                for handler in zos.logger.logger.handlers:
                    handler.flush()
                if hasattr(zos.logger, "framework"):
                    for handler in zos.logger.framework.handlers:
                        handler.flush()
            else:
                for handler in zos.logger.handlers:
                    handler.flush()
            cleanup_status[SHUTDOWN_LOGGER] = True

    # (Retired) zTraceback no longer installs a global sys.excepthook, so there is
    # nothing to uninstall at shutdown — it is now a pure error-shaping helper.

    zos.logger.framework.debug(SHUTDOWN_SEPARATOR)
    zos.logger.framework.debug(SHUTDOWN_MSG_STATUS_REPORT)
    for component, status in cleanup_status.items():
        status_str = SHUTDOWN_STATUS_SUCCESS if status else SHUTDOWN_STATUS_FAIL
        zos.logger.framework.debug(SHUTDOWN_MSG_COMPONENT_STATUS, status_str, component)
    zos.logger.framework.debug(SHUTDOWN_SEPARATOR)
    zos.logger.framework.debug(LOG_SHUTDOWN_COMPLETE)

    print(SHUTDOWN_PRINT_COMPLETE)

    return cleanup_status


__all__ = ["perform_shutdown"]

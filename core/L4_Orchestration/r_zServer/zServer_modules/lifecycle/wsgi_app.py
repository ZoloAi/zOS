# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/wsgi_app.py

"""
WSGI Application for zServer (Waitress / external WSGI hosts).

Thin WSGI adapter. It owns ZERO routing, security, or rendering logic — every
request is driven through :class:`WSGIBridgeHandler`, which replays the SAME
pipeline the development http.server uses (SecurityChecker, StaticFileHandler,
RouteDispatcher, RBAC, styled error pages). This is what makes "trust zServer
like Flask" true: dev and prod are the same code path, only the transport
differs.

The previous implementation re-derived routing/security here and ran the router
with ``zos=None`` (no RBAC, no path/extension blocking) — a production-only
security gap. That divergence is gone: the adapter holds a live ``zserver``
(real router, real ``zos``) and delegates everything to the bridge.
"""

from typing import Any, Callable, Iterable

from ..routing.wsgi_bridge import WSGIBridgeHandler


class zServerWSGIApp:
    """WSGI application — a transport adapter over the unified request pipeline.

    Attributes:
        zserver: Live zServer instance providing router (with real zos), logger,
                 mount_manager, and cache_manager.
    """

    def __init__(self, zserver: Any):
        self.zserver = zserver
        self.logger = zserver.logger

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        try:
            handler = WSGIBridgeHandler(
                environ,
                logger=self.zserver.logger,
                router=self.zserver.router,
                mount_manager=self.zserver.mount_manager,
                cache_manager=self.zserver.cache_manager,
                config=self.zserver.config_manager,
            )
            handler.dispatch()
            start_response(handler.status_line, handler.response_headers)
            return [handler.body]
        except Exception as exc:  # pragma: no cover - last-resort safety net
            if self.logger:
                self.logger.error(
                    f"[WSGI] Unhandled error for "
                    f"{environ.get('REQUEST_METHOD')} {environ.get('PATH_INFO')}: {exc}",
                    exc_info=True,
                )
            body = b"<html><body><h1>500 Internal Server Error</h1></body></html>"
            start_response(
                "500 Internal Server Error",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ],
            )
            return [body]


__all__ = ["zServerWSGIApp"]

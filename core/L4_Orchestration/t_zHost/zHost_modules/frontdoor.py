"""Front door — turn an app identity into a URL a visitor can be sent to.

This is the seam that used to live *inside* the data plane (zServer's zProxy
route handler imported ``AppSpec`` + ``ProxyFacade`` directly). Deciding which
app to bring up and where to point the visitor is a control-plane job, so it
lives here. zServer now only asks ``zos.zhost.resolve_proxy(...)`` and performs
the 302 / interstitial.

Dev returns the woken instance's own ``host:port`` (redirect hand-off, no WS
proxying). Prod returns an ingress URL whose reverse-proxy forwards HTTP/WS —
the byte-forwarding stays in the layer built for it, never hand-rolled here.
"""

from typing import Any, Optional


class FrontDoorMixin:
    """resolve_proxy: registry row → woken instance → :class:`ProxyTarget`."""

    zos: Any

    def resolve_proxy(
        self,
        app_id: str,
        spark_path: Optional[str],
        workspace_dir: Optional[str] = None,
        timeout: float = 25.0,
    ):
        """Wake ``app_id`` and return where to reach it (wake-and-hold).

        ``spark_path`` is the registry's ``zspark_path`` for the tenant; the
        SSOT folder/spark mapping lives in :meth:`AppSpec.from_spark_path`.
        Returns a :class:`ProxyTarget` (``ready`` / ``url`` / ``state``).
        """
        # Engine still resides in the SDK this pass; import lazily so a boot that
        # never touches hosting pays nothing and never hard-couples the seam.
        from zos_plugin import AppSpec  # pylint: disable=import-outside-toplevel
        from zos_plugin.drivers import ProxyTarget, get_driver  # pylint: disable=import-outside-toplevel

        spec = AppSpec.from_spark_path(app_id, spark_path, workspace_dir=workspace_dir)
        inst = get_driver(self.zos).wake(spec, timeout=timeout)
        return ProxyTarget(
            app_id=inst.app_id,
            state=inst.state,
            url=inst.address,
            ws_url=inst.ws_url,
            error=inst.error,
        )

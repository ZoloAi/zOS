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
        build: Any = None,
    ):
        """Wake ``app_id`` and return where to reach it (wake-and-hold).

        ``spark_path`` is the registry's ``zspark_path`` for the tenant; the
        SSOT folder/spark mapping lives in :meth:`AppSpec.from_spark_path`.
        Returns a :class:`ProxyTarget` (``ready`` / ``url`` / ``state``).

        ``build`` (the registry row's active build id, when the platform tracks
        one) versions the DRIVER key: instances table as ``slug#<build>`` — the
        SAME vocabulary zRelease/zHost use for blue/green — so a repush's
        pointer flip naturally makes the front door wake the NEW build instead
        of holding a stale bare-slug record on the old child. No build → bare
        slug, exactly as before (pre-zRelease apps).
        """
        # Engine still resides in the SDK this pass; import lazily so a boot that
        # never touches hosting pays nothing and never hard-couples the seam.
        from zos_plugin import AppSpec, instance_key  # pylint: disable=import-outside-toplevel
        from zos_plugin.drivers import ProxyTarget, get_driver  # pylint: disable=import-outside-toplevel

        from zos_plugin.ingress import IngressConfig  # pylint: disable=import-outside-toplevel

        spec = AppSpec.from_spark_path(app_id, spark_path, workspace_dir=workspace_dir)
        if build not in (None, ""):
            spec.app_id = instance_key(app_id, build)
        inst = get_driver(self.zos).wake(spec, timeout=timeout)

        # Prod ingress: publish the instance behind <slug>.<domain> and hand the
        # visitor the PUBLIC url — the reverse proxy owns the byte-forwarding.
        # Not configured (dev) → the instance's own host:port hand-off, as ever.
        ingress = IngressConfig.from_env()
        if ingress and inst.running and inst.port:
            try:
                # Publish under the BARE slug — the subdomain is the app's public
                # identity; the versioned key is driver-internal only.
                public_url = ingress.publish(app_id, inst.port, inst.ws_port)
                return ProxyTarget(
                    app_id=app_id,
                    state=inst.state,
                    url=public_url,
                    ws_url=ingress.public_ws_url(app_id),
                    error=inst.error,
                )
            except Exception as exc:  # pylint: disable=broad-except
                # A wake nobody can reach is a failed wake in prod — surface it
                # rather than leaking a localhost URL to an off-box visitor.
                return ProxyTarget(
                    app_id=inst.app_id,
                    state="error",
                    error=f"ingress publish failed: {exc}",
                )

        return ProxyTarget(
            app_id=app_id,
            state=inst.state,
            url=inst.address,
            ws_url=inst.ws_url,
            error=inst.error,
        )

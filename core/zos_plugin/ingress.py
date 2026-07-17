"""Ingress — publish woken app instances behind a real domain.

The front door's dev hand-off (redirect to the instance's own ``localhost:port``)
only works when the visitor IS the box. In production the visitor reaches apps
through the reverse proxy that already fronts the platform (Caddy), so waking an
app must also *publish* it: give ``<slug>.<domain>`` a route to the instance's
private ports. The byte-forwarding stays in the proxy — this module only tells
the proxy where to point, via its localhost admin API. No sudo, no config files,
no reloads.

Enable by setting ``ZHOST_INGRESS_DOMAIN`` (e.g. ``zolo.media``) in the host
platform's environment. Everything else has working defaults:

- ``ZHOST_INGRESS_WS_PORT``  public TLS port browsers use for the WS leg
  (default 8765 — the same port the platform's own WS already rides, shared by
  every app via SNI/Host routing; one security-group hole, ever).
- ``ZHOST_CADDY_ADMIN``      Caddy admin API base (default ``http://127.0.0.1:2019``).

Two Caddy routes per app, tagged with ``@id`` so re-wakes upsert idempotently:

- ``https://<slug>.<domain>``          → ``localhost:<instance http port>``
- ``<slug>.<domain>:<ws public port>`` → ``localhost:<instance ws port>``

Caddy's automatic HTTPS obtains a certificate per subdomain on config apply —
the wildcard DNS record makes the HTTP-01 challenge resolvable, no wildcard
certificate needed.
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Environment keys (the ONLY configuration surface).
_ENV_DOMAIN = "ZHOST_INGRESS_DOMAIN"
_ENV_WS_PORT = "ZHOST_INGRESS_WS_PORT"
_ENV_CADDY_ADMIN = "ZHOST_CADDY_ADMIN"

_DEFAULT_WS_PORT = 8765
_DEFAULT_CADDY_ADMIN = "http://127.0.0.1:2019"

# Child zEnv keys the published tenant needs so its PAGES advertise the ingress
# (wss on the shared public port, origin = its own subdomain) while its WS
# server still binds the private per-instance port the driver assigned.
_ENV_WS_SSL_ENABLED = "WEBSOCKET_SSL_ENABLED"
_ENV_WS_ADVERTISED_PORT = "WEBSOCKET_ADVERTISED_PORT"
_ENV_WS_ALLOWED_ORIGINS = "WEBSOCKET_ALLOWED_ORIGINS"

# DNS label rules — an app slug IS a subdomain, so enforce the hostname grammar
# rather than discovering it as a Caddy error at wake time.
_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def slugify(app_id: str) -> str:
    """Coerce an app id into a valid DNS name fragment.

    A NAMESPACED identity (``<app>.<owner>``, claim-your-username) is dot-
    separated labels — each label is coerced/validated on its own and the dots
    survive, so the fragment nests as subdomain levels (``zblog.gal.<domain>``).
    A wildcard DNS record matches any depth (RFC 4592) and Caddy issues certs
    per exact hostname, so no infra change rides on the number of labels.
    """
    labels = []
    for part in str(app_id).lower().split("."):
        label = re.sub(r"[^a-z0-9-]+", "-", part).strip("-")
        if not _SLUG_RE.match(label):
            raise ValueError(f"app id {app_id!r} cannot form a DNS name ({part!r})")
        labels.append(label)
    return ".".join(labels)


@dataclass(frozen=True)
class IngressConfig:
    """Resolved ingress settings — built once from the environment."""

    domain: str
    ws_port: int = _DEFAULT_WS_PORT
    caddy_admin: str = _DEFAULT_CADDY_ADMIN

    @classmethod
    def from_env(cls) -> Optional["IngressConfig"]:
        """None when ingress is not configured — the dev hand-off stays as-is."""
        domain = (os.getenv(_ENV_DOMAIN) or "").strip().rstrip(".")
        if not domain:
            return None
        try:
            ws_port = int(os.getenv(_ENV_WS_PORT) or _DEFAULT_WS_PORT)
        except ValueError:
            ws_port = _DEFAULT_WS_PORT
        admin = (os.getenv(_ENV_CADDY_ADMIN) or _DEFAULT_CADDY_ADMIN).rstrip("/")
        return cls(domain=domain, ws_port=ws_port, caddy_admin=admin)

    # -- public naming --------------------------------------------------------

    def hostname(self, app_id: str) -> str:
        return f"{slugify(app_id)}.{self.domain}"

    def public_url(self, app_id: str) -> str:
        return f"https://{self.hostname(app_id)}"

    def public_ws_url(self, app_id: str) -> str:
        return f"wss://{self.hostname(app_id)}:{self.ws_port}"

    # -- child environment ----------------------------------------------------

    def child_env(self, app_id: str) -> Dict[str, str]:
        """Extra zEnv the driver must inject into a published tenant's process.

        The child binds its WS on the private port the driver assigned; these
        keys only change what its pages ADVERTISE to browsers: wss on the
        shared ingress port, origin locked to its own subdomain.
        """
        return {
            _ENV_WS_SSL_ENABLED: "true",
            _ENV_WS_ADVERTISED_PORT: str(self.ws_port),
            _ENV_WS_ALLOWED_ORIGINS: self.public_url(app_id),
        }

    # -- Caddy admin API ------------------------------------------------------

    def _admin(self, method: str, path: str, payload: Any = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.caddy_admin}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # localhost only
            raw = resp.read()
        return json.loads(raw) if raw else None

    def _servers(self) -> Dict[str, Any]:
        return self._admin("GET", "/config/apps/http/servers") or {}

    def _server_for_port(self, port: int) -> Optional[str]:
        """Find the Caddy server whose listener carries ``:port``."""
        for name, server in self._servers().items():
            for addr in server.get("listen") or []:
                if str(addr).endswith(f":{port}"):
                    return name
        return None

    def _upsert_route(self, server: str, route_id: str, host: str, upstream_port: int) -> None:
        """Idempotently (re)install one host-matched reverse-proxy route."""
        try:
            self._admin("DELETE", f"/id/{route_id}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:  # 404 = first publish, nothing to replace
                raise
        route = {
            "@id": route_id,
            "match": [{"host": [host]}],
            "handle": [{
                "handler": "reverse_proxy",
                "upstreams": [{"dial": f"localhost:{upstream_port}"}],
            }],
            "terminal": True,
        }
        self._admin("POST", f"/config/apps/http/servers/{server}/routes", route)

    # -- TLS readiness ---------------------------------------------------------

    def tls_servable(self, app_id: str, timeout: float = 15.0) -> bool:
        """True once the app's hostname completes a VERIFIED TLS handshake.

        First publish of a hostname triggers on-demand ACME issuance, which
        takes seconds — a 302 issued before the cert exists lands the visitor
        on a browser SSL error (found live: cold zRM wake). This probe does
        exactly what the visitor's browser will do (SNI + chain + hostname
        verification) against the local proxy, so "True" means the redirect
        is actually followable. Budget via ``ZHOST_INGRESS_TLS_TIMEOUT``.
        """
        host = self.hostname(app_id)
        try:
            budget = float(os.getenv("ZHOST_INGRESS_TLS_TIMEOUT") or timeout)
        except ValueError:
            budget = timeout
        ctx = ssl.create_default_context()
        deadline = time.time() + budget
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", 443), timeout=3) as raw:
                    with ctx.wrap_socket(raw, server_hostname=host):
                        return True
            except (ssl.SSLError, OSError):
                time.sleep(0.5)
        return False

    def publish(self, app_id: str, http_port: int, ws_port: int) -> str:
        """Point ``<slug>.<domain>`` (HTTP + WS legs) at a woken instance.

        Returns the public URL. Raises on any admin-API failure — the caller
        decides whether an unpublished wake is still useful (it isn't, in prod).
        """
        slug = slugify(app_id)
        host = self.hostname(app_id)

        https_server = self._server_for_port(443)
        if not https_server:
            raise RuntimeError("ingress: no Caddy server listening on :443")
        self._upsert_route(https_server, f"zhost_{slug}_http", host, http_port)

        ws_server = self._server_for_port(self.ws_port)
        if not ws_server:
            raise RuntimeError(f"ingress: no Caddy server listening on :{self.ws_port}")
        self._upsert_route(ws_server, f"zhost_{slug}_ws", host, ws_port)

        return self.public_url(app_id)

    def unpublish(self, app_id: str) -> None:
        """Remove an app's routes (sleep/teardown). Missing routes are fine."""
        slug = slugify(app_id)
        for route_id in (f"zhost_{slug}_http", f"zhost_{slug}_ws"):
            try:
                self._admin("DELETE", f"/id/{route_id}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise


def ingress_child_env(app_id: str) -> Dict[str, str]:
    """Driver hook: extra child env when ingress is configured, else empty."""
    cfg = IngressConfig.from_env()
    return cfg.child_env(app_id) if cfg else {}

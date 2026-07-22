# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_http_server.py
"""HTTP Server Configuration Module"""

from zOS import Any, Dict, Optional, os
from zSys.Utils import print_ready_message
from zSys.logger import (
    resolve_deployment_from_zspark,
    DEPLOYMENT_PRODUCTION,
    DEPLOYMENT_TESTING,
    DEPLOYMENT_INFO,
)

# Module Constants

# Logging
_LOG_PREFIX = "[HttpServerConfig]"
_SUBSYSTEM_NAME = "HttpServerConfig"
_READY_MESSAGE = "zServer Ready"

# Config Section (v1.5.7: Renamed from 'http_server' to match subsystem name)
_CONFIG_SECTION_KEY = "zServer"  # Supports both http.server (Dev) and Waitress/WSGI (Prod)

# Config Keys
_KEY_HOST = "host"
_KEY_PORT = "port"
_KEY_SERVE_PATH = "serve_path"
_KEY_MOUNTS = "mounts"  # Canonical custom-mount block: zServer.mounts: {name: zPath}
_KEY_ROUTES_FILE = "routes_file"
_KEY_ENABLED = "enabled"
_KEY_TYPE = "type"  # Server runner type (dev/waitress) — see server_type SSOT
_KEY_WSGI = "wsgi"  # RETIRED key (see WSGI note) — kept only for deprecation detection
KEY_ZSHELL = "zShell"  # v1.5.8: Drop into zShell REPL (default: False = silent blocking)
_KEY_MAX_BODY_BYTES = "max_body_bytes"  # Request-body cap (anti-DoS), shared by both runners
_KEY_CORS_ORIGIN = "cors_origin"        # Cross-origin allowance (empty = same-origin only)

# Server runner types (Axis B — selects WHICH server BINDS the socket, decoupled
# from the environment NAME). Every runner binds a port and serves the SAME app;
# only the transport differs. The request pipeline, security checks, and RBAC are
# identical across all of them.
#
# NOTE: WSGI is NOT a runner and NOT a zServer mode. WSGI is the PEP 3333 calling
# convention that these servers speak to the app callable (zServer.get_wsgi_app()).
# To serve zOS via an EXTERNAL host (uWSGI / serverless / any systemd-managed WSGI host),
# the host imports the app's static `wsgi.py` (exposing `app = get_wsgi_app()`) and
# binds the socket itself — there is no zOS-side "wsgi" mode to enable.
#
# Both runners are SINGLE-PROCESS: the in-process server and the single stateful
# Bifrost WebSocket bridge coexist in one process. Multi-process prefork servers
# (e.g. gunicorn) are intentionally NOT runners — each fork would boot a competing
# WS bridge. Scale zBifrost horizontally (N instances + sticky LB), not by forking.
SERVER_TYPE_DEV = "dev"            # Python http.server in a background thread (local)
SERVER_TYPE_WAITRESS = "waitress"  # Waitress WSGI server, in-process (cross-platform prod)
VALID_SERVER_TYPES = {SERVER_TYPE_DEV, SERVER_TYPE_WAITRESS}
DEFAULT_SERVER_TYPE = SERVER_TYPE_DEV  # Safe floor: most local, least exposed
ENV_VAR_ZSERVER_TYPE = "ZSERVER_TYPE"  # Per-environment runner default (.zEnv)

# RETIRED: the `wsgi` runner token and the headless-export switch. `wsgi` was once a
# 4th "server type" / a bind-nothing posture, but that's a category mismatch (WSGI is
# a calling convention, not a server). The capability lives on as get_wsgi_app() + a
# static wsgi.py the external host imports. These names are kept ONLY to detect stale
# config and emit a one-time deprecation warning steering operators to the new model.
LEGACY_SERVER_TYPE_WSGI = "wsgi"
ENV_VAR_ZSERVER_WSGI = "ZSERVER_WSGI_EXPOSE"  # retired .zEnv switch (deprecation detection only)

# Default Values
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
# Port hunting window (zOS#43): when the port is UNPINNED (no zSpark/zEnv/env
# value — the bare code default) and taken, the runner may walk up to this many
# consecutive ports (8080→8099, WS 8765→8784) before failing. A PINNED port is
# never hunted — pinned means deployments point at it. SSOT for both legs:
# config_websocket and zGuard's bifrost import this value, don't redefine it.
PORT_HUNT_WINDOW = 20
DEFAULT_SERVE_PATH = "."
DEFAULT_ROUTES_FILE = None
DEFAULT_ENABLED = False
DEFAULT_ZSHELL = False  # v1.5.8: Default to silent blocking (standard server behavior)
DEFAULT_SSL_ENABLED = False  # v1.5.10: SSL disabled by default for local development
DEFAULT_SSL_CERT = None
DEFAULT_SSL_KEY = None

# Request-body cap (anti-DoS). SSOT for BOTH runners (dev http.server + WSGI bridge):
# a hostile Content-Length must never let a single request exhaust worker memory.
# Mirrors Flask's MAX_CONTENT_LENGTH — "trust zServer like Flask" includes this floor.
DEFAULT_MAX_BODY_BYTES = 25 * 1024 * 1024  # 25 MB

# CORS allowance. Empty string = SAME-ORIGIN ONLY (no Access-Control-Allow-Origin
# header emitted) — the safe default, since the zApp GUI/bifrost client are served
# from the same origin. Opt in explicitly to a trusted origin (or "*") when an app
# genuinely needs cross-origin reads; we never ship a wildcard by default.
DEFAULT_CORS_ORIGIN = ""

# Environment Variables
ENV_VAR_HTTP_HOST = "HTTP_HOST"            # Host floor (.zEnv / ops)
ENV_VAR_HTTP_PORT = "HTTP_PORT"            # Port floor (.zEnv / ops)
# Platform-managed marker (zOS #28). Set by the hosting compute driver when it
# spawns a tenant child with per-instance ports. When present, the injected
# HTTP/WS host+port env vars BEAT zSpark pins: on a local machine the author's
# spark is king (their ports, their business), but a hosted instance's network
# identity belongs to the platform — a pinned port would boot the child
# somewhere the driver never polls (eternal "waking", found live: zhornet).
ENV_VAR_ZHOST_MANAGED = "ZHOST_MANAGED"
ENV_VAR_ZSERVER_ENABLED = "ZSERVER_ENABLED"  # Enable floor (.zEnv / ops)
ENV_VAR_HTTP_SSL_ENABLED = "HTTP_SSL_ENABLED"
ENV_VAR_HTTP_SSL_CERT = "HTTP_SSL_CERT"
ENV_VAR_HTTP_SSL_KEY = "HTTP_SSL_KEY"
ENV_VAR_ZSERVER_MOUNTS = "ZSERVER_MOUNTS"  # v1.5.11: Static mount points
ENV_VAR_MAX_BODY_BYTES = "ZSERVER_MAX_BODY_BYTES"  # Override request-body cap (.zEnv)
ENV_VAR_CORS_ORIGIN = "ZSERVER_CORS_ORIGIN"        # Override CORS origin (.zEnv)

# Canonical zServer-block → env-var bridge (SSOT for the mapping).
# A declarative `zServer:` block in any zEnv layer is expanded through THIS map
# into os.environ by config_zenv, so authors write the SAME grammar in zSpark and
# every zEnv (base/development/production). Per-key layering falls out of the
# base→env load order; ops can still set the raw env vars directly (Docker/K8s/
# systemd). Keys not listed pass through as ZSERVER_<KEY>.
ZSERVER_BLOCK_ENV_MAP = {
    "enabled":        ENV_VAR_ZSERVER_ENABLED,
    "host":           ENV_VAR_HTTP_HOST,
    "port":           ENV_VAR_HTTP_PORT,
    "type":           ENV_VAR_ZSERVER_TYPE,
    "mounts":         ENV_VAR_ZSERVER_MOUNTS,
    "cors_origin":    ENV_VAR_CORS_ORIGIN,
    "max_body_bytes": ENV_VAR_MAX_BODY_BYTES,
}

# Truthy values for boolean environment variables
TRUTHY_VALUES = {'true', '1', 'yes', 'on'}


class HttpServerConfig:
    """
    Configuration for zServer (HTTP + WSGI deployment).
    
    Manages zServer settings from zSpark configuration with sensible defaults.
    Supports both Development (http.server) and Production (Waitress/WSGI) modes.
    
    Configuration Key: 'zServer' (backward compatible with 'http_server')
    
    Attributes:
        host: Server host address
        port: Server port
        serve_path: Directory to serve files from
        routes_file: Optional routes configuration file (auto-detected if not specified)
        enabled: Whether zServer is enabled (if True, server ALWAYS waits)
        zShell: Whether to drop into zShell REPL (False = silent blocking)
    """

    # Type hints for instance attributes
    logger: Any
    host: str
    port: int
    serve_path: str
    routes_file: Optional[str]
    enabled: bool
    server_type: str  # Runner that binds the socket (dev/waitress) — SSOT resolved below
    zShell: bool  # v1.5.8: Drop into zShell REPL (default: False)
    ssl_enabled: bool  # v1.5.10: HTTPS support
    ssl_cert: Optional[str]  # v1.5.10: SSL certificate path
    ssl_key: Optional[str]  # v1.5.10: SSL key path
    static_mounts: Dict[str, str]  # v1.5.11: Multi-mount support {url_prefix: fs_path}
    max_body_bytes: int  # Request-body cap (anti-DoS), shared by both runners
    cors_origin: str  # CORS origin allowance ("" = same-origin only)
    _verbose: bool

    def __init__(self, zspark_obj: Dict[str, Any], logger: Any, verbose: bool = False) -> None:
        """
        Initialize zServer configuration.
        
        Args:
            zspark_obj: zSpark configuration dictionary (looks for 'zServer' key)
            logger: Logger instance for configuration logging
            verbose: If True, show initialization output (default: False)
        """
        self.logger = logger
        self._verbose = verbose

        # Get zServer config from zSpark (v1.5.7: Supports 'zServer' key, backward compatible with 'http_server')
        http_config = zspark_obj.get(_CONFIG_SECTION_KEY, {})

        # Backward compatibility: Check for old 'http_server' key if 'zServer' not found
        if not http_config and "http_server" in zspark_obj:
            http_config = zspark_obj.get("http_server", {})
            self.logger.framework.debug("[HttpServerConfig] Using deprecated 'http_server' key (use 'zServer' instead)")

        # Set configuration with defaults.
        # SSOT cascade (king → floor), SYMMETRIC for host and port:
        #   zSpark.zServer.{host,port} → {HTTP_HOST,HTTP_PORT} env (.zEnv) → DEFAULT
        # host previously skipped the env tier and jumped to DEFAULT_HOST, so a
        # base/env HTTP_HOST (e.g. 'localhost') was silently dropped — causing a
        # localhost↔127.0.0.1 origin mismatch vs the WS host. Now host honors the
        # same cascade as port (base unique values flow through every runner).
        env_http_host = os.getenv(ENV_VAR_HTTP_HOST)
        default_host = env_http_host if env_http_host else DEFAULT_HOST
        env_http_port = os.getenv(ENV_VAR_HTTP_PORT)
        default_port = int(env_http_port) if env_http_port else DEFAULT_PORT
        self.host = http_config.get(_KEY_HOST, default_host)
        self.port = http_config.get(_KEY_PORT, default_port)
        # Pinned vs zOS-decides (port hunting, zOS#43): remember WHY this port
        # value exists. A port that arrived from zSpark/zEnv/env is a PIN —
        # sacred, never hunted off (deployments, launchd, Caddy all point at
        # it). Only the bare code default is huntable: "the user said nothing,
        # zOS decides". Recorded here because after this line the int alone
        # can't tell pinned-8080 from defaulted-8080.
        self.port_pinned = (_KEY_PORT in http_config) or bool(env_http_port)
        # Platform-managed instance (zOS #28): the driver's injected host/port
        # win over any spark pin — local boots have no marker and keep the
        # spark-king cascade above untouched.
        if os.getenv(ENV_VAR_ZHOST_MANAGED, "").strip().lower() in TRUTHY_VALUES:
            if env_http_port and self.port != int(env_http_port):
                self.logger.warning(
                    f"{_LOG_PREFIX} zServer.port {self.port} overridden by the "
                    f"hosting platform → {env_http_port} ({ENV_VAR_ZHOST_MANAGED})")
                self.port = int(env_http_port)
            if env_http_host and self.host != env_http_host:
                self.host = env_http_host
        self.serve_path = http_config.get(_KEY_SERVE_PATH, DEFAULT_SERVE_PATH)
        self.routes_file = http_config.get(_KEY_ROUTES_FILE, DEFAULT_ROUTES_FILE)
        # enabled cascade (king → floor): zSpark.zServer.enabled → ZSERVER_ENABLED
        # env (.zEnv) → DEFAULT. Lets a zEnv `zServer.enabled` flip the server on/off
        # per environment, same as host/port/type.
        env_enabled = os.getenv(ENV_VAR_ZSERVER_ENABLED)
        default_enabled = (env_enabled.strip().lower() in TRUTHY_VALUES) if env_enabled is not None else DEFAULT_ENABLED
        self.enabled = http_config.get(_KEY_ENABLED, default_enabled)
        self.zShell = http_config.get(KEY_ZSHELL, DEFAULT_ZSHELL)  # v1.5.8: Interactive mode

        # SSL Configuration (v1.5.10: HTTPS support with deployment-aware defaults)
        # Environment variables from .zEnv (base or deployment-specific)
        env_ssl_enabled = os.getenv(ENV_VAR_HTTP_SSL_ENABLED)
        env_ssl_cert = os.getenv(ENV_VAR_HTTP_SSL_CERT)
        env_ssl_key = os.getenv(ENV_VAR_HTTP_SSL_KEY)

        # Check deployment mode from zSpark (determines auto-SSL behavior).
        # SSOT: zSys.logger owns the deployment-mode vocabulary + env fallback.
        deployment = resolve_deployment_from_zspark(zspark_obj)
        is_production = deployment.lower() == DEPLOYMENT_PRODUCTION
        is_testing = deployment.lower() in (DEPLOYMENT_TESTING, DEPLOYMENT_INFO)

        # Raw runner token (zSpark king → ZSERVER_TYPE env).
        raw_type = (http_config.get(_KEY_TYPE) or os.getenv(ENV_VAR_ZSERVER_TYPE) or "").strip().lower()

        # Deprecation: warn (don't act) on any stale `wsgi`-as-mode config. The
        # external-host path is now a static wsgi.py, not a zServer mode.
        self._warn_legacy_wsgi(http_config, raw_type)

        # Server runner that BINDS the socket. Decoupled from the environment NAME:
        # the same app deploys across free-form zEnvs; the runner is chosen by an
        # explicit key, not inferred from the env's identity.
        self.server_type = self._resolve_server_type(raw_type, is_production)

        # Deployment-aware SSL defaults (v1.5.10):
        # - Explicit env var (HTTP_SSL_ENABLED) → highest priority
        # - Production + certs present → auto-enable HTTPS
        # - Development or no certs → disable HTTPS
        if env_ssl_enabled is not None:
            # Explicit env var takes precedence
            self.ssl_enabled = env_ssl_enabled.lower() in TRUTHY_VALUES
        elif is_production and env_ssl_cert and env_ssl_key:
            # Production + certs present = auto-enable SSL
            self.ssl_enabled = True
            self.logger.framework.debug(
                f"{_LOG_PREFIX} Production mode: SSL auto-enabled (certs detected)"
            )
        else:
            # Development or no certs = disable SSL
            self.ssl_enabled = DEFAULT_SSL_ENABLED

        self.ssl_cert = env_ssl_cert if env_ssl_cert else DEFAULT_SSL_CERT
        self.ssl_key = env_ssl_key if env_ssl_key else DEFAULT_SSL_KEY

        if self.ssl_enabled:
            self.logger.framework.debug(f"{_LOG_PREFIX} SSL enabled: {self.ssl_enabled}")
            if self.ssl_cert:
                self.logger.framework.debug(f"{_LOG_PREFIX} SSL cert: {self.ssl_cert}")
            if self.ssl_key:
                self.logger.framework.debug(f"{_LOG_PREFIX} SSL key: {self.ssl_key}")

        # Static Mounts Configuration — custom URL-prefix → folder mappings.
        # Canonical grammar (string-first, declarative) is a `zServer.mounts:` block:
        #     zServer:
        #       mounts:
        #         downloads: @.files          # zPath under the app root (zSpace)
        #         media: @.assets/media
        #         archive: /srv/shared/pdfs   # absolute = external host
        # Bare-name keys become URL prefixes (downloads → /downloads/); values are
        # zPaths resolved against the app root (zSpace) by MountManager — the SAME
        # single anchor serve_path uses.
        #   • canonical: zSpark/zEnv `zServer.mounts:` block (http_config[_KEY_MOUNTS]).
        #   • transport: ZSERVER_MOUNTS env — how a zEnv `zServer.mounts` block reaches
        #     here (expanded by config_zenv) AND the ops escape hatch (Docker/K8s).
        #   • DEPRECATED: a top-level `ZSERVER_MOUNTS:` dict in zSpark (pre-block form).
        env_mounts = os.getenv(ENV_VAR_ZSERVER_MOUNTS)
        top_level_mounts = zspark_obj.get('ZSERVER_MOUNTS', {})
        if top_level_mounts:
            self.logger.framework.debug(
                f"{_LOG_PREFIX} top-level ZSERVER_MOUNTS is deprecated — use a zServer.mounts: block"
            )
        canonical_mounts = http_config.get(_KEY_MOUNTS, {})
        self.static_mounts = self._parse_static_mounts(env_mounts or top_level_mounts, canonical_mounts)

        # Request-body cap (anti-DoS). Cascade: zSpark.zServer.max_body_bytes →
        # ZSERVER_MAX_BODY_BYTES env → DEFAULT. 0/negative disables the cap (opt-out).
        env_max_body = os.getenv(ENV_VAR_MAX_BODY_BYTES)
        try:
            default_max_body = int(env_max_body) if env_max_body else DEFAULT_MAX_BODY_BYTES
        except (TypeError, ValueError):
            default_max_body = DEFAULT_MAX_BODY_BYTES
        try:
            self.max_body_bytes = int(http_config.get(_KEY_MAX_BODY_BYTES, default_max_body))
        except (TypeError, ValueError):
            self.max_body_bytes = default_max_body

        # CORS origin allowance. Cascade: zSpark.zServer.cors_origin →
        # ZSERVER_CORS_ORIGIN env → "" (same-origin only). Never a wildcard default.
        env_cors = os.getenv(ENV_VAR_CORS_ORIGIN)
        default_cors = env_cors if env_cors is not None else DEFAULT_CORS_ORIGIN
        self.cors_origin = str(http_config.get(_KEY_CORS_ORIGIN, default_cors) or "").strip()

        # Log configuration
        if self.enabled:
            self.logger.info(f"{_LOG_PREFIX} Enabled - {self.host}:{self.port} (runner: {self.server_type})")
            self.logger.info(f"{_LOG_PREFIX} Serve path: {self.serve_path}")
            if self.routes_file:
                self.logger.info(f"{_LOG_PREFIX} Routes file: {self.routes_file}")
        else:
            self.logger.framework.debug(f"{_LOG_PREFIX} HTTP server disabled")

        # Print ready message (shown in Development mode only, not Testing or Production).
        # Pass explicit flags so print_ready_message doesn't self-resolve and override
        # the verbose force-show path (verbose => treat as non-prod for this banner).
        if verbose or not (is_production or is_testing):
            print_ready_message(
                _READY_MESSAGE, color="CONFIG",
                is_production=False if verbose else is_production,
                is_testing=False if verbose else is_testing,
            )

    def _warn_legacy_wsgi(self, http_config: Dict[str, Any], raw_type: str) -> None:
        """Emit a deprecation warning for any retired `wsgi`-as-mode configuration.

        RETIRED: `zServer.type: wsgi`, `ZSERVER_TYPE: wsgi`, `zServer.wsgi: true`, and
        `ZSERVER_WSGI_EXPOSE`. WSGI is a calling convention, not a zServer mode. To be
        served by an external host, ship a static `wsgi.py` (`app = get_wsgi_app()`)
        and point the host at `wsgi:app`. This method only warns — it does not change
        behavior; the app still runs a normal binding runner (server_type).
        """
        triggered = (
            _KEY_WSGI in http_config
            or os.getenv(ENV_VAR_ZSERVER_WSGI) is not None
            or raw_type == LEGACY_SERVER_TYPE_WSGI
        )
        if triggered:
            self.logger.warning(
                f"{_LOG_PREFIX} RETIRED config: 'wsgi' is not a zServer mode/type. "
                f"WSGI is a calling convention — to be served by an external host, ship a "
                f"static wsgi.py exposing `app = zOS(<zSpark>).server.get_wsgi_app()` and "
                f"point the host at 'wsgi:app'. The wsgi flag is IGNORED; zServer runs a "
                f"normal binding runner (dev/waitress). Remove zServer.wsgi / "
                f"{ENV_VAR_ZSERVER_WSGI} / type:wsgi from your config."
            )

    def _resolve_server_type(self, raw_type: str, legacy_is_production: bool) -> str:
        """Resolve the binding server runner (Axis B, SSOT precedence).

        Precedence (king → floor):
            1. zSpark.zServer.type        — explicit override, wins all
            2. ZSERVER_TYPE env (.zEnv)   — per-environment default
            3. DEFAULT_SERVER_TYPE (dev)  — safe floor

        The runner selects WHICH server binds the socket (threaded http.server /
        Waitress), decoupled from the environment NAME. The retired `wsgi` token
        is handled by _warn_legacy_wsgi, not here. Unknown values fail safe to
        'dev' (most local, least exposed).

        Legacy bridge: if no explicit type is set but the deployment is Production,
        default to 'waitress' (cross-platform, single-process) with a deprecation
        warning.
        """
        if raw_type and raw_type != LEGACY_SERVER_TYPE_WSGI:
            if raw_type in VALID_SERVER_TYPES:
                return raw_type
            self.logger.warning(
                f"{_LOG_PREFIX} Unknown server type '{raw_type}' "
                f"(expected one of {sorted(VALID_SERVER_TYPES)}); "
                f"falling back to '{DEFAULT_SERVER_TYPE}'"
            )
            return DEFAULT_SERVER_TYPE

        if legacy_is_production:
            self.logger.warning(
                f"{_LOG_PREFIX} No zServer.type / ZSERVER_TYPE set but deployment is "
                f"Production — defaulting to '{SERVER_TYPE_WAITRESS}'. "
                f"DEPRECATED: set zServer.type (zSpark) or ZSERVER_TYPE (.zEnv) explicitly."
            )
            return SERVER_TYPE_WAITRESS

        return DEFAULT_SERVER_TYPE

    def _parse_static_mounts(self, legacy_mounts: Any, canonical_mounts: Any = None) -> Dict[str, str]:
        """
        Parse custom static-mount config into {url_prefix: declared_path}.

        Declared paths are kept VERBATIM (zPath strings like `@.files` or absolute
        paths). They are resolved to absolute filesystem paths later by
        MountManager, anchored on the app root (zSpace) — the SINGLE mount anchor
        (the same one serve_path uses). This module only validates shape and
        normalizes URL prefixes (bare "downloads" → "/downloads/").

        Sources (canonical wins on key collision):
            legacy_mounts    — deprecated ZSERVER_MOUNTS (env JSON string or dict)
            canonical_mounts — zServer.mounts: block (preferred grammar)

        Returns:
            Dict of {url_prefix: declared_path_string} (unresolved zPaths)
        """
        import json

        def _coerce(cfg: Any) -> Dict[str, Any]:
            # .zEnv ships ZSERVER_MOUNTS as a JSON string; zSpark blocks arrive as dicts.
            if isinstance(cfg, str):
                try:
                    return json.loads(cfg)
                except json.JSONDecodeError:
                    self.logger.warning(f"{_LOG_PREFIX} Invalid ZSERVER_MOUNTS (not valid JSON), ignoring")
                    return {}
            if cfg and not isinstance(cfg, dict):
                self.logger.warning(f"{_LOG_PREFIX} mounts must be a mapping, got {type(cfg)}")
                return {}
            return cfg or {}

        merged: Dict[str, Any] = {}
        merged.update(_coerce(legacy_mounts))
        merged.update(_coerce(canonical_mounts))  # canonical overlays legacy

        validated: Dict[str, str] = {}
        for url_prefix, fs_path in merged.items():
            if not isinstance(fs_path, str) or not fs_path.strip():
                self.logger.warning(f"{_LOG_PREFIX} Mount '{url_prefix}' has no path, skipping")
                continue
            # Normalize bare keys: "downloads" → "/downloads/" (slashes optional).
            key = str(url_prefix).strip()
            # An empty or root-only key ("" / "/") can't name a mount — a root mount
            # would shadow every route/default — so skip it rather than register "/".
            if not key or key == '/':
                self.logger.warning(
                    f"{_LOG_PREFIX} Mount key '{url_prefix}' is empty/root, skipping "
                    "(a mount needs a name, e.g. downloads:)"
                )
                continue
            if not key.startswith('/'):
                key = '/' + key
            if not key.endswith('/'):
                key = key + '/'
            validated[key] = fs_path.strip()

        return validated

    def __repr__(self) -> str:
        """Return string representation of HttpServerConfig instance."""
        return f"HttpServerConfig(host={self.host}, port={self.port}, enabled={self.enabled})"

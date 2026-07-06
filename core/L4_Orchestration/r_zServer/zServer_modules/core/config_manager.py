# zOS/core/L4_Orchestration/r_zServer/zServer_modules/core/config_manager.py

"""
ConfigManager - Server configuration management for zServer

Handles:
- Configuration extraction from HttpServerConfig
- Path resolution (serve_path)
- Deployment mode detection
- SSL configuration

Note: Mount management (static, templates, UI folders) moved to MountManager.
"""

from ..utils.zserver_constants import MODE_DEVELOPMENT


class ConfigManager:
    """
    Manages zServer configuration (server settings only).
    
    Extracts and validates configuration from HttpServerConfig object.
    Mount management delegated to MountManager for SSOT.
    """

    def __init__(self, config, zos, logger):
        """
        Initialize ConfigManager.
        
        Args:
            config: HttpServerConfig instance from zConfig
            zos: zOS instance (for deployment mode detection)
            logger: zOS logger instance
        """
        self.config = config
        self.zos = zos
        self.logger = logger

        # Extract configuration from config object
        self.enabled = config.enabled
        self.port = config.port
        self.host = config.host
        self.routes_file = config.routes_file

        # Server runner that BINDS the socket (dev/waitress) — resolved SSOT
        # in HttpServerConfig (zSpark.zServer.type → ZSERVER_TYPE → dev). To serve via
        # an external host, ship a static wsgi.py (zServer.get_wsgi_app()) — not a mode.
        self.server_type = getattr(config, "server_type", "dev")

        # SSL Configuration
        self.ssl_enabled = config.ssl_enabled
        self.ssl_cert = config.ssl_cert
        self.ssl_key = config.ssl_key

        # Static Mounts (passed to MountManager)
        self.static_mounts = config.static_mounts.copy() if config.static_mounts else {}

        # Response policy SSOT (resolved in HttpServerConfig): request-body cap +
        # CORS origin. Mirrored here so request handlers read one config object.
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_http_server import (
            DEFAULT_MAX_BODY_BYTES,
            DEFAULT_CORS_ORIGIN,
        )
        self.max_body_bytes = getattr(config, "max_body_bytes", DEFAULT_MAX_BODY_BYTES)
        self.cors_origin = getattr(config, "cors_origin", DEFAULT_CORS_ORIGIN)

        # Resolve serve_path
        self.serve_path = self._resolve_serve_path(config.serve_path)

    def _resolve_serve_path(self, serve_path):
        """
        Resolve serve_path to an absolute path, anchored on the app root (zSpace).

        SSOT: the application root is zSpace (zSpark.zSpace, else cwd) — the SAME
        root every `@.` zPath resolves against. serve_path is NOT an independent
        app-root knob; it defaults to zSpace and, when given, is interpreted
        relative to it (absolute paths are honored as-is). This keeps zServer's
        route discovery, static serving, and zAPI scan on the one workspace
        truth instead of a separate cwd resolve that could silently diverge from
        zSpace (e.g. when zSpace is set but serve_path is not).

        Args:
            serve_path: Optional override (relative → under zSpace, absolute → as-is)

        Returns:
            str: Resolved absolute path
        """
        # App root = zSpace (SSOT), with the same cwd fallback zConfig uses.
        try:
            from zOS import os as _os
        except Exception:  # pragma: no cover - defensive
            import os as _os
        from zOS.zPath import resolve_folder

        session = getattr(self.zos, "session", None) or {}
        zspace = session.get("zSpace") or _os.getcwd()

        # One rule for "@./bare/absolute/'.'" — the same primitive mounts use.
        return resolve_folder(serve_path, zspace)

    def get_deployment_mode(self) -> str:
        """
        Get deployment mode from zOS config.
        
        Returns:
            str: Deployment mode ("Development", "Testing", or "Production")
        """
        if not self.zos or not hasattr(self.zos, 'config'):
            return MODE_DEVELOPMENT
        return self.zos.config.get_environment("deployment", MODE_DEVELOPMENT)

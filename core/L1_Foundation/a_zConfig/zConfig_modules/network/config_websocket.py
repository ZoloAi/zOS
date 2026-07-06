# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_websocket.py
"""WebSocket configuration management as part of zConfig."""

from zOS import os, Any, Dict, List, Optional
from zSys.Utils import print_ready_message, validate_zos_instance
from zSys.logger import resolve_deployment_from_zspark, DEPLOYMENT_PRODUCTION

# Loopback SSOT: the WS leg inherits the HTTP server's canonical bind host so the
# two legs can never drift to different origins (127.0.0.1 vs localhost). Safe at
# module level — config_http_server never imports back into this module.
from .config_http_server import DEFAULT_HOST as _LOOPBACK_HOST

# Module Constants

# Logging
_LOG_PREFIX = "[WebSocketConfig]"
_SUBSYSTEM_NAME = "WebSocketConfig"
_READY_MESSAGE = "zSocket Ready"

# Config Section
# zSpark/zEnv canonical block is `zSocket:` (z-branded, parallel to `zServer:`).
# `websocket:` is the deprecated alias kept for back-compat.
_CONFIG_SECTION_KEY = "zSocket"
_CONFIG_SECTION_KEY_LEGACY = "websocket"

# Environment Variables
_ENV_VAR_HOST = "WEBSOCKET_HOST"
_ENV_VAR_PORT = "WEBSOCKET_PORT"
_ENV_VAR_REQUIRE_AUTH = "WEBSOCKET_REQUIRE_AUTH"
_ENV_VAR_ALLOWED_ORIGINS = "WEBSOCKET_ALLOWED_ORIGINS"
_ENV_VAR_TOKEN = "WEBSOCKET_TOKEN"
_ENV_VAR_SSL_ENABLED = "WEBSOCKET_SSL_ENABLED"
_ENV_VAR_SSL_CERT = "WEBSOCKET_SSL_CERT"
_ENV_VAR_SSL_KEY = "WEBSOCKET_SSL_KEY"

# Config Keys
_KEY_HOST = "host"
_KEY_PORT = "port"
_KEY_REQUIRE_AUTH = "require_auth"
_KEY_ALLOWED_ORIGINS = "allowed_origins"
_KEY_TOKEN = "token"
_KEY_MAX_CONNECTIONS = "max_connections"
_KEY_PING_INTERVAL = "ping_interval"
_KEY_PING_TIMEOUT = "ping_timeout"
_KEY_SSL_ENABLED = "ssl_enabled"
_KEY_SSL_CERT = "ssl_cert"
_KEY_SSL_KEY = "ssl_key"

# Canonical zSocket-block → env-var bridge (SSOT for the mapping). Mirrors
# config_http_server.ZSERVER_BLOCK_ENV_MAP: a declarative `zSocket:` block in zSpark
# or any zEnv layer is expanded through THIS map into os.environ by config_zenv, so
# authors write the SAME grammar everywhere and per-key layering falls out of the
# base→env load order. Keys not listed pass through as WEBSOCKET_<KEY>.
ZSOCKET_BLOCK_ENV_MAP = {
    "host":            _ENV_VAR_HOST,
    "port":            _ENV_VAR_PORT,
    "require_auth":    _ENV_VAR_REQUIRE_AUTH,
    "allowed_origins": _ENV_VAR_ALLOWED_ORIGINS,
    "token":           _ENV_VAR_TOKEN,
    "ssl_enabled":     _ENV_VAR_SSL_ENABLED,
    "ssl_cert":        _ENV_VAR_SSL_CERT,
    "ssl_key":         _ENV_VAR_SSL_KEY,
}

# Default Values
# Public WS defaults — the single SSOT consumed everywhere, including zGuard's
# bifrost fallback and the zServer page-injection fallback. Don't redefine these
# literals elsewhere; import from here instead.
DEFAULT_HOST = _LOOPBACK_HOST  # inherits zServer's canonical loopback (127.0.0.1)
DEFAULT_PORT = 8765  # Standard WebSocket development port (matches zComm primitives)

# Private aliases kept for existing internal references in this module.
_DEFAULT_HOST = DEFAULT_HOST
_DEFAULT_PORT = DEFAULT_PORT
_DEFAULT_REQUIRE_AUTH = False  # Security is opt-in, not opt-out (better UX for beginners)
_DEFAULT_ALLOWED_ORIGINS: List[str] = []
_DEFAULT_TOKEN = ""  # Empty by default - configure via .zEnv or env vars
_DEFAULT_MAX_CONNECTIONS = 100
_DEFAULT_PING_INTERVAL = 20
_DEFAULT_PING_TIMEOUT = 10
_DEFAULT_SSL_ENABLED = False  # SSL disabled by default for easier local development
_DEFAULT_SSL_CERT = None
_DEFAULT_SSL_KEY = None

# String Parsing
_TRUTHY_VALUES = ("true", "1", "yes")
_ORIGINS_DELIMITER = ","

class WebSocketConfig:
    """Manages WebSocket configuration with hierarchical loading."""

    # Type hints for instance attributes
    environment: Any  # EnvironmentConfig
    zos: Any  # zOS framework instance
    logger: Any  # Logger instance
    config: Dict[str, Any]
    _verbose: bool

    def __init__(self, environment_config: Any, zos: Any, logger: Any, verbose: bool = False) -> None:
        """
        Initialize WebSocket config with environment config and zos instance.
        
        Args:
            environment_config: EnvironmentConfig instance with environment settings
            zos: Main zOS framework instance for accessing zSpark and other subsystems
            logger: Logger instance for configuration logging
            verbose: If True, show initialization output (default: False)
        """
        # Validate required parameters
        validate_zos_instance(zos, _SUBSYSTEM_NAME, require_session=False)

        self.environment = environment_config
        self.zos = zos
        self.logger = logger
        self._verbose = verbose

        # Get WebSocket configuration from environment (which uses hierarchy)
        self._load_websocket_config()

        # Print ready message (shown in Development mode or when verbose=True)
        if verbose or self.environment.is_development():
            print_ready_message(_READY_MESSAGE, color="CONFIG")

    def _load_websocket_config(self) -> None:
        """Load WebSocket configuration following hierarchy: zSpark > env > config file > defaults."""

        # Get base config from environment (zEnv) — canonical `zSocket`, legacy `websocket`.
        websocket_config: Dict[str, Any] = (
            self.environment.get(_CONFIG_SECTION_KEY, {})
            or self.environment.get(_CONFIG_SECTION_KEY_LEGACY, {})
        )

        # 1. Check environment variables (Layer 3/4 - .zEnv or system env)
        env_host = os.getenv(_ENV_VAR_HOST)
        env_port = os.getenv(_ENV_VAR_PORT)
        env_auth = os.getenv(_ENV_VAR_REQUIRE_AUTH)
        env_origins = os.getenv(_ENV_VAR_ALLOWED_ORIGINS)
        env_token = os.getenv(_ENV_VAR_TOKEN)
        env_ssl_enabled = os.getenv(_ENV_VAR_SSL_ENABLED)
        env_ssl_cert = os.getenv(_ENV_VAR_SSL_CERT)
        env_ssl_key = os.getenv(_ENV_VAR_SSL_KEY)

        if env_host:
            websocket_config[_KEY_HOST] = env_host
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket host from env: {env_host}")

        if env_port:
            try:
                websocket_config[_KEY_PORT] = int(env_port)
                self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket port from env: {env_port}")
            except ValueError:
                self.logger.framework.warning(f"{_LOG_PREFIX} Invalid {_ENV_VAR_PORT}: {env_port}")

        if env_auth:
            websocket_config[_KEY_REQUIRE_AUTH] = env_auth.lower() in _TRUTHY_VALUES
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket auth from env: {websocket_config[_KEY_REQUIRE_AUTH]}")

        if env_origins:
            origins_list = [origin.strip() for origin in env_origins.split(_ORIGINS_DELIMITER) if origin.strip()]
            websocket_config[_KEY_ALLOWED_ORIGINS] = origins_list
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket origins from env: {origins_list}")

        if env_token:
            websocket_config[_KEY_TOKEN] = env_token
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket token from env: {'*' * len(env_token)}")

        # SSL Configuration with deployment-aware defaults (v1.5.10)
        # Check deployment mode for auto-SSL behavior.
        # SSOT: zSys.logger owns the deployment-mode vocabulary + env fallback.
        deployment = resolve_deployment_from_zspark(self.zos.zspark_obj)
        is_production = deployment.lower() == DEPLOYMENT_PRODUCTION

        # Deployment-aware SSL defaults:
        # - Explicit env var (WEBSOCKET_SSL_ENABLED) → highest priority
        # - Production + certs present → auto-enable WSS
        # - Development or no certs → disable WSS
        if env_ssl_enabled is not None:
            # Explicit env var takes precedence
            websocket_config[_KEY_SSL_ENABLED] = env_ssl_enabled.lower() in _TRUTHY_VALUES
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket SSL from env: {websocket_config[_KEY_SSL_ENABLED]}")
        elif is_production and env_ssl_cert and env_ssl_key:
            # Production + certs present = auto-enable SSL
            websocket_config[_KEY_SSL_ENABLED] = True
            self.logger.framework.debug(f"{_LOG_PREFIX} Production mode: WSS auto-enabled (certs detected)")

        if env_ssl_cert:
            websocket_config[_KEY_SSL_CERT] = env_ssl_cert
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket SSL cert from env: {env_ssl_cert}")

        if env_ssl_key:
            websocket_config[_KEY_SSL_KEY] = env_ssl_key
            self.logger.framework.debug(f"{_LOG_PREFIX} WebSocket SSL key from env: {env_ssl_key}")

        # 2. Check zSpark_obj for WebSocket settings (Layer 5 - highest priority, overrides env)
        #    Canonical block is `zSocket:`; `websocket:` is the deprecated alias.
        if self.zos.zspark_obj:
            zspark_ws = self.zos.zspark_obj.get(_CONFIG_SECTION_KEY, {})
            if not zspark_ws:
                zspark_ws = self.zos.zspark_obj.get(_CONFIG_SECTION_KEY_LEGACY, {})
                if zspark_ws:
                    print("⚠️  Deprecated zSpark key 'websocket' → use 'zSocket' instead")
            if zspark_ws:
                self.logger.framework.debug(f"{_LOG_PREFIX} zSocket settings from zSpark: {list(zspark_ws.keys())}")
                websocket_config.update(zspark_ws)  # zSpark overrides everything else

        # 3. Apply defaults for any missing values.
        #    HOST fallback follows the zServer leg (one host per app, two ports):
        #    when zSocket/WEBSOCKET_HOST give no host, inherit the HTTP host the
        #    same way HttpServerConfig resolves it (zSpark.zServer.host → HTTP_HOST
        #    env → 127.0.0.1) — so omitting zSocket.host binds the WS to the same
        #    host the page is served from, never a stray 127.0.0.1 vs localhost split.
        self.config = {
            _KEY_HOST: websocket_config.get(_KEY_HOST, self._zserver_host_fallback()),
            _KEY_PORT: websocket_config.get(_KEY_PORT, _DEFAULT_PORT),
            _KEY_REQUIRE_AUTH: websocket_config.get(_KEY_REQUIRE_AUTH, _DEFAULT_REQUIRE_AUTH),
            _KEY_ALLOWED_ORIGINS: websocket_config.get(_KEY_ALLOWED_ORIGINS, _DEFAULT_ALLOWED_ORIGINS),
            _KEY_TOKEN: websocket_config.get(_KEY_TOKEN, _DEFAULT_TOKEN),
            _KEY_MAX_CONNECTIONS: websocket_config.get(_KEY_MAX_CONNECTIONS, _DEFAULT_MAX_CONNECTIONS),
            _KEY_PING_INTERVAL: websocket_config.get(_KEY_PING_INTERVAL, _DEFAULT_PING_INTERVAL),
            _KEY_PING_TIMEOUT: websocket_config.get(_KEY_PING_TIMEOUT, _DEFAULT_PING_TIMEOUT),
            _KEY_SSL_ENABLED: websocket_config.get(_KEY_SSL_ENABLED, _DEFAULT_SSL_ENABLED),
            _KEY_SSL_CERT: websocket_config.get(_KEY_SSL_CERT, _DEFAULT_SSL_CERT),
            _KEY_SSL_KEY: websocket_config.get(_KEY_SSL_KEY, _DEFAULT_SSL_KEY),
        }

    def _zserver_host_fallback(self) -> str:
        """Resolve the WS host when none is given — inherit the zServer (HTTP) host.

        Mirrors HttpServerConfig's cascade so the two legs share ONE host:
        zSpark.zServer.host → HTTP_HOST env → DEFAULT_HOST. config.http_server is
        not built yet at this point (WebSocketConfig initializes first), so we read
        the same sources directly instead of the sibling config object.
        """
        try:
            from .config_http_server import ENV_VAR_HTTP_HOST, DEFAULT_HOST
        except Exception:  # pylint: disable=broad-except
            ENV_VAR_HTTP_HOST, DEFAULT_HOST = "HTTP_HOST", _DEFAULT_HOST
        zspark = getattr(self.zos, "zspark_obj", None) or {}
        zserver_block = zspark.get("zServer") or zspark.get("http_server") or {}
        return zserver_block.get("host") or os.getenv(ENV_VAR_HTTP_HOST) or DEFAULT_HOST

    def get(self, key: str, default: Any = None) -> Any:
        """Get WebSocket config value by key."""
        return self.config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get complete WebSocket configuration."""
        return self.config.copy()

    def update(self, key: str, value: Any) -> None:
        """Update WebSocket config value (runtime only)."""
        self.config[key] = value

    # ═══════════════════════════════════════════════════════════
    # Convenience Properties
    # ═══════════════════════════════════════════════════════════

    @property
    def host(self) -> str:
        """WebSocket bind address."""
        return self.config[_KEY_HOST]

    @property
    def port(self) -> int:
        """WebSocket port."""
        return self.config[_KEY_PORT]

    @property
    def require_auth(self) -> bool:
        """Whether authentication is required."""
        return self.config[_KEY_REQUIRE_AUTH]

    @property
    def allowed_origins(self) -> List[str]:
        """List of allowed origins."""
        return self.config[_KEY_ALLOWED_ORIGINS]

    @property
    def token(self) -> str:
        """Authentication token (from .zEnv or env vars)."""
        return self.config[_KEY_TOKEN]

    @property
    def ssl_enabled(self) -> bool:
        """Whether SSL/TLS is enabled for WSS connections."""
        return self.config[_KEY_SSL_ENABLED]

    @property
    def ssl_cert(self) -> Optional[str]:
        """Path to SSL certificate file."""
        return self.config[_KEY_SSL_CERT]

    @property
    def ssl_key(self) -> Optional[str]:
        """Path to SSL private key file."""
        return self.config[_KEY_SSL_KEY]

    @property
    def max_connections(self) -> int:
        """Maximum concurrent connections."""
        return self.config[_KEY_MAX_CONNECTIONS]

    @property
    def ping_interval(self) -> int:
        """Ping interval in seconds."""
        return self.config[_KEY_PING_INTERVAL]

    @property
    def ping_timeout(self) -> int:
        """Ping timeout in seconds."""
        return self.config[_KEY_PING_TIMEOUT]

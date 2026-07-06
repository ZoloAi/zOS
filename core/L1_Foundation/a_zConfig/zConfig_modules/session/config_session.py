# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_session.py
"""
Session Configuration and Management for zCLI.

Manages runtime session creation with three-tier authentication architecture:

1. zVisitor Auth (Layer 1): Internal zOS/Zolo users (the flask-like caller identity)
   - session["zLobby"]["zVisitor"] contains zOS user credentials
   - Used for zOS features, premium plugins, Zolo cloud services
   - Authenticated via zos.auth.login()

2. Application Auth (Layer 2): External application users
   - session["zLobby"]["applications"] is a dict of app-specific credentials
   - Multiple apps can be authenticated simultaneously (multi-app support!)
   - Used for applications BUILT on zOS (e.g., eCommerce stores, SaaS apps)
   - Authenticated via zos.auth.authenticate_app_user(app_name, token, config)
   - Configurable user model (developer defines schema)
   - session["zLobby"]["active_app"] tracks which app is currently focused

3. Dual-Auth (Layer 3): Both contexts active simultaneously
   - session["zLobby"]["active_context"] = "dual"
   - session["zLobby"]["dual_mode"] = True
   - Example: Store owner using zOS analytics on their store

Session Structure:
    session["session_hash"] = "a1b2c3d4"  # v1.6.0: Cache invalidation token (regenerates on login/logout)
    session["zLobby"] = {
        "zVisitor": {
            "authenticated": False,
            "id": None,
            "username": None,
            "role": None,
            "api_key": None
        },
        "applications": {  # Multi-app support: dict of app authentications
            "ecommerce_store": {
                "authenticated": True,
                "id": 456,
                "username": "customer_bob",
                "role": "customer",
                "api_key": "store_token_xyz"
            },
            "analytics_dashboard": {
                "authenticated": True,
                "id": 789,
                "username": "analyst_alice",
                "role": "analyst",
                "api_key": "analytics_token_abc"
            }
        },
        "active_app": None,  # Which app is currently focused?
        "active_context": None,  # "zSession", "application", or "dual"
        "dual_mode": False
    }
"""

from zOS import secrets, Any, Dict, Optional, Colors
from zSys.Utils import print_ready_message, validate_zos_instance
from zSys.logger import LOG_LEVEL_PROD as _LOG_LEVEL_PROD
from ..machine.detectors.shared import _safe_getcwd

# Import all public constants from centralized constants module
from ..config_constants import (
    # zMode values
    ZMODE_ZCLI,
    ZMODE_ZBIFROST,
    # Session keys
    SESSION_KEY_ZS_ID,
    SESSION_KEY_TITLE,
    SESSION_KEY_ZSPACE,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    SESSION_KEY_ZMODE,
    SESSION_KEY_ZLOGGER,
    SESSION_KEY_LOGGER_PATH,
    SESSION_KEY_ZPAGINATE,
    SESSION_KEY_ZMACHINE,
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZCACHE,
    SESSION_KEY_WIZARD_MODE,
    SESSION_KEY_ZSPARK,
    SESSION_KEY_VIRTUAL_ENV,
    SESSION_KEY_SYSTEM_ENV,
    SESSION_KEY_LOGGER_INSTANCE,
    SESSION_KEY_ZVARS,
    SESSION_KEY_ZSHORTCUTS,
    SESSION_KEY_BROWSER,
    SESSION_KEY_IDE,
    SESSION_KEY_SESSION_HASH,
    SESSION_KEY_ZORIGIN,
    # zSpark keys
    ZSPARK_KEY_TITLE,
    ZSPARK_KEY_ZSPACE,
    ZSPARK_KEY_ZPAGINATE,
    ZSPARK_KEY_ZMODE,
    ZSPARK_KEY_ZLOG,
    ZSPARK_KEY_LOGGER,
    ZSPARK_KEY_LOGGER_PATH,
    ZSPARK_KEY_LOGGER_PATH_ALIAS,
    # zAuth keys (single signed-in identity: session["zVisitor"])
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
    # zCache keys
    ZCACHE_KEY_SYSTEM,
    ZCACHE_KEY_PINNED,
    ZCACHE_KEY_SCHEMA,
    ZCACHE_KEY_PLUGIN,
    # Wizard keys
    WIZARD_KEY_ACTIVE,
    WIZARD_KEY_LINES,
    WIZARD_KEY_FORMAT,
    WIZARD_KEY_TRANSACTION,
)

# Module-specific constants (internal use only)
_LOG_PREFIX = "[SessionConfig]"
_READY_MESSAGE = "zSession Ready"
_SUBSYSTEM_NAME = "SessionConfig"
_COLOR_MAIN = "MAIN"
_COLOR_CONFIG = "CONFIG"
_DEFAULT_SESSION_PREFIX = "zS"
_TOKEN_HEX_LENGTH = 4
_DEFAULT_ZPAGINATE = False
_DEFAULT_LOG_LEVEL = "INFO"
_VALID_ZMODES = (ZMODE_ZCLI, ZMODE_ZBIFROST)
_ENV_VAR_LOGGER = "ZOLO_LOGGER"
_ENV_VAR_PATH = "PATH"
_CONFIG_KEY_LOGGING = "logging"
_CONFIG_KEY_LEVEL = "level"

# Logger level constants (for PROD deprecation handling)
_LOG_LEVEL_INFO = "INFO"


class SessionConfig:
    """
    Manages runtime session creation and configuration for zCLI.
    
    Creates isolated session instances with machine config, environment settings,
    logger initialization, and zSpark integration for programmatic use.
    """

    def __init__(
        self,
        machine_config: Any,
        environment_config: Any,
        zos: Any,
        zSpark_obj: Optional[Dict[str, Any]] = None,
        zconfig: Optional[Any] = None,
        verbose: bool = False
    ) -> None:
        """
        Initialize SessionConfig with machine/environment configs and zOS instance.
        
        Args:
            machine_config: MachineConfig instance for hardware/OS details
            environment_config: EnvironmentConfig instance for deployment settings
            zos: zOS framework instance (required for validation)
            zSpark_obj: Optional dict for programmatic configuration override
            zconfig: zConfig instance (required for logger creation)
            verbose: If True, show initialization output (default: False)
        
        Raises:
            ValueError: If zconfig is None (required for logger initialization)
        """
        validate_zos_instance(zos, _SUBSYSTEM_NAME, require_session=False)
        if zconfig is None:
            raise ValueError(f"{_SUBSYSTEM_NAME} requires a zConfig instance")

        self.machine = machine_config
        self.environment = environment_config
        self.zos = zos
        self.zSpark = zSpark_obj
        self.zconfig = zconfig
        self.mycolor = _COLOR_MAIN
        self._verbose = verbose

        # Extract log level for log-aware printing
        from zSys.Utils import get_log_level_from_zspark
        self._log_level = get_log_level_from_zspark(zSpark_obj)

        # Print ready message (shown in Development mode or when verbose=True)
        if verbose or self.environment.is_development():
            print_ready_message(_READY_MESSAGE, color=_COLOR_CONFIG)

    def generate_id(self, prefix: str = _DEFAULT_SESSION_PREFIX) -> str:
        """Generate random session ID with prefix (default: 'zS') -> 'zS_a1b2c3d4'."""
        random_hex = secrets.token_hex(_TOKEN_HEX_LENGTH)
        return f"{prefix}_{random_hex}"

    def _generate_session_hash(self) -> str:
        """
        Generate session hash for frontend cache invalidation (v1.6.0).
        
        This hash changes on every session creation and should be regenerated
        on auth state changes (login/logout) to invalidate frontend caches.
        
        Returns:
            8-character hex hash (e.g., 'a1b2c3d4')
        """
        return secrets.token_hex(4)  # 4 bytes = 8 hex chars

    @staticmethod
    def regenerate_session_hash(session: Dict[str, Any]) -> str:
        """
        Regenerate session_hash in existing session (called on login/logout).
        
        This is called by zAuth when authentication state changes to invalidate
        frontend caches. Frontend should detect hash change and clear stale caches.
        
        Args:
            session: zCLI session dict
        
        Returns:
            New session hash (8-character hex)
        
        Usage:
            # In zAuth after login/logout
            new_hash = SessionConfig.regenerate_session_hash(zos.session)
        """
        new_hash = secrets.token_hex(4)
        session[SESSION_KEY_SESSION_HASH] = new_hash
        return new_hash

    def _get_zSpark_value(self, key: str, default: Any = None) -> Any:
        """
        Safely get value from zSpark dict with type checking.
        
        Args:
            key: The key to retrieve from zSpark dict
            default: Default value if key not found or zSpark is None
        
        Returns:
            Value from zSpark[key] if exists, otherwise default
        """
        if self.zSpark is not None and isinstance(self.zSpark, dict):
            return self.zSpark.get(key, default)
        return default

    def _detect_session_title(self, zs_id: Optional[str] = None) -> str:
        """
        Detect session title for log file naming.
        
        Priority:
            1. zSpark["title"] - explicit user override
            2. Script filename (sys.argv[0]) - automatic detection
            3. zS_id - fallback for edge cases
        
        Args:
            zs_id: Optional session ID to use as fallback
        
        Returns:
            Session title string suitable for log filename
        """
        import sys
        from pathlib import Path

        # Check for explicit title in zSpark
        explicit_title = self._get_zSpark_value(ZSPARK_KEY_TITLE)
        if explicit_title:
            return str(explicit_title)

        # Detect from script filename
        try:
            script_path = sys.argv[0]
            if script_path:
                # Handle different execution modes
                if script_path == "-c":
                    # python -c "code"
                    return "zcli-interactive"
                elif script_path == "-m":
                    # python -m module
                    # Try to get module name from argv[1]
                    if len(sys.argv) > 1:
                        return Path(sys.argv[1]).stem
                    return "zcli-module"
                elif script_path in ("", "-"):
                    # Interactive or stdin
                    return "zcli-interactive"
                else:
                    # Normal script execution
                    return Path(script_path).stem
        except (IndexError, AttributeError):
            pass

        # Fallback to zS_id if provided, otherwise generate one
        return zs_id if zs_id else self.generate_id()

    def create_session(self, machine_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create isolated session instance for zCLI with optional machine config.
        
        Builds complete session dict with machine config, environment detection,
        zSpark overrides, and logger initialization. Session dict is the foundation
        for all runtime state in zCLI.
        
        Args:
            machine_config: Optional machine config dict (uses self.machine if None)
        
        Returns:
            Dict containing complete session configuration with all runtime state
        """
        # Use provided machine config or get from machine config instance
        if machine_config is None:
            machine_config = self.machine.get_all()

        # Environment detection priority: zSpark > virtual environment > system environment
        zSpark_value = self.zSpark
        virtual_env = self.environment.get_venv_path() if self.environment.is_in_venv() else None
        system_env = self.environment.get_env_var(_ENV_VAR_PATH)

        # Determine zSpace: zSpark > getcwd (safe version handles deleted directories)
        zSpace = self._get_zSpark_value(ZSPARK_KEY_ZSPACE) or _safe_getcwd()

        # zPaginate: gate zData table pagination-pause (default off). Honest rename
        # of the former "zTraceback" flag (excepthook feature retired).
        zPaginate = self._get_zSpark_value(ZSPARK_KEY_ZPAGINATE, _DEFAULT_ZPAGINATE)

        # Generate session ID first so it can be used as title fallback
        zs_id = self.generate_id()

        # Determine session title for log file naming (with zS_id as fallback)
        session_title = self._detect_session_title(zs_id)

        # Determine logger path for custom log file location
        logger_path = self._detect_logger_path()

        # ── TODO(zServer/zAuth): PER-CALLER SESSION ISOLATION ─────────────────
        # create_session() builds ONE dict and zOS holds it as the process-global
        # zos.session. In zServer — including pure zCLI/HTTP render, NOT just
        # Bifrost/WS — every concurrent caller dispatches against THIS one dict, so
        # zAuth identity, zCrumbs, zVars and wizard_mode all bleed across callers.
        # This is a SINGLETON-SESSION gap, not a per-tenant bug: zCrumbs is already
        # 100% session-resident (audited 2026-06-17 — all trail state in
        # session["zCrumbs"], no instance/global cache), so it becomes multi-session
        # -correct for FREE once a per-caller session registry exists. The fix
        # belongs at the zServer request boundary (resolve a session by id/cookie)
        # + zAuth (per-caller identity) — NEVER re-implemented inside crumbs/zVars.
        # See ZAUTH_INSTANCE.notes.md §15; sibling of the single-instance drift (§2).
        # ──────────────────────────────────────────────────────────────────────
        # Create session dict with constants for all keys
        session = {
            SESSION_KEY_ZS_ID: zs_id,
            SESSION_KEY_TITLE: session_title,
            SESSION_KEY_ZSPACE: zSpace,
            SESSION_KEY_ZVAFOLDER: self._get_zSpark_value("zVaFolder"),
            SESSION_KEY_ZVAFILE: self._get_zSpark_value("zVaFile"),
            SESSION_KEY_ZBLOCK: self._get_zSpark_value("zBlock"),
            SESSION_KEY_ZMODE: self.detect_zMode(),
            SESSION_KEY_ZLOGGER: self._detect_logger_level(),
            SESSION_KEY_LOGGER_PATH: logger_path,
            SESSION_KEY_ZPAGINATE: zPaginate,
            SESSION_KEY_ZMACHINE: machine_config,
            SESSION_KEY_BROWSER: self._get_zSpark_value("browser"),  # Optional override
            SESSION_KEY_IDE: self._get_zSpark_value("ide"),          # Optional override
            # zOrigin — true transport that spawned this session. Defaults to
            # zCLI (genuine local boot); a zTerminal swap-run stamps zBifrost so
            # zOpen's local gate judges by origin, not the emulated zMode (#35).
            SESSION_KEY_ZORIGIN: self._get_zSpark_value(SESSION_KEY_ZORIGIN, ZMODE_ZCLI),
            SESSION_KEY_SESSION_HASH: self._generate_session_hash(),  # v1.6.0: Cache invalidation token
            # Single signed-in caller identity — root-level, sibling of zCrumbs.
            # One zOS instance = one app = one zVisitor (no multi-app nesting).
            SESSION_KEY_ZVISITOR: {
                ZAUTH_KEY_AUTHENTICATED: False,
                ZAUTH_KEY_ID: None,
                ZAUTH_KEY_USERNAME: None,
                ZAUTH_KEY_ROLE: None,
                ZAUTH_KEY_API_KEY: None,
            },
            SESSION_KEY_ZCRUMBS: {},
            SESSION_KEY_ZCACHE: {
                ZCACHE_KEY_SYSTEM: {},
                ZCACHE_KEY_PINNED: {},
                ZCACHE_KEY_SCHEMA: {},
                ZCACHE_KEY_PLUGIN: {},
            },
            SESSION_KEY_WIZARD_MODE: {
                WIZARD_KEY_ACTIVE: False,
                WIZARD_KEY_LINES: [],
                WIZARD_KEY_FORMAT: None,
                WIZARD_KEY_TRANSACTION: False
            },
            SESSION_KEY_ZSPARK: zSpark_value,
            SESSION_KEY_VIRTUAL_ENV: virtual_env,
            SESSION_KEY_SYSTEM_ENV: system_env,
            SESSION_KEY_ZVARS: {},
            SESSION_KEY_ZSHORTCUTS: {},
        }

        # Initialize logger now that session is created with zLogger level
        # Use zConfig's create_logger method to avoid late imports
        logger = self.zconfig.create_logger(session)

        # Store logger in session for easy access
        session[SESSION_KEY_LOGGER_INSTANCE] = logger

        return session

    def detect_zMode(self) -> str:
        """
        Detect zMode based on zSpark override, fallback to zCLI.
        
        Returns:
            "zCLI" or "zBifrost" based on zSpark or default
        """
        # Check zSpark for explicit zMode setting (highest priority)
        zMode = self._get_zSpark_value(ZSPARK_KEY_ZMODE)
        if zMode and zMode in _VALID_ZMODES:
            return zMode

        # Default to zCLI if no valid zMode specified
        return ZMODE_ZCLI

    def _detect_logger_level(self) -> str:
        """
        Detect logger level following hierarchy:
        1. zSpark zLog (ad-hoc override / king) - EXPLICIT user choice
        2. ZOLO_LOGGER env var - per-environment SSOT injected by the zEnv loader
           (also picks up a system/venv ZOLO_LOGGER). One live os.environ read.
        3. zConfig.zEnvironment.yaml (logging.app.level)
        4. Default: INFO
        
        Returns:
            Logger level string (e.g., "INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL")
        """
        # 1. Check zSpark for log level (zLog canonical; zScrap deprecated)
        zSpark_logger = self._get_zSpark_value(ZSPARK_KEY_ZLOG)
        _used_deprecated_key = False
        if not zSpark_logger:
            zSpark_logger = self._get_zSpark_value(ZSPARK_KEY_LOGGER)
            if zSpark_logger:
                _used_deprecated_key = True
        if zSpark_logger:
            if _used_deprecated_key:
                print(
                    f"{Colors.WARNING}⚠️  Deprecated zSpark key 'zScrap' → use 'zLog' instead{Colors.RESET}"
                )
            level = str(zSpark_logger).upper()

            if self.environment.is_development():
                print(f"{Colors.CYAN}{_LOG_PREFIX} zLog level from zSpark: {level}{Colors.RESET}")

            return level

        # 2. ZOLO_LOGGER — one canonical SCREAMING key, read LIVE from os.environ.
        #    zEnv .zolo injects here (per-environment SSOT), and this same read also
        #    picks up a system/venv ZOLO_LOGGER override. zSpark above stays the
        #    ad-hoc king. One live read replaces the old snapshot cascade
        #    (camelCase zLog + venv + system branches) — must be LIVE, not the
        #    EnvironmentConfig snapshot, since zEnv injects after that snapshot.
        import os  # pylint: disable=import-outside-toplevel
        env_logger = os.environ.get(_ENV_VAR_LOGGER)
        if env_logger:
            level = str(env_logger).upper()
            if self.environment.is_development():
                print(f"{Colors.CYAN}{_LOG_PREFIX} Logger level from zEnv ({_ENV_VAR_LOGGER}): {level}{Colors.RESET}")
            return level

        # 3. Check zConfig.zEnvironment.yaml file
        logging_config = self.environment.get(_CONFIG_KEY_LOGGING, {})
        if isinstance(logging_config, dict):
            app_config = logging_config.get("app", {})
            level = app_config.get(_CONFIG_KEY_LEVEL, None) if isinstance(app_config, dict) else None

            if level:
                # Only print in Development mode (UI decision)
                if self.environment.is_development():
                    print(f"{Colors.CYAN}{_LOG_PREFIX} Logger level from zEnvironment config: {level}{Colors.RESET}")

                return level

        # 4. Default fallback (deployment-independent)
        # Logger level is independent of deployment mode
        # Production/Development/Testing all default to INFO
        default = _DEFAULT_LOG_LEVEL  # INFO

        # UI Decision: Only print in Development (keep console clean in Production)
        if self.environment.is_development():
            print(f"{Colors.CYAN}{_LOG_PREFIX} Logger level defaulting to: {default}{Colors.RESET}")

        return default

    def _detect_logger_path(self) -> Optional[str]:
        """
        Detect custom logger path from zSpark (highest priority).
        
        Returns:
            Custom logger path string if provided, None for default system path
        """
        # Check zSpark for zLogPath override (zScrapath is deprecated alias)
        logger_path = self._get_zSpark_value(ZSPARK_KEY_LOGGER_PATH)
        if not logger_path:
            logger_path = self._get_zSpark_value(ZSPARK_KEY_LOGGER_PATH_ALIAS)
            if logger_path and self.environment.is_development():
                print(f"{Colors.YELLOW}{_LOG_PREFIX} zScrapath is deprecated — use zLogPath{Colors.RESET}")
        if logger_path:
            if self.environment.is_development():
                print(f"{Colors.CYAN}{_LOG_PREFIX} zLogPath from zSpark: {logger_path}{Colors.RESET}")
            return str(logger_path)

        # No custom path specified, return None (use default system path)
        return None

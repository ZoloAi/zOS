# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_zenv.py
"""
zEnv - Declarative Environment Configuration Loader

THE zCLI WAY: Replace traditional .env files with declarative config files.

This module provides a secure, declarative alternative to python-dotenv while
maintaining backward compatibility. It parses zEnv config files (.zolo, .yaml, .json)
and injects values into os.environ (just like dotenv), ensuring security and standard practices.

Key Features:
- Parse ZOLO/YAML/JSON declarative config files
- Auto-detect file format (.zolo preferred, .yaml fallback)
- Flatten nested structures to JSON strings for complex values
- Priority-based loading (base → environment-specific)
- Secure: Values injected into os.environ (process-isolated)
- Backward compatible: Falls back to dotenv if no config files found

File Format:
-----------
zEnv.base.zolo         - Base configuration (preferred - string-first, type hints)
zEnv.base.yaml         - Base configuration (fallback)
zEnv.base.yml          - Base configuration (fallback)
zEnv.base.json         - Base configuration (fallback)
zEnv.development.zolo  - Development-specific overrides
zEnv.production.zolo   - Production-specific overrides
zEnv.testing.zolo      - Testing-specific overrides

Priority Order:
--------------
1. zEnv.{environment}.zolo (highest priority - environment-specific, preferred)
2. zEnv.{environment}.yaml (fallback if .zolo not found)
3. zEnv.{environment}.yml  (fallback if .yaml not found)
4. zEnv.{environment}.json (fallback if .yml not found)
5. zEnv.base.zolo          (base configuration, preferred)
6. zEnv.base.yaml          (fallback if .zolo not found)
7. zEnv.base.yml           (fallback if .yaml not found)
8. zEnv.base.json          (fallback if .yml not found)
9. .zEnv.{environment}     (legacy dotenv fallback)
10. .zEnv                  (legacy dotenv base)

Example:
--------
# zEnv.base.zolo
ZNAVBAR:
  zVaF:
  zAccount:
    zRBAC:
      require_role: [zAdmin]

AWS_SECRET_KEY: secret123  # No quotes needed (string-first default)
DEBUG(bool): true          # Explicit type hint

After loading:
os.getenv("ZNAVBAR")  # '{"zVaF": null, "zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}'
os.getenv("AWS_SECRET_KEY")  # "secret123"
os.getenv("DEBUG")  # "true"

Security:
---------
- Values stored in os.environ (process-isolated, standard practice)
- No serialization risk (secrets not in Python objects)
- Works with Docker, K8s, systemd
- Audit trail via OS logging
"""

from zOS import os, yaml, json, Path, Any, Dict, Optional, List, Union
from zOS.zVocabulary import FILE_EXT_ZOLO, FILE_EXT_YAML, FILE_EXT_YML, FILE_EXT_JSON

# Module constants
LOG_PREFIX = "[zEnv]"

# Top-level zEnv key carrying a declarative server block (same grammar as zSpark).
# Recognized specially in _inject_to_environ → expanded onto the canonical env
# bridge rather than dumped as opaque JSON. Mirrors zSpark's _CONFIG_SECTION_KEY.
_ZSERVER_BLOCK_KEY = "zServer"

# Top-level zEnv key carrying a declarative WebSocket block (same grammar as zSpark).
# Expanded onto the canonical WEBSOCKET_* env bridge, mirroring _ZSERVER_BLOCK_KEY.
# `websocket` is the deprecated alias for `zSocket`.
_ZSOCKET_BLOCK_KEY = "zSocket"
_ZSOCKET_BLOCK_KEY_LEGACY = "websocket"

# zEnv file extensions (priority order). Extension atoms are single-sourced in
# zVocabulary (root SSOT); these names remain for back-compat.
ZENV_EXT_ZOLO = FILE_EXT_ZOLO
ZENV_EXT_YAML = FILE_EXT_YAML
ZENV_EXT_YML = FILE_EXT_YML
ZENV_EXT_JSON = FILE_EXT_JSON
ZENV_EXTENSIONS = [
    ZENV_EXT_ZOLO,    # Try .zolo first (new DRY format)
    ZENV_EXT_YAML,    # Fall back to .yaml
    ZENV_EXT_YML,     # Also try .yml
    ZENV_EXT_JSON     # Also try .json
]

# ── Tenant-isolation manifest ────────────────────────────────────────────────
# Every key zEnv writes to os.environ is recorded here and published under
# ZENV_EXPORTED_KEYS (a JSON list) — the env documents which of its keys came
# from zEnv FILES rather than the genuine launch environment.
# Two spawn paths consume it:
#   • zos_plugin drivers (tenant children): pop the marker + scrub the listed
#     keys, so a host app's declarative env (ZNAVBAR chrome, flags, RBAC
#     defaults…) never leaks into a tenant via os.environ.copy().
#   • THIS module at import (`z swap` self-replace): the fresh instance
#     inherits the old instance's ALREADY-INJECTED env, so without hygiene
#     every zEnv value would land in the launch snapshot below and masquerade
#     as an ops override — skipped on load (stale zEnv edits forever) and,
#     one generation later, leaked into tenants UNRECORDED (the manifest only
#     lists keys this process wrote itself). The pass below deletes inherited
#     zEnv keys so the process starts as-if launched fresh and re-derives its
#     config from its own files.
# Env-var transport (not an import) keeps the SDK decoupled from L1 config.
# Module-level so the record accumulates across `z reload` loader rebuilds.
ZENV_EXPORTED_KEYS_VAR = "ZENV_EXPORTED_KEYS"
_EXPORTED_KEYS: set = set()

try:
    _INHERITED_ZENV_KEYS = json.loads(os.environ.pop(ZENV_EXPORTED_KEYS_VAR, "[]"))
except (ValueError, TypeError):
    _INHERITED_ZENV_KEYS = []
for _key in _INHERITED_ZENV_KEYS:
    os.environ.pop(_key, None)

# Genuine PROCESS-LAUNCH environment snapshot — captured at first import of this
# module (AFTER the inherited-zEnv hygiene pass above), which always precedes any
# zEnv injection (injection happens only *through* this module). Keys present here
# are explicit launch-time overrides (ops env, or a driver injecting per-instance
# ports) and MUST win over zEnv FILE defaults — even across a hot `z reload`.
# Without this, a fresh loader built during reload would snapshot the
# ALREADY-injected env in __init__ and wrongly treat every zEnv value as a launch
# override, making reload silently ignore edited zEnv files. SSOT for the
# launch-precedence rule across boot AND reload.
_LAUNCH_ENV_KEYS = frozenset(os.environ.keys())


class zEnv:
    """
    Declarative environment configuration loader (THE zCLI WAY).
    
    Replaces python-dotenv with YAML/JSON declarative configs while
    maintaining security through os.environ injection.
    """

    def __init__(self, workspace_dir: str, environment: str = "development", logger=None,
                 launch_env_keys: Optional[frozenset] = None):
        """
        Initialize zEnv loader.
        
        Args:
            workspace_dir: Path to workspace directory containing zEnv files
            environment: Current environment (development, production, testing)
            logger: Optional logger instance for debug output
            launch_env_keys: Optional explicit launch-env key set. Defaults to the
                module-level genuine process-launch snapshot (``_LAUNCH_ENV_KEYS``)
                so the precedence rule is stable across boot AND `z reload`. Tests
                may inject a custom set.
        """
        self.workspace_dir = Path(workspace_dir)
        self.environment = environment.lower()
        self.logger = logger
        self._loaded_files: List[str] = []
        # Keys present in the LAUNCH environment (BEFORE any zEnv layer) are explicit
        # overrides (ops, or a compute driver injecting per-instance HTTP_PORT/
        # WEBSOCKET_PORT for blue-green / hosted instances) and MUST win over zEnv
        # FILE defaults (dotenv override=False semantics). We use the module-level
        # snapshot — not a fresh os.environ read — so a loader rebuilt during reload
        # still refreshes edited zEnv values instead of mistaking them for overrides.
        # Base→env layering is unaffected: those keys aren't in this snapshot, so a
        # later zEnv layer still overrides an earlier one.
        self._launch_env_keys = (
            launch_env_keys if launch_env_keys is not None else _LAUNCH_ENV_KEYS
        )

    def load(self) -> bool:
        """
        Load environment configuration from config files into os.environ.
        
        Auto-detects file format (.zolo preferred, .yaml/.yml/.json fallback).
        Priority order:
        1. zEnv.base.{zolo|yaml|yml|json} (base configuration)
        2. zEnv.{environment}.{zolo|yaml|yml|json} (environment-specific overrides)
        
        Returns:
            bool: True if any config files were loaded, False if no files found
            
        Note:
            Does NOT fall back to dotenv - that's handled by config_paths.load_dotenv()
            This ensures declarative files always take precedence when they exist.
        """
        # Find files with auto-detection
        base_file = self._find_file_with_extension("zEnv.base")
        env_file = self._find_file_with_extension(f"zEnv.{self.environment}")

        # Delegate to load_files()
        return self.load_files(base_file, env_file)

    def load_files(self, base_file: Optional[Path], env_file: Optional[Path]) -> bool:
        """
        Load specified config files into os.environ.
        
        This is the execution layer - it loads whatever files it's told to load.
        File detection happens in config_paths.py (the decision layer).
        
        Args:
            base_file: Path to base config file (or None)
            env_file: Path to environment config file (or None)
        
        Returns:
            bool: True if any files were loaded successfully
        """
        any_loaded = False

        # Load base configuration
        if base_file:
            base_config = self._load_file(base_file)
            if base_config:
                self._inject_to_environ(base_config)
                self._loaded_files.append(str(base_file))
                any_loaded = True
                self._log(f"[OK] Loaded base config from {base_file.name}")

        # Load environment-specific configuration (overrides base)
        if env_file:
            env_config = self._load_file(env_file)
            if env_config:
                self._inject_to_environ(env_config)
                self._loaded_files.append(str(env_file))
                any_loaded = True
                self._log(f"[OK] Loaded {self.environment} config from {env_file.name}")

        if not any_loaded:
            self._log("[INFO]  No zEnv config files found in workspace")

        # Publish the tenant-isolation manifest — refreshed after every load so
        # child-spawning drivers always see the current set (boot AND reload).
        if _EXPORTED_KEYS:
            os.environ[ZENV_EXPORTED_KEYS_VAR] = json.dumps(sorted(_EXPORTED_KEYS))

        return any_loaded

    def _find_file_with_extension(self, base_name: str) -> Optional[Path]:
        """
        Find a file by trying extensions in priority order.
        
        Args:
            base_name: Base filename without extension (e.g., "zEnv.base")
        
        Returns:
            Path to file if found, None otherwise
        """
        for ext in ZENV_EXTENSIONS:
            candidate = self.workspace_dir / f"{base_name}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _load_file(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Load and parse a YAML, JSON, or ZOLO file.
        
        Args:
            file_path: Path to the file to load (string or Path object)
        
        Returns:
            Dict containing parsed data, or None if file doesn't exist or parse failed
        """
        # Convert string to Path if needed
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check file extension
            file_extension = file_path.suffix

            # For .zolo files, use the zlsp parser library (like PyYAML for .yaml)
            if file_extension == ZENV_EXT_ZOLO:
                try:
                    from zlsp import parser as zolo
                    data = zolo.loads(content, filename=str(file_path))
                    if data is None:
                        self._log(f"[WARN]  {file_path.name} is empty")
                        return None
                    return data
                except ImportError:
                    self._log(f"[WARN]  zolo library not installed, falling back to YAML parser for {file_path.name}")
                    # Fallback to YAML if zolo not installed
                    try:
                        data = yaml.safe_load(content)
                        if data is None:
                            self._log(f"[WARN]  {file_path.name} is empty")
                            return None
                        return data
                    except yaml.YAMLError as e:
                        self._log(f"[FAIL] Failed to parse {file_path.name}: {e}")
                        return None
                except Exception as e:
                    self._log(f"[FAIL] Failed to parse .zolo file {file_path.name}: {e}")
                    return None

            # For .yaml, .yml, and .json files, try YAML first (supports both YAML and JSON)
            if file_extension in (ZENV_EXT_YAML, ZENV_EXT_YML):
                try:
                    data = yaml.safe_load(content)
                    if data is None:
                        self._log(f"[WARN]  {file_path.name} is empty")
                        return None
                    return data
                except yaml.YAMLError as e:
                    self._log(f"[FAIL] Failed to parse {file_path.name}: {e}")
                    return None
            
            # For .json files, use JSON parser directly
            if file_extension == ZENV_EXT_JSON:
                try:
                    data = json.loads(content)
                    if data is None:
                        self._log(f"[WARN]  {file_path.name} is empty")
                        return None
                    return data
                except json.JSONDecodeError as e:
                    self._log(f"[FAIL] Failed to parse {file_path.name}: {e}")
                    return None
            
            # Unknown extension - try YAML then JSON as fallback
            try:
                data = yaml.safe_load(content)
                if data is None:
                    self._log(f"[WARN]  {file_path.name} is empty")
                    return None
                return data
            except yaml.YAMLError as e:
                try:
                    data = json.loads(content)
                    return data
                except json.JSONDecodeError as e2:
                    self._log(f"[FAIL] Failed to parse {file_path.name}: YAML error: {e}, JSON error: {e2}")
                    return None

        except Exception as e:
            self._log(f"[FAIL] Failed to read {file_path.name}: {e}")
            return None

    # Substrings (case-insensitive) marking a key whose VALUE must never be logged.
    _SECRET_HINTS = ("SECRET", "TOKEN", "KEY", "PASSWORD", "PASSWD",
                     "PRIVATE", "CREDENTIAL", "AUTH")

    def _redacted(self, key: str, value: Any) -> str:
        """Display value for logs, redacting secret-ish keys (zEnv may hold creds)."""
        up = key.upper()
        if any(hint in up for hint in self._SECRET_HINTS):
            return "<redacted>"
        return str(value)

    def _set_env(self, key: str, raw_value: str) -> None:
        """Write a resolved zEnv value to ``os.environ`` — the single chokepoint.

        Skips keys present in the LAUNCH environment so an explicit launch-time
        override (ops, or a driver injecting per-instance ports) always wins over a
        zEnv file default. All zEnv writers (flat keys + the zServer block bridge)
        go through here so the precedence rule lives in exactly one place (SSOT).
        """
        if key in self._launch_env_keys:
            self._log(f"  {key}: <kept launch override> (zEnv file value ignored)")
            return
        os.environ[key] = raw_value
        _EXPORTED_KEYS.add(key)  # tenant-isolation manifest (see ZENV_EXPORTED_KEYS_VAR)
        self._log(f"  {key}: {self._redacted(key, raw_value)}")

    def _inject_to_environ(self, config: Dict[str, Any]) -> None:
        """
        Inject configuration values into os.environ.
        
        Nested structures (dicts, lists) are flattened to JSON strings.
        Simple values are converted to strings.

        SECURITY: zEnv files behave like dotenv and may contain secrets. Values
        are NEVER logged verbatim — secret-ish keys are redacted (see _redacted)
        and complex structures are logged as <complex> only.

        Args:
            config: Dictionary of configuration values to inject
        """
        for key, value in config.items():
            if value is None:
                # Skip None values (don't set env var)
                continue

            # Declarative `zServer:` block — SAME grammar as zSpark. Expand its
            # sub-keys onto the canonical env bridge (host→HTTP_HOST, etc.) instead
            # of dumping the whole block as opaque JSON, so per-key layering works
            # across base→env and config_http_server reads what it already reads.
            if key == _ZSERVER_BLOCK_KEY and isinstance(value, dict):
                self._expand_zserver_block(value)
                continue

            # Declarative `zSocket:` block (alias `websocket:`) — SAME grammar as
            # zSpark. Expand onto the WEBSOCKET_* env bridge instead of dumping it
            # as opaque JSON, so per-key layering works across base→env.
            if key in (_ZSOCKET_BLOCK_KEY, _ZSOCKET_BLOCK_KEY_LEGACY) and isinstance(value, dict):
                if key == _ZSOCKET_BLOCK_KEY_LEGACY:
                    print("⚠️  Deprecated zEnv key 'websocket' → use 'zSocket' instead")
                self._expand_zsocket_block(value)
                continue

            if isinstance(value, (dict, list)):
                # Flatten complex structures to JSON strings (content never logged)
                self._set_env(key, json.dumps(value, ensure_ascii=False))
            elif isinstance(value, bool):
                # Convert boolean to lowercase string (true/false)
                self._set_env(key, str(value).lower())
            else:
                # Simple values to strings
                self._set_env(key, str(value))

    def _expand_zserver_block(self, block: Dict[str, Any]) -> None:
        """Expand a declarative zEnv `zServer:` block onto the canonical env bridge.

        ONE grammar in zSpark and every zEnv layer. The mapping (block key → env
        var name) is owned by config_http_server (SSOT); we lazy-import it so zEnv
        stays dependency-light at early boot. Per-key layering is automatic: base
        loads first, the chosen environment overrides only the keys it declares.

        Scalars → str; bools → "true"/"false"; nested values (e.g. mounts) → JSON
        (config_http_server JSON-parses ZSERVER_MOUNTS). Unknown keys pass through
        as ZSERVER_<KEY> so the block never silently drops a setting.
        """
        try:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_http_server import (
                ZSERVER_BLOCK_ENV_MAP,
            )
        except Exception:
            ZSERVER_BLOCK_ENV_MAP = {}

        for k, v in block.items():
            if v is None:
                continue
            env_name = ZSERVER_BLOCK_ENV_MAP.get(k, f"ZSERVER_{str(k).upper()}")
            if isinstance(v, (dict, list)):
                self._set_env(env_name, json.dumps(v, ensure_ascii=False))
            elif isinstance(v, bool):
                self._set_env(env_name, str(v).lower())
            else:
                self._set_env(env_name, str(v))

    def _expand_zsocket_block(self, block: Dict[str, Any]) -> None:
        """Expand a declarative zEnv `zSocket:` block onto the WEBSOCKET_* env bridge.

        Sister of _expand_zserver_block. The mapping (block key → env var name) is
        owned by config_websocket (SSOT); lazy-imported to keep zEnv dependency-light
        at early boot. Unknown keys pass through as WEBSOCKET_<KEY> so nothing is
        silently dropped.
        """
        try:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.network.config_websocket import (
                ZSOCKET_BLOCK_ENV_MAP,
            )
        except Exception:
            ZSOCKET_BLOCK_ENV_MAP = {}

        for k, v in block.items():
            if v is None:
                continue
            env_name = ZSOCKET_BLOCK_ENV_MAP.get(k, f"WEBSOCKET_{str(k).upper()}")
            if isinstance(v, (dict, list)):
                self._set_env(env_name, json.dumps(v, ensure_ascii=False))
            elif isinstance(v, bool):
                self._set_env(env_name, str(v).lower())
            else:
                self._set_env(env_name, str(v))


    def _log(self, message: str) -> None:
        """
        Log a message (if logger is available).
        
        Args:
            message: Message to log
        """
        if self.logger:
            self.logger.framework.info(f"{LOG_PREFIX} {message}")
        # Silently skip if no logger (during bootstrap)


def loads_env_value(raw: Optional[str]) -> Any:
    """Parse a zEnv value that was injected into ``os.environ``.

    zEnv nested structures (dicts/lists) are stored as JSON strings by
    ``_inject_to_environ``; scalars stay plain strings. This is the inverse,
    and it lives HERE — in the zEnv format module that already owns json — so
    consumers (config accessors, subsystems) never import json to read a nested
    zEnv value (file-agnosticism: format parsing stays in the config layer).

    Returns the parsed structure for JSON values, the original string for plain
    scalars, and None when ``raw`` is None.
    """
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def load_zenv(workspace_dir: str, environment: str = "development", logger=None) -> bool:
    """
    Convenience function to load zEnv configuration.
    
    Args:
        workspace_dir: Path to workspace directory containing zEnv files
        environment: Current environment (development, production, testing)
        logger: Optional logger instance
    
    Returns:
        bool: True if YAML files were loaded, False if fell back to dotenv
    
    Example:
        >>> from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_zenv import load_zenv
        >>> load_zenv("/path/to/workspace", "development")
        True
    """
    loader = zEnv(workspace_dir, environment, logger)
    return loader.load()

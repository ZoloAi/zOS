# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/config_helpers.py
"""Shared helper functions for configuration loading across zConfig subsystems."""

import re

from zOS import logging, yaml, Path, Dict, Any, Callable, Optional, shutil

# Module-level logger
logger = logging.getLogger(__name__)

# Module constants
SOURCE_USER = "user"
LOG_PREFIX = "[ConfigHelpers]"
ZUI_CLI_SYS_FILENAME = "zUI.zcli_sys.yaml"


def slugify_app_id(name: Any) -> str:
    """Turn an authored name into a filesystem/namespace/RBAC-safe app id.

    Case is PRESERVED on purpose — the slug only removes whitespace and unsafe
    characters so existing identities (e.g. ``zCloud``) stay byte-stable. Spaces
    collapse to ``-`` and anything outside ``[A-Za-z0-9_-]`` is dropped.

    Examples:
        "zCloud"   → "zCloud"
        "Acme CRM" → "Acme-CRM"
        "My_App!"  → "My_App"
    """
    s = str(name or "").strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^A-Za-z0-9_-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def resolve_app_id(
    zSpark: Optional[Dict[str, Any]],
    *,
    block_zapp: Optional[str] = None,
    fallback: Optional[str] = None,
) -> str:
    """SSOT for the app's machine identity (auth scope, zAPI, persistence dir).

    One authored name — ``title`` — IS the identity. ``zApp`` is a deprecated
    optional override (block-level or spark-level) for the rare case the slug
    must differ from the display title.

    Precedence: block ``zApp`` → spark ``zApp`` → ``title`` → ``zVaFile`` stem →
    ``fallback`` → ``"app"``. The result is always slugged.
    """
    zSpark = zSpark or {}
    candidate = block_zapp or zSpark.get("zApp") or zSpark.get("title")
    if not candidate:
        va_file = str(zSpark.get("zVaFile", "") or "")
        if va_file.lower().startswith("zui."):
            candidate = va_file[4:]
    candidate = candidate or fallback or "app"
    return slugify_app_id(candidate) or "app"

def ensure_user_directories(paths: Any) -> None:
    """
    Ensure user configuration directories exist (zConfigs, zUIs, zSchemas).
    
    Creates user_config_dir subdirectories if they don't already exist:
    - zConfigs: Configuration files (zConfig.machine.zolo, zConfig.environment.zolo)
    - zUIs: User-customized UI definition files
    - zSchemas: User schema templates
    
    Args:
        paths: zConfigPaths instance
        
    Notes:
        - Called during zConfig initialization
        - Uses exist_ok=True for safe repeated calls
        - Silently handles errors (non-critical operation)
    """
    try:
        # Ensure zConfigs directory exists
        paths.user_zconfigs_dir.mkdir(parents=True, exist_ok=True)

        # Ensure zUIs directory exists
        paths.user_zuis_dir.mkdir(parents=True, exist_ok=True)

        # Ensure zSchemas directory exists
        paths.user_zschemas_dir.mkdir(parents=True, exist_ok=True)

    except Exception as e:
        logger.warning("%s Failed to create user directories: %s", LOG_PREFIX, e)

def ensure_app_directory(paths: Any, zSpark: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    """
    Create app root directory if zPersist is enabled in zSpark.

    Simple opt-in: Creates Apps/{app_id}/ root folder, where app_id is the
    slugged identity derived from title (SSOT: resolve_app_id).
    App creates subdirectories as needed.

    Args:
        paths: zConfigPaths instance
        zSpark: zSpark configuration dict

    Returns:
        Path: App root directory if created, None if not enabled

    Example:
        zSpark = {"title": "zCloud", "zPersist": True}
        → Creates ~/Library/Application Support/zOS/Apps/zCloud/

    Notes:
        - Only creates directory if zPersist (or deprecated zSwap) is truthy in zSpark
        - Requires title key in zSpark to determine app name
        - Non-critical operation (silently handles errors)
    """
    if not zSpark:
        return None

    # zPersist is canonical; zSwap is deprecated
    zpersist_enabled = zSpark.get('zPersist')
    if not zpersist_enabled:
        zswap_val = zSpark.get('zSwap')
        if zswap_val:
            print("⚠️  Deprecated zSpark key 'zSwap' → use 'zPersist' instead")
            zpersist_enabled = zswap_val
    if not zpersist_enabled:
        return None

    # Identity is derived from title (SSOT: resolve_app_id). title is required.
    if not zSpark.get('title') and not zSpark.get('zApp'):
        logger.warning("%s zPersist enabled but no title specified", LOG_PREFIX)
        return None
    app_name = resolve_app_id(zSpark)

    try:
        # Create app root: Apps/{app_id}/
        app_root = paths.user_data_dir / "Apps" / app_name
        app_root.mkdir(parents=True, exist_ok=True)

        logger.info("%s App storage initialized: %s", LOG_PREFIX, app_root)
        return app_root

    except Exception as e:
        logger.warning("%s Failed to create app directory: %s", LOG_PREFIX, e)
        return None

def initialize_system_ui(paths: Any) -> None:
    """
    Copy system UI file (zUI.zcli_sys.yaml) from package to user zUIs directory.
    
    Copies the system UI file containing help menus, traceback UI, and uninstall
    walker definitions on first run. This ensures system UI features work from any
    directory. Users can customize this file after initial copy.
    
    Args:
        paths: zConfigPaths instance
        
    Notes:
        - Only copies if file doesn't exist (preserves user customizations)
        - Source: zOS/UI/zUI.zcli_sys.yaml (from installed package)
        - Target: user_zuis_dir/zUI.zcli_sys.yaml
        - Non-critical operation (silently handles errors)
    """
    try:
        target_file = paths.user_zuis_dir / ZUI_CLI_SYS_FILENAME

        # Skip if file already exists (user may have customized)
        if target_file.exists():
            return

        # Get source file from package (zOS/UI/)
        import zOS
        zos_package_dir = Path(zOS.__path__[0])
        source_file = zos_package_dir / "UI" / ZUI_CLI_SYS_FILENAME

        # Copy file if source exists
        if source_file.exists():
            shutil.copy2(source_file, target_file)
            logger.debug("%s Initialized system UI: %s", LOG_PREFIX, ZUI_CLI_SYS_FILENAME)
            logger.debug("%s Location: %s", LOG_PREFIX, target_file)
        else:
            logger.warning("%s Source UI file not found: %s", LOG_PREFIX, source_file)

    except Exception as e:
        logger.warning("%s Failed to initialize system UI: %s", LOG_PREFIX, e)

def load_config_with_override(
    paths: Any,  # zConfigPaths (avoid circular import)
    yaml_key: str,
    create_func: Callable[[Path, Dict[str, Any], bool], None],
    data_dict: Dict[str, Any],
    filename: str,
    subsystem_name: str,
    verbose: bool = False
) -> None:
    """Load config file from user directory, creating with defaults if missing.
    
    Args:
        paths: zConfigPaths instance
        yaml_key: YAML key to extract from file
        create_func: Function to create default config if missing (signature: func(path, data, verbose))
        data_dict: Dictionary to merge config into
        filename: Config filename
        subsystem_name: Name of subsystem for logging
        verbose: If True, show loading messages (default: False)
    """
    user_config_path = paths.user_zconfigs_dir / filename

    if user_config_path.exists():
        _load_and_override(user_config_path, yaml_key, data_dict, subsystem_name, SOURCE_USER, verbose)
    else:
        create_func(user_config_path, data_dict, verbose)
        _load_and_override(user_config_path, yaml_key, data_dict, subsystem_name, SOURCE_USER, verbose)

def _load_and_override(
    path: Path,
    yaml_key: str,
    data_dict: Dict[str, Any],
    subsystem_name: str,
    source: str,
    verbose: bool = False
) -> None:
    """Load YAML config file and merge its contents into data_dict (verbose-aware).
    
    Args:
        path: Path to config file
        yaml_key: YAML key to extract
        data_dict: Dictionary to merge config into
        subsystem_name: Name of subsystem for logging
        source: Source description for logging
        verbose: If True, show loading messages (default: False)
    """
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()

        if Path(path).suffix == '.zolo':
            from zlsp.parser.parser import loads as zolo_loads
            data = zolo_loads(content)
        else:
            data = yaml.safe_load(content)

        if data and yaml_key in data:
            data_dict.update(data[yaml_key])
            if verbose:
                logger.info("[%s] Overriding with %s settings from: %s", subsystem_name, source, path)

    except Exception as e:
        if verbose:
            logger.warning("[%s] Failed to load %s config: %s", subsystem_name, source, e)

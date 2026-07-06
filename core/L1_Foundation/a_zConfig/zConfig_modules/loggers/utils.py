# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/loggers/utils.py
"""Shared logger utilities."""

from zOS import Path, os, logging
from zSys import zpath  # zPath grammar — Layer-0 SSOT for sigil/segment decomposition
from .constants import (
    VALID_LOG_LEVELS,
    DEFAULT_LOG_LEVEL,
    LOG_PREFIX,
    PYTHON_EXTENSION,
    PATH_SUBSYSTEMS_MARKER,
    PATH_ZOS_MARKER,
    PATH_SUBSYSTEMS_DIR,
    get_base_log_level,
    is_zos_log_level,
)
from zOS import Colors


def normalize_log_level(level) -> str:
    """Normalize log level to uppercase string."""
    return str(level).upper()


def validate_log_level(level: str) -> str:
    """
    Validate log level against valid levels.

    z-prefixed levels (e.g. ZDEBUG, ZINFO, ZWARNING) are accepted if their
    base level (level stripped of the leading Z) is valid.

    Args:
        level: Log level string (already normalized to uppercase)

    Returns:
        str: Valid log level or DEFAULT_LOG_LEVEL if invalid
    """
    if level in VALID_LOG_LEVELS:
        return level
    # Accept z-prefixed variant when the base level is valid
    if is_zos_log_level(level) and get_base_log_level(level) in VALID_LOG_LEVELS:
        return level
    print(f"{Colors.WARNING}{LOG_PREFIX} Invalid log level '{level}', "
          f"using '{DEFAULT_LOG_LEVEL}'{Colors.RESET}")
    return DEFAULT_LOG_LEVEL


def strip_py_extension(filename: str) -> str:
    """Strip .py extension from filename if present."""
    if filename.endswith(PYTHON_EXTENSION):
        return filename[:-len(PYTHON_EXTENSION)]
    return filename


def resolve_logger_path(path_str: str, zos) -> Path:
    """
    Resolve logger path with zPath notation support.
    
    Supports:
        - @.path → workspace-relative (zPath convention)
        - ~.path or ~/path → home-relative
        - ./path → current directory relative
        - path → absolute or relative
    
    Args:
        path_str: Path string to resolve
        zos: zOS framework instance
        
    Returns:
        Resolved Path object
    
    Examples:
        >>> resolve_logger_path("@.logs", zos)  # workspace/logs
        >>> resolve_logger_path("./logs", zos)  # cwd/logs
        >>> resolve_logger_path("~/logs", zos)  # home/logs
    """
    path_str = str(path_str).strip()

    # Handle zPath workspace-relative notation (@.path or @path)
    if path_str.startswith(zpath.SIGIL_WORKSPACE):
        # Peel the workspace sigil via the grammar SSOT
        relative_path = zpath.strip_symbol(path_str)
        # Get workspace directory from config paths
        if hasattr(zos, 'config') and hasattr(zos.config, 'sys_paths'):
            workspace = zos.config.sys_paths.workspace_dir
            if workspace:
                return Path(workspace) / relative_path
        # Fallback to current directory if workspace not available
        return Path.cwd() / relative_path

    elif path_str.startswith("@"):
        # Handle @path (without dot)
        relative_path = path_str[1:]
        if hasattr(zos, 'config') and hasattr(zos.config, 'sys_paths'):
            workspace = zos.config.sys_paths.workspace_dir
            if workspace:
                return Path(workspace) / relative_path
        return Path.cwd() / relative_path

    # Handle tilde notation (~.path or ~/path) and regular paths
    return Path(path_str).expanduser().resolve()


def get_caller_info(record: logging.LogRecord) -> str:
    """
    Extract caller file information from log record.
    
    Provides hierarchical naming for zOS subsystems (e.g., 'zComm.http_server')
    and simple filenames for other modules.
    
    Args:
        record: Python logging record with pathname information
    
    Returns:
        str: Formatted caller name (subsystem.module or filename)
    """
    pathname = record.pathname

    # For zOS subsystems, show hierarchical subsystem/module names
    if PATH_SUBSYSTEMS_MARKER in pathname:
        # Extract subsystem name from path like: /path/to/zOS/subsystems/zComm/zComm.py
        parts = pathname.split(PATH_SUBSYSTEMS_MARKER)
        if len(parts) > 1:
            subsystem_part = parts[1]
            # Get the first directory after subsystems (e.g., zComm from zComm/zComm.py)
            subsystem_segments = subsystem_part.split('/')
            subsystem = subsystem_segments[0]

            # Determine module filename (if available)
            if len(subsystem_segments) > 1:
                module_filename = subsystem_segments[-1]
                module, _ = os.path.splitext(module_filename)

                # If the module filename matches the subsystem, return subsystem only
                if module == subsystem:
                    return subsystem

                # Otherwise return hierarchical name subsystem.module
                return f"{subsystem}.{module}"

            return subsystem

    # For zOS core files, show the module name
    if PATH_ZOS_MARKER in pathname and PATH_SUBSYSTEMS_DIR not in pathname:
        filename = os.path.basename(pathname)
        return strip_py_extension(filename)

    # For other files, just show the filename
    filename = os.path.basename(pathname)
    return strip_py_extension(filename)


def get_logs_directory(zos) -> Path:
    """
    Get the standard logs directory for the platform.
    
    Args:
        zos: zOS framework instance
        
    Returns:
        Path to logs directory
    """
    if hasattr(zos, 'config') and hasattr(zos.config, 'sys_paths'):
        return zos.config.sys_paths.user_logs_dir

    # Fallback if config not available yet
    home_path = Path.home()
    import platform
    if platform.system() == "Windows":
        return home_path / "AppData" / "Local" / "zOS" / "logs"
    elif platform.system() == "Darwin":  # macOS
        return home_path / "Library" / "Application Support" / "zOS" / "logs"
    else:  # Linux
        return home_path / ".local" / "share" / "zOS" / "logs"

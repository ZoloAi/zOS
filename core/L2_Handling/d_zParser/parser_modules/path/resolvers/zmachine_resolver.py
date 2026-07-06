# zOS/core/L2_Handling/g_zParser/parser_modules/path/resolvers/zmachine_resolver.py

"""
zMachine path resolution for path package.

Resolves zMachine.* or ~.zMachine.* path references to OS-specific paths
in the user data directory.

Public API:
    - resolve_zmachine_path: Resolve zMachine paths to OS paths

Dependencies:
    - pathlib: Path validation
    - zConfig: User data directory resolution
    - zExceptions: Error handling

Created: Phase 3.1 - Extract Resolvers from parser_path.py
"""

from zOS import Path, Any, Optional, Union
from zSys.errors import zMachinePathError

# Import constants from shared
from ...shared.file_constants import (
    PATH_SEP_DOT,
    PATH_SEP_SLASH,
    ZMACHINE_PREFIX_SHORT,
    ZMACHINE_PREFIX_LONG,
    ZMACHINE_KEYWORDS,
    FILE_EXT_YAML,
    LOG_MSG_ZMACHINE_PATH
)


def resolve_zmachine_path(
    data_path: Any,
    logger: Any,
    config_paths: Optional[Any] = None
) -> Union[str, Any]:
    """
    Resolve zMachine.* or ~.zMachine.* path references to OS-specific paths.
    
    Converts zMachine path syntax to actual file system paths in the user data
    directory (typically ~/Library/Application Support/zolo-zcli on macOS).
    
    Supported formats:
        - zMachine.{subpath}
        - ~.zMachine.{subpath}
    
    Dot notation is converted to path separators:
        zMachine.Data.cache → {user_data_dir}/Data/cache
        ~.zMachine.zSchema.auth → {user_data_dir}/zSchema/auth
    
    For paths containing zVaFile keywords (zSchema, zUI, zConfig), validates
    that the file exists (adding .yaml extension).
    
    Args:
        data_path: Path string to resolve, or non-string to return as-is
        logger: Logger instance for diagnostic output
        config_paths: Optional zConfigPaths instance (created if not provided)
    
    Returns:
        Union[str, Any]:
            - str: Resolved OS-specific path if zMachine path
            - Any: Original data_path if not a zMachine path or not a string
    
    Raises:
        zMachinePathError: If file path cannot be resolved or file not found
                           (only for paths containing zVaFile keywords)
    
    Examples:
        >>> logger = get_logger()
        
        # Simple zMachine path
        >>> resolve_zmachine_path('zMachine.Data.cache', logger)
        '/Users/user/Library/Application Support/zolo-zcli/Data/cache'
        
        # Alternative format
        >>> resolve_zmachine_path('~.zMachine.zSchema.auth', logger)
        '/Users/user/Library/Application Support/zolo-zcli/zSchema/auth'
        
        # Non-zMachine path (returned as-is)
        >>> resolve_zmachine_path('regular/path', logger)
        'regular/path'
        
        # Non-string (returned as-is)
        >>> resolve_zmachine_path(123, logger)
        123
    
    Notes:
        - Non-string inputs are returned without modification
        - Non-zMachine paths are returned without modification
        - File existence is only validated for zVaFile paths
        - Uses zConfigPaths to get user data directory
        - Raises zMachinePathError for missing zVaFiles
    
    See Also:
        - zPath_decoder: Related path resolution utility
        - is_zvafile_type: zVaFile detection
    """
    # Return non-string inputs as-is
    if not isinstance(data_path, str):
        return data_path

    # Check for both zMachine formats
    if data_path.startswith(ZMACHINE_PREFIX_SHORT):
        prefix = ZMACHINE_PREFIX_SHORT
    elif data_path.startswith(ZMACHINE_PREFIX_LONG):
        prefix = ZMACHINE_PREFIX_LONG
    else:
        # Not a zMachine path, return as-is
        return data_path

    # Get config paths (import inline to avoid circular dependency)
    if not config_paths:
        from zOS.L1_Foundation.a_zConfig.zConfig_modules import zConfigPaths
        config_paths = zConfigPaths()

    # Extract the subpath after zMachine prefix
    # Example: "zMachine.zDataTests" => "zDataTests"
    # Example: "~.zMachine.Data/cache.csv" => "Data/cache.csv"
    subpath = data_path[len(prefix):]

    # Convert dot notation to path separators
    # Example: "zDataTests" stays as is, "tests.zData_tests" => "tests/zData_tests"
    subpath = subpath.replace(PATH_SEP_DOT, PATH_SEP_SLASH)

    # Build full path using user_data_dir as base
    if config_paths is None:
        raise RuntimeError("config_paths should not be None after initialization")
    base_dir = config_paths.user_data_dir
    full_path = base_dir / subpath

    logger.debug(LOG_MSG_ZMACHINE_PATH, data_path, full_path)

    # Validate if this looks like a file reference (contains zVaFile keywords)
    if any(keyword in data_path for keyword in ZMACHINE_KEYWORDS):
        # Check if file exists (add .yaml extension for zVaFiles)
        test_path = Path(str(full_path) + FILE_EXT_YAML)
        if not test_path.exists():
            raise zMachinePathError(
                zpath=data_path,
                resolved_path=str(test_path),
                context_type="file"
            )

    return str(full_path)

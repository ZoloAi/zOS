"""
zSys.Utils - System-level utility exports and compatibility helpers.

This module consolidates utility re-exports previously exposed via zOS.utils.
New code should import from here directly.
"""

# Cache utilities - lazy import to avoid circular dependency
# zSys.Utils is imported by zConfig, which is needed by zLoader
# So we can't import zLoader at module level
def _lazy_cache_utils():
    """Lazy import of cache_utils to avoid circular imports."""
    from zOS.L1_Foundation.c_zLoader.loader_modules import cache_utils  # pylint: disable=redefined-outer-name
    return cache_utils


def create_shortcut_from_cache(*args, **kwargs):
    """Re-export from zLoader for backward compatibility."""
    return _lazy_cache_utils().create_shortcut_from_cache(*args, **kwargs)


def get_cached_files(*args, **kwargs):
    """Re-export from zLoader for backward compatibility."""
    return _lazy_cache_utils().get_cached_files(*args, **kwargs)


def get_cached_files_count(*args, **kwargs):
    """Re-export from zLoader for backward compatibility."""
    return _lazy_cache_utils().get_cached_files_count(*args, **kwargs)


def clear_system_cache(*args, **kwargs):
    """Re-export from zLoader for backward compatibility."""
    return _lazy_cache_utils().clear_system_cache(*args, **kwargs)


# Make cache_utils available as a property
class _CacheUtilsProxy:
    """Proxy to lazily load cache_utils module."""

    def __getattr__(self, name):
        return getattr(_lazy_cache_utils(), name)


cache_utils = _CacheUtilsProxy()

# Import from zSys.errors
# pylint: disable=wrong-import-position
from zSys.errors import (  # noqa: E402
    validate_zos_instance,
    validate_zcli_instance,  # Backward compatibility
    zTraceback,
    ExceptionContext,
    zCLIException,
    SchemaNotFoundError,
    DatabaseNotInitializedError,
    TableNotFoundError,
    ConfigurationError,
    ValidationError,
    zMachinePathError,
)

# Import from zSys.formatting
# pylint: disable=wrong-import-position
from zSys.formatting import (  # noqa: E402
    Colors,
    print_ready_message,
)

# Import from zSys.logger
# pylint: disable=wrong-import-position
from zSys.logger import (  # noqa: E402
    get_log_level_from_zspark,
    is_production_from_zspark,
    is_testing_from_zspark,
    should_suppress_init_prints,
)

# Additional exceptions from zSys.errors
# pylint: disable=wrong-import-position
from zSys.errors import (  # noqa: E402
    FormModelNotFoundError,
    InvalidzPathError,
    zUIParseError,
    AuthenticationRequiredError,
    PermissionDeniedError,
    PluginNotFoundError,
)

__all__ = [
    # From zSys (backward compatibility)
    "Colors",
    "validate_zos_instance",
    "validate_zcli_instance",
    "zTraceback",
    "ExceptionContext",
    "zCLIException",
    "SchemaNotFoundError",
    "DatabaseNotInitializedError",
    "TableNotFoundError",
    "ConfigurationError",
    "ValidationError",
    "zMachinePathError",

    # From zLoader cache utilities (backward compatibility)
    "cache_utils",
    "create_shortcut_from_cache",
    "get_cached_files",
    "get_cached_files_count",
    "clear_system_cache",

    # Formatting utilities
    "print_ready_message",
    # Logger configuration
    "get_log_level_from_zspark",
    "is_production_from_zspark",
    "is_testing_from_zspark",
    "should_suppress_init_prints",

    # Local exceptions
    "FormModelNotFoundError",
    "InvalidzPathError",
    "zUIParseError",
    "AuthenticationRequiredError",
    "PermissionDeniedError",
    "PluginNotFoundError",
]

# zOS/core/L1_Foundation/c_zLoader/loader_modules/loader_validator.py

"""
Validation layer for loader configuration and file paths.

This module provides fail-fast validation for zLoader subsystem, following the
pattern established by a_zConfig's ConfigValidator. It validates cache configuration,
file paths, and cache types before any operations occur, preventing errors early
in the initialization/operation chain.

Purpose
-------
The LoaderValidator class provides upfront validation for zLoader operations,
implementing the "fail fast" principle to catch configuration errors before they
cause runtime issues. It validates cache configuration, file paths, and cache types.

Architecture
------------
**Tier 2.5 - Validation Layer**
    - Position: Validation tier between facade and operations
    - Dependencies: loader_constants, os, pathlib
    - Used By: zLoader (Tier 5), CacheOrchestrator (Tier 3)
    - Purpose: Fail-fast validation before operations

Key Responsibilities
--------------------
1. **Cache Configuration Validation**: Validate max_size, cache types, etc.
2. **File Path Validation**: Validate file paths are absolute and exist
3. **Cache Type Validation**: Validate cache_type is known
4. **Session Structure Validation**: Validate session dict structure

Design Decisions
----------------
1. **Fail Fast Pattern**: Following a_zConfig's ConfigValidator, validation
   happens BEFORE any initialization or operations, not during.

2. **Explicit Exceptions**: Raises ValidationError (not generic Exception) with
   clear error messages explaining what's wrong and how to fix it.

3. **No Logger Dependency**: Validation happens before logger may be available,
   so errors are raised directly, not logged.

4. **Immutable Validation**: Validators don't modify state, only check it.

5. **Composable Validation**: Each validation method is independent and focused,
   enabling selective validation based on context.

External Usage
--------------
**Used By**:
    - zLoader.py: Validates file paths before loading
    - cache_orchestrator.py: Validates cache_type before routing
    - User code: Can validate before operations

Integration Points
------------------
**zLoader.__init__**:
    - Validates cache configuration during initialization
    - Raises ValidationError if invalid configuration

**zLoader.handle()**:
    - Validates file path before loading
    - Raises ValidationError if path invalid

**CacheOrchestrator.get/set()**:
    - Validates cache_type parameter
    - Raises ValidationError if unknown cache type

Version History
---------------
- v1.6.0: Created validation layer (Phase 3 refactoring - enhancement)
"""

from zOS import Any, Dict, Path
from .loader_constants import (
    # Cache type constants
    CACHE_TYPE_SYSTEM,
    CACHE_TYPE_PINNED,
    CACHE_TYPE_SCHEMA,
    CACHE_TYPE_PLUGIN,
    CACHE_TYPE_ALL,
    # Error message templates
    ERROR_INVALID_MAX_SIZE,
    ERROR_INVALID_FILE_PATH,
    ERROR_INVALID_CACHE_TYPE,
    ERROR_INVALID_CACHE_CONFIG,
    # Exception class (centralized)
    ValidationError,
)


# ============================================================================
# LOADERVALIDATOR CLASS
# ============================================================================

class LoaderValidator:
    """
    Validates loader configuration and file paths before operations.
    
    Provides fail-fast validation following a_zConfig's ConfigValidator pattern.
    All validation methods raise ValidationError with clear messages if validation
    fails, enabling early error detection and debugging.
    
    Attributes
    ----------
    None (stateless validator)
    
    Examples
    --------
    **Validate Cache Configuration**:
        >>> validator = LoaderValidator()
        >>> cache_config = {'max_size': 100}
        >>> validator.validate_cache_config(cache_config)  # No error
        >>> 
        >>> invalid_config = {'max_size': -1}
        >>> validator.validate_cache_config(invalid_config)
        ValidationError: Invalid max_size: -1 (must be positive integer)
    
    **Validate File Path**:
        >>> validator.validate_file_path("/path/to/file.zolo")  # No error
        >>> validator.validate_file_path("relative/path.zolo")
        ValidationError: Invalid file path: relative/path.zolo (must be absolute)
    
    **Validate Cache Type**:
        >>> validator.validate_cache_type("system")  # No error
        >>> validator.validate_cache_type("unknown")
        ValidationError: Invalid cache type: unknown
    
    Notes
    -----
    **Stateless Design**: No instance state, all methods are stateless.
    **Explicit Errors**: Raises ValidationError with clear messages.
    **No Logging**: Validation happens before logger available.
    """

    # Valid cache types (as tuple for in-membership checks)
    VALID_CACHE_TYPES = (
        CACHE_TYPE_SYSTEM,
        CACHE_TYPE_PINNED,
        CACHE_TYPE_SCHEMA,
        CACHE_TYPE_PLUGIN,
        CACHE_TYPE_ALL,
    )

    def validate_cache_config(self, cache_config: Dict[str, Any]) -> None:
        """
        Validate cache configuration dictionary.
        
        Checks:
        - max_size is positive integer (if present)
        - cache_type is valid (if present)
        - No unknown configuration keys
        
        Parameters
        ----------
        cache_config : Dict[str, Any]
            Cache configuration dictionary
        
        Raises
        ------
        ValidationError
            If cache configuration is invalid
        
        Examples
        --------
        >>> validator = LoaderValidator()
        >>> validator.validate_cache_config({'max_size': 100})  # OK
        >>> validator.validate_cache_config({'max_size': -1})   # ValidationError
        >>> validator.validate_cache_config({'max_size': 'invalid'})  # ValidationError
        
        Notes
        -----
        **Optional Validation**: Returns None (no error) if config is valid.
        **Fail Fast**: Raises on first validation error found.
        """
        if not isinstance(cache_config, dict):
            raise ValidationError(
                ERROR_INVALID_CACHE_CONFIG.format(reason="must be a dictionary")
            )

        # Validate max_size (if present)
        if 'max_size' in cache_config:
            max_size = cache_config['max_size']
            if not isinstance(max_size, int) or max_size <= 0:
                raise ValidationError(
                    ERROR_INVALID_MAX_SIZE.format(value=max_size)
                )

        # Validate cache_type (if present)
        if 'cache_type' in cache_config:
            cache_type = cache_config['cache_type']
            self.validate_cache_type(cache_type)

    def validate_file_path(
        self,
        file_path: str,
        must_exist: bool = False,
        must_be_absolute: bool = True,
    ) -> None:
        """
        Validate file path string.
        
        Checks:
        - Path is non-empty string
        - Path is absolute (if must_be_absolute=True)
        - File exists (if must_exist=True)
        
        Parameters
        ----------
        file_path : str
            File path to validate
        must_exist : bool, optional
            If True, validates file exists on disk (default: False)
        must_be_absolute : bool, optional
            If True, validates path is absolute (default: True)
        
        Raises
        ------
        ValidationError
            If file path is invalid
        
        Examples
        --------
        >>> validator = LoaderValidator()
        >>> validator.validate_file_path("/path/to/file.zolo")  # OK
        >>> validator.validate_file_path("relative/path.zolo")  # ValidationError (not absolute)
        >>> validator.validate_file_path("/nonexistent.zolo", must_exist=True)  # ValidationError
        
        Notes
        -----
        **Flexible Validation**: must_exist and must_be_absolute are optional.
        **Path Type**: Accepts both str and Path, converts to Path internally.
        """
        if not file_path or not isinstance(file_path, (str, Path)):
            raise ValidationError(
                ERROR_INVALID_FILE_PATH.format(path=file_path)
            )

        path = Path(file_path) if isinstance(file_path, str) else file_path

        # Validate absolute path (if required)
        if must_be_absolute and not path.is_absolute():
            raise ValidationError(
                ERROR_INVALID_FILE_PATH.format(path=file_path) + " (must be absolute)"
            )

        # Validate file exists (if required)
        if must_exist and not path.exists():
            raise ValidationError(
                ERROR_INVALID_FILE_PATH.format(path=file_path) + " (file not found)"
            )

    def validate_cache_type(self, cache_type: str) -> None:
        """
        Validate cache type string.
        
        Checks:
        - cache_type is non-empty string
        - cache_type is in VALID_CACHE_TYPES
        
        Parameters
        ----------
        cache_type : str
            Cache type to validate ("system", "pinned", "schema", "plugin", "all")
        
        Raises
        ------
        ValidationError
            If cache type is invalid
        
        Examples
        --------
        >>> validator = LoaderValidator()
        >>> validator.validate_cache_type("system")   # OK
        >>> validator.validate_cache_type("pinned")   # OK
        >>> validator.validate_cache_type("unknown")  # ValidationError
        
        Notes
        -----
        **Known Types**: See VALID_CACHE_TYPES class attribute.
        **Case Sensitive**: Validation is case-sensitive ("System" != "system").
        """
        if not cache_type or not isinstance(cache_type, str):
            raise ValidationError(
                ERROR_INVALID_CACHE_TYPE.format(type=cache_type)
            )

        if cache_type not in self.VALID_CACHE_TYPES:
            raise ValidationError(
                ERROR_INVALID_CACHE_TYPE.format(type=cache_type) +
                f" (valid types: {', '.join(self.VALID_CACHE_TYPES)})"
            )

    def validate_session_structure(self, session: Dict[str, Any], namespace: str) -> None:
        """
        Validate session dictionary has expected structure for cache.
        
        Checks:
        - session is a dict
        - namespace exists in session (if namespace provided)
        
        Parameters
        ----------
        session : Dict[str, Any]
            Session dictionary to validate
        namespace : str
            Expected namespace key (e.g., "zCache")
        
        Raises
        ------
        ValidationError
            If session structure is invalid
        
        Examples
        --------
        >>> validator = LoaderValidator()
        >>> session = {"zCache": {"system_cache": {}}}
        >>> validator.validate_session_structure(session, "zCache")  # OK
        >>> validator.validate_session_structure({}, "zCache")  # ValidationError
        
        Notes
        -----
        **Namespace Check**: Only validates namespace exists, not its contents.
        **Graceful**: Returns None if validation passes.
        """
        if not isinstance(session, dict):
            raise ValidationError(
                ERROR_INVALID_CACHE_CONFIG.format(reason="session must be a dictionary")
            )

        if namespace and namespace not in session:
            raise ValidationError(
                ERROR_INVALID_CACHE_CONFIG.format(
                    reason=f"session missing required namespace: {namespace}"
                )
            )


# ============================================================================
# MODULE METADATA
# ============================================================================

# Note: ValidationError is imported from loader_constants, not defined here
__all__ = ["LoaderValidator"]

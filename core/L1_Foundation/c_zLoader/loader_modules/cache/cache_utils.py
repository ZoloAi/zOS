# zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_utils.py

"""
Cache utility functions for zLoader subsystem.

This module provides user-facing utilities to inspect and manage zLoader's
multi-tier cache system (pinned, system, schema, plugin). These utilities are
designed for interactive use (via zShell func commands) and programmatic access.

Purpose
-------
The cache_utils module serves as user-facing utilities (Tier 6) in the zLoader
architecture, providing inspection and management functions for all cache tiers.
It complements the internal cache implementations (Tier 2) by offering high-level
tools for cache visibility and control.

Architecture
------------
**Tier 6 - User Utilities (Cache Inspection & Management)**
    - Position: User-facing layer above facade
    - Dependencies: Requires initialized zos instance
    - Used By: zShell func commands, Python scripts
    - Purpose: Cache inspection + management + shortcut creation

**6-Tier Architecture**:
    - Tier 1: Foundation (loader_io.py - Raw file I/O)
    - Tier 2: Cache Implementations (System, Pinned, Schema, Plugin)
    - Tier 3: Cache Orchestrator (CacheOrchestrator - Unified cache router)
    - Tier 4: Package Aggregator (loader_modules/__init__.py)
    - Tier 5: Facade (zLoader.py - Public interface to zOS)
    - Tier 6: User Utilities ← THIS MODULE

Key Functions
-------------
1. **get_cached_files()**: List all cached files from system and pinned caches
2. **get_cached_files_count()**: Get cache statistics by tier
3. **clear_system_cache()**: Clear system cache (Tier 2)
4. **create_shortcut_from_cache()**: Interactive wizard for shortcut creation

Layer Position
--------------
Layer 2, Position 8 (zLoader - Tier 6 User Utilities)

External Usage
--------------
**Used By**:
    - zOS/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_shortcut.py
      Usage: from zSys.Utils import create_shortcut_from_cache
      Purpose: shortcut cache command (interactive shortcut creation)

See Also
--------
- cache_orchestrator.py: Underlying cache router (Tier 3)
- loader_cache_system.py: System cache implementation
- loader_cache_pinned.py: Pinned cache implementation
- zLoader.py: zLoader facade that manages these caches

Version History
---------------
- v1.5.9: Moved from zSys to zLoader (proper architectural placement)
- v1.5.8: Original implementation in zSys
"""

from zOS import Any, List, Dict


def get_cached_files(zos: Any) -> List[str]:
    """
    Get list of all currently cached files (system + pinned).
    
    Retrieves cached file paths from both system_cache and pinned_cache,
    returning a deduplicated list of file names/paths.
    
    Args:
        zos: zOS framework instance (auto-injected when called via func command)
            - zos.loader.cache.system_cache: System-level cache
            - zos.loader.cache.pinned_cache: User-pinned cache
    
    Returns:
        List[str]: List of cached file paths/names
            Format: ["path/to/file1", "path/to/file2 → $alias", ...]
    
    Examples:
        # From zShell
        >>> func @.zCLI.utils.cache_utils.get_cached_files
        [
            "/workspace/zUI.users.zolo (System Cache)",
            "@.Schemas.zSchema.users → $users (Pinned)"
        ]
        
        # From Python
        >>> from zSys.Utils import cache_utils
        >>> cache_utils.get_cached_files()
        >>> cached = get_cached_files(zos)
        >>> print(f"Found {len(cached)} cached files")
    
    Cache Tiers:
        Tier 1 (Pinned): User-loaded, never evicted, has aliases
        Tier 2 (System): Auto-cached, LRU eviction, mtime tracking
        Tier 3 (Disk): Not included (direct I/O fallback)
    
    Notes:
        - System cache keys have "parsed:" prefix (removed in output)
        - Pinned cache items include alias (e.g., "→ $alias")
        - Duplicates are preserved (same file in both caches)
    """
    cached_files: List[str] = []

    # Get from system_cache (Tier 2)
    system_cache = zos.loader.cache.system_cache._cache  # pylint: disable=protected-access
    for key in system_cache:
        # Extract filename from cache key (remove "parsed:" prefix)
        display_key = key.replace("parsed:", "")
        cached_files.append(f"{display_key} (System Cache)")

    # Get from pinned_cache (Tier 1)
    pinned = zos.loader.cache.pinned_cache.list_aliases()
    for item in pinned:
        cached_files.append(f"{item['zpath']} → ${item['name']} (Pinned)")

    return cached_files


def get_cached_files_count(zos: Any) -> Dict[str, Any]:
    """
    Get count of cached files by tier.
    
    Returns a summary of cache statistics across both tiers.
    
    Args:
        zos: zOS framework instance (auto-injected when called via func command)
    
    Returns:
        Dict[str, Any]: Cache statistics
            {
                "system_cache": int,   # Tier 2 count
                "pinned_cache": int,   # Tier 1 count
                "total": int           # Combined count
            }
    
    Examples:
        >>> func @.zCLI.utils.cache_utils.get_cached_files_count
        {
            "system_cache": 3,
            "pinned_cache": 2,
            "total": 5
        }
    """
    system_count = len(zos.loader.cache.system_cache._cache)  # pylint: disable=protected-access
    pinned_count = len(zos.loader.cache.pinned_cache.list_aliases())

    return {
        "system_cache": system_count,
        "pinned_cache": pinned_count,
        "total": system_count + pinned_count
    }


def clear_system_cache(zos: Any) -> Dict[str, str]:
    """
    Clear the system cache (Tier 2).
    
    Removes all entries from the system-level cache while
    preserving pinned cache entries.
    
    Args:
        zos: zOS framework instance (auto-injected when called via func command)
    
    Returns:
        Dict[str, str]: Status message
            {"status": "System cache cleared"}
    
    Examples:
        >>> func @.zCLI.utils.cache_utils.clear_system_cache
        {"status": "System cache cleared"}
    
    Notes:
        - Only clears Tier 2 (system cache)
        - Pinned cache (Tier 1) is preserved
        - Use load clear command to clear pinned cache
    """
    zos.loader.cache.clear(cache_type="system")
    return {"status": "System cache cleared"}


def create_shortcut_from_cache(zos: Any) -> Dict[str, str]:
    """
    Interactive wizard to create a shell shortcut from cached files.
    
    This function provides a complete interactive flow:
    1. Display cached files as a numbered menu
    2. Prompt user to select a file
    3. Prompt user for shortcut name
    4. Create the shortcut
    5. Display success message
    
    Args:
        zos: zOS framework instance (auto-injected when called via func command)
            - zos.display: For menu and input display
            - zos.shell.shortcuts: For shortcut creation
    
    Returns:
        Dict[str, str]: Result status
            {"status": "created", "shortcut": "name", "file": "path"}
            OR
            {"status": "cancelled"}
    
    Examples:
        # From zShell
        >>> shortcut cache
        # (Interactive menu appears, user selects file and enters name)
        
        # From Python
        >>> from zSys.Utils import create_shortcut_from_cache
        >>> result = create_shortcut_from_cache(zos)
        >>> print(result["status"])
    
    Notes:
        - Bypasses YAML zDisplay wrapper limitations by calling methods directly
        - Uses zMenu for file selection (interactive numbered menu)
        - Uses read_string for shortcut name input
        - Validates shortcut name (no spaces, special chars)
        - Prevents overwriting existing shortcuts without confirmation
    """
    # Step 1: Get cached files
    files = get_cached_files(zos)

    if not files:
        zos.display.warning("No cached files available")
        zos.display.text("Load a file first using: load <path>", indent=1)
        return {"status": "cancelled", "reason": "no_cache"}

    # Step 2: Display menu and get selection
    menu_pairs = list(enumerate(files))

    zos.display.text("")  # Blank line
    zos.display.header("Create Shortcut from Cache", color="CYAN")

    selected_file = zos.display.zMenu(
        menu_items=menu_pairs,
        prompt="Select a cached file:",
        return_selection=True
    )

    if not selected_file:
        zos.display.info("Selection cancelled")
        return {"status": "cancelled", "reason": "no_selection"}

    # Step 3: Prompt for shortcut name
    zos.display.text("")  # Blank line
    shortcut_name = zos.display.read_string(
        prompt="Enter shortcut name (e.g., 'gs', 'myui'): "
    )

    if not shortcut_name or not shortcut_name.strip():
        zos.display.warning("Shortcut name cannot be empty")
        return {"status": "cancelled", "reason": "empty_name"}

    shortcut_name = shortcut_name.strip()

    # Validate shortcut name (basic validation)
    if ' ' in shortcut_name or any(c in shortcut_name for c in ['/', '\\', '|', ';', '&']):
        zos.display.error("Invalid shortcut name. Avoid spaces and special characters.")
        return {"status": "cancelled", "reason": "invalid_name"}

    # Step 4: Create the shortcut by adding to session
    # Initialize shortcuts dict if not present
    if "zShortcuts" not in zos.session:
        zos.session["zShortcuts"] = {}

    shortcuts = zos.session["zShortcuts"]

    # Check if shortcut already exists
    if shortcut_name in shortcuts:
        zos.display.warning(f"Shortcut '{shortcut_name}' already exists: {shortcuts[shortcut_name]}")
        overwrite = zos.display.read_string("Overwrite? (y/n): ")
        if overwrite.lower() not in ['y', 'yes']:
            zos.display.info("Shortcut creation cancelled")
            return {"status": "cancelled", "reason": "exists"}

    # Create the shortcut (command to load the file)
    command = f"load {selected_file}"
    shortcuts[shortcut_name] = command

    # Display success
    zos.display.text("")  # Blank line
    zos.display.success(f"Shortcut '{shortcut_name}' created!")
    zos.display.text(f"  File: {selected_file}", indent=1)
    zos.display.text(f"  Command: {command}", indent=1)
    zos.display.text(f"  Usage: {shortcut_name}", indent=1)

    return {
        "status": "created",
        "shortcut": shortcut_name,
        "file": selected_file,
        "command": command
    }

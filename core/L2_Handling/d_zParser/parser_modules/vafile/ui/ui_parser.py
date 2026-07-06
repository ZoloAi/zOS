# zOS/core/L2_Handling/g_zParser/parser_modules/vafile/ui/ui_parser.py

"""
Main UI file parser for vafile/ui package.

Orchestrates UI file parsing with RBAC extraction and zBlock processing.

Public API:
    - parse_ui_file: Main UI file parser (CRITICAL - used by parser_file.py)

External Usage:
    - parser_file.py: Uses parse_ui_file for UI parsing

Created: Phase 5.4 - Extract Main Parser from vafile_ui.py
"""

from zOS import Any, Dict, Optional

# Import from parent vafile package
from .. import (
    FILE_TYPE_UI,
    DICT_KEY_TYPE, DICT_KEY_FILE_PATH, DICT_KEY_ZBLOCKS, DICT_KEY_METADATA_KEY,
    DICT_KEY_RBAC,
    LOG_MSG_PARSING_UI, LOG_MSG_FILE_RBAC_FOUND, LOG_MSG_PROCESSING_ZBLOCK,
    LOG_MSG_PARSING_UI_COMPLETED,
    SCOPE_FILE,
    extractzRBAC_directives,
    extract_ui_metadata
)

# Import from sibling modules
from .ui_zblock_processor import parse_ui_zblock

# Navigation alias SSOT — canonicalize Greek-letter event names at the UI parse
# boundary so every downstream consumer (zCLI walker/dispatch AND the Bifrost
# serializer) receives the canonical zLink / zPsi spelling.
from zSys.nav_aliases import canonicalize_nav_aliases


def parse_ui_file(
    data: Dict[str, Any],
    logger: Any,
    file_path: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse UI file with UI-specific logic and validation.
    
    ⚠️ CRITICAL: This function is used externally by parser_file.py.
    Signature must remain stable.
    
    Parses a UI file (zUI.*) with comprehensive RBAC directive extraction and
    zBlock processing. This is the main entry point for UI file parsing and is
    called by parser_file.py when a UI file is detected.
    
    Process Flow:
        1. **File-Level RBAC Extraction**: Extract !require_* directives from root
        2. **zBlock Processing**: Parse each menu section (zBlock)
        3. **Metadata Extraction**: Count zBlocks, UI constructs, and items
        4. **Return**: Structured UI data with RBAC and metadata
    
    Args:
        data: Parsed YAML/JSON data from UI file
        logger: Logger instance for diagnostic output
        file_path: Optional file path for error messages and logging
        session: Optional session dict (reserved for future session-aware parsing)
    
    Returns:
        Optional[Dict[str, Any]]: Parsed UI structure, or None on fatal error.
            
            On success, returns dict with format:
            {{
                "type": "ui",
                "file_path": str or None,
                "zblocks": {{
                    "zblock_name": {{
                        "name": str,
                        "type": "zblock",
                        "items": {{...}},
                        "constructs": {{...}},
                        "_filezRBAC": {{...}} or None
                    }}
                }},
                "metadata": {{...}},
                "zRBAC": {{...}} or None  # File-level RBAC (if exists)
            }}
            
            Returns None if fatal validation error (e.g., empty zBlock)
    
    Examples:
        >>> data = {{
        ...     "!require_role": "user",
        ...     "Main Menu": {{
        ...         "Add User": {{"zFunc": "add_user"}},
        ...         "Delete User": {{
        ...             "zRBAC": {{"require_role": "admin"}},
        ...             "zFunc": "delete_user"
        ...         }}
        ...     }}
        ... }}
        >>> logger = get_logger()
        >>> result = parse_ui_file(data, logger, file_path="zUI.users.yaml")
        >>> result["zRBAC"]
        {{"require_role": "user"}}
        >>> result["zblocks"]["Main Menu"]["items"]["Add User"]["zRBAC"]
        None  # Inherits from file-level
        >>> result["zblocks"]["Main Menu"]["items"]["Delete User"]["zRBAC"]
        {{"require_role": "admin"}}  # Inline RBAC overrides
    
    External Usage:
        parser_file.py (line 43):
            from .parser_vafile import parse_ui_file
            parsed_ui = parse_ui_file(data, logger, file_path=file_path, session=session)
        Purpose: Parse UI files with RBAC extraction
    
    Notes:
        - Signature stability is CRITICAL for external usage
        - File-level RBAC applies to all items (unless overridden)
        - Inline zRBAC in items overrides file-level RBAC
        - Default behavior: PUBLIC ACCESS (no RBAC = accessible to all)
        - zBlocks must be dictionaries (validated)
        - Metadata includes zBlock count, construct counts, total items
    
    See Also:
        - extractzRBAC_directives: Extracts file-level RBAC
        - parse_ui_zblock: Parses individual zBlocks
        - parser_file.py: External usage
        - authzRBAC.py: Verifies RBAC during execution
    """
    logger.framework.debug(LOG_MSG_PARSING_UI)

    # Greek-letter navigation alias normalization (SSOT seam). Rewrite authored
    # zAlpha→zLink / zOmega→zPsi (keys + imperative wrappers) once, here, so the
    # parsed UI everything downstream consumes is single-spelling. zDelta/zURL
    # are untouched.
    data = canonicalize_nav_aliases(data)

    parsed_ui: Dict[str, Any] = {
        DICT_KEY_TYPE: FILE_TYPE_UI,
        DICT_KEY_FILE_PATH: file_path,
        DICT_KEY_ZBLOCKS: {},
        DICT_KEY_METADATA_KEY: {}
    }

    # Extract file-level RBAC directives (v1.5.4 Week 3.3)
    filezRBAC, data_withoutzRBAC = extractzRBAC_directives(data, logger, scope=SCOPE_FILE)
    if filezRBAC:
        parsed_ui[DICT_KEY_RBAC] = filezRBAC
        logger.framework.debug(LOG_MSG_FILE_RBAC_FOUND, filezRBAC)

    # Process each zBlock (menu section) using cleaned data
    for zblock_name, zblock_data in data_withoutzRBAC.items():
        if not isinstance(zblock_data, dict):
            # Enhanced error message with clear fix suggestion
            logger.error(
                f"\n{'='*60}\n"
                f"ERROR: Empty or invalid zBlock detected\n"
                f"{'='*60}\n"
                f"  File: {file_path}\n"
                f"  Block: '{zblock_name}'\n"
                f"  Problem: zBlock is empty (got {type(zblock_data).__name__})\n"
                f"\n"
                f"  Current YAML:\n"
                f"    {zblock_name}:\n"
                f"\n"
                f"  Expected YAML:\n"
                f"    {zblock_name}:\n"
                f"      Block_Name:\n"
                f"        - zDisplay:\n"
                f"            event: text\n"
                f"            content: 'Your content here'\n"
                f"\n"
                f"  Fix: Add at least one sub-block with content under '{zblock_name}'\n"
                f"{'='*60}"
            )
            # Return None to immediately stop processing - this is a fatal error
            return None

        logger.debug(LOG_MSG_PROCESSING_ZBLOCK, zblock_name)

        # Parse zBlock content (with file-level RBAC passed down)
        parsed_zblock = parse_ui_zblock(zblock_name, zblock_data, logger, session, filezRBAC=filezRBAC)
        parsed_ui[DICT_KEY_ZBLOCKS][zblock_name] = parsed_zblock

    # Extract UI metadata
    parsed_ui[DICT_KEY_METADATA_KEY] = extract_ui_metadata(data)

    logger.framework.debug(LOG_MSG_PARSING_UI_COMPLETED, len(parsed_ui[DICT_KEY_ZBLOCKS]))
    return parsed_ui

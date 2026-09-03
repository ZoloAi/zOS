# zOS/core/L2_Handling/h_zNavigation/navigation_modules/navigation_constants.py

"""
Navigation Constants - Centralized Constants for zNavigation Subsystem.

This module provides all constants used across the zNavigation subsystem, organized
into logical categories for easy maintenance and discovery.

Organization:
    - Session Keys: Keys for session storage
    - Dictionary Keys: Keys for data dictionaries
    - Display Settings: Visual formatting configuration
    - Status & Operations: State machine values
    - Navigation & Semantic Types: Navigation categorization
    - Prefixes & Separators: String parsing constants
    - Commands & Prompts: User interaction strings
    - Templates & Formatters: String formatting patterns
    - Error Messages: User-facing error text
    - Log Messages: Internal logging text
    - Configuration Values: Numeric configuration

Architecture:
    Tier: Foundation (Tier 0) - Pure constants, no dependencies
    
    Used By:
    - MenuSystem (menu creation & display)
    - Breadcrumbs (trail management)
    - Navigation (state tracking)
    - Linking (inter-file navigation)
    - MenuBuilder (menu construction)
    - MenuRenderer (display formatting)
    - MenuInteraction (user input)

Public vs Private:
    - PUBLIC constants: Exported in __all__, used by external code (35 constants)
    - PRIVATE constants: Prefixed with _, not exported, module-internal only (168 constants)
    
    Privatization Ratio: 83% (168/203)

Version History:
    - v1.5.8: Phase 3.4.3 - Privatized 168 internal constants (83% ratio)
      * PUBLIC: 35 constants (session keys, menu keys, navigation types, status values)
      * PRIVATE: 168 constants (display, logging, formatting, parsing internals)
    - v1.5.7: Phase 3.4.1 - Created during constants extraction
      * Centralized 203 constants from 8 module files
      * Organized into 12 logical categories
      * Established PUBLIC vs PRIVATE boundary
"""

# Canonical cross-subsystem session keys (root SSOT via a_zConfig → zVocabulary).
# zVaFolder/zVaFile are shared with zLoader, zParser, zDispatch — alias them here
# rather than re-declaring the literal so the schema has one source of truth.
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZVAFOLDER as SESSION_KEY_VAFOLDER,
    SESSION_KEY_ZVAFILE as SESSION_KEY_VAFILE,
)

# Canonical control-flow return signals (root SSOT in zVocabulary). zNavigation
# and zOpen both return these to the walker; alias rather than re-declare so the
# "zBack"/"stop" contract has one source of truth.
from zOS.zVocabulary import (
    CONTROL_RETURN_ZBACK,
    CONTROL_RETURN_STOP,
)

# ============================================================================
# Session Keys - Keys for session storage (PUBLIC - 4)
# ============================================================================

# Navigation-internal session keys (not shared — local to zNavigation state)
SESSION_KEY_CURRENT_LOCATION: str = "current_location"
SESSION_KEY_NAVIGATION_HISTORY: str = "navigation_history"

# ============================================================================
# Dictionary Keys - Keys for data dictionaries
# ============================================================================

# Generic Dictionary Keys (PRIVATE - internal state management)
_DICT_KEY_TARGET: str = "target"
_DICT_KEY_CONTEXT: str = "context"
_DICT_KEY_TIMESTAMP: str = "timestamp"
_DICT_KEY_STATUS: str = "status"
_DICT_KEY_MESSAGE: str = "message"

# Menu-specific Keys (PUBLIC - 6, used by external code to build/inspect menus)
KEY_OPTIONS: str = "options"
KEY_TITLE: str = "title"
KEY_ALLOW_BACK: str = "allow_back"
KEY_METADATA: str = "metadata"
KEY_CREATED_BY: str = "created_by"
KEY_TIMESTAMP: str = "timestamp"

# Breadcrumb-specific Keys (PRIVATE - internal breadcrumb state)
_KEY_TRAILS: str = "trails"
_KEY_CONTEXT: str = "_context"
_KEY_DEPTH_MAP: str = "_depth_map"

# ============================================================================
# Display Settings - Visual formatting configuration (PRIVATE)
# ============================================================================

# Display Colors (PUBLIC - 3, may be referenced externally)
COLOR_MENU: str = "MENU"
COLOR_ZCRUMB: str = "ZCRUMB"
DISPLAY_COLOR_ZLINK: str = "ZLINK"

# Display Styles (PRIVATE - internal formatting)
_DISPLAY_STYLE_FULL: str = "full"
_DISPLAY_STYLE_SINGLE: str = "single"
_DISPLAY_STYLE_TILDE: str = "~"
_DISPLAY_STYLE_INIT: str = "full"
_STYLE_FULL: str = "full"

# Display Indentation (PRIVATE - internal formatting)
_DISPLAY_INDENT_INIT: int = 0
_DISPLAY_INDENT_HANDLE: int = 1
_DISPLAY_INDENT_PARSE: int = 2
_DISPLAY_INDENT_AUTH: int = 2
_DISPLAY_INDENT_MENU: int = 1
_INDENT_ZCRUMBS: int = 2
_INDENT_ZBACK: int = 1

# Display Messages (PRIVATE - internal display labels)
_DISPLAY_MSG_READY: str = "zNavigation Ready"
_DISPLAY_MSG_CREATE: str = "zNavigation Menu Create"
_DISPLAY_MSG_SELECT: str = "zNavigation Menu Select"
_DISPLAY_MSG_HANDLE: str = "Handle zNavigation Menu"
_DISPLAY_MSG_RETURN: str = "zNavigation Menu return"
_DISPLAY_MSG_HANDLE_ZLINK: str = "Handle zLink"
_DISPLAY_MSG_PARSE: str = "zLink Parsing"
_DISPLAY_MSG_AUTH: str = "zLink Auth"
_MSG_HANDLE_ZCRUMBS: str = "Handle zNavigation Breadcrumbs"
_MSG_HANDLE_ZBACK: str = "zBack"

# ============================================================================
# Status & Operation Types - State machine values (PUBLIC)
# ============================================================================

# Status Values (PUBLIC - 3, returned to external code)
STATUS_NAVIGATED: str = "navigated"
STATUS_ERROR: str = "error"
STATUS_STOP: str = CONTROL_RETURN_STOP  # SSOT: zVocabulary.CONTROL_RETURN_STOP

# Trampoline signal (PUBLIC — SSOT for the zCLI REPLACE-navigation hop).
# A staged navigation (zLink/zDelta/zBack/zPsi) returns this sentinel; the
# executor bubbles it up to zWalker.run()'s trampoline, which re-enters
# execute_loop with the destination staged in session["_pending_nav"].
# MUST equal zWalker.NAV_SIGNAL and zGuard zengine's _SIGNAL_NAVIGATE.
# Any seam that consumes a dispatch result (menus, buttons, wizards) must
# PROPAGATE this value, never swallow it — swallowing it ends the session
# with the landed page never rendered (zOS#19).
NAV_SIGNAL: str = "navigate"

# Operation Types (PUBLIC - 5, used by breadcrumb API)
OP_RESET: str = "RESET"
OP_APPEND: str = "APPEND"
OP_REPLACE: str = "REPLACE"
OP_POP: str = "POP"
OP_NEW_KEY: str = "NEW_KEY"

# ============================================================================
# Navigation & Semantic Types - Navigation categorization (PUBLIC)
# ============================================================================

# One-shot marker (top-level of the crumbs map) that the user's NEXT navigation
# is a navbar pick → triggers the trail RESET. SSOT: set/read/cleared only via
# Breadcrumbs.set_navbar_pending / is_navbar_pending / reset_trail.
KEY_NAVBAR_PENDING: str = "_navbar_navigation"

# Companion marker holding the HOST SCOPE for an INLINE navbar pick. Global navbars
# reset to absolute root (full clear); inline navbars must reset only DOWN TO their
# host scope (the block the bar lives in) so a nested host — e.g. a zDash page —
# is preserved rather than wiped. When present, reset_trail does a SCOPED truncation
# (keep host + ancestors, drop deeper) instead of clearing every scope. SSOT:
# set via set_navbar_pending(scoped=True); read/cleared by reset_trail.
KEY_NAVBAR_SCOPED: str = "_navbar_host_scope"

# Navigation Types (PUBLIC - 7, used by external navigation logic)
NAV_NAVBAR: str = "navbar"
NAV_DELTA: str = "delta"
NAV_DASHBOARD: str = "dashboard_panel"
NAV_MENU: str = "menu_select"
NAV_SEQUENTIAL: str = "sequential"
NAV_ZLINK: str = "zlink"
NAV_ZBACK: str = CONTROL_RETURN_ZBACK  # SSOT: zVocabulary.CONTROL_RETURN_ZBACK
# Friendly display label for the auto-injected Back option. The option VALUE stays
# NAV_ZBACK (the selection key the wizard interprets as Back) — this is the human
# label shown in the rendered menu list only, so the terminal reads "← Back" instead
# of the raw "zBack" action token.
NAV_ZBACK_LABEL: str = "← Back"

# Done — the navbar's "exit-forward" affordance. zNavbars are innately ANCHORED
# (no Back); instead they always carry a visible Done row. Picking an item is a
# terminal nav (it RESETs + hops); picking Done is a NON-navigating signal that
# returns control to the wizard so the block flow continues to the next key
# (e.g. inline Done → falls through to the global navbar; global Done at root →
# the loop ends). The option VALUE is NAV_ZDONE (intercepted by modifier_menu,
# never reaches the wizard); NAV_ZDONE_LABEL is the human row label.
NAV_ZDONE: str = "zDone"
NAV_ZDONE_LABEL: str = "✓ Done"

# Semantic Types (PUBLIC - 5, used for depth/semantic classification)
TYPE_ROOT: str = "root"
TYPE_PANEL: str = "panel"
TYPE_MENU: str = "menu"
TYPE_SELECTION: str = "selection"
TYPE_SEQUENTIAL: str = "sequential"

# Creator Identifiers (PUBLIC - 1, part of menu metadata API)
CREATOR_ZMENU: str = "zMenu"

# ============================================================================
# Prefixes & Separators - String parsing constants (PRIVATE)
# ============================================================================

# Prefixes (PRIVATE - internal parsing)
_PREFIX_NEWLINE: str = "\n"
_PREFIX_SEARCH: str = "/"
_PREFIX_BLOCK_DELTA: str = "$"
_PREFIX_DEFAULT_PATH: str = "@."
_PARSE_PREFIX_ZLINK: str = "zLink("

# Separators (PRIVATE - internal string formatting)
_SEPARATOR_CRUMB: str = " > "
_SEPARATOR_DOT: str = "."
_SEPARATOR_EMPTY: str = ""
_SEPARATOR_COMMA: str = ","
_SEPARATOR_SPACE: str = " "
_SEPARATOR_COMPACT: str = " | "
_PATH_SEPARATOR: str = "."
_PARSE_PERMS_SEPARATOR: str = ", {"

# Parsing Tokens (PRIVATE - internal parsing)
_PARSE_SUFFIX_RPAREN: str = ")"
_PARSE_BRACE_OPEN: str = "{"
_PARSE_BRACE_CLOSE: str = "}"

# ============================================================================
# Commands & Prompts - User interaction strings (PRIVATE)
# ============================================================================

# Commands (PRIVATE - internal command detection)
_CMD_EXIT: str = "exit"

# Prompts (PRIVATE - internal user prompts)
_PROMPT_DEFAULT: str = "> "
_PROMPT_MULTIPLE_DEFAULT: str = "Select options (comma-separated)"
_PROMPT_SEARCH_DEFAULT: str = "Search"
_DEFAULT_PROMPT: str = "Select option"

# ============================================================================
# Templates & Formatters - String formatting patterns (PRIVATE)
# ============================================================================

# Menu Templates (PRIVATE - internal string formatting)
_TEMPLATE_SIMPLE_ITEM: str = "  [{index}] {option}"
_TEMPLATE_COMPACT_ITEM: str = "{index}:{option}"
_TEMPLATE_OPTION_ITEM: str = "  [{index}] {option}"
_TEMPLATE_SEARCH_PROMPT: str = "\n{search_prompt} (enter number or /term to filter):"

# Result Templates (PRIVATE - internal result formatting)
_TEMPLATE_RESULTS_FROM: str = "Results from {func_name}"
_TEMPLATE_ERROR_CALLING: str = "Error calling {func_name}"
_TEMPLATE_FILTERED_COUNT: str = "Filtered to {count} options:"
_TEMPLATE_INVALID_INDICES: str = "Invalid indices: {invalid_indices}"

# Error Title Templates (PRIVATE - internal error formatting)
_TITLE_ERROR: str = "Error"
_TITLE_FUNC_ERROR_TEMPLATE: str = "Error calling {func_name}"

# Timestamp Formats (PRIVATE - internal timestamp formatting)
_TIMESTAMP_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# Error Messages - User-facing error text (PRIVATE)
# ============================================================================

# General Errors (PRIVATE - internal error handling)
_ERROR_MSG_NO_ZCLI: str = "zNavigation requires a zCLI instance"
_ERROR_MSG_NO_WALKER: str = "requires walker parameter"
_MSG_NO_WALKER: str = "[ERROR] No walker instance provided to zLink."
_MSG_PERMISSION_DENIED: str = "Permission denied for this section."

# Input Validation Errors (PRIVATE - internal validation)
_ERR_INVALID_DIGIT: str = "Invalid input - enter a number."
_ERR_OUT_OF_RANGE: str = "Choice out of range."
_ERR_INVALID_COMMA: str = "Invalid input - enter comma-separated numbers."
_ERR_INVALID_SEARCH: str = "Invalid input - enter a number or /search"

# Dynamic Menu Errors (PRIVATE - internal error handling)
_ERR_DYNAMIC_MENU: str = "Error loading menu"
_ERR_FUNCTION_MENU: str = "Function error"

# Breadcrumb Errors (PRIVATE - internal error handling)
_ERR_EMPTY_FILENAME: str = "Cannot reload file: zVaFile is empty in session"
_ERR_NO_KEYS_AFTER_BACK: str = "No keys in active zBlock after zBack; cannot resume."

# Warning Messages (PRIVATE - internal warnings)
_MSG_NO_HISTORY: str = "No navigation history"
_MSG_HISTORY_CLEARED: str = "Navigation history cleared"
_WARN_NO_MATCHES: str = "No matches found."

# ============================================================================
# Log Messages - Internal logging text (PRIVATE - ALL)
# ============================================================================

# General Log Messages (PRIVATE)
_LOG_MSG_READY: str = "[zNavigation] Unified navigation system ready"

# Menu System Logs (PRIVATE)
_LOG_BUILT_MENU: str = "Built menu object: %s"
_LOG_FAILED_DYNAMIC: str = "Failed to build dynamic menu: %s"
_LOG_FAILED_FUNCTION: str = "Failed to build menu from function %s: %s"
_LOG_ZMENU_OBJECT: str = (
    "\nzMenu object:\n"
    "- Title: %s\n"
    "- Options: %s\n"
    "- allow_back: %s\n"
    "- created_by: %s"
)
_LOG_ANCHOR_ACTIVE: str = "Anchor mode active - injecting zBack into menu."
_LOG_MENU_OPTIONS: str = "zMenu options:\n%s"
_LOG_MENU_SELECTED: str = "Menu selected: %s"

# Menu Renderer Logs (PRIVATE)
_LOG_RENDERED_MENU: str = "Rendered full menu with %d options"
_LOG_RENDERED_SIMPLE: str = "Rendered simple menu with %d options"
_LOG_RENDERED_COMPACT: str = "Rendered compact menu with %d options"
_LOG_BREADCRUMB_FAILED: str = "Breadcrumb display not available: %s"

# Navigation State Logs (PRIVATE)
_LOG_NAVIGATING_TO: str = "Navigating to: %s"

# Linking Logs (PRIVATE)
_LOG_INCOMING_REQUEST: str = "incoming zLink request: %s"
_LOG_ZLINK_PATH: str = "zLink_path: %s"
_LOG_REQUIRED_PERMS: str = "required_perms: %s"
_LOG_ZFILE_PARSED: str = "zFile_parsed: %s"
_LOG_RAW_EXPRESSION: str = "Raw zLink expression: %s"
_LOG_STRIPPED_INNER: str = "Stripped inner contents: %s"
_LOG_PATH_PART: str = "Path part: %s"
_LOG_PERMS_PART_RAW: str = "Permissions part (raw): %s"
_LOG_PARSED_PERMS: str = "Parsed required permissions: %s"
_LOG_WARN_NON_DICT: str = "strict_eval returned non-dict permissions. Defaulting to empty."
_LOG_NO_PERMS_BLOCK: str = "[INFO] No permission block found. Path: %s"
_LOG_ZAUTH_USER: str = "zAuth user: %s"
_LOG_REQUIRED_PERMS_CHECK: str = "Required permissions: %s"
_LOG_NO_PERMS_REQUIRED: str = "No permissions required - allowing access."
_LOG_CHECK_PERM_KEY: str = "Checking permission key: %s | expected=%s, actual=%s"
_LOG_WARN_PERM_DENIED: str = "Permission denied. Required %s=%s, but got %s"
_LOG_ALL_PERMS_MATCHED: str = "All required permissions matched."

# Breadcrumb Logs (PRIVATE)
_LOG_INCOMING_BLOCK_KEY: str = "\nIncoming zBlock: %s,\nand zKey: %s"
_LOG_CURRENT_ZCRUMBS: str = "\nCurrent zCrumbs: %s"
_LOG_CURRENT_TRAIL: str = "\nCurrent zTrail: %s"
_LOG_DUPLICATE_SKIP: str = "Breadcrumb '%s' already exists at the end of scope '%s' - skipping."
_LOG_ACTIVE_CRUMB: str = "active_zCrumb: %s"
_LOG_ORIGINAL_CRUMB: str = "original_zCrumb: %s"
_LOG_ACTIVE_BLOCK: str = "active_zBlock: %s"
_LOG_TRAIL: str = "trail: %s"
_LOG_TRAIL_AFTER_POP: str = "Trail after pop in '%s': %s"
_LOG_POPPED_SCOPE: str = "Popped empty zCrumb scope: %s => %s"
_LOG_ACTIVE_CRUMB_PARENT: str = "active_zCrumb (parent): %s"
_LOG_PARENT_TRAIL_BEFORE: str = "parent trail before pop: %s"
_LOG_PARENT_TRAIL_AFTER: str = "parent trail after pop: %s"
_LOG_ROOT_EMPTY: str = "Root scope reached with empty trail; nothing to pop."
_LOG_POST_POP_EMPTY: str = "Post-pop empty scope removed: %s => %s"
_LOG_PARENT_TRAIL_PRE_SECOND: str = "parent trail (pre second pop): %s"
_LOG_PARENT_TRAIL_POST_SECOND: str = "parent trail (post second pop): %s"
_LOG_ROOT_CLEARED: str = "Root scope reached; crumb cleared but scope preserved."
_LOG_ACTIVE_PARTS: str = "Active zCrumb parts: %s (count: %d)"
_LOG_PARSED_SESSION: str = "Parsed session: path=%s, filename=%s, block=%s"
_LOG_RELOADING_PATH: str = "Reloading file with zPath: %s"
_LOG_WARN_INVALID_KEY: str = "Resolved zKey %r not valid for block %r"
_LOG_ERR_INVALID_CRUMB: str = "Invalid active_zCrumb format: %s (needs at least 3 parts)"

# Menu Interaction Logs (PRIVATE)
_LOG_RAW_INPUT: str = "User raw input: '%s'"
_LOG_INVALID_DIGIT: str = "Input is not a valid digit."
_LOG_OUT_OF_RANGE: str = "Input index %s is out of range."
_LOG_SELECTED: str = "Selected: %s"
_LOG_SELECTED_MULTIPLE: str = "Selected multiple: %s"
_LOG_SELECTED_SEARCH: str = "Selected with search: %s"

# ============================================================================
# Configuration Values - Numeric configuration (PRIVATE)
# ============================================================================

# Navigation History Settings (PRIVATE - internal config)
_HISTORY_MAX_SIZE: int = 50
_HISTORY_FIRST_INDEX: int = 0

# Path Parsing Indices & Limits (PRIVATE - internal parsing magic numbers)
_PATH_INDEX_LAST: int = -1
_PATH_INDEX_BLOCK: int = -1
_PATH_INDEX_FILENAME_START: int = -2
_PATH_PARTS_MIN: int = 2
_PATH_PARTS_BASE_OFFSET: int = -2
_PATH_DEFAULT_BASE: str = ""

# Breadcrumb Parsing Indices (PRIVATE - internal parsing magic numbers)
_CRUMB_PARTS_MIN: int = 3
_INDEX_PARTS_FROM_END: int = -3
_INDEX_FILENAME_START: int = -3
_INDEX_FILENAME_END: int = -1
_INDEX_LAST_PART: int = -1

# Default Configuration (PRIVATE - internal defaults)
_DEFAULT_ALLOW_BACK: bool = True
_DEFAULT_INDENT: int = 0
_DEFAULT_STYLE_FULL: str = "full"
_DEFAULT_STYLE_SINGLE: str = "single"


# ============================================================================
# Exports (PUBLIC API - 35 constants)
# ============================================================================

__all__ = [
    # Session Keys (4) - Used by external subsystems (zDispatch, zWalker)
    "SESSION_KEY_CURRENT_LOCATION",
    "SESSION_KEY_NAVIGATION_HISTORY",
    "SESSION_KEY_VAFOLDER",
    "SESSION_KEY_VAFILE",

    # Menu Object Keys (6) - Used by external code to build/inspect menus
    "KEY_OPTIONS",
    "KEY_TITLE",
    "KEY_ALLOW_BACK",
    "KEY_METADATA",
    "KEY_CREATED_BY",
    "KEY_TIMESTAMP",

    # Display Colors (3) - May be referenced externally
    "COLOR_MENU",
    "COLOR_ZCRUMB",
    "DISPLAY_COLOR_ZLINK",

    # Status Values (3) - Returned to external code
    "STATUS_NAVIGATED",
    "STATUS_ERROR",
    "STATUS_STOP",
    "NAV_SIGNAL",

    # Operation Types (5) - Used by breadcrumb API
    "OP_RESET",
    "OP_APPEND",
    "OP_REPLACE",
    "OP_POP",
    "OP_NEW_KEY",

    # Navigation Types (7) - Used by external navigation logic
    "NAV_NAVBAR",
    "NAV_DELTA",
    "NAV_DASHBOARD",
    "NAV_MENU",
    "NAV_SEQUENTIAL",
    "NAV_ZLINK",
    "NAV_ZBACK",
    "NAV_ZBACK_LABEL",
    "NAV_ZDONE",
    "NAV_ZDONE_LABEL",

    # Semantic Types (5) - Used for depth/semantic classification
    "TYPE_ROOT",
    "TYPE_PANEL",
    "TYPE_MENU",
    "TYPE_SELECTION",
    "TYPE_SEQUENTIAL",

    # Creator Identifiers (1) - Part of menu metadata API
    "CREATOR_ZMENU",
]

# PRIVATE constants (not exported - 168 constants):
# - All _DISPLAY_* (display formatting internals)
# - All _LOG_* (internal logging)
# - All _ERR_*, _ERROR_MSG_*, _MSG_*, _WARN_* (internal error/warning handling)
# - All _TEMPLATE_*, _TITLE_* (internal string formatting)
# - All _PREFIX_*, _SEPARATOR_*, _PARSE_* (internal parsing)
# - All _PROMPT_*, _CMD_*, _DEFAULT_PROMPT (internal UI)
# - All _DICT_KEY_*, _KEY_* (internal dict keys)
# - All _HISTORY_*, _PATH_*, _CRUMB_*, _INDEX_*, _DEFAULT_*, _TIMESTAMP_FORMAT (internal config)
# - All _INDENT_*, _STYLE_* (internal formatting)

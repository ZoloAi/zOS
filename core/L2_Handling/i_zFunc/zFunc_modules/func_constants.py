# zOS/core/L2_Handling/i_zFunc/zFunc_modules/func_constants.py

"""
Centralized constants for the zFunc subsystem.

This module consolidates all constants used across zFunc modules, following
the pattern established in a_zConfig and b_zComm. Extracting constants to
a single location improves maintainability and prevents magic strings/numbers.

Pattern Source:
    - a_zConfig/zConfig_modules/config_constants.py
    - b_zComm/zComm_modules/comm_constants.py

Architecture Position
--------------------
**Tier 1: Foundation** - Central constants repository

Constants Categories:
    1. Execution timeouts
    2. Special argument identifiers
    3. Plugin search paths
    4. File extensions and characters
    5. Date/time format tokens
    6. Error messages
    7. Debug/log messages
    8. Parameter names

Version History
---------------
- v1.6.0: Extracted from distributed constants across modules (refactoring)
- v1.5.x: Constants lived in individual modules
"""

# ============================================================================
# Execution Timeouts (in seconds)
# ============================================================================

TIMEOUT_ASYNC_EXECUTION = 300  # 5 minutes for async Python functions
TIMEOUT_JS_EXECUTION = 30      # 30 seconds for JavaScript execution

# ============================================================================
# Special Argument Identifiers (zCLI-specific)
# ============================================================================

ARG_ZCONTEXT = "zContext"           # Full context dictionary injection
ARG_ZHAT = "zHat"                   # Wizard step context (from zWizard)
ARG_ZCONV = "zConv"                 # Dialog conversation data (from zDialog)
ARG_ZCONV_PREFIX = "zConv."         # Dialog field notation prefix
ARG_THIS_PREFIX = "this."           # Context key notation prefix

# ============================================================================
# Plugin System
# ============================================================================

# Standard search paths for plugin discovery (in priority order)
PLUGIN_SEARCH_PATHS = [
    "@",                   # Primary: Workspace root (for demo/test plugins)
    "@.zTestSuite.demos",  # Secondary: Test/demo plugins
    "@.utils",             # Tertiary: Workspace utilities
    "@.plugins",           # Quaternary: Workspace plugins directory
]

# ============================================================================
# File Extensions
# ============================================================================

# Drawn from the root SSOT (core/zVocabulary.py) so every subsystem agrees on
# the canonical extension atoms. Re-exported here for zFunc-local convenience.
from zOS.zVocabulary import FILE_EXT_PY, FILE_EXT_JS

# ============================================================================
# Characters
# ============================================================================

CHAR_DOT = '.'
CHAR_AMPERSAND = '&'
DELIMITER_COMMA = ","

# ============================================================================
# Brackets (for argument parsing)
# ============================================================================

BRACKETS_OPEN = "([{"
BRACKETS_CLOSE = ")]}"

# ============================================================================
# Date/Time Format Tokens
# ============================================================================

# Token mappings for _convert_format_to_strftime
DATE_FORMAT_CONVERSIONS = {
    "yyyy": "%Y",  # 4-digit year
    "yy": "%y",    # 2-digit year
    "mm": "%m",    # 2-digit month
    "dd": "%d",    # 2-digit day
    "HH": "%H",    # 24-hour
    "MM": "%M",    # minutes
    "SS": "%S",    # seconds
}

# Default formats (fallback when config unavailable)
DEFAULT_DATE_FORMAT = "ddmmyyyy"
DEFAULT_TIME_FORMAT = "HH:MM:SS"
DEFAULT_DATETIME_FORMAT = "ddmmyyyy HH:MM:SS"

# ============================================================================
# Parameter Names (for auto-injection)
# ============================================================================

PARAM_NAME_ZOS = "zos"
PARAM_NAME_SESSION = "session"
PARAM_NAME_CONTEXT = "context"

# ============================================================================
# Special Detection Strings
# ============================================================================

STR_COLLISION = "collision"
STR_PASSWORD = "password"  # For password masking

# ============================================================================
# Masking
# ============================================================================

MASK_DEFAULT = "********"

# ============================================================================
# Error Messages - Argument Parsing
# ============================================================================

ERROR_MSG_PARSE_FAILED = "Failed to parse args: %s"
ERROR_MSG_BRACKET_MISMATCH = "Bracket mismatch in argument string: {details}"
ERROR_MSG_INVALID_ARG_STR_TYPE = "arg_str must be a string, got: {arg_type}"
ERROR_MSG_INVALID_SPLIT_FN = "split_fn must be callable, got: {split_fn_type}"

# ============================================================================
# Error Messages - Plugin System
# ============================================================================

ERROR_MSG_PLUGIN_NOT_FOUND = "Plugin not found: {}"
ERROR_MSG_SEARCHED_IN = "Searched in: {}"
ERROR_MSG_PLUGIN_HINT = "Hint: Use 'plugin load <zPath>' to load from custom location"
ERROR_MSG_FUNCTION_NOT_FOUND = "Function not found in plugin '{}': {}"
ERROR_MSG_AVAILABLE_FUNCTIONS = "Available functions: {}"
ERROR_MSG_NOT_CALLABLE = "'{}' in plugin '{}' is not callable"

# ============================================================================
# Error Messages - Plugin Execution
# ============================================================================

ERROR_MSG_FUNCTION_CALL_FAILED = "Plugin function call failed: {}"
ERROR_MSG_CHECK_SIGNATURE = "Check function signature and arguments"
ERROR_MSG_EXECUTION_FAILED = "Plugin function execution failed: {}"

# ============================================================================
# Error Messages - JavaScript Execution
# ============================================================================

ERROR_MSG_NODE_NOT_FOUND = "Node.js not found. Please install Node.js to execute JavaScript functions."
ERROR_MSG_JS_FILE_NOT_FOUND = "JavaScript file not found: {file_path}"
ERROR_MSG_JS_EXECUTION_FAILED = "JavaScript execution failed for '{file_path} > {func_name}': {error}"
ERROR_MSG_JS_RESULT_PARSE = "Failed to parse JavaScript result as JSON: {error}"
ERROR_MSG_JS_FUNCTION_NOT_FOUND = "Function '{func_name}' not found in {file_path}"

# ============================================================================
# Browser-only JS detection (graceful zCLI/server feedback)
# ----------------------------------------------------------------------------
# A `.js` zFunc always runs server-side via a Node subprocess — on BOTH zCLI and
# zBifrost. The browser DOM/BOM does not exist there, so a function that touches
# these globals throws `ReferenceError: <global> is not defined`. We detect that
# class of failure and turn the raw traceback into one clean, render-agnostic
# signal that points the author to the right tool (a zScripts browser plugin).
# ============================================================================

# Common browser/DOM/BOM globals absent in a Node subprocess.
JS_BROWSER_GLOBALS = frozenset({
    "document", "window", "navigator", "location", "history", "screen",
    "localStorage", "sessionStorage",
    "requestAnimationFrame", "cancelAnimationFrame",
    "alert", "confirm", "prompt",
    "fetch", "XMLHttpRequest", "WebSocket",
    "Element", "HTMLElement", "Node", "CustomEvent", "Event",
    "customElements", "getComputedStyle", "matchMedia",
})

# Node's ReferenceError phrasing for a missing global: "<name> is not defined".
JS_NOT_DEFINED_SUFFIX = "is not defined"

# Graceful, render-agnostic feedback (shown as a warning signal: yellow line in
# zCLI, warning card in zBifrost). Names the offending global and the fix.
WARN_MSG_JS_BROWSER_ONLY = (
    "'{func_name}' is a browser-only function — it uses '{global_name}', which "
    "exists only in the browser. A zFunc runs server-side via Node (the same in "
    "zCLI and zBifrost), so DOM/UI code can't run here. Keep zFunc for data "
    "(compute / format / validate); move visual effects to a zScripts browser "
    "plugin. Skipped gracefully."
)
LOG_MSG_JS_BROWSER_ONLY = "Browser-only JS skipped: %s > %s (uses '%s')"

# ============================================================================
# Error Messages - Function Resolution
# ============================================================================

ERROR_MSG_MISSING_FUNCTION = "Function '{func_name}' not found in module '{module_path}'"
ERROR_MSG_INVALID_SYNTAX = "Invalid function call syntax: {syntax}"
ERROR_MSG_FILE_NOT_FOUND = "No such file: {file_path}"
ERROR_MSG_SPEC_NONE = "Failed to create module spec from: {file_path}"
ERROR_MSG_LOADER_NONE = "Module spec has no loader for: {file_path}"
ERROR_MSG_RESOLUTION_FAILED = "Failed to resolve callable from '%s > %s': %s"

# ============================================================================
# Debug Messages - Function Resolution
# ============================================================================

DEBUG_MSG_FILE_PATH = "File path: %s"
DEBUG_MSG_FUNCTION_NAME = "Function name: %s"
DEBUG_MSG_RESOLVED = "Resolved callable: %s"

# ============================================================================
# Debug Messages - Argument Parsing
# ============================================================================

DEBUG_MSG_NO_ARGS = "No arguments to parse"
DEBUG_MSG_RAW_ARG = "Raw arg string: %s"
DEBUG_MSG_SPLIT_ARGS = "Split args: %s"
DEBUG_MSG_INJECTED_ZCONTEXT = "Injected full zContext"
DEBUG_MSG_INJECTED_ZHAT = "Injected zHat from context: %s"
DEBUG_MSG_INJECTED_ZCONV = "Injected zConv from context: %s"
DEBUG_MSG_RESOLVED_ZCONV_FIELD = "Resolved 'zConv.%s' => %s"
DEBUG_MSG_RESOLVED_THIS_KEY = "Resolved 'this.%s' => %s"
DEBUG_MSG_EVALUATED_ZPARSER = "Evaluated via zParser '%s' => %s"
DEBUG_MSG_LITERAL_FALLBACK = "No zParser - using literal '%s'"
DEBUG_MSG_FINAL_ARGS = "Final parsed args: %s"

# ============================================================================
# Debug Messages - JavaScript Execution
# ============================================================================

DEBUG_MSG_JS_CALL = "Executing JavaScript: %s > %s with args: %s"
DEBUG_MSG_JS_RESULT = "JavaScript result: %s"
DEBUG_MSG_NODE_VERSION = "Node.js version: %s"

# ============================================================================
# Log Messages - Plugin Loading
# ============================================================================

LOG_MSG_CACHE_HIT = "Plugin cache HIT: %s"
LOG_MSG_CACHE_MISS = "Plugin cache MISS: %s (searching...)"
LOG_MSG_LOADING_PLUGIN = "Loading plugin: %s from %s"
LOG_MSG_FAILED_LOAD = "Failed to load from %s: %s"

# ============================================================================
# Log Messages - Plugin Execution
# ============================================================================

LOG_MSG_AUTO_INJECT = "Auto-injecting zos instance to plugin function"
LOG_MSG_AUTO_INJECT_CONTEXT = "Auto-injecting context to plugin function"
LOG_MSG_AUTO_INJECT_SESSION = "Auto-injecting session to function"
LOG_MSG_COROUTINE_DETECTED = "Plugin function returned coroutine - awaiting in event loop"
LOG_MSG_EVENT_LOOP_RUNNING = "Event loop is running - using run_coroutine_threadsafe"
LOG_MSG_NO_EVENT_LOOP = "No running event loop - using asyncio.run()"

# ============================================================================
# Module Metadata
# ============================================================================

__all__ = [
    # Timeouts
    "TIMEOUT_ASYNC_EXECUTION",
    "TIMEOUT_JS_EXECUTION",

    # Special arguments
    "ARG_ZCONTEXT",
    "ARG_ZHAT",
    "ARG_ZCONV",
    "ARG_ZCONV_PREFIX",
    "ARG_THIS_PREFIX",

    # Plugin system
    "PLUGIN_SEARCH_PATHS",

    # File extensions
    "FILE_EXT_PY",
    "FILE_EXT_JS",

    # Browser-only JS detection
    "JS_BROWSER_GLOBALS",
    "JS_NOT_DEFINED_SUFFIX",
    "WARN_MSG_JS_BROWSER_ONLY",
    "LOG_MSG_JS_BROWSER_ONLY",

    # Characters
    "CHAR_DOT",
    "CHAR_AMPERSAND",
    "DELIMITER_COMMA",

    # Brackets
    "BRACKETS_OPEN",
    "BRACKETS_CLOSE",

    # Date/time
    "DATE_FORMAT_CONVERSIONS",
    "DEFAULT_DATE_FORMAT",
    "DEFAULT_TIME_FORMAT",
    "DEFAULT_DATETIME_FORMAT",

    # Parameter names
    "PARAM_NAME_ZOS",
    "PARAM_NAME_SESSION",
    "PARAM_NAME_CONTEXT",

    # Special strings
    "STR_COLLISION",
    "STR_PASSWORD",

    # Masking
    "MASK_DEFAULT",
]

# zOS/core/L2_Handling/g_zParser/parser_modules/plugin/plugin_syntax.py

"""
Plugin invocation syntax parsing for plugin package.

Provides parsing and validation of plugin invocation syntax using regex,
and zPath resolution for plugin file paths.

Public API:
    - parse_plugin_invocation: Parse &Plugin.function(args) syntax
    - resolve_plugin_path: Convert zPath to file path

Dependencies:
    - re: Regex for syntax validation

Created: Phase 2.1 - Extract Syntax from parser_plugin.py
"""

from zOS import re, Any, Tuple

# Regex Patterns
# Peel the trailing call only: ``&<path>(<args>)``. The <path> body (everything
# between ``&`` and ``(``) is handed to the zPath SSOT (zSys.zpath.split), so the
# folder grammar lives in ONE place — never duplicated here. Args are captured
# lazily up to the final ``)``.
REGEX_PLUGIN_CALL: str = r'^(&[^()]*)\((.*?)\)$'

# Characters
CHAR_DOT: str = '.'
CHAR_AMPERSAND: str = '&'

# Error Messages
ERROR_MSG_INVALID_SYNTAX: str = "Invalid plugin invocation syntax: {}"
ERROR_MSG_EXPECTED_FORMAT: str = (
    "Expected format: &.plugin[.subfolder].function(args) "
    "— the leading dot is part of the sigil (like @. / ~.); a bare "
    "&plugin.fn() is not accepted."
)
ERROR_MSG_SYNTAX_EXAMPLES: str = (
    "Examples:\n"
    "  &.test_plugin.hello_world('Alice')\n"
    "  &.demos.deploy_demo.deploy()\n"
    "  &.DateUtils.get_timestamp()"
)


def parse_plugin_invocation(value: str) -> Tuple[str, str, str]:
    """
    Parse a ``&`` plugin invocation into (plugin_path, function_name, args).

    Folder-aware, SSOT-aligned grammar. The path body between ``&`` and ``(`` is
    decoded by the canonical zPath reader (``zSys.zpath.split``) — the SAME reader
    that powers ``@.``/``~.``/``&.`` everywhere else — so the dot-as-folder rule
    lives in ONE place. The leading dot is REQUIRED: ``&.`` is the canonical
    sigil (the dot belongs to it, exactly like ``@.``/``~.``), and a bare
    ``&demos.x.f()`` is rejected — not silently tolerated — so call sites stay
    single-form across the codebase. The LAST segment is the function, every
    segment before it is the plugin's file zPath (folders supported).

    Grammar::

        &.<seg>[.<seg>...].<function>(<args>)
        └─────── plugin path ─────┘ └ func ┘

    Args:
        value: Plugin invocation string to parse.

    Returns:
        Tuple[str, str, str]: (plugin_name, function_name, args_str)
            - plugin_name: Dotted plugin file path (e.g. ``"demos.deploy_demo"``
              or flat ``"test_plugin"``) — fed to the folder-aware loader.
            - function_name: Name of the function to call (last segment).
            - args_str: Arguments string (may be empty), parsed separately.

    Raises:
        ValueError: If syntax doesn't match ``&....(...)``, omits the canonical
            leading dot (``&.``), or lacks both a plugin segment and a function
            segment.

    Examples:
        >>> parse_plugin_invocation("&.test_plugin.hello('Alice')")
        ('test_plugin', 'hello', "'Alice'")

        >>> parse_plugin_invocation("&.demos.deploy_demo.deploy()")
        ('demos.deploy_demo', 'deploy', '')

        >>> parse_plugin_invocation("&.math.add(10, 20)")
        ('math', 'add', '10, 20')

    See Also:
        - zSys.zpath.split: The canonical sigil/segment decoder (SSOT).
        - plugin_loader.resolve_plugin_path: Folder-aware file lookup.
        - plugin_args.parse_plugin_arguments: Parses the args_str component.
    """
    # Step 1 — peel the trailing call: head = "&<path>", args = inside parens.
    match = re.match(REGEX_PLUGIN_CALL, value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError(
            f"{ERROR_MSG_INVALID_SYNTAX.format(value)}\n"
            f"{ERROR_MSG_EXPECTED_FORMAT}\n"
            f"{ERROR_MSG_SYNTAX_EXAMPLES}"
        )
    head, args_str = match.group(1), match.group(2)

    # Hard canon: the plugin sigil is "&." — the leading dot is part of it,
    # exactly like "@." / "~.". zpath_split strips boundary dots and so cannot
    # tell "&abc" from "&.abc"; enforce the dot HERE on the raw head before
    # decoding, so a bare "&plugin.fn()" is rejected, not silently tolerated.
    if not head.startswith(CHAR_AMPERSAND + CHAR_DOT):
        raise ValueError(
            f"{ERROR_MSG_INVALID_SYNTAX.format(value)}\n"
            f"{ERROR_MSG_EXPECTED_FORMAT}\n"
            f"{ERROR_MSG_SYNTAX_EXAMPLES}"
        )

    # Step 2 — decode the path body via the zPath SSOT (dot-delimited folder
    # segments → uniform decode; the leading dot was already vetted above).
    from zSys.zpath import split as zpath_split  # pylint: disable=import-outside-toplevel
    parts = zpath_split(head)
    segments = parts.segments

    # Need at least one plugin segment + one function segment.
    if parts.symbol != CHAR_AMPERSAND or len(segments) < 2:
        raise ValueError(
            f"{ERROR_MSG_INVALID_SYNTAX.format(value)}\n"
            f"{ERROR_MSG_EXPECTED_FORMAT}\n"
            f"{ERROR_MSG_SYNTAX_EXAMPLES}"
        )

    function_name = segments[-1]
    plugin_name = CHAR_DOT.join(segments[:-1])  # dotted path → folder-aware loader
    return plugin_name, function_name, args_str


def resolve_plugin_path(zpath: str, zos: Any) -> str:
    """
    Resolve zPath to absolute file path using zParser.
    
    Delegates to zParser's resolve_symbol_path() to convert a zPath string
    (e.g., "@.utils.test_plugin") into an absolute filesystem path.
    
    zPath Format:
        symbol.part1.part2.partN
        
        Where:
        - symbol: @ (workspace root), ~ (home), etc.
        - parts: Directory/file path components
    
    Args:
        zpath: zPath string (e.g., "@.utils.test_plugin")
        zos: zOS instance with zparser subsystem
    
    Returns:
        str: Absolute file path (without .py extension)
    
    Examples:
        >>> resolve_plugin_path("@.utils.test_plugin", zos)
        "/Users/user/workspace/utils/test_plugin"
        
        >>> resolve_plugin_path("@.plugins.data_processor", zos)
        "/Users/user/workspace/plugins/data_processor"
        
        >>> resolve_plugin_path("@.zTestSuite.demos.demo_plugin", zos)
        "/Users/user/workspace/zTestSuite/demos/demo_plugin"
    
    Notes:
        - Uses zParser's resolve_symbol_path() for resolution
        - Splits zPath by dot to extract symbol and parts
        - Returns path without .py extension (added by caller)
        - Symbol resolution follows zParser rules
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Uses this to resolve plugin paths
        - zParser.resolve_symbol_path: Underlying resolution logic
    """
    # Parse zPath
    parts = zpath.split(CHAR_DOT)
    symbol = parts[0]
    path_parts = parts[1:]

    # Resolve using zParser
    return zos.zparser.resolve_symbol_path(symbol, [symbol] + path_parts)

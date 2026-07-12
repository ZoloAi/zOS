# zOS/core/L2_Core/g_zParser/zParser.py

"""
zParser facade - unified interface for all parsing operations.

This module provides the zParser facade class, which serves as the primary
interface for all parsing operations in the zOS framework. The facade delegates
to specialized parser modules organized in a three-tier architecture.

Facade Pattern:
    The zParser class implements the Facade design pattern, providing a simplified
    unified interface to the complex subsystem of parser modules. This:
    - Simplifies client code (no need to know module structure)
    - Provides centralized access to all parsing operations
    - Encapsulates module dependencies and initialization
    - Enables consistent error handling and logging

Architecture Overview:
    **Tier 1 - Foundation (Core Utilities)**:
        - parser_utils: Expression evaluation, dotted paths, references
        - parser_path: Path resolution and file type identification
    
    **Tier 2 - Specialized Parsers**:
        - parser_commands: Command string parsing (20+ types)
        - parser_plugin: Plugin invocation resolution
        - parser_file: File content parsing (YAML, JSON, auto-detection)
        - vafile/ package: zVaFile parsing (UI, Schema, Config, Generic)
    
    **Tier 3 - Facade (This File)**:
        - zParser class: Unified interface delegating to Tier 1-2 modules
    
    **Tier 4 - Package Root**:
        - __init__.py: Package exports and initialization

Method Categories:
    The zParser facade organizes its 21+ methods into logical categories:
    
    1. **Path Resolution** (5 methods):
       - zPath_decoder, identify_zFile, resolve_zmachine_path
       - resolve_symbol_path, resolve_data_path
    
    2. **Plugin Invocation** (2 methods):
       - is_plugin_invocation, resolve_plugin_invocation
    
    3. **Command Parsing** (1 method):
       - parse_command
    
    4. **File Parsing** (6 methods):
       - parse_file_content, parse_yaml, parse_json
       - detect_format, parse_file_by_path, parse_json_expr
    
    5. **Expression Evaluation** (4 methods):
       - zExpr_eval, parse_dotted_path, handle_zRef, handle_zParser
    
    6. **zVaFile Parsing** (7 methods):
       - parse_zva_file, validate_zva_structure, extract_zva_metadata
       - parse_ui_file, parse_schema_file, parse_config_file
       - validate_ui_structure, validate_schema_structure
    
    7. **Function Path Parsing** (1 method):
       - parse_function_path (for zFunc)

Initialization:
    zParser requires a zOS instance during initialization. The instance must have:
    - session attribute (zSession dict)
    - logger attribute (logging instance)
    - display attribute (zDisplay instance)
    
    On initialization, zParser:
    1. Validates the zOS instance
    2. Extracts dependencies (session, logger, display)
    3. Declares readiness via display

External Usage:
    zParser is initialized during framework startup and is accessible
    as self.parser or zos.parser throughout the framework. All subsystems that
    need parsing functionality use this facade.

Design Principles:
    1. **Delegation**: All methods delegate to specialized modules
    2. **Dependency Injection**: zOS instance provides all dependencies
    3. **Validation**: Validates zOS instance and attributes
    4. **Consistency**: Consistent parameter passing (logger, session, display)
    5. **Type Safety**: 100% type hint coverage

Thread Safety:
    zParser is thread-safe as it delegates to thread-safe modules.
    The logger and session are passed as parameters to all delegated calls.

Performance:
    The facade adds minimal overhead (method call delegation). Performance
    characteristics depend on the underlying parser modules (see their docs).

Examples:
    >>> # Initialize (done by framework)
    >>> parser = zParser(zos)
    
    >>> # Path resolution
    >>> path = parser.zPath_decoder("zMachine.Config")
    >>> file_type = parser.identify_zFile("zUI.users.yaml", "/path/to/UI/")
    
    >>> # Command parsing
    >>> cmd = parser.parse_command("zFunc users.list --limit 10")
    
    >>> # File parsing
    >>> data = parser.parse_file_content(raw_yaml, ".yaml")
    >>> ui_data = parser.parse_ui_file(yaml_data, file_path="zUI.users.yaml")
    
    >>> # Expression evaluation
    >>> result = parser.zExpr_eval('{"key": "value"}')
    
    >>> # Plugin invocation
    >>> if parser.is_plugin_invocation("&MyPlugin.func()"):
    ...     result = parser.resolve_plugin_invocation("&MyPlugin.func()")

Version History:
    - v1.5.4 Week 6.8.1-6.8.8: All Tier 1-2 modules upgraded to A+
    - v1.5.4 Week 6.8.9: Facade upgraded (C+ → A+)
                         - Added 100% type hints
                         - Added module constants
                         - Comprehensive documentation
                         - Refactored imports to use aggregator
                         - Added missing methods

See Also:
    - parser_modules package: All specialized parser modules
    - zOS: Main framework instance (initializes zParser)
    - zLoader: Uses parser for UI file loading
    - zDispatch: Uses parser for plugin resolution
"""


__version__ = "1.0.0"
from zOS import Any, Dict, List, Optional, Tuple, Union

# Import from parser_modules aggregator (Week 6.8.8)
from .parser_modules import (
    # Path operations
    zPath_decoder as zPath_decoder_func,
    identify_zFile as identify_zFile_func,
    # Command operations
    parse_command as parse_command_func,
    # Utility operations
    zExpr_eval as zExpr_eval_func,
    parse_dotted_path as parse_dotted_path_func,
    handle_zRef as handle_zRef_func,
    handle_zParser as handle_zParser_func,
    # Plugin operations
    is_plugin_invocation as is_plugin_invocation_func,
    # File operations
    parse_file_content as parse_file_content_func,
    parse_yaml as parse_yaml_func,
    parse_json as parse_json_func,
    detect_format as detect_format_func,
    parse_file_by_path as parse_file_by_path_func,
    parse_json_expr as parse_json_expr_func,
    # zVaFile operations
    parse_ui_file as parse_ui_file_func,
    parse_schema_file as parse_schema_file_func,
    parse_config_file as parse_config_file_func,
    parse_generic_file as parse_generic_file_func,
)

# Additional imports from parser_modules (not in aggregator __all__)
from .parser_modules.parser_path import (
    resolve_zmachine_path as resolve_zmachine_path_func,
    resolve_symbol_path as resolve_symbol_path_func
)
from .parser_modules.vafile import (
    parse_zva_file as parse_zva_file_func,
    validate_zva_structure as validate_zva_structure_func,
    extract_zva_metadata as extract_zva_metadata_func,
    validate_ui_structure as validate_ui_structure_func,
    validate_schema_structure as validate_schema_structure_func,
    validate_config_structure as validate_config_structure_func
)

# zGuard seam — permissive in open-core, sealed by the zguard wheel when present.
from .parser_modules.parser_trust import verify_path_trust  # noqa: F401

# Subsystem constant SSOT (shared/file_constants) — avoid local literal copies.
from .parser_modules.shared.file_constants import (
    SESSION_KEY_ZSPACE,
    FILE_EXT_PY,
    FILE_EXT_JS,
    SYMBOL_AT,
    SYMBOL_TILDE,
    ZMACHINE_PREFIX_LONG,
)

# zPath grammar — Layer-0 SSOT for the sigil/segment decomposition. zParser owns
# filesystem resolution (parts → path); the dumb string peel comes from here.
from zSys import zpath


# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Display constants
PARSER_COLOR: str = "PARSER"
PARSER_READY_MESSAGE: str = "zParser Ready"

# Session dict keys (drawn from subsystem SSOT)
SESSION_KEY_WORKSPACE: str = SESSION_KEY_ZSPACE

# Supported function file extensions in resolution priority order
FUNC_FILE_EXTENSIONS: list = [FILE_EXT_PY, FILE_EXT_JS]

# Path prefixes (drawn from subsystem SSOT)
PATH_PREFIX_ZMACHINE: str = ZMACHINE_PREFIX_LONG
PATH_PREFIX_WORKSPACE: str = SYMBOL_AT
PATH_PREFIX_HOME: str = SYMBOL_TILDE  # bare ~ → user home (shell-style)

# Error messages
ERROR_MSG_NO_ZCLI: str = "zParser requires a zOS instance"
ERROR_MSG_NO_SESSION: str = "Invalid zOS instance: missing 'session' attribute"


# ============================================================================
# FACADE CLASS
# ============================================================================

class zParser:
    """
    zParser facade providing unified interface to all parsing operations.
    
    This facade delegates to specialized parser modules organized in a three-tier
    architecture (Foundation → Specialized → Facade). It provides 21+ methods
    covering path resolution, command parsing, file parsing, expression evaluation,
    and zVaFile parsing.
    
    Attributes:
        zos: zOS instance (dependency injection)
        zSession: Session dict from zOS
        logger: Logger instance from zOS
        display: zDisplay instance from zOS
        mycolor: Display color for parser messages
    
    Methods:
        See method docstrings below for comprehensive documentation.
    
    Examples:
        >>> parser = zParser(zos)
        >>> path = parser.zPath_decoder("zMachine.Config")
        >>> cmd = parser.parse_command("zFunc users.list")
        >>> data = parser.parse_file_content(raw_yaml, ".yaml")
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize zParser with zOS instance.
        
        Validates the zOS instance and extracts required dependencies
        (session, logger, display). Declares readiness via display.
        
        Args:
            zos: zOS instance providing dependencies
        
        Raises:
            ValueError: If zos is None or missing 'session' attribute
        
        Examples:
            >>> parser = zParser(zos)  # Done by framework during initialization
        """
        if zos is None:
            raise ValueError(ERROR_MSG_NO_ZCLI)

        if not hasattr(zos, 'session'):
            raise ValueError(ERROR_MSG_NO_SESSION)

        # Modern architecture: zOS instance provides all dependencies
        self.zos = zos
        self.zSession: Dict[str, Any] = zos.session
        self.logger: Any = zos.logger
        self.display: Any = zos.display
        self.mycolor: str = PARSER_COLOR
        self.display.zDeclare(PARSER_READY_MESSAGE, color=self.mycolor, indent=0, style="full")

        # Cache for path resolutions to reduce log noise
        self._resolved_paths_cache: set = set()

    # ═══════════════════════════════════════════════════════════
    # Path Resolution
    # ═══════════════════════════════════════════════════════════

    def zPath_decoder(
        self,
        zPath: Optional[str] = None,
        zType: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Resolve dotted paths to file paths.
        
        Args:
            zPath: Dotted path to resolve (e.g., "users.list")
            zType: Optional type hint for resolution
        
        Returns:
            Tuple[str, str]: (full_path, filename)
        
        Examples:
            >>> path = parser.zPath_decoder("users.list")
        """
        return zPath_decoder_func(self.zSession, self.logger, zPath, zType, self.display)

    def identify_zFile(
        self,
        filename: str,
        full_zFilePath: str
    ) -> tuple:
        """
        Identify file type and find actual file path with extension.
        
        Args:
            filename: Base filename to identify
            full_zFilePath: Full path to search
        
        Returns:
            tuple: (file_type, resolved_path)
        
        Examples:
            >>> file_type, path = parser.identify_zFile("users", "/path/to/UI/")
        """
        return identify_zFile_func(filename, full_zFilePath, self.logger, self.display)

    def resolve_zmachine_path(
        self,
        data_path: str,
        config_paths: Optional[Any] = None
    ) -> str:
        """
        Resolve ~.zMachine.* path references to OS-specific paths.
        
        Args:
            data_path: Path starting with ~.zMachine.
            config_paths: Optional config paths instance
        
        Returns:
            str: Resolved OS-specific path
        
        Examples:
            >>> path = parser.resolve_zmachine_path("~.zMachine.Config")
        """
        # Draw the live, zSpark-aware zConfigPaths from L1 (SSOT) instead of
        # letting the resolver instantiate a bare zConfigPaths() without zSpark.
        if config_paths is None:
            config_paths = getattr(getattr(self.zos, "config", None), "paths", None)
        return resolve_zmachine_path_func(data_path, self.logger, config_paths)

    def resolve_symbol_path(
        self,
        symbol: Optional[str],
        path_parts: list,
        workspace: Optional[str] = None
    ) -> str:
        """
        Resolve path based on symbol (@, ~, or no symbol).
        
        Args:
            symbol: Path symbol (@ for workspace, ~ for absolute, None for relative)
            path_parts: Path components list
            workspace: Optional workspace override
        
        Returns:
            str: Resolved path
        
        Examples:
            >>> path = parser.resolve_symbol_path("@", ["utils", "file"])
        """
        resolved_workspace: str = workspace or self.zSession.get(SESSION_KEY_WORKSPACE) or ""
        return resolve_symbol_path_func(symbol, path_parts, resolved_workspace, self.zSession, self.logger)

    def resolve_data_path(self, data_path: Union[str, Any]) -> Union[str, Any]:
        """
        Resolve data paths (supports ~.zMachine.* and @ workspace paths).
        
        Handles special path prefixes:
        - ~.zMachine.*: OS-specific machine paths
        - @: Workspace-relative paths
        - No prefix: Returns as-is
        
        Args:
            data_path: Path to resolve (str or other type)
        
        Returns:
            Union[str, Any]: Resolved path or original value if not string
        
        Examples:
            >>> path = parser.resolve_data_path("~.zMachine.Config")
            >>> path = parser.resolve_data_path("@utils.myfile")
        
        Notes:
            This method contains inline logic (not delegated to modules).
            Future: Consider moving to parser_modules.parser_path
        """
        if not isinstance(data_path, str):
            return data_path

        # zGuard path-trust gate (no-op in open-core; zGuard enforces containment)
        verify_path_trust(data_path, self.zos, self.logger)

        # Handle ~.zMachine.* paths (machine app-support persistence — NOT home).
        # Must precede the bare-~ home branch since it is a more specific ~ form.
        if data_path.startswith(PATH_PREFIX_ZMACHINE):
            return self.resolve_zmachine_path(data_path)

        # Handle ~ home paths (shell-style: ~ = current user's home directory)
        if data_path.startswith(PATH_PREFIX_HOME):
            from zOS import Path
            resolved = self._join_dotted_path(zpath.strip_symbol(data_path), Path.home())
            if data_path not in self._resolved_paths_cache:
                self.logger.debug("Resolved ~ path: %s => %s", data_path, resolved)
                self._resolved_paths_cache.add(data_path)
            return resolved

        # Handle @ workspace paths
        if data_path.startswith(PATH_PREFIX_WORKSPACE):
            from zOS import Path
            workspace = self.zSession.get(SESSION_KEY_WORKSPACE)
            workspace = Path(workspace) if workspace else Path.cwd()
            resolved = self._join_dotted_path(zpath.strip_symbol(data_path), workspace)
            # Only log the first time a path is resolved
            if data_path not in self._resolved_paths_cache:
                self.logger.debug("Resolved @ path: %s => %s", data_path, resolved)
                self._resolved_paths_cache.add(data_path)
            return resolved

        # No special prefix, return as-is
        return data_path

    def _join_dotted_path(self, dotted: str, base: Any) -> str:
        """Join a dot-delimited zPath body onto a base directory (extension-LESS).

        zPath is extension-less by default: every dotted segment is a path part,
        full stop. The OPTIONAL trailing-extension behaviour is NOT here — it is
        an EXCEPTION that lives ONLY in :meth:`resolve_zfile`, used by the
        extension-aware file events: zImage / zVideo / zAudio ``src`` and zInput
        ``type: file``. General data/resource paths never guess an extension, so
        a folder named ``docs`` or ``css`` is never mistaken for one.

        Args:
            dotted: The path body after the symbol (e.g. "static.media.demos.x").
            base:   A pathlib.Path base directory (workspace root or home).

        Returns:
            str: The resolved OS path.
        """
        path_parts = [p for p in dotted.strip(".").split(".") if p]
        return str(base / "/".join(path_parts))

    def resolve_zfile(
        self, value: Union[str, Any], allowed_exts: "Optional[set]" = None
    ) -> Union[str, Any]:
        """Extension-aware zPath resolution — file events ONLY.

        The extension-aware exception set is: zImage / zVideo / zAudio ``src``
        (resolved via MediaEvents._resolve_media_fields) and zInput ``type: file``.
        These events EXTEND the plain (extension-less) zPath grammar so the
        trailing file extension is OPTIONAL — no new separators, still dotted:

            omitted  → the single file whose stem matches in that directory is
                       used (auto-detect; the agnostic default, the whole point).
            included → the explicit ``<stem>.<ext>`` file is used, letting authors
                       disambiguate same-stem siblings (``logo.psd`` vs
                       ``logo.jpeg``) — the graphic-designer control case.

        ``allowed_exts`` (optional) is the event's declared allowed-extension set
        (bare, lower-case, no dot — e.g. ``{"png", "jpg"}``), derived from a
        zInput ``accept`` or a media event's type. When an extension is OMITTED
        and several ``<stem>.*`` siblings exist, it disambiguates by keeping only
        the accepted ones — turning ``logo.png``/``logo.zip`` from an ambiguous
        give-up into an auto-pick. Pure set filtering; final-type *validation*
        stays the caller's job.

        Pure dotted grammar in, an absolute OS path out (system-correct
        separators via ``os.path``). Existence is the caller's concern: when
        nothing matches we return the plain extension-less join so the caller's
        own "file not found" surfaces the original zPath.

        NOTE: scoped to the file/media events above. Plain resources
        (``@.zViews.…``, ``@.models.…``) must keep using :meth:`resolve_data_path`
        — routing them here would wrongly glob a folder name as a stem.
        """
        if not isinstance(value, str):
            return value

        import os
        from zOS import Path

        # zGuard path-trust gate (no-op in open-core; zGuard enforces containment)
        verify_path_trust(value, self.zos, self.logger)

        parts = zpath.split(value)
        segments = list(parts.segments)

        if parts.symbol == SYMBOL_TILDE:
            base = Path.home()
        elif parts.symbol == SYMBOL_AT:
            workspace = self.zSession.get(SESSION_KEY_WORKSPACE)
            base = Path(workspace) if workspace else Path.cwd()
        else:
            # Not a dotted zPath (native/literal path) — caller resolves it.
            return value

        base_str = str(base)
        if not segments:
            return base_str

        # Extension INCLUDED: '<dir>/<stem>.<ext>' is a real file.
        if len(segments) >= 2:
            ext_dir = os.path.join(base_str, *segments[:-2])
            ext_file = os.path.join(ext_dir, f"{segments[-2]}.{segments[-1]}")
            if os.path.isfile(ext_file):
                return ext_file

        # Extension OMITTED (default): auto-detect a single '<stem>.*' in '<dir>'.
        stem_dir = os.path.join(base_str, *segments[:-1])
        stem = segments[-1]
        if os.path.isdir(stem_dir):
            exact = os.path.join(stem_dir, stem)
            if os.path.isfile(exact):
                return exact
            matches = [
                name for name in os.listdir(stem_dir)
                if os.path.splitext(name)[0] == stem
                and os.path.isfile(os.path.join(stem_dir, name))
            ]
            # Declared allowed-extensions (accept / media type) disambiguate
            # same-stem siblings: keep only accepted ones when that narrows it.
            if allowed_exts and len(matches) > 1:
                accepted = [
                    name for name in matches
                    if os.path.splitext(name)[1].lstrip(".").lower() in allowed_exts
                ]
                if accepted:
                    matches = accepted
            if len(matches) == 1:
                return os.path.join(stem_dir, matches[0])
            if len(matches) > 1:
                self.logger.warning(
                    "[zParser] resolve_zfile: %d files match stem '%s' in %s — "
                    "include the extension to disambiguate.",
                    len(matches), stem, stem_dir,
                )

        # Best-effort extension-less join (caller's existence check reports a miss).
        return os.path.join(base_str, *segments)

    def absolute_path_to_web_path(self, absolute_path: str) -> str:
        """
        Convert absolute filesystem path to web-relative path for zServer.

        Checks all ZSERVER_MOUNTS first (custom mounts take priority), then
        falls back to serve_path for default-mounted directories (static/, UI/, etc.).

        Args:
            absolute_path: Absolute filesystem path (e.g., '/Users/.../zCloud/static/logo.png')

        Returns:
            str: Web-relative path (e.g., '/static/logo.png') if under any mount,
                 otherwise returns the original absolute_path

        Examples:
            >>> parser.absolute_path_to_web_path('/Users/.../zCloud/static/logo.png')
            '/static/logo.png'
            >>> parser.absolute_path_to_web_path('/Users/.../zbifrost-client/bifrost_core.js')
            '/zbifrost-client-local/bifrost_core.js'

        Integration:
            - SSOT for filesystem → HTTP URL conversion across zOS
            - Used by zOpen, zDisplay (Bifrost), and resolve_zpath_references
            - Respects all ZSERVER_MOUNTS and serve_path
        """
        from pathlib import Path

        zserver = getattr(self.zos, 'server', None)
        if not zserver:
            self.logger.debug("[zParser] zServer not available - returning absolute path")
            return absolute_path

        absolute_path_obj = Path(absolute_path).resolve()

        try:
            # Priority 1: check all registered mounts (ZSERVER_MOUNTS + defaults like /static/)
            static_mounts = getattr(zserver, 'static_mounts', None)
            if static_mounts:
                for url_prefix, mount_fs_path in static_mounts.items():
                    try:
                        mount_path_obj = Path(mount_fs_path).resolve()
                        if absolute_path_obj.is_relative_to(mount_path_obj):
                            rel_path = absolute_path_obj.relative_to(mount_path_obj)
                            web_path = url_prefix.rstrip("/") + "/" + str(rel_path).replace("\\", "/")
                            self.logger.debug("[zParser] Mount match: %s → %s", absolute_path, web_path)
                            return web_path
                    except (ValueError, AttributeError):
                        continue

            # Priority 2: serve_path fallback (catches anything under workspace root)
            serve_path = getattr(zserver, 'serve_path', None)
            if not serve_path:
                self.logger.debug("[zParser] zServer serve_path not configured - returning absolute path")
                return absolute_path

            serve_path_obj = Path(serve_path).resolve()
            if absolute_path_obj.is_relative_to(serve_path_obj):
                rel_path = absolute_path_obj.relative_to(serve_path_obj)
                web_path = "/" + str(rel_path).replace("\\", "/")
                self.logger.debug("[zParser] serve_path match: %s → %s", absolute_path, web_path)
                return web_path

            self.logger.debug("[zParser] Path outside all mounts: %s", absolute_path)
            return absolute_path

        except (ValueError, AttributeError) as e:
            self.logger.warning("[zParser] Error converting path %s: %s", absolute_path, e)
            return absolute_path

    # ═══════════════════════════════════════════════════════════
    # Plugin Invocation (& modifier)
    # ═══════════════════════════════════════════════════════════

    def is_plugin_invocation(self, value: Any) -> bool:
        """
        Check if value is a plugin invocation.
        
        Args:
            value: Value to check
        
        Returns:
            bool: True if value starts with & and looks like a plugin call
        
        Examples:
            >>> if parser.is_plugin_invocation("&test_plugin.hello_world('Alice')"):
            ...     result = parser.resolve_plugin_invocation("&test_plugin.hello_world('Alice')")
        """
        return is_plugin_invocation_func(value)

    def resolve_plugin_invocation(self, value: str, context: Optional[Any] = None) -> Any:
        """
        Resolve plugin function invocation with optional context for zWizard/zHat access.
        
        NOTE: This method now delegates execution to zFunc. zParser only handles
        syntax parsing; all loading and execution happens in zFunc subsystem.
        
        Syntax: &plugin_name.function_name(arg1, arg2, ...)
        
        Args:
            value: Plugin invocation string
            context: Optional context dict with zHat for wizard steps
        
        Returns:
            Any: Result of plugin function execution
        
        Raises:
            ValueError: If syntax is invalid, plugin not loaded, or function not found
        
        Examples:
            >>> result = parser.resolve_plugin_invocation("&test_plugin.hello_world('Alice')")
            "Hello, Alice!"
            
            >>> num = parser.resolve_plugin_invocation("&test_plugin.random_number(1, 10)")
            7  # Random integer between 1 and 10
        """
        # Delegate execution to zFunc (plugin system consolidated there)
        return self.zos.zfunc.execute_plugin(value, context=context)

    # ═══════════════════════════════════════════════════════════
    # Command Parsing
    # ═══════════════════════════════════════════════════════════

    def parse_command(self, command: str) -> Dict[str, Any]:
        """
        Parse shell commands into structured format.
        
        Supports 20+ command types including zFunc, zLink, zOpen, zWizard,
        zRead, and many others.
        
        Args:
            command: Command string to parse
        
        Returns:
            Dict[str, Any]: Structured command dict with type, args, options
        
        Examples:
            >>> cmd = parser.parse_command("zFunc users.list --limit 10")
            >>> cmd
            {"type": "zFunc", "function": "users.list", "args": {"limit": "10"}}
        """
        return parse_command_func(command, self.logger)

    # ═══════════════════════════════════════════════════════════
    # File Parsing (YAML/JSON)
    # ═══════════════════════════════════════════════════════════

    def parse_file_content(
        self,
        raw_content: Union[str, bytes],
        file_extension: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None
    ) -> Optional[Union[Dict[str, Any], list, str, int, float, bool]]:
        """
        Parse raw file content (YAML/JSON) into Python objects.
        
        Main file parser with auto-detection, RBAC transformation for UI files,
        and comprehensive error handling. CRITICAL method used by 6 subsystems.
        
        Args:
            raw_content: Raw file content (string or bytes)
            file_extension: Optional extension hint (".json", ".yaml", ".yml")
            session: Optional session dict (for RBAC context)
            file_path: Optional file path (for UI file detection)
        
        Returns:
            Optional[Union[Dict, list, str, int, float, bool]]: Parsed data or None
        
        Examples:
            >>> data = parser.parse_file_content(raw_yaml, ".yaml")
            >>> ui_data = parser.parse_file_content(raw_yaml, ".yaml", file_path="zUI.users.yaml")
        """
        return parse_file_content_func(raw_content, self.logger, file_extension, session=session, file_path=file_path)

    def parse_yaml(
        self, raw_content: Union[str, bytes]
    ) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
        """
        Parse YAML content into Python objects.
        
        Args:
            raw_content: Raw YAML content
        
        Returns:
            Optional[Union[Dict, List, str, int, float, bool]]: Parsed YAML or None on error
        
        Examples:
            >>> data = parser.parse_yaml("key: value")
            {"key": "value"}
        """
        return parse_yaml_func(raw_content, self.logger)

    def parse_json(
        self, raw_content: Union[str, bytes]
    ) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
        """
        Parse JSON content into Python objects.
        
        Args:
            raw_content: Raw JSON content
        
        Returns:
            Optional[Union[Dict, List, str, int, float, bool]]: Parsed JSON or None on error
        
        Examples:
            >>> data = parser.parse_json('{"key": "value"}')
            {"key": "value"}
        """
        return parse_json_func(raw_content, self.logger)

    def detect_format(self, raw_content: Union[str, bytes]) -> str:
        """
        Auto-detect file format from content inspection.
        
        Args:
            raw_content: Raw file content
        
        Returns:
            str: Detected format (".json" or ".yaml")
        
        Examples:
            >>> fmt = parser.detect_format('{"key": "value"}')
            ".json"
        """
        return detect_format_func(raw_content, self.logger)

    def parse_file_by_path(
        self, file_path: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
        """
        Load and parse file in one convenient call.
        
        Args:
            file_path: Path to file
        
        Returns:
            Optional[Union[Dict, List, str, int, float, bool]]: Parsed content or None on error
        
        Examples:
            >>> data = parser.parse_file_by_path("/path/to/config.yaml")
        """
        # zGuard path-trust gate (no-op in open-core; zGuard enforces containment)
        verify_path_trust(file_path, self.zos, self.logger)
        return parse_file_by_path_func(file_path, self.logger)

    def parse_json_expr(
        self, expr: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
        """
        Parse JSON-like expression strings into Python objects.
        
        Args:
            expr: JSON expression string
        
        Returns:
            Optional[Union[Dict, List, str, int, float, bool]]: Parsed expression or None on error
        
        Examples:
            >>> data = parser.parse_json_expr("{'key': 'value'}")  # Single quotes OK
            {"key": "value"}
        """
        return parse_json_expr_func(expr, self.logger)

    # ═══════════════════════════════════════════════════════════
    # Function Path Parsing (for zFunc)
    # ═══════════════════════════════════════════════════════════

    def parse_function_path(
        self,
        zFunc_spec: Union[str, Dict[str, Any]],
        zContext: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        Parse zFunc path specification into (func_path, arg_str, function_name).
        
        Supports multiple formats:
        - Dict: {"zFunc_path": "path/to/file.py", "zFunc_args": "args"}
        - String: "zFunc(@utils.myfile.my_function, args)"
        - String: "zFunc(path.to.file.function_name)"
        
        Args:
            zFunc_spec: zFunc specification (dict or string)
            zContext: Optional context dict
        
        Returns:
            tuple: (func_path, arg_str, function_name)
        
        Examples:
            >>> path, args, name = parser.parse_function_path("zFunc(@utils.myfile.my_function, arg1)")
        
        Notes:
            This method contains inline logic (not delegated to modules).
            Future: Consider moving to parser_modules.parser_utils
        """
        from zOS import os

        # Handle dict format
        if isinstance(zFunc_spec, dict):
            func_path = zFunc_spec["zFunc_path"]
            arg_str = zFunc_spec.get("zFunc_args")
            function_name = os.path.splitext(os.path.basename(func_path))[0]
            return func_path, arg_str, function_name

        # Handle string format: "zFunc(path.to.file.function_name, args)" OR "@.path.to.function(args)"
        if zFunc_spec.startswith("zFunc("):
            zFunc_raw = zFunc_spec[len("zFunc("):-1].strip()
        else:
            # Direct function call format: "@.path.to.function(args)"
            zFunc_raw = zFunc_spec

        self.logger.debug("Parsing zFunc spec: %s", zFunc_raw)
        if zContext:
            self.logger.debug("Context model: %s", zContext.get("model"))

        # Split path and arguments using parentheses for function calls
        if "(" in zFunc_raw and zFunc_raw.endswith(")"):
            # Extract function path and arguments: "path.to.func(arg1, arg2)" -> "path.to.func", "arg1, arg2"
            open_paren_idx = zFunc_raw.index("(")
            path_part = zFunc_raw[:open_paren_idx].strip()
            arg_str = zFunc_raw[open_paren_idx+1:-1].strip()  # Remove parentheses
            if not arg_str:  # Empty parentheses
                arg_str = None
        elif "," in zFunc_raw:
            path_part, arg_str = zFunc_raw.split(",", 1)
            arg_str = arg_str.strip()
        else:
            path_part = zFunc_raw
            arg_str = None

        # Parse path components: @utils.myfile.my_function OR @utils.myfile.js.my_function
        path_parts = path_part.split(".")
        function_name = path_parts[-1]  # "my_function"

        # Check if second-to-last part is a file extension (.js, .py, etc.)
        file_extension = None
        if len(path_parts) >= 3 and path_parts[-2] in ['js', 'py', 'mjs']:
            # Format: @.file.js.function → file_name="file", extension="js"
            file_extension = f".{path_parts[-2]}"
            file_name = path_parts[-3]
            path_prefix = path_parts[:-3]
        else:
            # Format: @.file.function → file_name="file", default to .py
            file_name = path_parts[-2]
            path_prefix = path_parts[:-2]

        self.logger.debug("file_name: %s", file_name)
        self.logger.debug("file_extension: %s", file_extension)
        self.logger.debug("function_name: %s", function_name)
        self.logger.debug("path_prefix: %s", path_prefix)

        # Extract symbol from first part
        first_part = path_prefix[0] if path_prefix else ""
        symbol = None

        if first_part and (first_part.startswith("@") or first_part.startswith("~")):
            symbol = first_part[0]
            # Remove symbol from first part
            path_prefix[0] = first_part[1:]

        self.logger.debug("symbol: %s", symbol)

        # Build path_parts list for resolve_symbol_path
        if symbol:
            symbol_parts = [symbol] + path_prefix
        else:
            symbol_parts = path_prefix

        # Use the class method - no cross-module imports needed!
        base_path = self.resolve_symbol_path(symbol, symbol_parts)

        # Add appropriate file extension
        if file_extension:
            func_path = os.path.join(base_path, f"{file_name}{file_extension}")
        else:
            # Language-agnostic resolution: probe supported extensions in order.
            # func_resolver routes to the correct runtime (importlib vs Node.js)
            # based on the extension it receives — no language logic here.
            base = os.path.join(base_path, file_name)
            resolved = next(
                (base + ext for ext in FUNC_FILE_EXTENSIONS if os.path.exists(base + ext)),
                None
            )
            func_path = resolved if resolved else base + FILE_EXT_PY

        self.logger.debug("Resolved func_path: %s", func_path)

        return func_path, arg_str, function_name

    # ═══════════════════════════════════════════════════════════
    # Expression Evaluation
    # ═══════════════════════════════════════════════════════════

    def zExpr_eval(self, expr: str) -> Any:
        """
        Evaluate JSON expressions.
        
        Args:
            expr: JSON expression string
        
        Returns:
            Any: Evaluated expression result
        
        Examples:
            >>> result = parser.zExpr_eval('{"key": "value"}')
            {"key": "value"}
        """
        return zExpr_eval_func(expr, self.logger, self.display)

    def parse_dotted_path(self, ref_expr: str) -> Dict[str, Any]:
        """
        Parse a dotted path into useful parts.
        
        Args:
            ref_expr: Dotted path expression (e.g., "user.name")
        
        Returns:
            Dict[str, Any]: Parsed path components
        
        Examples:
            >>> parts = parser.parse_dotted_path("user.name")
        """
        return parse_dotted_path_func(ref_expr)

    def handle_zRef(
        self,
        ref_expr: str,
        base_path: Optional[str] = None
    ) -> Any:
        """
        Handle zRef expressions to load YAML data.
        
        Args:
            ref_expr: zRef expression string
            base_path: Optional base path for resolution
        
        Returns:
            Any: Loaded data from zRef
        
        Examples:
            >>> data = parser.handle_zRef("zRef(users.yaml)")
        """
        return handle_zRef_func(ref_expr, self.logger, base_path, self.display, self.zos)

    def handle_zParser(self, zFile_raw: str) -> Any:
        """
        Handle zParser directives.
        
        Args:
            zFile_raw: Raw zParser directive
        
        Returns:
            Any: Result of zParser handling
        
        Examples:
            >>> result = parser.handle_zParser("zParser(...)")
        """
        return handle_zParser_func(zFile_raw, self.display)

    # ═══════════════════════════════════════════════════════════
    # zVaFile Parsing
    # ═══════════════════════════════════════════════════════════

    def parse_zva_file(
        self,
        data: Dict[str, Any],
        file_type: str,
        file_path: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse zVaFile with type-specific logic and validation.
        
        Args:
            data: Raw YAML data
            file_type: File type (UI, Schema, Config, Generic)
            file_path: Optional file path
            session: Optional session dict
        
        Returns:
            Dict[str, Any]: Parsed zVaFile structure
        
        Examples:
            >>> parsed = parser.parse_zva_file(yaml_data, "UI", file_path="zUI.users.yaml")
        """
        return parse_zva_file_func(data, file_type, self.logger, file_path, session, self.display)

    def validate_zva_structure(
        self,
        data: Dict[str, Any],
        file_type: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate zVaFile structure based on type.
        
        Args:
            data: zVaFile data to validate
            file_type: File type (UI, Schema, Config, Generic)
            file_path: Optional file path
        
        Returns:
            Dict[str, Any]: Validation result with keys: valid, errors, warnings
        
        Examples:
            >>> is_valid = parser.validate_zva_structure(data, "UI")
        """
        return validate_zva_structure_func(data, file_type, self.logger, file_path)

    def extract_zva_metadata(
        self,
        data: Dict[str, Any],
        file_type: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from zVaFiles.
        
        Args:
            data: zVaFile data
            file_type: File type (UI, Schema, Config, Generic)
        
        Returns:
            Dict[str, Any]: Extracted metadata
        
        Examples:
            >>> metadata = parser.extract_zva_metadata(data, "UI")
        """
        return extract_zva_metadata_func(data, file_type, self.logger)

    def parse_ui_file(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse UI file with UI-specific logic and RBAC extraction.
        
        CRITICAL method used by zLoader for UI file loading.
        
        Args:
            data: Raw YAML data
            file_path: Optional file path
            session: Optional session dict (for RBAC context)
        
        Returns:
            Optional[Dict[str, Any]]: Parsed UI structure with RBAC metadata, or None on fatal error
        
        Examples:
            >>> ui_data = parser.parse_ui_file(yaml_data, file_path="zUI.users.yaml")
        """
        return parse_ui_file_func(data, self.logger, file_path, session)

    def parse_schema_file(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse schema file with schema-specific logic and validation.
        
        Args:
            data: Raw YAML data
            file_path: Optional file path
            session: Optional session dict
        
        Returns:
            Dict[str, Any]: Parsed schema structure
        
        Examples:
            >>> schema = parser.parse_schema_file(yaml_data, file_path="zSchema.users.yaml")
        """
        return parse_schema_file_func(data, self.logger, file_path, session)

    def parse_config_file(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse config file with config-specific logic and validation.
        
        NEW in Week 6.8.6 - dedicated parser for zConfig files.
        
        Args:
            data: Raw YAML data
            file_path: Optional file path
            session: Optional session dict
        
        Returns:
            Dict[str, Any]: Parsed config structure
        
        Examples:
            >>> config = parser.parse_config_file(yaml_data, file_path="zConfig.app.yaml")
        """
        return parse_config_file_func(data, self.logger, file_path, session)

    def parse_generic_file(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse generic file (fallback for unrecognized types).
        
        Args:
            data: Raw YAML data
            file_path: Optional file path
        
        Returns:
            Dict[str, Any]: Parsed generic structure
        
        Examples:
            >>> generic = parser.parse_generic_file(yaml_data)
        """
        return parse_generic_file_func(data, self.logger, file_path)

    def validate_ui_structure(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate UI file structure.
        
        Args:
            data: UI data to validate
            file_path: Optional file path
        
        Returns:
            Dict[str, Any]: Validation result with keys: valid, errors, warnings
        
        Examples:
            >>> is_valid = parser.validate_ui_structure(ui_data)
        """
        return validate_ui_structure_func(data, self.logger, file_path)

    def validate_schema_structure(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate schema file structure.
        
        Args:
            data: Schema data to validate
            file_path: Optional file path
        
        Returns:
            Dict[str, Any]: Validation result with keys: valid, errors, warnings
        
        Examples:
            >>> is_valid = parser.validate_schema_structure(schema_data)
        """
        return validate_schema_structure_func(data, self.logger, file_path)

    def validate_config_structure(
        self,
        data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate config file structure.
        
        NEW in Week 6.8.6 - dedicated validator for zConfig files.
        
        Args:
            data: Config data to validate
            file_path: Optional file path
        
        Returns:
            Dict[str, Any]: Validation result with keys: valid, errors, warnings
        
        Examples:
            >>> is_valid = parser.validate_config_structure(config_data)
        """
        return validate_config_structure_func(data, self.logger, file_path)


# Export main components
__all__ = ["zParser"]

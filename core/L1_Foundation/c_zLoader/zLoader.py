# zOS/core/L1_Foundation/c_zLoader/zLoader.py

"""
zLoader facade for file loading, caching, and zParser delegation.

This module provides the main facade (Tier 5) for zLoader subsystem, handling
zVaFile (UI, Schema, Config) loading with intelligent caching and delegation to
zParser for path resolution and content parsing. It serves as the public interface
between zOS framework and the internal zLoader 6-tier architecture.

Purpose
-------
The zLoader facade serves as Tier 5 (Facade) in the zLoader architecture, providing
a simple, unified interface for loading and parsing zVaFiles. It delegates to:
    - CacheOrchestrator (Tier 3) for intelligent caching
    - zParser subsystem for path resolution and file parsing
    - load_file_raw (Tier 1) for raw file I/O

Architecture
------------
**Tier 5 - Facade (Public Interface to zOS Framework)**
    - Position: Public interface between zOS subsystems and internal zLoader components
    - Delegates To: CacheOrchestrator (Tier 3), zParser, load_file_raw (Tier 1)
    - Used By: zOS subsystems (zDispatch, zNavigation, zCLI mode)
    - Purpose: Unified file loading + intelligent caching + zParser delegation

**6-Tier Architecture**:
    - Tier 1: Foundation (loader_io.py - Raw file I/O)
    - Tier 2: Cache Implementations (SystemCache, PinnedCache, SchemaCache, PythonModuleCache)
    - Tier 3: Cache Orchestrator (CacheOrchestrator - Unified cache router)
    - Tier 4: Package Aggregator (loader_modules/__init__.py - Public API exposure)
    - Tier 5: Facade ← THIS MODULE
    - Tier 6: Package Root (__init__.py - zLoader package entry point)

Key Responsibilities
--------------------
1. **File Loading**: Load zVaFiles (UI, Schema, Config) from disk or cache
2. **Intelligent Caching**: Cache UI/config files, skip schemas (loaded fresh)
3. **zParser Delegation**: Delegate path resolution and parsing to zParser subsystem
4. **Session Integration**: Support session-based file loading (zPath=None)

Caching Strategy
----------------
**Cached (System Cache)**:
    - UI files (zUI.*.zolo): User interface definitions
    - Config files (zConfig.*.zolo): Configuration files
    - Cache Key: f"parsed:{absolute_filepath}" (uses OS path for consistency)
    - Cache Type: "system" (LRU eviction, max_size=100)

**NOT Cached (Fresh Load)**:
    - Schema files (zSchema.*.zolo): Database schemas
    - Reason: Schemas should reflect latest DB structure
    - Detection: "zSchema" in filename (format-agnostic; never cached)

**Cache Key Construction**:
    - Format: "parsed:{absolute_filepath}"
    - Example: "parsed:/Users/name/workspace/zUI.users.zolo"
    - Uses absolute OS path for session-independent consistency
    - Ensures same file always uses same cache key (prevents duplicates)

Integration Points
------------------
**Week 6.6 (zDispatch)**:
    - dispatch_launcher.py (line 447): raw_zFile = self.zos.loader.handle(zVaFile)
    - dispatch_modifiers.py (line 570): raw_zFile = self.zos.loader.handle(zVaFile)
    - Purpose: Load UI files for command dispatch and modifier resolution

**Week 6.7 (zNavigation)**:
    - navigation_linking.py: walker.loader.handle() (via walker parameter)
    - Purpose: Load target UI files when processing zLink expressions

**Week 6.8 (zParser)**:
    - Uses zpath_decoder: Path resolution (zPath → full OS path)
    - Uses identify_zfile: File type identification and extension detection
    - Uses parse_file_content: Parse raw YAML/JSON content into Python objects

External Usage
--------------
**Used By**:
    - zCLI mode: zos.loader.handle(zPath)
    - zDispatch (via zos.loader): self.zos.loader.handle(zVaFile)
    - zNavigation (via walker.loader): walker.loader.handle()

Usage Examples
--------------
**UI File Loading (with zPath)**:
    >>> loader = zLoader(zos)
    >>> ui_data = loader.handle("@.zUI.users.zolo")
    >>> # Returns: Parsed UI dictionary (cached for subsequent loads)

**UI File Loading (session fallback)**:
    >>> loader = zLoader(zos)
    >>> ui_data = loader.handle()  # zPath=None, uses session values
    >>> # Returns: Parsed UI dictionary from session context

**Config File Loading**:
    >>> loader = zLoader(zos)
    >>> config_data = loader.handle("~.zMachine.zConfig.app.zolo")
    >>> # Returns: Parsed config dictionary (cached)

**Schema File Loading (fresh load)**:
    >>> loader = zLoader(zos)
    >>> schema_data = loader.handle("@.zSchema.users.zolo")
    >>> # Returns: Parsed schema dictionary (NOT cached, always fresh)

Layer Position
--------------
Layer 1, Position 6 (zLoader - Tier 5 Facade)
    - Tier 1: Foundation (loader_io.py)
    - Tier 2: Cache Implementations (4 caches)
    - Tier 3: Cache Orchestrator (cache_orchestrator.py)
    - Tier 4: Package Aggregator (loader_modules/__init__.py)
    - Tier 5: Facade ← THIS MODULE
    - Tier 6: Package Root (__init__.py)

Dependencies
------------
Internal:
    - loader_modules.CacheOrchestrator (Tier 3)
    - loader_modules.load_file_raw (Tier 1)
    - zParser.zpath_decoder, identify_zfile, parse_file_content

External:
    - zOS imports: Any, Dict, Optional (for type hints)

See Also
--------
- cache_orchestrator.py: Unified cache router (Tier 3)
- loader_io.py: Raw file I/O (Tier 1)
- zParser: Path resolution and content parsing

Version History
---------------
- v1.5.4: Industry-grade upgrade (type hints, constants, comprehensive docs,
          integration points documentation, caching strategy documentation)
- v1.5.3: Original implementation (file loading, caching, zParser delegation)
"""


__version__ = "1.0.0"
import copy

from zOS import Any, Dict, Optional
from .loader_modules.ui_version import handle_ui_version
from .loader_modules import (
    CacheOrchestrator,
    load_file_raw,
    # Import all constants from centralized module
    COLOR_LOADER,
    FILE_TYPE_UI,
    FILE_TYPE_SCHEMA,
    SESSION_KEY_VAFILE,
    CACHE_KEY_PREFIX,
    CACHE_TYPE_SYSTEM,
    MSG_READY,
    MSG_START,
    MSG_CACHED,
    MSG_RETURN,
    INDENT_ROOT,
    INDENT_PRIMARY,
    STYLE_FULL,
    STYLE_TILDE,
)

# ============================================================================
# ZLOADER CLASS
# ============================================================================


class zLoader:
    """
    Middleware layer for loading and caching zVaFiles (UI, Schema, Config).

    The zLoader class serves as the main facade for the zLoader subsystem, providing
    intelligent file loading with caching and delegation to zParser for path resolution
    and content parsing. It implements a smart caching strategy that caches UI/config
    files but loads schemas fresh each time.

    Attributes
    ----------
    zos : Any
        Reference to main zOS framework instance (provides access to all subsystems)
    logger : Any
        Reference to zOS logger for debug/info logging
    zSession : Dict[str, Any]
        Reference to zOS session dictionary for state management
    display : Any
        Reference to zDisplay for visual feedback (zDeclare calls)
    mycolor : str
        Color key for display messages (COLOR_KEY constant)
    cache : CacheOrchestrator
        Tier 3 cache orchestrator for managing all cache tiers
    zpath_decoder : Callable
        zParser method for path resolution (zPath → full OS path)
    identify_zfile : Callable
        zParser method for file type identification
    parse_file_content : Callable
        zParser method for parsing raw YAML/JSON content

    Caching Strategy
    ----------------
    **Cached (System Cache)**:
        - UI files (zUI.*.zolo): User interface definitions
        - Config files (zConfig.*.zolo): Configuration files
        - Cache Key: "parsed:{absolute_filepath}" (uses OS path for consistency)
        - Cache Type: "system" (LRU eviction, max_size=100)

    **NOT Cached (Fresh Load)**:
        - Schema files (zSchema.*.zolo): Database schemas
        - Reason: Schemas should reflect latest DB structure
        - Detection: "zSchema" in filename (format-agnostic; never cached)
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize zLoader with zOS framework instance.

        Parameters
        ----------
        zos : Any
            Main zOS framework instance providing access to:
                - session: Session dictionary for state management
                - logger: Logger for debug/info logging
                - display: zDisplay for visual feedback
                - zparser: zParser for path resolution and parsing

        Notes
        -----
        - Initializes cache orchestrator (manages all 4 cache tiers)
        - Stores parser method references for cleaner code
        - Displays "zLoader Ready" message via zDisplay
        """
        self.zos = zos
        self.logger = zos.logger
        self.zSession = zos.session
        self.display = zos.display
        self.mycolor = COLOR_LOADER

        # Initialize cache orchestrator (manages system, pinned, and schema caches)
        self.cache = CacheOrchestrator(self.zSession, self.logger, zos)

        # Note: No longer caching parser method references to break circular dependency.
        # Parser methods accessed dynamically via self.zos.zparser when needed.
        self.display.zDeclare(MSG_READY, color=self.mycolor, indent=INDENT_ROOT, style=STYLE_FULL)

    @staticmethod
    def _is_schema(name: str) -> bool:
        """
        SSOT schema detection: schemas are identified by the zSchema filename
        prefix, NOT by extension (zParser resolves .zolo/.json/.yaml/.yml).
        Schema files are always loaded fresh (never cached).
        """
        return FILE_TYPE_SCHEMA in (name or "")

    @staticmethod
    def _cache_key(filepath: str) -> str:
        """Build the system-cache key for a resolved absolute filepath (SSOT)."""
        return f"{CACHE_KEY_PREFIX}{filepath}"

    def handle(self, zPath: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for zVaFile loading and parsing.

        Loads and parses a zVaFile (UI, Schema, Config) with intelligent caching.
        Delegates to zParser for path resolution and content parsing. Supports
        both explicit zPath specification and session-based fallback (zPath=None).

        Parameters
        ----------
        zPath : Optional[str], default=None
            Declarative path to zVaFile (e.g., "@.zUI.users.zolo")
            - If None: Uses session values (SESSION_KEY_VAFILE, SESSION_KEY_VAFOLDER)
            - If provided: Explicit path to load
            - Symbols: "@" (workspace-relative), "~" (absolute), none (relative to cwd)

        Returns
        -------
        Dict[str, Any]
            Parsed zVaFile content as Python dictionary. Structure depends on file type:
                - UI files: {zName, zLoad, zBlock, zOptions, etc.}
                - Schema files: {tables, fields, constraints, etc.}
                - Config files: {settings, values, etc.}

        Raises
        ------
        FileNotFoundError
            If zVaFile cannot be found (via zParser)
        ParseError
            If zVaFile content is invalid YAML/JSON (via zParser)

        Examples
        --------
        **UI File Loading (with zPath)**:
            >>> loader = zLoader(zos)
            >>> ui_data = loader.handle("@.zUI.users.zolo")
            >>> # Returns: {'zName': 'users', 'zBlock': [...], ...}

        **UI File Loading (session fallback)**:
            >>> # Session has: {'zVaFile': 'users.zolo', 'zVaFolder': '@'}
            >>> loader = zLoader(zos)
            >>> ui_data = loader.handle()  # zPath=None
            >>> # Returns: {'zName': 'users', 'zBlock': [...], ...}

        **Config File Loading**:
            >>> loader = zLoader(zos)
            >>> config_data = loader.handle("~.zMachine.zConfig.app.zolo")
            >>> # Returns: {'setting1': 'value1', 'setting2': 'value2', ...}

        **Schema File Loading (fresh load)**:
            >>> loader = zLoader(zos)
            >>> schema_data = loader.handle("@.zSchema.users.zolo")
            >>> # Returns: {'tables': [...], 'fields': [...], ...} (NOT cached)

        **Navigation Linking (via walker.loader)**:
            >>> # In navigation_linking.py:
            >>> target_ui = walker.loader.handle(target_file)
            >>> # Returns: Parsed target UI dictionary

        **Command Dispatch (via zos.loader)**:
            >>> # In dispatch_launcher.py or dispatch_modifiers.py:
            >>> raw_zFile = self.zos.loader.handle(zVaFile)
            >>> # Returns: Parsed UI dictionary for command dispatch

        Notes
        -----
        **Caching Strategy**:
            - Cached: UI files (zUI.*), Config files (zConfig.*)
            - NOT Cached: Schema files (zSchema.*) - always loaded fresh
            - Cache Key: "parsed:{absolute_filepath}" (uses OS path for consistency)
            - Cache Type: "system" (LRU eviction, max_size=100)
            - Mtime Invalidation: Automatically detects file changes and reloads

        **zParser Delegation**:
            - Path Resolution: self.zos.zparser.zPath_decoder(zPath, zType)
            - File Identification: self.zos.zparser.identify_zFile(zVaFile, zVaFile_fullpath)
            - Content Parsing: self.zos.zparser.parse_file_content(zFile_raw, zFile_extension, ...)

        **Integration Points**:
            - zDispatch: dispatch_launcher.py, dispatch_modifiers.py
            - zNavigation: navigation_linking.py (via walker.loader)
            - zCLI mode: Direct access via zos.loader
        """
        self.display.zDeclare(MSG_START, color=self.mycolor, indent=INDENT_PRIMARY, style=STYLE_TILDE)
        self.logger.debug("zFile_zObj: %s", zPath)

        # Determine if we should use session values (UI file loading)
        # When zPath is None and session has zVaFile, use session values
        zType = FILE_TYPE_UI if not zPath and self.zSession.get(SESSION_KEY_VAFILE) else None

        # Step 1: Use zParser for path resolution and file discovery
        zVaFile_fullpath, zVaFile = self.zos.zparser.zPath_decoder(zPath, zType)
        zFilePath_identified, zFile_extension = self.zos.zparser.identify_zFile(zVaFile, zVaFile_fullpath)
        self.logger.debug("zFilePath_identified!\n%s", zFilePath_identified)

        # Detect if this is a zSchema file (should not be cached)
        is_schema = self._is_schema(zVaFile)

        if not is_schema:
            # Step 2: Check system cache (UI and config files)
            # Use absolute filepath for cache key (session-independent)
            # This ensures same file always uses same cache key, preventing duplicates
            cache_key = self._cache_key(zFilePath_identified)
            cached = self.cache.get(cache_key, cache_type=CACHE_TYPE_SYSTEM, filepath=zFilePath_identified)
            if cached is not None:
                self.display.zDeclare(MSG_CACHED, color=self.mycolor, indent=INDENT_PRIMARY, style=STYLE_TILDE)
                self.logger.debug("[SystemCache] Cache hit: %s", cache_key)
                # Never hand out the shared cached object: zLoom's list/knot
                # expansion mutates the returned block in place (e.g.
                # loop_ops.expand_list_bindings pops `zList` after expanding
                # it once) — a bare `return cached` lets the FIRST render
                # permanently consume the cached file's loop template, so
                # every later render (new connection, Back nav, reload) of
                # the same UI file gets a pre-expanded, frozen snapshot
                # instead of a fresh one. A cheap deep copy per cache hit
                # keeps the cache itself pristine for every caller.
                return copy.deepcopy(cached)
        else:
            self.logger.debug("[zSchema] Skipping cache - schemas are loaded fresh each time")

        # Step 4: Load raw file content (PRIORITY 3 - Disk I/O)
        self.logger.debug("[Priority 3] Cache miss - loading from disk")
        zFile_raw = load_file_raw(zFilePath_identified, self.logger, self.display)
        # Only log raw content if file is very small (< 200 chars) for debugging
        # Removed: Too noisy for standard DEBUG mode

        # Step 5: Parse using zParser (delegates to zParser)
        result = self.zos.zparser.parse_file_content(
            zFile_raw, zFile_extension, session=self.zSession, file_path=zFilePath_identified
        )
        self.logger.debug("zLoader parse result:\n%s", result)

        # Step 5.45: Structural transforms (zShuttle loop → zList+%pattern, then
        # zPattern expansion) BEFORE navbar injection and caching. zLoom owns the
        # grammar; the loader just provides the seam (runtime handle, like
        # resolve_navbar below). zShuttle MUST run first — it emits a %pattern
        # invocation that expand_components then resolves. Both idempotent + a
        # no-op when their directive is absent, so safe on every load.
        _zloom = getattr(self.zos, "zloom", None)
        if _zloom is not None and isinstance(result, dict):
            result = _zloom.expand_shuttles(result)
            result = _zloom.expand_components(result)

        # Step 5.5: Inject meta.zNavBar as synthetic keys (if present)
        # This transforms the zVaFile structure BEFORE caching
        result = self._inject_navbar_if_present(result)

        # Step 5.6: zUIVersion — track structural changes when opted-in
        if not is_schema and isinstance(result, dict):
            _meta = result.get("zMeta", {}) or {}
            if _meta.get("zUITracking"):
                handle_ui_version(zFilePath_identified, zFile_raw, result, self.zos)

        # Step 6: Return result (cache only if not a schema)
        self.display.zDeclare(MSG_RETURN, color=self.mycolor, indent=INDENT_PRIMARY, style=STYLE_TILDE)

        # Don't cache schemas - they should be loaded fresh each time
        if is_schema:
            self.logger.debug("[zSchema] Not caching - returning fresh data")
            return result

        # zOS#48: never cache a tree that still carries %-pattern KEYS. A load
        # that ran before zLoom existed at all (the boot-time zAPI/RBAC sweep
        # fires while self.zos.zloom is still None — proven live 2026-07-26,
        # local 9090) comes back unexpanded — caching it would serve the
        # poisoned parse for the whole server life (the "Eleven doors" empty
        # grid). So the guard MUST NOT ride the _zloom handle that just
        # skipped expansion: it calls the pure detector directly. Returning
        # the tree uncached costs one re-parse on the first real render,
        # which then expands + caches the good tree. KEY-position % is
        # unambiguous grammar (render tokens are value-position), so the
        # only other trees this skips are ones with unknown pattern names —
        # already broken-and-warned, and better re-parsed than frozen.
        if isinstance(result, dict):
            from zOS.L3_Abstraction.n_zLoom.zLoom_modules.component_expand import (  # pylint: disable=import-outside-toplevel
                has_component_keys,
            )
            if has_component_keys(result):
                self.logger.warning(
                    "[SystemCache] NOT caching %s — unexpanded %%-pattern keys "
                    "remain (zLoom not up yet, registry empty, or unknown "
                    "component)", zFilePath_identified,
                )
                return result

        # Cache other resources (UI, configs, etc.) in system cache
        # Use absolute filepath for cache key (same as get() for consistency)
        cache_key = self._cache_key(zFilePath_identified)
        return self.cache.set(cache_key, result, cache_type=CACHE_TYPE_SYSTEM, filepath=zFilePath_identified)

    def _inject_navbar_if_present(self, raw_zFile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject meta.zNavBar as synthetic menu keys into all blocks (if present).
        
        This transformation happens AFTER parsing and BEFORE caching, ensuring that
        navbar items appear as natural menu options to downstream subsystems (zWalker,
        zWizard, zDispatch, zDisplay). The navbar logic is centralized in zNavigation.
        
        Parameters
        ----------
        raw_zFile : Dict[str, Any]
            Parsed zVaFile structure (may contain meta.zNavBar)
        
        Returns
        -------
        Dict[str, Any]
            Transformed zVaFile with navbar items injected into all blocks
        
        Notes
        -----
        **Architecture**:
            - zLoader: Transformation layer (this method)
            - zNavigation: Resolves navbar items (global, local, route fallback)
            - zWalker/zWizard: Process navbar items like any other keys
            - zDispatch: Handles navbar selections
            - zDisplay: Renders navbar items
        
        **Synthetic Key Format**:
            - Key: _zNavBar_{blockName} (e.g., "_zNavBar_zVaF")
            - Value: ${blockName} (e.g., "$zVaF" - delta link)
        """
        # Safety check
        if not isinstance(raw_zFile, dict):
            return raw_zFile

        # Block-level navbars first (`zNavBar: [Group]` inside a block) — these are
        # inline, group-sourced, and independent of any zMeta-level navbar.
        raw_zFile = self._inject_block_navbars(raw_zFile)

        # Get route metadata from session (for server-side routes)
        route_meta = self.zSession.get('_router_meta', {})

        # Resolve navbar items via zNavigation (handles global, local, route fallback)
        navbar_items = self.zos.navigation.resolve_navbar(raw_zFile, route_meta=route_meta)

        # No zMeta-level navbar to inject (block-level may still have been injected above)
        if not navbar_items or len(navbar_items) == 0:
            return raw_zFile

        self.logger.debug(f"[zLoader] Injecting navbar items into all blocks: {navbar_items}")

        # Create navbar menu with modifiers
        # Format: ~zNavBar*: [$zVaF, $zAbout, {zAccount: {zRBAC: ...}}, ...]
        # ~ = no back modifier (anchor menu)
        # * = explicit menu marker
        # Items display cleanly (zDisplay strips $), backend handles delta/zLink
        # Dict items (with RBAC) are kept as-is for dynamic filtering in zDispatch
        navbar_menu_items = self._format_navbar_menu_items(navbar_items)

        # zBrand (SSOT): if declared under ZNAVBAR, prepend a home entry so the
        # brand renders as the first navbar item in zCLI (Bifrost renders it as
        # brand chrome via nav_html_builder). The pick targets the zSpark root and
        # — being a ~zNavBar selection — triggers the navbar OP_RESET like any item.
        brand_item = self._build_navbar_brand_item()
        if brand_item:
            navbar_menu_items.insert(0, brand_item)

        navbar_key = {"~zNavBar*": navbar_menu_items}

        # Inject into all top-level blocks (skip "meta" and blocks with modifiers like ^)
        for block_name, block_content in raw_zFile.items():
            # Skip metadata block
            if block_name == "meta" or block_name.startswith("_"):
                continue

            # Skip blocks with ^ prefix (bounce-back blocks) - they should bounce immediately after content
            if block_name.startswith("^"):
                self.logger.debug(f"[zLoader] Skipping navbar injection for bounce-back block: {block_name}")
                continue

            # Only inject into dict blocks (not lists or primitives)
            if isinstance(block_content, dict):
                # Inject at the end of the block
                raw_zFile[block_name] = {**block_content, **navbar_key}
                self.logger.debug(f"[zLoader] Injected navbar menu into block: {block_name}")

        return raw_zFile

    def _format_navbar_menu_items(self, navbar_items: list) -> list:
        """Format resolved navbar items into menu values (``$name`` strings / dicts).

        String items get the delta (``$``) prefix; dict items (zRBAC/zSub/zLink)
        pass through verbatim for downstream filtering/resolution. Unknown types are
        skipped with a warning. Brand is prepended separately by the caller.
        """
        menu_items = []
        for item in navbar_items:
            if isinstance(item, str):
                menu_items.append(f"${item}")
            elif isinstance(item, dict):
                menu_items.append(item)
            else:
                self.logger.warning(f"[zLoader] Unknown navbar item type: {type(item)} ({item})")
        return menu_items

    def _inject_block_navbars(self, raw_zFile: Dict[str, Any]) -> Dict[str, Any]:
        """Replace block-level ``zNavBar: [Group]`` keys with inline navbar menus.

        A block-level navbar is an authored key (``zNavBar``) whose value is a group
        name or list of group names. It is rewritten in place (position preserved) to
        a synthetic ``~zNavBar{Groups}*`` menu sourced from the named zEnv group(s).
        zMeta is left untouched (its zNavBar is the page-level directive). Block-level
        bars carry no brand — the brand belongs to the page/global bar only.
        """
        navigation = getattr(self.zos, "navigation", None)
        handler = getattr(navigation, "navbar_handler", None) if navigation else None
        if handler is None:
            return raw_zFile

        for block_name, block_content in raw_zFile.items():
            if block_name in ("zMeta", "meta") or block_name.startswith("_"):
                continue
            if isinstance(block_content, dict):
                raw_zFile[block_name] = self._replace_block_navbar_keys(block_content, handler)
        return raw_zFile

    def _replace_block_navbar_keys(self, node: Any, handler: Any) -> Any:
        """Recursively rewrite ``zNavBar: [Group]`` keys within a block into menus."""
        if not isinstance(node, dict):
            return node

        rebuilt: Dict[str, Any] = {}
        for key, value in node.items():
            if key == "zNavBar" and isinstance(value, (list, str)):
                # Group-ref form: `zNavBar: [Group]` — source items from named zEnv group(s).
                names = value if isinstance(value, list) else [value]
                items = []
                for name in names:
                    group_items = handler.get_group_items(name)
                    if group_items:
                        items.extend(group_items)
                    else:
                        self.logger.warning(
                            f"[zLoader] Block-level zNavBar references unknown group: {name}"
                        )
                joined = "".join(str(n) for n in names)
                menu_key = self._unique_navbar_key(rebuilt, f"~zNavBar{joined}*")
                rebuilt[menu_key] = self._format_navbar_menu_items(items)
                self.logger.debug(
                    f"[zLoader] Injected block-level navbar {names} -> {menu_key}"
                )
            elif key == "zNavBar" and isinstance(value, dict):
                # Inline form: `zNavBar: {Item: {zLink: ...}}` — a page-local bar
                # declared in the block itself (no zEnv group). Same item grammar as
                # a group; ideal for in-page zPsi navbars (a TOC that jumps to the
                # block's own sections) without polluting the global ZNAVBAR.
                items = handler.parse_dict(value)
                menu_key = self._unique_navbar_key(rebuilt, "~zNavBarInline*")
                rebuilt[menu_key] = self._format_navbar_menu_items(items)
                self.logger.debug(
                    f"[zLoader] Injected inline block-level navbar -> {menu_key}"
                )
            else:
                rebuilt[key] = self._replace_block_navbar_keys(value, handler)
        return rebuilt

    @staticmethod
    def _unique_navbar_key(rebuilt: Dict[str, Any], base_key: str) -> str:
        """Return ``base_key`` (``~zNavBar...*``) made unique within ``rebuilt``.

        Multiple block-level navbars in one block would otherwise collide on the
        same synthetic key; suffix a counter before the trailing ``*`` when needed.
        """
        if base_key not in rebuilt:
            return base_key
        stem = base_key[:-1] if base_key.endswith("*") else base_key
        idx = 2
        while f"{stem}{idx}*" in rebuilt:
            idx += 1
        return f"{stem}{idx}*"

    def _build_navbar_brand_item(self) -> Optional[Dict[str, Any]]:
        """Build the zCLI navbar brand/home item from the zBrand declaration.

        Returns a menu item ``{"zBrand": {"label", "icon", "zLink"}}`` whose zLink
        points at the zSpark root, or None when zBrand is undeclared / the root is
        unresolved. The item is always-public; the renderer shows the label (with an
        optional ANSI-safe zIcon glyph), not the target name.
        """
        navigation = getattr(self.zos, "navigation", None)
        handler = getattr(navigation, "navbar_handler", None) if navigation else None
        brand = getattr(handler, "brand", None) if handler else None
        if not brand or not isinstance(brand, dict):
            return None
        # An icon-only brand is valid (renders the glyph); require label OR icon.
        if not brand.get("label") and not brand.get("icon"):
            return None

        home_zlink = self._spark_root_zlink()
        if not home_zlink:
            return None

        brand_item = {"label": brand.get("label"), "zLink": home_zlink}
        if brand.get("icon"):
            brand_item["icon"] = brand["icon"]
        return {"zBrand": brand_item}

    def _spark_root_zlink(self) -> Optional[str]:
        """Construct a zLink path to the zSpark root block (the home target)."""
        spark = getattr(self.zos.config, "zSpark", None) or {}
        folder = str(spark.get("zVaFolder") or "").strip()
        vafile = str(spark.get("zVaFile") or "").strip()
        block = str(spark.get("zBlock") or "").strip()
        if not vafile or not block:
            return None
        if not folder:
            return f"{vafile}.{block}"
        if not folder.startswith("@"):
            folder = f"@.{folder}"
        return f"{folder}.{vafile}.{block}"

    # ========================================================================
    # Python Module Loading (Phase 3 Refactoring - Single Source of Truth)
    # ========================================================================

    def load_python_module(self, file_path: str, module_name: Optional[str] = None) -> Any:
        """
        Load Python module from file path with caching.
        
        Main entry point for higher subsystems (zFunc, zUtils, zServer) to load
        Python modules. Delegates to PythonModuleCache for actual loading with
        importlib, collision detection, session injection, and LRU caching.
        
        Parameters
        ----------
        file_path : str
            Absolute path to Python file (e.g., "/path/to/plugin.py")
        module_name : Optional[str], optional
            Module name override. If None, uses filename stem (default: None)
        
        Returns
        -------
        Any
            Loaded Python module with zos instance injected
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> module = loader.load_python_module("/path/to/calculator.py")
        >>> result = module.add(5, 3)
        
        Notes
        -----
        - Uses PythonModuleCache for caching (LRU eviction, max_size=50)
        - Collision detection prevents duplicate filenames
        - Mtime tracking enables auto-reload on file changes
        - Session injection: module.zos = zos instance
        """
        return self.cache.python_module_cache.load_and_cache(file_path, module_name)

    def get_python_module(self, module_name: str) -> Optional[Any]:
        """
        Get cached Python module by name.
        
        Retrieves a previously loaded module from cache. Performs mtime
        freshness check and invalidates/reloads if file changed.
        
        Parameters
        ----------
        module_name : str
            Module filename without .py extension (e.g., "calculator")
        
        Returns
        -------
        Optional[Any]
            Cached module if found and fresh, None otherwise
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> module = loader.get_python_module("calculator")
        >>> if module:
        ...     result = module.add(5, 3)
        """
        return self.cache.python_module_cache.get(module_name)

    def invalidate_python_module(self, module_name: str) -> None:
        """
        Invalidate cached Python module by name.
        
        Removes module from cache, forcing reload on next access.
        Useful for development when module code changes.
        
        Parameters
        ----------
        module_name : str
            Module filename without .py extension (e.g., "calculator")
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> loader.invalidate_python_module("calculator")
        >>> # Next load_python_module() will reload from disk
        """
        self.cache.python_module_cache.invalidate(module_name)

    # ========================================================================
    # Plugin Management (Migrated from zUtils v1.7.0)
    # ========================================================================

    def load_plugins(self, plugin_paths, display_progress: bool = True):
        """
        Load Python/JavaScript plugins into cache with optional progress display.
        
        This method supports both Python (.py) and JavaScript (.js) plugins,
        with automatic collision detection, progress display, and statistics tracking.
        
        Parameters
        ----------
        plugin_paths : Union[List[str], str, None]
            Plugin paths to load. Supports:
            - Absolute file paths: "/path/to/plugin.py"
            - Module import paths: "package.module.plugin"
            - JavaScript files: "/path/to/plugin.js"
            - Single string or list of strings
            - None or empty list returns empty dict
        display_progress : bool, optional
            Show progress feedback via zDisplay (default: True)
        
        Returns
        -------
        Dict[str, Any]
            Dictionary of successfully loaded plugins.
            Key: Plugin name (filename without extension)
            Value: Loaded module object (with zos injected)
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> plugins = loader.load_plugins(["/path/to/calculator.py", "/path/to/utils.js"])
        >>> calculator = plugins.get("calculator")
        >>> calculator.add(5, 3)
        
        Notes
        -----
        - Uses PythonModuleCache for caching and collision detection
        - Failed plugins are logged but don't halt loading (best-effort)
        - JavaScript plugins are registered as proxy modules
        - Progress display can be disabled for silent loading
        """
        from pathlib import Path
        from .loader_modules.loader_trust import verify_plugin_trust, PluginTrustError
        
        # Handle None or empty list
        if not plugin_paths:
            return {}
        
        # Convert single string to list
        if isinstance(plugin_paths, str):
            plugin_paths = [plugin_paths]
        
        loaded_plugins = {}
        
        # Prepare progress iterator
        items = plugin_paths
        if display_progress:
            items = self.display.progress_iterator(plugin_paths, "Loading plugins")
        
        # Load each plugin
        for path in items:
            try:
                # Extract module name from path
                if path.endswith('.py') or path.endswith('.js'):
                    module_name = Path(path).stem
                else:
                    # Module import path
                    module_name = path.split('.')[-1]
                
                # Load based on file type
                if path.endswith('.js'):
                    # JavaScript plugin
                    module = self.cache.python_module_cache.register_js_plugin(path, module_name)
                elif path.endswith('.py'):
                    # Python file path
                    module = self.cache.python_module_cache.load_and_cache(path, module_name)
                else:
                    # Module import path - use importlib (no file path for mtime tracking)
                    import importlib
                    import importlib.util

                    # Trust gate (single door): the dotted-module path executes
                    # top-level code on import just like a .py/.js plugin, so it
                    # must pass the same zGuard seam. Resolve the module's origin
                    # file for the path-based policy when available; fall back to
                    # the dotted name. Permissive no-op in open-core; raises
                    # PluginTrustError when a sealed policy denies (propagates).
                    try:
                        spec = importlib.util.find_spec(path)
                        origin = getattr(spec, "origin", None) if spec else None
                    except (ImportError, AttributeError, ValueError):
                        origin = None
                    verify_plugin_trust(origin or path, self.zos, self.logger)

                    module = importlib.import_module(path)
                    if module:
                        module.zos = self.zos
                        self.cache.python_module_cache.register_import_module(
                            module, module_name, path
                        )
                
                if module:
                    loaded_plugins[module_name] = module
                    self.logger.debug(f"[zLoader] Loaded plugin: {module_name} from {path}")
                    
            except PluginTrustError:
                # Trust-policy denial (zGuard). MUST propagate, never be swallowed
                # by the best-effort handlers below — a denied plugin is a security
                # event, not a routine load failure. Code never executed (the gate
                # runs before import/exec), so re-raising fails closed.
                self.logger.error(f"[zLoader] Plugin blocked by trust policy: {path}")
                raise
            except ValueError as e:
                # Collision error
                if "collision" in str(e).lower():
                    self.logger.error(f"[zLoader] Collision detected: {e}")
                else:
                    self.logger.warning(f"[zLoader] Failed to load {path}: {e}")
            except (ImportError, AttributeError, PermissionError) as e:
                self.logger.warning(f"[zLoader] Failed to load {path}: {type(e).__name__}: {e}")
            except Exception as e:
                self.logger.warning(f"[zLoader] Failed to load {path}: {e}")
        
        return loaded_plugins

    def get_plugin(self, name: str):
        """
        Get loaded plugin module by name.
        
        Parameters
        ----------
        name : str
            Plugin name (filename without extension)
        
        Returns
        -------
        Optional[Any]
            Plugin module if found, None otherwise
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> plugin = loader.get_plugin("calculator")
        >>> if plugin:
        ...     result = plugin.add(5, 3)
        """
        return self.cache.python_module_cache.get(name)

    def list_plugins(self):
        """
        List all loaded plugins with metadata.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of plugin info dictionaries with keys:
            - name: Plugin name
            - filepath: Absolute path to plugin file
            - cached_at: Timestamp when cached
            - accessed_at: Last access timestamp
            - hits: Number of cache hits
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> plugins = loader.list_plugins()
        >>> for p in plugins:
        ...     print(f"{p['name']}: {p['hits']} hits")
        """
        return self.cache.python_module_cache.list_modules()

    def get_plugins_dict(self):
        """
        Get all plugins as a dictionary (name -> module).
        
        Convenience method for subsystems that need direct plugin access.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary mapping plugin names to module objects
        
        Examples
        --------
        >>> loader = zLoader(zos)
        >>> plugins = loader.get_plugins_dict()
        >>> calculator = plugins.get("calculator")
        """
        plugins_dict = {}
        for info in self.cache.python_module_cache.list_modules():
            name = info.get("name")
            if name:
                module = self.cache.python_module_cache.get(name)
                if module:
                    plugins_dict[name] = module
        return plugins_dict

    def handle_absolute_path(self, absolute_path: str) -> Dict[str, Any]:
        """
        Load file by absolute OS path, bypassing zPath decoder.
        
        For use by subsystems that work with direct file paths (e.g., zServer
        route auto-detection via glob). Auto-detects format (.zolo/.yaml/.json)
        and delegates to zParser for extension resolution and parsing.
        
        This method maintains SSOT/DRY principles by delegating format detection
        to zParser instead of reimplementing it in calling subsystems.
        
        Parameters
        ----------
        absolute_path : str
            Absolute OS path (may or may not include extension)
            Examples:
                - "/workspace/zServer.routes.zolo" (with extension)
                - "/workspace/zServer.routes" (extension auto-detected)
        
        Returns
        -------
        Dict[str, Any]
            Parsed file content as Python dictionary
        
        Raises
        ------
        FileNotFoundError
            If file cannot be found (tried all extensions for zVaFiles)
        ParseError
            If file content is invalid
        
        Examples
        --------
        **Route File Loading (zServer)**:
            >>> loader = zLoader(zos)
            >>> routes = loader.handle_absolute_path("/workspace/zServer.routes.zolo")
            >>> # Returns: {"type": "server", "routes": {...}, "meta": {...}}
        
        **Schema File Loading (zServer)**:
            >>> schema = loader.handle_absolute_path("/workspace/models/zSchema.users")
            >>> # Extension auto-detected (.zolo/.yaml/.json), NOT cached
        
        **With Extension Detection**:
            >>> config = loader.handle_absolute_path("/etc/zConfig.app")
            >>> # Tries .zolo, .json, .yaml, .yml in order
        
        Notes
        -----
        **Path Handling**:
            - Bypasses zPath_decoder (no dot interpretation)
            - Accepts paths with or without extensions
            - Uses identify_zfile for extension detection/validation
        
        **Caching Strategy** (same as handle()):
            - Cached: UI files (zUI.*), Config files (zConfig.*)
            - NOT Cached: Schema files (zSchema.*) - always loaded fresh
            - Cache Key: "parsed:{absolute_filepath}"
        
        **Format Detection**:
            - Delegates to zParser.identify_zfile()
            - Tries extensions: .zolo, .json, .yaml, .yml
            - First match wins
        
        **SSOT Compliance**:
            - zParser owns format detection logic
            - zLoader owns file loading/caching logic
            - Calling subsystems (zServer) delegate instead of reimplementing
        
        See Also
        --------
        handle : Main entry point using zPath notation
        """
        import os

        self.logger.debug("[zLoader.handle_absolute_path] Loading: %s", absolute_path)

        # Extract filename from path
        filename = os.path.basename(absolute_path)

        # If path already has extension and file exists, use it directly
        # Otherwise, let identify_zfile auto-detect extension for zVaFiles
        if os.path.exists(absolute_path):
            # File exists with provided path - use as-is
            file_path = absolute_path
            _, extension = os.path.splitext(absolute_path)
            # File existence is expected - only log if missing or problematic
        else:
            # File doesn't exist at provided path - use identify_zfile for detection
            # Strip extension if present to allow identify_zfile to try alternatives
            base_name, ext = os.path.splitext(absolute_path)
            base_path = base_name if ext else absolute_path

            # Use zParser's identify_zfile for extension detection and validation
            # This tries .zolo, .json, .yaml, .yml in order for zVaFiles
            file_path, extension = self.zos.zparser.identify_zFile(filename, base_path)
            self.logger.debug("[zLoader.handle_absolute_path] Identified: %s (ext: %s)", file_path, extension)

        # Detect if this is a zSchema file (should not be cached)
        is_schema = self._is_schema(filename)

        if not is_schema:
            # Check system cache (UI and config files)
            cache_key = self._cache_key(file_path)
            cached = self.cache.get(cache_key, cache_type=CACHE_TYPE_SYSTEM, filepath=file_path)
            if cached is not None:
                self.logger.debug("[zLoader.handle_absolute_path] Cache hit: %s", cache_key)
                # SAME hazard `handle()` already guards against (see its own
                # cache-hit branch above): callers of THIS entry point (zLoom's
                # load_zloom_registry/_resolve_zloom_zpath, route/schema
                # managers) get the raw registry dict back and some of them
                # mutate a WHERE clause or block IN PLACE (e.g. QueryOps
                # resolving %route.*/%session.* into a spool's `where`) —
                # a bare `return cached` would let the FIRST request's
                # resolved value freeze into the shared spool definition
                # forever, corrupting every later request with different
                # route/session state. Deep copy keeps the cache pristine.
                return copy.deepcopy(cached)
        # zSchema files are not cached (expected behavior, no need to log)

        # Load raw file content
        zFile_raw = load_file_raw(file_path, self.logger, self.display)

        # Parse content using zParser (positional arguments, same as handle())
        parsed_data = self.zos.zparser.parse_file_content(
            zFile_raw, extension, session=self.zSession, file_path=file_path
        )

        # Cache if not schema
        if not is_schema and parsed_data:
            # zOS#48: THIS is the seam the boot-time zAPI/RBAC sweep fills the
            # cache through (route managers call handle_absolute_path, not
            # handle) — and this path NEVER runs zLoom expansion. Caching a
            # tree that still carries %-pattern KEYS would hand the poisoned
            # parse to every later handle() cache-hit for the whole server
            # life (zCloud's Advanced "Eleven doors" empty grid). Skip the
            # set; the first real render re-parses via handle(), expands with
            # the registry ready, and caches the good tree.
            if isinstance(parsed_data, dict):
                from zOS.L3_Abstraction.n_zLoom.zLoom_modules.component_expand import (  # pylint: disable=import-outside-toplevel
                    has_component_keys,
                )
                if has_component_keys(parsed_data):
                    self.logger.warning(
                        "[SystemCache] NOT caching %s — unexpanded %%-pattern "
                        "keys remain (loaded outside the expansion seam)",
                        file_path,
                    )
                    return parsed_data
            self.cache.set(cache_key, parsed_data, cache_type=CACHE_TYPE_SYSTEM, filepath=file_path)
            # Cache SET is already logged by cache.set() - no need for duplicate log

        return parsed_data


# ============================================================================
# MODULE METADATA
# ============================================================================

__all__ = ["zLoader"]

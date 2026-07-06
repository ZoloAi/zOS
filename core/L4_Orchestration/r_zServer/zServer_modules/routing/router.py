# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/router.py

"""
HTTP Router - Declarative routing with RBAC integration

This module provides HTTP request routing based on zServer.*.zVaFile definitions,
with integrated role-based access control (RBAC) using zAuth.

Philosophy:
    "Routes are data, not code" - Flask blueprint style for zOS

Architecture:
    - Match incoming paths to route definitions
    - Enforce RBAC before serving content
    - Serve error pages on access denial
    - Support exact match, wildcard, and default routes

Route Matching Priority:
    1. Exact match ("/about" → "/about")
    2. Wildcard match ("/*" → any path)
    3. Default route (Meta.default_route)

RBAC Integration:
    Uses zos.auth.has_role() and zos.auth.is_authenticated()
    to enforce route-level access control defined in zRBAC metadata.

Examples:
    >>> router = HTTPRouter(routes_data, zos, logger)
    >>> route = router.match_route("/admin")
    >>> has_access, error_page = router.check_access(route)
    >>> if has_access:
    ...     file_path = router.resolve_file_path(route)

Version: v1.5.4 Phase 2
"""

from zOS import os, Path, Any, Dict, Optional, Tuple

# Import zVaFile extension constants for auto-discovery
from zOS.L2_Handling.d_zParser.parser_modules.parser_path import ZVAFILE_EXTENSIONS

# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath

# =============================================================================
# MODULE CONSTANTS
# =============================================================================

# Route keys (must match vafile_server.py)
KEY_META = "meta"
KEY_ROUTES = "routes"
KEY_BASE_PATH = "base_path"
KEY_DEFAULT_ROUTE = "default_route"
KEY_ERROR_PAGES = "error_pages"
KEY_TYPE = "type"
KEY_FILE = "file"

# RBAC keys
RBAC_KEY_REQUIRE_AUTH = "require_auth"
RBAC_KEY_REQUIRE_ROLE = "require_role"

# Route types (the surviving set — content/json/form/dynamic/redirect removed 2026-06)
ROUTE_TYPE_STATIC = "static"
ROUTE_TYPE_TEMPLATE = "template"  # Jinja2 template rendering from the templates/ folder
ROUTE_TYPE_ZWALKER = "zWalker"  # Execute zVaF blocks via zWalker (server-side rendering)

# HTTP error codes
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404

# Wildcard pattern
WILDCARD_PATTERN = "/*"

# Default error pages
DEFAULT_ERROR_403 = "403.html"
DEFAULT_ERROR_404 = "404.html"

# Log messages
LOG_MSG_ROUTER_INIT = "[HTTPRouter] Initialized with %d routes"
LOG_MSG_ROUTE_MATCHED = "[HTTPRouter] Matched route: %s → %s"
LOG_MSG_NO_MATCH = "[HTTPRouter] No route match for: %s"
LOG_MSG_RBAC_CHECK = "[HTTPRouter] RBAC check for %s: %s"
LOG_MSG_ACCESS_GRANTED = "[HTTPRouter] Access granted: %s"
LOG_MSG_ACCESS_DENIED = "[HTTPRouter] Access denied: %s (reason: %s)"
LOG_MSG_RESOLVE_PATH = "[HTTPRouter] Resolved path: %s → %s"


# =============================================================================
# HTTP ROUTER CLASS
# =============================================================================

class HTTPRouter:
    """
    HTTP request router with RBAC enforcement.
    
    Matches incoming HTTP requests to route definitions from zServer route files
    and enforces role-based access control before serving content.
    
    Attributes:
        routes: Full routes data structure from parser
        zos: zOS instance (for auth access)
        logger: Logger instance
        meta: Metadata (base_path, default_route, error_pages)
        route_map: Map of path → route definition
    
    Methods:
        match_route(path): Find route definition for request path
        check_access(route): Check RBAC and return (has_access, error_page)
        resolve_file_path(route): Get absolute file path for route
    """

    def __init__(
        self,
        routes: Dict[str, Any],
        zos: Any,
        logger: Any,
        serve_path: str = '.'
    ):
        """
        Initialize HTTP router.
        
        Args:
            routes: Parsed routes data from parse_server_file()
            zos: zOS instance (required for auth access)
            logger: Logger instance
            serve_path: Base path for serving files (for resolving zVaFile paths)
        """
        self.routes = routes
        self.zos = zos
        self.logger = logger
        self.serve_path = serve_path

        # Extract metadata
        self.meta = routes.get(KEY_META, {})
        self.route_map = routes.get(KEY_ROUTES, {})

        # Auto-discovered routes from zWalker files
        self.auto_discovered_routes = {}

        # Discover zBlock routes from walker routes with auto_discover_blocks
        self._discover_walker_blocks()

        route_count = len(self.route_map) + len(self.auto_discovered_routes)
        self.logger.info(f"[HTTPRouter] Initialized with {route_count} total routes ({len(self.route_map)} explicit + {len(self.auto_discovered_routes)} auto-discovered)")

    def _discover_walker_blocks(self):
        """
        Auto-discover zBlock routes from zWalker routes with auto_discover_blocks=true.
        
        For each walker route with auto_discover_blocks enabled:
        1. Parse the referenced zVaFile (e.g., zUI.zVaF.zolo)
        2. Extract all top-level keys (excluding 'zMeta') from that file
        3. Scan the entire zVaFolder directory for ALL zUI files (.zolo/.yaml/.json)
        4. For each file, extract the first top-level block (excluding 'zMeta')
        5. Create virtual routes: /{zBlock} → walker(zBlock={zBlock})
        
        This allows direct navigation to /zAbout, /zRegister, /zLogin, etc. without
        requiring explicit route definitions for each block, matching zCLI mode behavior.
        """
        self.logger.info(f"[Router] Starting auto-discovery ({len(self.route_map)} explicit routes)...")

        if not self.route_map:
            self.logger.info("[Router] No routes to check for auto-discovery")
            return

        for route_path, route_config in self.route_map.items():
            self.logger.debug(f"[Router] Checking route: {route_path}, type={route_config.get(KEY_TYPE)}, auto_discover={route_config.get('auto_discover_blocks')}")
            # Only process zWalker routes with auto_discover_blocks
            if route_config.get(KEY_TYPE) != ROUTE_TYPE_ZWALKER:
                continue

            if not route_config.get('auto_discover_blocks', False):
                continue

            # Get zVaFile path for parsing (with session fallback)
            zVaFolder = route_config.get('zVaFolder')
            zVaFile = route_config.get('zVaFile')

            # Fall back to session defaults if not specified in route
            if not zVaFolder and self.zos and self.zos.session:
                zVaFolder = self.zos.session.get('zVaFolder', '')
            if not zVaFile and self.zos and self.zos.session:
                zVaFile = self.zos.session.get('zVaFile', '')

            if not zVaFile:
                self.logger.warning(f"[Router] Cannot auto-discover blocks for {route_path}: no zVaFile in route or session")
                continue

            self.logger.debug(f"[Router] Auto-discovering blocks for {route_path} from {zVaFolder}/{zVaFile}")

            # Resolve zPath notation via the grammar SSOT. Dots are SEGMENTS:
            # @.zViews.zAccount → zViews/zAccount (multi-segment folders were
            # previously left as "zViews.zAccount" → walk of a nonexistent dir
            # → 0 discovered routes for any nested zVaFolder).
            if zVaFolder and zVaFolder.startswith(zpath.SIGIL_WORKSPACE):
                segments = zpath.split(zVaFolder).segments
                zVaFolder_resolved = os.path.join(*segments) if segments else ''
            elif not zVaFolder:
                zVaFolder_resolved = ''  # Default to empty (root level)
            else:
                zVaFolder_resolved = zVaFolder

            # Build directory path
            directory_path = os.path.join(self.serve_path, zVaFolder_resolved)

            # ── Parse-free discovery (SSOT) ──────────────────────────────────
            # Routes are derived from the DIRECTORY TREE alone — boot never reads a
            # file body just to discover it (that double-parse + cache thrash was
            # the old "100-fill"). Folder structure mirrors URL structure
            # (terminal-first). Each zUI.* file becomes ONE route; its root block is
            # the FIRST top-level block, resolved lazily on first serve through the
            # single loader path (see _resolve_route_block). Two consequences:
            #   • no zBlock naming convention — any root block name works
            #   • multiple blocks in one file = ONE URL; zLink swaps blocks in place
            # The main zVaFile is served by the explicit '/' route, so it is never
            # aliased here.
            self.logger.debug(
                f"[Router] Scanning directory tree {directory_path} (recursive, parse-free) for zUI files"
            )

            try:
                for root, dirs, files in os.walk(directory_path):
                    # Filter out directories starting with _ (in-place modification).
                    # Excludes _panels/, _components/, etc. 'error' is reserved:
                    # UI/error/zUI.<code> pages are served by _serve_error on the
                    # real HTTP error, never as normal routes.
                    dirs[:] = [d for d in dirs if not d.startswith('_') and d != 'error']

                    for file_name in files:
                        if not file_name.startswith('zUI.'):
                            continue

                        file_ext = None
                        for ext in ['.zolo', '.json', '.yaml', '.yml']:
                            if file_name.endswith(ext):
                                file_ext = ext
                                break
                        if not file_ext:
                            continue

                        file_base = file_name[:-len(file_ext)]  # e.g. "zUI.zCaching"

                        # The main zVaFile is the home page ('/' route) — never alias it.
                        if file_base == zVaFile and root == directory_path:
                            continue

                        route_name = (
                            file_base[len('zUI.'):] if file_base.startswith('zUI.') else file_base
                        )

                        # URL + zVaFolder mirror the directory structure.
                        rel_path = os.path.relpath(root, directory_path)
                        if rel_path == '.':
                            virtual_path = f"/{route_name}"
                            zVaFolder_computed = zVaFolder
                        else:
                            url_suffix = rel_path.replace(os.sep, '/')
                            virtual_path = f"/{url_suffix}/{route_name}"
                            zVaFolder_computed = f"{zVaFolder}.{rel_path.replace(os.sep, '.')}"

                        # Explicit routes and earlier discoveries win.
                        if virtual_path in self.route_map or virtual_path in self.auto_discovered_routes:
                            self.logger.debug(f"[Router] Skipping {virtual_path} - already exists")
                            continue

                        # Copy the default-walker config, override location, and defer
                        # the block. zMeta is intentionally NOT stored — the serve path
                        # re-reads it (block-first) through the loader, so storing it
                        # here would be a stale duplicate.
                        virtual_route = route_config.copy()
                        virtual_route['zVaFile'] = file_base
                        virtual_route['zVaFolder'] = zVaFolder_computed
                        virtual_route['zBlock'] = None
                        virtual_route['_auto_discovered'] = True
                        virtual_route['_lazy_block'] = True
                        # Real on-disk path of the page this route maps to. Discovery
                        # itself stays parse-free, but the reload safety net (see
                        # RouteManager._validate_pages) loads this exact file to catch
                        # bad syntax BEFORE the new table goes live — no re-resolving.
                        virtual_route['_page_path'] = os.path.join(root, file_name)
                        virtual_route.pop('zMeta', None)

                        self.auto_discovered_routes[virtual_path] = virtual_route
                        self.logger.debug(
                            f"[Router] Mapped route (parse-free): {virtual_path} → "
                            f"{zVaFolder_computed}/{file_base} [block: lazy]"
                        )

                self.logger.debug(
                    f"[Router] Auto-discovery complete: {len(self.auto_discovered_routes)} virtual routes"
                )

            except Exception as e:
                self.logger.error(f"[Router] Error discovering routes under {directory_path}: {e}")
                import traceback
                self.logger.error(f"[Router] Traceback: {traceback.format_exc()}")

    def resolve_first_block(self, route: Dict[str, Any]) -> tuple:
        """
        SSOT: load a page route's body and return its FIRST renderable block.

        This is the ONE definition of "does this route resolve to a usable page?" —
        used by BOTH the serve path (:meth:`_resolve_route_block`, which memoizes
        the result) and the reload parse-safety net
        (``RouteManager._validate_pages``, which turns a failure into an aborted
        swap). Sharing it makes "validates == serves" structurally true rather than
        a convention two copies have to keep in sync.

        The root block is the first top-level key that isn't ``zMeta`` (any name —
        no naming convention), read through the single loader path the renderer
        uses. Read-only: never mutates ``route`` (callers decide what to do).

        Returns:
            tuple(block_name|None, reason|None). On success → (name, None); on
            failure → (None, human reason) so callers can log or surface it.
        """
        if not isinstance(route, dict):
            return None, "route is not a dict"
        zVaFile = route.get('zVaFile')
        zVaFolder = route.get('zVaFolder')
        if not (self.zos and zVaFile and zVaFolder):
            return None, "route missing zos/zVaFile/zVaFolder"
        try:
            from .utils import HandlerUtils
            from zOS.L2_Handling.d_zParser.parser_modules.parser_utils import semantic_keys
            zPath = HandlerUtils.build_zpath(zVaFolder, zVaFile)
            data = self.zos.loader.handle(zPath=zPath)
            if not isinstance(data, dict) or not data:
                return None, "page did not load (empty) — likely a syntax error"
            # A page's root block is its first semantic (non-zMeta) child — the
            # shared SSOT for "what's structure vs. chrome" (parser_utils).
            blocks = semantic_keys(data, exclude=frozenset({"zMeta"}))
            if not blocks:
                return None, "no renderable block (only zMeta) — likely a syntax error"
            return blocks[0], None
        except Exception as exc:  # pylint: disable=broad-except
            return None, str(exc)

    def _resolve_route_block(self, route: Dict[str, Any]) -> None:
        """
        Lazily resolve a parse-free route's root zBlock at serve time, then memoize.

        Boot-time discovery maps files to URLs without reading their bodies, so an
        auto-discovered route carries no zBlock (``_lazy_block=True``). The actual
        load+inspect is delegated to :meth:`resolve_first_block` (the shared SSOT);
        here we just memoize the result onto the route dict so it's a one-time cost
        per page. A failure is non-fatal at serve time (logged at debug) — the
        reload net is what blocks bad pages from going live in the first place.
        """
        if not isinstance(route, dict) or route.get('zBlock') or not route.get('_lazy_block'):
            return
        block, err = self.resolve_first_block(route)
        if block:
            route['zBlock'] = block
            self.logger.debug(f"[Router] Lazy-resolved block for {route.get('zVaFile')}: {block}")
        elif err:
            self.logger.debug(
                f"[Router] Lazy block resolve skipped for {route.get('zVaFile')}: {err}"
            )

    def match_route(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Match request path to route definition.
        
        Matching Priority:
            1. Exact match (explicit routes)
            2. Parametrized match (/:param patterns)
            3. Auto-discovered zBlock routes (from zWalker)
            4. Wildcard match (/*)
            5. Default route (from Meta)
        
        Args:
            path: HTTP request path (e.g., "/about" or "/users/123/avatar")
        
        Returns:
            Optional[Dict[str, Any]]: Route definition or None
        
        Examples:
            >>> router = HTTPRouter(routes, zos, logger)
            >>> route = router.match_route("/admin")
            >>> route["file"]
            "admin.html"
            >>> route = router.match_route("/users/123/avatar")
            >>> route["type"]
            "zFunc"
        """
        # 1. Exact match (explicit routes)
        if path in self.route_map:
            route = self.route_map[path]
            self.logger.debug(LOG_MSG_ROUTE_MATCHED, path, route.get(KEY_FILE, "N/A"))
            return route

        # 2. Parametrized match (/:param patterns)
        route, params = self._match_parametrized_route(path)
        if route:
            # Store extracted parameters for handler access
            route['_route_params'] = params
            self.logger.debug(LOG_MSG_ROUTE_MATCHED, path, f"parametrized: {route.get('handler', 'N/A')}")
            return route

        # 3. Auto-discovered zBlock routes (from zWalker with auto_discover_blocks)
        if path in self.auto_discovered_routes:
            route = self.auto_discovered_routes[path]
            # Parse-free routes defer their root block — resolve it now (memoized).
            self._resolve_route_block(route)
            self.logger.debug(LOG_MSG_ROUTE_MATCHED, path, f"auto-discovered zBlock: {route.get('zBlock')}")
            return route

        # 4. Wildcard match
        if WILDCARD_PATTERN in self.route_map:
            route = self.route_map[WILDCARD_PATTERN]
            self.logger.debug(LOG_MSG_ROUTE_MATCHED, path, "wildcard")
            return route

        # 5. Default route
        default_route = self.meta.get(KEY_DEFAULT_ROUTE)
        if default_route:
            route = {KEY_TYPE: ROUTE_TYPE_STATIC, KEY_FILE: default_route}
            self.logger.debug(LOG_MSG_ROUTE_MATCHED, path, default_route)
            return route

        # No match
        self.logger.warning(LOG_MSG_NO_MATCH, path)
        return None

    def reverse_route(self, zVaFile: str, zBlock: str, zVaFolder=None) -> Optional[str]:
        """
        Reverse-resolve a (zVaFile, zBlock) pair to its URL path (smart routing).

        This is the SSOT inverse of match_route: given the target a zLink points
        at, find the canonical URL that serves it. Explicit routes win over
        auto-discovered ones (so the home page '/' is preferred over '/zVaF').

        Args:
            zVaFile:   target file, with or without the 'zUI.' prefix (e.g. 'zVaF')
            zBlock:    target block (e.g. 'zVaF')
            zVaFolder: optional directory of the target (dotted string like
                       '@.zViews.zStack.zCloud', or a tuple of folder segments).
                       When given, it disambiguates two same-named files that live
                       in different folders — smart routing is one file = one URL,
                       but "file" must include its directory, not just the basename.

        Returns:
            The matching URL path (e.g. '/'), or None if nothing matches.
        """
        def _norm(name: str) -> str:
            return (name or "").replace("zUI.", "")

        def _folder_key(value) -> Tuple[str, ...]:
            # Normalize a folder reference (string or segment iterable) to a tuple
            # of real directory segments — sigil-free, '/'-or-'.'-split, with the
            # 'zUI' grammar marker dropped so href folders and stored zVaFolders
            # compare apples to apples.
            if isinstance(value, (tuple, list)):
                segs = list(value)
            else:
                s = value or ""
                if s[:1] in ("@", "~", "&"):
                    s = s[1:]
                s = s.strip(".").replace("/", ".")
                segs = s.split(".")
            return tuple(p for p in segs if p and p != "zUI")

        target_file = _norm(zVaFile)
        target_block = zBlock or ""

        # 0. Directory-aware exact match (folder + file [+ block]). Tried first when
        #    a folder is supplied so a nested page (e.g. /zStack/zCloud/zFeed) wins
        #    over a root page that merely shares its basename (/zFeed). Without this,
        #    the file-only fallback below collapses both to the first basename hit.
        if zVaFolder is not None:
            target_folder = _folder_key(zVaFolder)
            for source in (self.route_map, self.auto_discovered_routes):
                for route_path, cfg in source.items():
                    if not isinstance(cfg, dict):
                        continue
                    if _norm(cfg.get("zVaFile", "")) != target_file:
                        continue
                    if _folder_key(cfg.get("zVaFolder", "")) != target_folder:
                        continue
                    cfg_block = cfg.get("zBlock", "") or ""
                    # Block matters only when both sides name one (parse-free auto
                    # routes defer the block → folder+file is enough).
                    if target_block and cfg_block and cfg_block != target_block:
                        continue
                    return route_path

        # 1. Exact file+block — lets an explicit/manual route pin a specific block,
        #    and keeps the canonical home '/' (zVaF.zVaF) winning over any alias.
        for source in (self.route_map, self.auto_discovered_routes):
            for route_path, cfg in source.items():
                if not isinstance(cfg, dict):
                    continue
                if _norm(cfg.get("zVaFile", "")) == target_file and cfg.get("zBlock", "") == target_block:
                    return route_path

        # 2. File-only — smart routing is one file = one URL. A zLink to ANY block
        #    of a page resolves to that page's URL (the block is intra-page nav,
        #    swapped in place). Parse-free routes defer zBlock, so file is the SSOT
        #    key for reverse resolution; explicit routes are tried first.
        for source in (self.route_map, self.auto_discovered_routes):
            for route_path, cfg in source.items():
                if not isinstance(cfg, dict):
                    continue
                if _norm(cfg.get("zVaFile", "")) == target_file:
                    return route_path
        return None

    def _match_parametrized_route(self, path: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
        """
        Match request path against parametrized route patterns (e.g., /users/:user_id/avatar).
        
        Args:
            path: HTTP request path (e.g., "/users/123/avatar")
        
        Returns:
            Tuple of (route_definition, extracted_parameters)
        
        Examples:
            >>> route, params = self._match_parametrized_route("/users/123/avatar")
            >>> params
            {"user_id": "123"}
        """
        path_segments = [s for s in path.split('/') if s]  # Split and remove empty strings

        # Parameter segments are marked with a leading sigil. '%' is the zLoom-
        # consistent form (/users/%username) — the captured name matches the
        # %varname token zLoom reads from zVars, so it's one token end to end.
        # ':' is the legacy form (/users/:user_id/avatar) kept for zAPI routes.
        _PARAM_SIGILS = (':', '%')

        for route_pattern, route in self.route_map.items():
            # Skip if not a parametrized route
            if ':' not in route_pattern and '%' not in route_pattern:
                continue

            pattern_segments = [s for s in route_pattern.split('/') if s]

            # Must have same number of segments
            if len(path_segments) != len(pattern_segments):
                continue

            # Try to match each segment
            params = {}
            match = True

            for path_seg, pattern_seg in zip(path_segments, pattern_segments):
                if pattern_seg.startswith(_PARAM_SIGILS):
                    # Parameter segment - extract value (strip the sigil)
                    param_name = pattern_seg[1:]
                    params[param_name] = path_seg
                elif path_seg != pattern_seg:
                    # Static segment - must match exactly
                    match = False
                    break

            if match:
                return route, params

        return None, {}

    def check_access(self, route: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check RBAC for route.
        
        Enforces access control based on zRBAC metadata in route definition.
        Uses zos.auth to check authentication and roles.
        
        Args:
            route: Route definition from match_route()
        
        Returns:
            Tuple[bool, Optional[str]]: (has_access, error_page_path)
                - has_access: True if access granted, False if denied
                - error_page_path: Path to error page (403.html) if denied, None if granted
        
        Examples:
            >>> router = HTTPRouter(routes, zos, logger)
            >>> route = router.match_route("/admin")
            >>> has_access, error_page = router.check_access(route)
            >>> if not has_access:
            ...     # Serve error_page instead
        """
        # One gate engine governs routes too (zGate). Extract the authored gate
        # (zGate:) via the SSOT engine — no gate present → public route.
        gate = self.zos.zgate.gate_predicate(route)
        if gate is None:
            self.logger.debug(LOG_MSG_ACCESS_GRANTED, "public route")
            return True, None

        # Evaluate via zos.zgate — the engine forwards auth to the CONTEXT-AWARE
        # check_zrbac SSOT. This replaced the prior raw is_authenticated()/has_role()
        # bypass, which diverged from page/navbar gates (a Bifrost WS login is
        # context-authed but not tier-agnostic authed, so an authed user could be
        # wrongly 403'd). zGate covers auth/role plus zGuest / require / value gates.
        try:
            granted, reason = self.zos.zgate.evaluate(gate)
        except Exception as exc:  # pylint: disable=broad-except
            # Never crash routing; fail closed on a gated route.
            granted, reason = False, f"zGate error: {exc}"

        if not granted:
            error_page = self.meta.get(KEY_ERROR_PAGES, {}).get(HTTP_403_FORBIDDEN, DEFAULT_ERROR_403)
            self.logger.info(LOG_MSG_ACCESS_DENIED, "zGate", reason or "denied")
            return False, error_page

        # All checks passed
        self.logger.debug(LOG_MSG_ACCESS_GRANTED, "zGate checks passed")
        return True, None

    def resolve_file_path(self, route: Dict[str, Any]) -> str:
        """
        Resolve absolute file path from route definition.
        
        Combines Meta.base_path with route.file to get full path.
        
        Args:
            route: Route definition from match_route()
        
        Returns:
            str: Absolute file path
        
        Examples:
            >>> router = HTTPRouter(routes, zos, logger)
            >>> route = {"file": "about.html"}
            >>> router.resolve_file_path(route)
            "/path/to/public/about.html"
        """
        base_path = self.meta.get(KEY_BASE_PATH, ".")
        file_name = route.get(KEY_FILE, "")

        resolved = os.path.join(base_path, file_name)
        self.logger.debug(LOG_MSG_RESOLVE_PATH, file_name, resolved)

        return resolved

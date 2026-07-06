# zOS/core/L2_Handling/h_zNavigation/navigation_modules/resolvers/resolver_zlink.py

"""
zLink Expression Resolver for zNavigation Subsystem.

This module provides the ZLinkResolver class, which parses zLink expressions
and validates RBAC permissions. Extracted from navigation_linking.py to follow
the approved resolver pattern from e_zDispatch.

Architecture
------------
The ZLinkResolver encapsulates parsing and validation logic:

1. **Expression Parsing** (parse_expression)
   - Extracts file path from zLink expression
   - Parses optional permission requirements
   - Supports imperative (zLink(...)) and declarative (raw path) formats

2. **RBAC Validation** (check_permissions)
   - Validates user permissions against requirements
   - Exact matching strategy (all keys must match)
   - Session-based user authentication

zLink Syntax
------------
Basic link (no permissions):
    zLink(@.zUI.settings.NetworkSettings)

Link with permissions:
    zLink(@.zUI.admin.UserManagement, {"role": "admin"})
    zLink(@.zUI.finance.Reports, {"role": "finance", "level": "manager"})

Path Format:
- @ = Base path (workspace root)
- zUI = UI directory
- filename = YAML file name (without extension)
- BlockName = Target block within file

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Resolver (Tier 1)

Integration
-----------
- Called by: Linking handler (navigation_linking.py)
- Uses: zParser.zExpr_eval() for permission dict parsing
- Session: Read-only for SESSION_KEY_ZVISITOR
"""

import re
from dataclasses import dataclass, field

from zOS import Any, Dict, Optional, Tuple
from zOS.L2_Handling.d_zParser.parser_modules.parser_utils import zExpr_eval
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZVISITOR

# zPath grammar — the Layer-0 SSOT for zPath string ↔ parts decomposition.
from zSys import zpath

# Parsing constants
_PARSE_PREFIX_ZLINK = "zLink("
# zAlpha — Greek-letter first-class name for the cross-file nav event. zLink is a
# permanent alias; the imperative wrapper is canonicalized to "zLink(" here so the
# ONE compiler path (compile_intent → _normalize_value) stays single-spelling.
_PARSE_PREFIX_ZALPHA = "zAlpha("
_PARSE_PREFIX_ZDELTA = "zDelta("
_PARSE_SUFFIX_RPAREN = ")"


def _canonicalize_nav_imperative(expr: str) -> str:
    """Rewrite a leading ``zAlpha(`` wrapper to the canonical ``zLink(`` token.

    Greek-letter rename seam: ``zAlpha`` is the new first-class name for the
    ``zLink`` event; ``zLink`` remains a permanent legacy alias. Normalizing the
    string here keeps the wrapper-stripping logic single-spelling (no length
    juggling) and leaves ``zDelta`` / ``zURL`` untouched.
    """
    if isinstance(expr, str) and expr.startswith(_PARSE_PREFIX_ZALPHA):
        return _PARSE_PREFIX_ZLINK + expr[len(_PARSE_PREFIX_ZALPHA):]
    return expr
_PARSE_PERMS_SEPARATOR = ", {"
_PARSE_BRACE_OPEN = "{"
_PARSE_BRACE_CLOSE = "}"

# href classification constants (shared with display_event_links via classify_href)
LINK_TYPE_INTERNAL_DELTA = 'internal_delta'
LINK_TYPE_INTERNAL_ZPATH = 'internal_zpath'
LINK_TYPE_EXTERNAL = 'external'
LINK_TYPE_ANCHOR = 'anchor'
LINK_TYPE_PLACEHOLDER = 'placeholder'

# Inline markdown link: [label](href){optional-attrs}. The optional {classes}/
# {_blank} brace is captured (group 3) so it survives an href rewrite. THE SSOT
# for the inline-link shape — shared by the GUI rich_text renderer and the
# zBifrost chunk path so both scan + rewrite content links identically.
INLINE_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)(\{[^}]*\})?')

# ---------------------------------------------------------------------------
# Navigation verbs — the canonical IR vocabulary.
#
# A NavIntent's `verb` is the resolved navigation primitive. zLink/zDelta know
# their verb up front (explicit dispatch); zURL derives it from the href via
# classify_href (it is the "compiler" that picks which primitive to run).
# ---------------------------------------------------------------------------
NAV_VERB_ZLINK = 'zLink'           # cross-file navigation (@. zPath)
NAV_VERB_ZDELTA = 'zDelta'         # same-file block navigation ($X / bare)
NAV_VERB_ANCHOR = 'anchor'         # in-page jump (#section → zPsi within block)
NAV_VERB_EXTERNAL = 'external'     # http(s) → zOpen
NAV_VERB_PLACEHOLDER = 'placeholder'  # '#' / '' → no-op

# classify_href kind → verb (the one verb-selection table; zURL's core decision).
_KIND_TO_VERB = {
    LINK_TYPE_INTERNAL_ZPATH: NAV_VERB_ZLINK,
    LINK_TYPE_INTERNAL_DELTA: NAV_VERB_ZDELTA,
    LINK_TYPE_ANCHOR: NAV_VERB_ANCHOR,
    LINK_TYPE_EXTERNAL: NAV_VERB_EXTERNAL,
    LINK_TYPE_PLACEHOLDER: NAV_VERB_PLACEHOLDER,
}


@dataclass(frozen=True)
class NavIntent:
    """Canonical, format-agnostic navigation intent (the nav IR).

    The single normalized shape that every navigation source compiles into —
    zLink, zDelta, and (the compiler) zURL — so downstream dispatch consumes ONE
    structure instead of re-parsing strings/dicts per call site.

    Attributes
    ----------
    verb : str
        Resolved primitive: one of NAV_VERB_* (zLink / zDelta / anchor /
        external / placeholder).
    target : str
        The destination address as authored — ``@.…`` zPath (zLink),
        ``$Block``/bare block (zDelta), URL (external), or ``""`` for a pure
        in-page anchor. Never URL-resolved here; that is a render-time concern
        (resolve_href_to_route) so the IR stays surface-agnostic.
    zpsi : Optional[str]
        In-block section anchor (start_key), or None. For ``#section`` hrefs the
        fragment is lifted into zpsi (anchor verb).
    perms : Dict[str, Any]
        RBAC requirements ({} when public).
    kind : str
        The raw classify_href taxonomy value (LINK_TYPE_*), retained for
        rendering decisions that care about the href shape, not the verb.
    """

    verb: str
    target: str
    zpsi: Optional[str] = None
    perms: Dict[str, Any] = field(default_factory=dict)
    kind: str = ''

# Log messages
_LOG_RAW_EXPRESSION = "[ZLinkResolver] Raw zLink expression: %s"
_LOG_STRIPPED_INNER = "[ZLinkResolver] Stripped inner: %s"
_LOG_PATH_PART = "[ZLinkResolver] Path: %s"
_LOG_PERMS_PART_RAW = "[ZLinkResolver] Raw permissions: %s"
_LOG_PARSED_PERMS = "[ZLinkResolver] Parsed permissions: %s"
_LOG_WARN_NON_DICT = "[ZLinkResolver] Parsed permissions is not a dict, using {}"
_LOG_NO_PERMS_BLOCK = "[ZLinkResolver] No permissions block specified for: %s"
_LOG_ZAUTH_USER = "[ZLinkResolver] User auth data: %s"
_LOG_REQUIRED_PERMS_CHECK = "[ZLinkResolver] Required permissions: %s"
_LOG_NO_PERMS_REQUIRED = "[ZLinkResolver] No permissions required (public link)"
_LOG_CHECK_PERM_KEY = "[ZLinkResolver] Checking: '%s' (expected: %s, actual: %s)"
_LOG_WARN_PERM_DENIED = "[ZLinkResolver] Permission denied: '%s' (expected: %s, actual: %s)"
_LOG_ALL_PERMS_MATCHED = "[ZLinkResolver] All permissions matched - access granted"


class ZLinkResolver:
    """
    zLink expression parser and RBAC validator.
    
    Provides parsing and validation services for zLink expressions without
    side effects. Pure resolver pattern - no session mutation, only reads.
    
    Attributes
    ----------
    logger : Any
        Logger instance for resolver operations
    
    Methods
    -------
    classify_href(href)
        Classify a raw href string into a link type constant (static)
    parse_expression(expr)
        Parse zLink expression to extract path and permissions
    check_permissions(session, required)
        Check if user has required permissions
    """

    # Class-level type declarations
    logger: Any  # Logger instance

    def __init__(self, logger: Any) -> None:
        """
        Initialize zLink resolver.
        
        Args
        ----
        logger : Any
            Logger instance for resolver operations
        """
        self.logger = logger

    @staticmethod
    def classify_href(href: str) -> str:
        """
        Classify a raw href string into a link type constant.

        This is the Python SSOT for href classification, used by both
        zNavigation (zLink) and zDisplay (zURL) to ensure consistent
        type detection across all link-rendering subsystems.

        Args
        ----
        href : str
            Raw href value (e.g. "$zAbout", "@.UI.foo.Bar",
            "https://example.com", "#section", "#")

        Returns
        -------
        str
            One of: 'internal_delta', 'internal_zpath', 'external',
            'anchor', 'placeholder'

        Examples
        --------
        ::

            ZLinkResolver.classify_href("$zAbout")          # 'internal_delta'
            ZLinkResolver.classify_href("@.UI.app.Main")    # 'internal_zpath'
            ZLinkResolver.classify_href("https://zolo.io")  # 'external'
            ZLinkResolver.classify_href("#features")        # 'anchor'
            ZLinkResolver.classify_href("#")                # 'placeholder'

        Note
        ----
        This is the *link-rendering* taxonomy (how a zURL/zLink renders). It maps
        the zPath-grammar SSOT (``zSys.zpath.classify``) onto the LINK_TYPE_*
        constants, preserving the link rule that only the ``@`` workspace sigil
        is a zPath nav target; ``~``/``&`` and bare tokens render as delta nav.
        """
        kind = zpath.classify(href)
        if kind == zpath.KIND_PLACEHOLDER:
            return LINK_TYPE_PLACEHOLDER
        if kind == zpath.KIND_EXTERNAL:
            return LINK_TYPE_EXTERNAL
        if kind == zpath.KIND_ANCHOR:
            return LINK_TYPE_ANCHOR
        if kind == zpath.KIND_DELTA:
            return LINK_TYPE_INTERNAL_DELTA
        # zPath sigils (nav/asset/backend): only '@' is a zPath nav target.
        if href.startswith(zpath.SIGIL_WORKSPACE):
            return LINK_TYPE_INTERNAL_ZPATH
        # ~ / & / bare tokens → delta navigation (preserves prior default).
        return LINK_TYPE_INTERNAL_DELTA

    def parse_expression(self, expr: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse zLink expression to extract path and permissions.
        
        Parses zLink syntax to extract the file path and optional permission
        requirements. Uses zParser.zExpr_eval() to parse permission dict strings.
        
        Args
        ----
        expr : str
            zLink expression string to parse
        
        Returns
        -------
        Tuple[str, Dict[str, Any]]
            Tuple of (path, permissions):
            - path (str): File path (e.g., "@.zUI.settings.Network")
            - permissions (Dict[str, Any]): Required permissions dict (empty if none)
        
        Examples
        --------
        Parse basic zLink::
        
            path, perms = resolver.parse_expression("zLink(@.zUI.settings.Main)")
            # path = "@.zUI.settings.Main"
            # perms = {}
        
        Parse zLink with permissions::
        
            path, perms = resolver.parse_expression(
                'zLink(@.zUI.admin.Users, {"role": "admin"})'
            )
            # path = "@.zUI.admin.Users"
            # perms = {"role": "admin"}
        
        Notes
        -----
        - Syntax: zLink(path) or zLink(path, {"key": "value"})
        - Permission Parsing: Uses zParser.zExpr_eval() to convert string to dict
        - Error Handling: Defaults to empty dict if parsing fails or returns non-dict
        - Supports both imperative (zLink(...)) and declarative (raw path) formats
        
        Algorithm
        ---------
        1. Log raw expression
        2. Strip "zLink(" prefix and ")" suffix (if present)
        3. Log stripped inner contents
        4. Check if ", {" exists (indicates permissions)
        5. If permissions:
           a. Split on ", {" to separate path and permissions
           b. Reconstruct permission dict string with braces
           c. Parse permissions with zExpr_eval()
           d. Validate result is dict (default to {} if not)
        6. If no permissions:
           a. Use inner contents as path
           b. Set permissions to empty dict
        7. Return (path, permissions) tuple
        """
        # Log raw expression
        self.logger.info(_LOG_RAW_EXPRESSION, expr)

        # zAlpha → zLink alias normalization (Greek-letter rename seam).
        expr = _canonicalize_nav_imperative(expr)

        # Check if expression has "zLink(" wrapper (imperative) or is raw path (declarative YAML)
        if expr.startswith(_PARSE_PREFIX_ZLINK) and expr.endswith(_PARSE_SUFFIX_RPAREN):
            # Imperative format: zLink(@.path) → strip wrapper
            inner = expr[len(_PARSE_PREFIX_ZLINK):-1].strip()
        else:
            # Declarative YAML format: already a raw path → use as-is
            inner = expr.strip()

        self.logger.info(_LOG_STRIPPED_INNER, inner)

        # Check if permissions are specified
        if _PARSE_PERMS_SEPARATOR in inner:
            # Split path and permissions
            path_str, perms_str = inner.rsplit(_PARSE_PERMS_SEPARATOR, 1)
            zLink_path = path_str.strip()

            # Reconstruct permission dict string
            perms_str = (
                _PARSE_BRACE_OPEN +
                perms_str.strip().rstrip(_PARSE_BRACE_CLOSE) +
                _PARSE_BRACE_CLOSE
            )

            # Log parts
            self.logger.info(_LOG_PATH_PART, zLink_path)
            self.logger.info(_LOG_PERMS_PART_RAW, perms_str)

            # Parse permissions with zExpr_eval
            required = zExpr_eval(perms_str, self.logger)

            # Validate result is dict
            if not isinstance(required, dict):
                self.logger.warning(_LOG_WARN_NON_DICT)
                required = {}
            else:
                self.logger.info(_LOG_PARSED_PERMS, required)
        else:
            # No permissions specified
            zLink_path = inner
            required = {}
            self.logger.debug(_LOG_NO_PERMS_BLOCK, zLink_path)

        return zLink_path, required

    def check_permissions(
        self,
        session: Dict[str, Any],
        required: Dict[str, Any]
    ) -> bool:
        """
        Check if user has required permissions.
        
        Validates user permissions from session against required permissions dict.
        Uses exact matching: each required permission key must exist in user dict
        with the exact same value.
        
        Args
        ----
        session : Dict[str, Any]
            Session dictionary containing user auth data
        required : Dict[str, Any]
            Required permissions dict (e.g., {"role": "admin"})
        
        Returns
        -------
        bool
            True if user has all required permissions (or no permissions required),
            False if any permission check fails
        
        Examples
        --------
        Check admin role::
        
            # Session: {SESSION_KEY_ZVISITOR: {"role": "admin"}}
            has_access = resolver.check_permissions(session, {"role": "admin"})
            # Returns: True
        
        Check multiple permissions::
        
            # Session: {SESSION_KEY_ZVISITOR: {"role": "finance", "level": "manager"}}
            has_access = resolver.check_permissions(
                session,
                {"role": "finance", "level": "manager"}
            )
            # Returns: True
        
        Permission mismatch::
        
            # Session: {SESSION_KEY_ZVISITOR: {"role": "user"}}
            has_access = resolver.check_permissions(session, {"role": "admin"})
            # Returns: False
        
        No permissions required::
        
            has_access = resolver.check_permissions(session, {})
            # Returns: True (public link)
        
        Notes
        -----
        - User Data: Reads from session[SESSION_KEY_ZVISITOR]
        - Exact Matching: user[key] must == required[key] for all keys
        - No Permissions: Returns True if required dict is empty
        - Missing Keys: Returns False if user dict doesn't have required key
        
        Algorithm
        ---------
        1. Get user dict from session[SESSION_KEY_ZVISITOR]
        2. Log user dict and required permissions
        3. If no permissions required, allow access (return True)
        4. For each required permission key:
           a. Get actual value from user dict
           b. Log comparison (key, expected, actual)
           c. If value doesn't match, deny access (return False)
        5. If all permissions match, allow access (return True)
        """
        # Get user auth data from session
        user = session.get(SESSION_KEY_ZVISITOR, {})

        # Log auth check
        self.logger.debug(_LOG_ZAUTH_USER, user)
        self.logger.debug(_LOG_REQUIRED_PERMS_CHECK, required)

        # No permissions required (public link)
        if not required:
            self.logger.debug(_LOG_NO_PERMS_REQUIRED)
            return True

        # Check each required permission
        for perm_key, expected_value in required.items():
            actual_value = user.get(perm_key)

            self.logger.debug(_LOG_CHECK_PERM_KEY, perm_key, expected_value, actual_value)

            if actual_value != expected_value:
                self.logger.warning(
                    _LOG_WARN_PERM_DENIED,
                    perm_key,
                    expected_value,
                    actual_value
                )
                return False

        # All permissions matched
        self.logger.debug(_LOG_ALL_PERMS_MATCHED)
        return True

    # ------------------------------------------------------------------ #
    # zPsi — SSOT for in-block section addressing.
    #
    # zPsi is NOT a navigation verb. It is a shared PROPERTY of the navigation
    # event (zLink / zDelta / zURL), carried in the event's dict form — never an
    # inline path fragment, so it stays format-agnostic (.zolo/.yaml/.json
    # identical). Semantically identical to a menu pick: it sets WHERE the run
    # starts inside the landed block (start_key), then the walker runs from there
    # to the end — see zUI.zMenu (Option A vs B). Stateless: ignores source/trail.
    #
    #   zLink: @.UI.x.Block                       → ("@.UI.x.Block", None)
    #   zLink: {target: @.UI.x.Block, zPsi: Sec}  → ("@.UI.x.Block", "Sec")
    #   zLink: {zPsi: Sec}                         → ("", "Sec")  (in-page: current block)
    # ------------------------------------------------------------------ #
    _ZPSI_KEY = "zPsi"
    # zOmega — Greek-letter first-class name for the in-block section property.
    # zPsi stays a permanent alias; both spellings resolve to the same anchor.
    _ZOMEGA_KEY = "zOmega"
    _TARGET_KEY = "target"

    @staticmethod
    def parse_zpsi_value(value: Any) -> Tuple[str, Optional[str]]:
        """Normalize a zLink/zDelta event value into ``(target, zPsi_anchor)``.

        String shorthand → ``(string, None)``. Dict form → ``(target, zPsi)``,
        where an absent/empty ``target`` means an in-page jump within the current
        block. Non-string/dict → ``("", None)``.
        """
        if isinstance(value, dict):
            target = value.get(ZLinkResolver._TARGET_KEY)
            target = target.strip() if isinstance(target, str) else ""
            # zOmega is the Greek-letter alias for zPsi (in-block section pin).
            anchor = value.get(ZLinkResolver._ZPSI_KEY)
            if anchor is None:
                anchor = value.get(ZLinkResolver._ZOMEGA_KEY)
            anchor = anchor.strip() if isinstance(anchor, str) and anchor.strip() else None
            return target, anchor
        if isinstance(value, str):
            return value.strip(), None
        return "", None

    @staticmethod
    def resolve_anchor_key(block_dict: Any, anchor: Optional[str]) -> Optional[str]:
        """Resolve a zPsi anchor to the real (modifier-bearing) block key.

        Block keys may carry navigation modifiers ($ ~ ^ *) and synthetic menu
        keys; the wizard's ``start_key`` needs the exact key string. Matches the
        anchor against each key with modifiers stripped. Returns None when the
        anchor is empty or no key matches (caller should start at the top).
        """
        if not anchor or not isinstance(block_dict, dict):
            return None
        if anchor in block_dict:
            return anchor
        for key in block_dict:
            if isinstance(key, str) and key.strip("$~^*") == anchor:
                return key
        return None

    # ------------------------------------------------------------------ #
    # compile_intent — THE single entry that normalizes any navigation
    # source (zLink / zDelta / zURL) into a NavIntent (the nav IR).
    # ------------------------------------------------------------------ #
    def compile_intent(self, value: Any, verb: Optional[str] = None) -> NavIntent:
        """Compile a raw navigation value into a canonical :class:`NavIntent`.

        This is the SSOT navigation "compiler". It accepts every authored form
        and yields one normalized intent:

        * **Explicit verb** (``verb`` passed) — how zLink/zDelta dispatch. The
          verb is trusted; the value is only normalized into target/zPsi/perms.
        * **Href-driven** (``verb=None``) — how zURL dispatches. The verb is
          derived from ``classify_href(target)`` via the ``_KIND_TO_VERB`` table,
          so a ``$delta`` href compiles to ``zDelta``, a ``@.`` href to ``zLink``,
          a ``#section`` href to ``anchor`` (fragment lifted to zPsi), etc.

        Accepted value shapes
        ---------------------
        * ``"zLink(@.x.Y)"`` / ``"zDelta($B)"`` — imperative wrappers (perms
          parsed from the optional ``, {…}`` tail).
        * ``"@.x.Y"`` / ``"$B"`` / ``"#sec"`` / ``"https://…"`` — bare href.
        * ``{target, zPsi, permissions}`` — dict form (the only way to carry a
          zPsi alongside a non-anchor target).

        Returns
        -------
        NavIntent
        """
        target, zpsi, perms = self._normalize_value(value)

        # Pure in-page anchor authored as "#section": lift fragment → zPsi.
        # Empty target with a zPsi is an in-page anchor; empty with none is a no-op.
        if target:
            kind = ZLinkResolver.classify_href(target)
        else:
            kind = LINK_TYPE_ANCHOR if zpsi else LINK_TYPE_PLACEHOLDER
        if kind == LINK_TYPE_ANCHOR and target.startswith('#'):
            anchor = target[1:].strip()
            if anchor:
                zpsi = zpsi or anchor
            target = ''
        elif kind == LINK_TYPE_PLACEHOLDER:
            # No destination — '#'/'' carry no address.
            target = ''

        resolved_verb = verb or _KIND_TO_VERB.get(kind, NAV_VERB_ZLINK)
        return NavIntent(
            verb=resolved_verb,
            target=target,
            zpsi=zpsi,
            perms=perms,
            kind=kind,
        )

    def _normalize_value(self, value: Any) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """Normalize any nav value → ``(target, zPsi, perms)``.

        Strips imperative ``zLink(…)``/``zDelta(…)`` wrappers (parsing the perms
        tail for zLink), and routes dict/bare-string forms through
        :meth:`parse_zpsi_value`. Perms only ever come from the imperative
        zLink tail or the dict ``permissions`` key.
        """
        if isinstance(value, str):
            stripped = _canonicalize_nav_imperative(value.strip())
            if stripped.startswith(_PARSE_PREFIX_ZLINK) and stripped.endswith(_PARSE_SUFFIX_RPAREN):
                path, perms = self.parse_expression(stripped)
                return path, None, perms
            if stripped.startswith(_PARSE_PREFIX_ZDELTA) and stripped.endswith(_PARSE_SUFFIX_RPAREN):
                inner = stripped[len(_PARSE_PREFIX_ZDELTA):-1].strip()
                return inner, None, {}
            target, anchor = self.parse_zpsi_value(stripped)
            return target, anchor, {}
        if isinstance(value, dict):
            target, anchor = self.parse_zpsi_value(value)
            perms = value.get('permissions') or value.get('perms') or {}
            if not isinstance(perms, dict):
                perms = {}
            return target, anchor, perms
        return "", None, {}

    def extract_block_from_path(self, zLink_path: str) -> Tuple[str, str]:
        """
        Extract block name and file path from zLink path.
        
        Args
        ----
        zLink_path : str
            Full zLink path (e.g., "@.zUI.settings.NetworkSettings")
        
        Returns
        -------
        Tuple[str, str]
            Tuple of (selected_zBlock, zFile_path):
            - selected_zBlock: Block name (last part)
            - zFile_path: File path (all parts except last)
        
        Examples
        --------
        Extract components::
        
            block, file = resolver.extract_block_from_path("@.zUI.settings.Network")
            # block = "Network"
            # file = "@.zUI.settings"
        """
        parts = zpath.split(zLink_path)
        selected_zBlock = parts.block
        # Rebuild the file path (symbol + all-but-last segment) via the grammar
        # SSOT so the "@.zUI.settings" form is reconstructed identically.
        zFile_path = zpath.join(parts.symbol, *parts.segments[:-1])
        return selected_zBlock, zFile_path

    # ------------------------------------------------------------------ #
    # zPath → URL — THE single authority for navigation address conversion.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_router(zos: Any) -> Any:
        """Fetch the canonical zServer HTTPRouter (SSOT for path↔URL), or None.

        Two wiring paths exist across subsystems: zDisplay reaches the router as
        ``server.router``; zBifrost reaches it via ``server.route_manager
        .get_router()``. Both resolve to the same instance — try direct first,
        fall back to the manager.
        """
        try:
            server = getattr(zos, 'server', None)
            if server is None:
                return None
            router = getattr(server, 'router', None)
            if router is not None:
                return router
            route_manager = getattr(server, 'route_manager', None)
            if route_manager is not None and hasattr(route_manager, 'get_router'):
                return route_manager.get_router()
        except Exception:
            pass
        return None

    def resolve_href_to_route(self, zos: Any, href: str) -> str:
        """SSOT: resolve a navigation href to its canonical web route.

        The ONE authority for zPath→URL navigation conversion, shared by
        zDisplay (zURL), zNavigation (zLink) and zBifrost (chunk expansion +
        form onSuccess). Replaces the former structural dot→slash converter.

        Contract (idempotent)
        ----------------------
        - Non-zPath href (already a route, ``$delta``, ``#anchor``, ``http``,
          empty) → returned UNCHANGED. Safe to call across multiple render
          pipelines without double-conversion.
        - zPath href (``@.…``) → decomposed via ``extract_block_from_path`` into
          ``(zBlock, zVaFile)`` (the SAME primitive zCLI navigation uses), then
          resolved against the route map via ``router.reverse_route`` (the SSOT
          inverse of ``match_route`` — one file = one URL, honoring manual and
          custom routes):
            * route found → canonical URL (including ``/`` for the home page)
            * no route / no server (pure zCLI) → raw href preserved, so the
              walker/zNav resolves it (a backend/data path or terminal nav).

        There is deliberately NO structural fallback: a navigation target with
        no registered route is surfaced (raw href returned), never papered over
        with a fabricated URL that would only 404.
        """
        if not href or not href.startswith(zpath.SIGIL_WORKSPACE):
            return href
        router = self._get_router(zos)
        if router is None or not hasattr(router, 'reverse_route'):
            return href
        try:
            # Decompose to (folder, file_stem, block) via the grammar SSOT — the
            # exact input reverse_route expects (one file = one URL; it normalizes
            # any 'zUI.' prefix itself). The folder is passed so two same-named
            # files in different directories resolve to their own routes instead
            # of colliding on the basename. nav_triple is None for single-segment
            # paths (data/folder refs), which have no route → keep raw href.
            triple = zpath.nav_triple(href)
            if triple is None:
                return href
            zVaFolder, zVaFile, zBlock = triple
            url = router.reverse_route(zVaFile, zBlock, zVaFolder=zVaFolder)
            if url:
                if self.logger:
                    self.logger.debug(f"[ZLinkResolver] zPath→route: {href} → {url}")
                return url
            return href
        except Exception as exc:  # pragma: no cover — never block rendering
            if self.logger:
                self.logger.debug(f"[ZLinkResolver] zPath→route skipped for '{href}': {exc}")
            return href

    # ------------------------------------------------------------------ #
    # Inline markdown links — THE single scanner for [label](href){attrs}
    # inside a content string, shared by the GUI rich_text renderer and the
    # zBifrost chunk path so the two pipelines never drift.
    # ------------------------------------------------------------------ #
    def resolve_inline_links(
        self,
        content: str,
        zos: Any,
        session: Optional[Dict[str, Any]] = None,
        apply_rbac: bool = True,
    ) -> str:
        """SSOT: RBAC-gate + route-resolve inline markdown links in a string.

        One pass over every ``[label](href){attrs}`` in ``content``, applying the
        SAME two transforms to internal (zPath / delta) links that zURL/zLink use;
        external, anchor and placeholder links pass through untouched:

        1. **RBAC gate** (``apply_rbac``) — an internal link the visitor may not
           see is downgraded to its plain label (same contract as
           ``zURL._render_bifrost(disabled=True)``). Inline links carry no
           per-link perms today, so the check runs with ``{}`` (forward-compatible
           no-op) — kept so per-link perms can be honored later in ONE place.
        2. **zPath → route** — an internal ``@.`` href is resolved to its
           canonical web route via :meth:`resolve_href_to_route` (idempotent;
           a no-op on ``$delta`` / external / anchor hrefs). Without this the raw
           ``@.`` zPath reaches the browser, whose structural converter only
           understands ``@.UI.*`` and mangles ``@.zViews.*`` into ``/@/…`` dead
           links.

        This is the ONE inline-link scanner: the direct GUI rich_text renderer and
        the zBifrost chunk path both call it, so ``[label](@.zPath)`` resolves
        identically regardless of render pipeline.
        """
        if not content or '](' not in content:
            return content
        session = session if session is not None else {}

        def _transform(match: "re.Match") -> str:
            label = match.group(1)
            href = match.group(2).strip()
            attrs = match.group(3) or ''
            link_type = ZLinkResolver.classify_href(href)
            if link_type in (LINK_TYPE_INTERNAL_DELTA, LINK_TYPE_INTERNAL_ZPATH):
                if apply_rbac and not self.check_permissions(session, {}):
                    return label  # permission denied → plain label
                resolved = self.resolve_href_to_route(zos, href)
                return f'[{label}]({resolved}){attrs}'
            return match.group(0)  # external / anchor / placeholder unchanged

        return INLINE_LINK_PATTERN.sub(_transform, content)

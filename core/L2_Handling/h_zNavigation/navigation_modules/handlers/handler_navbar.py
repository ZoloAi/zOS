# zOS/core/L2_Handling/h_zNavigation/navigation_modules/handlers/handler_navbar.py

"""
Navigation Bar Handler for zNavigation Subsystem.

This module provides the NavbarHandler class, which manages navigation bar
resolution, RBAC filtering, and multi-format parsing. Extracted from zNavigation
facade to follow the approved handler pattern from e_zDispatch.

Architecture
------------
The NavbarHandler encapsulates all navbar-related logic that was previously
in the zNavigation facade (lines 288-697). It provides:

1. **Global Navbar Loading** (load_global)
   - Reads from os.environ["ZNAVBAR"] (zEnv YAML files)
   - Legacy .zEnv file fallback
   - Multiple format support (JSON dict, JSON array, comma-separated)

2. **Dict Format Parsing** (parse_dict)
   - Converts navbar dict to internal list format
   - Preserves zRBAC and zSub metadata

3. **RBAC Filtering** (filter_by_rbac)
   - Terminal-first implementation (backend filtering)
   - Supports zGuest, authenticated, require_role rules
   - Preserves zSub metadata for hierarchical menus

4. **Navbar Resolution** (resolve)
   - Priority chain: local override > zVaFile opt-in > route fallback
   - Session-aware (checks authentication state)

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Handler (Tier 2)

Integration
-----------
- Called by: zNavigation facade (delegation)
- Uses: zAuth (authentication checks), zConfig (environment vars)
- Session: Read-only for auth state
"""

import re

from zOS import Any, Dict, List, Optional, Union
from zSys import zpath

# Name given to the implicit single group when ZNAVBAR is authored in the flat
# (legacy) form. `zNavBar: true` always resolves to the default group, so the
# literal name only matters for explicit `[GroupName]` references (grouped form).
_DEFAULT_GROUP = "Main"

# Item-level keys that mark a value as an item config (flat form) rather than a
# named group of items (grouped form). Used by _is_grouped() disambiguation.
# zGate is the modern per-item auth gate (zRBAC is its retired predecessor).
_ITEM_KEYS = {"zGate", "zRBAC", "zSub", "zLink"}


class NavbarHandler:
    """
    Navigation bar handler for zNavigation subsystem.
    
    Manages navbar loading, parsing, RBAC filtering, and resolution following
    the approved handler pattern. Extracted from zNavigation facade for better
    separation of concerns.
    
    Attributes
    ----------
    navigation : Any
        Reference to parent zNavigation system
    zos : Any
        Reference to zOS instance
    logger : Any
        Logger instance for navbar operations
    _global_navbar : Optional[List[Any]]
        Cached global navbar from environment
    
    Methods
    -------
    load_global()
        Load global navbar from environment configuration
    parse_dict(navbar_raw)
        Parse navbar dict format into internal list format
    filter_by_rbac(navbar_items)
        Filter navbar items based on RBAC rules
    resolve(raw_zFile, route_meta)
        Resolve navbar for a given zVaFile with route fallback
    """

    # Class-level type declarations
    navigation: Any  # Navigation system reference
    zos: Any  # zOS instance
    logger: Any  # Logger instance
    _global_navbar: Optional[List[Any]]  # Cached global navbar (default group items)
    _brand: Optional[Dict[str, Any]]  # Cached zBrand declaration (default group, SSOT)
    _groups: Dict[str, Dict[str, Any]]  # Named groups: {name: {brand, items}}
    _default_group: Optional[str]  # First-declared group name (sugar for `true`)

    def __init__(self, navigation: Any) -> None:
        """
        Initialize navbar handler.
        
        Args
        ----
        navigation : Any
            Parent zNavigation system instance
        
        Notes
        -----
        Loads global navbar from environment during initialization and caches it.
        The cached navbar is unfiltered - RBAC filtering happens dynamically.
        """
        self.navigation = navigation
        self.zos = navigation.zos
        self.logger = navigation.logger

        # zBrand: first-class navbar element (home/logo). Populated by load_global
        # when ZNAVBAR declares a zBrand key. SSOT — there is no zSpark.title fallback.
        self._brand = None

        # Named navbar groups (multi-navbar support). Flat ZNAVBAR collapses into a
        # single default group; grouped ZNAVBAR yields one group per top-level name.
        self._groups = {}
        self._default_group = None

        # Load global navbar from environment (.zEnv)
        self._global_navbar = self.load_global()

    def reload(self) -> None:
        """Re-read the global navbar from the SSOT and replace the boot-time cache.

        The handler parses ``os.environ["ZNAVBAR"]`` ONCE at ``__init__`` and caches
        the result (``_global_navbar`` + ``_groups`` + ``_brand``) for per-render
        speed. A soft ``z reload`` re-injects edited zEnv values into ``os.environ``
        through zConfig, but this in-memory copy would otherwise survive untouched —
        so a renamed or retargeted navbar item kept resolving to its boot-time value
        (the navbar drift). This invalidates the cache and re-runs the SAME
        ``load_global()`` path (os.environ is the SSOT bridge zConfig populates), so
        boot and reload share one navbar source of truth — no parallel parsing.
        """
        self._brand = None
        self._groups = {}
        self._default_group = None
        self._global_navbar = self.load_global()

    @property
    def brand(self) -> Optional[Dict[str, Any]]:
        """Normalized zBrand declaration ({label, logo, href}) or None if undeclared.

        zBrand is opt-in and the single source of truth for the navbar brand. When
        absent, no brand renders on any surface (Bifrost shows no brand chrome).
        """
        return self._brand

    def _extract_brand(self, navbar_raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Pull the optional zBrand declaration out of a raw navbar dict.

        Accepts two authoring forms (string-first):

            zBrand: zCloud                      # label only; href -> zSpark root '/'
            zBrand:                             # extended
                label: zCloud
                zIcon: cloud                    # zCLI: ANSI-safe glyph; Bifrost: <i>
                logo:  @.static.brand.logo.png  # Bifrost: <img>; zCLI: suppressed
                href:  /

        Returns a normalized dict ``{label, icon, logo, href}`` or None when zBrand
        is absent/empty. ``href`` defaults to '/' (the zSpark root) so the brand is a
        home link by default. Visual precedence — Bifrost: logo > icon > label; zCLI:
        icon + label (logo is suppressed to the label/alt text in the terminal).
        """
        if not isinstance(navbar_raw, dict):
            return None
        raw = navbar_raw.get("zBrand")
        if raw is None:
            return None
        if isinstance(raw, str):
            label = raw.strip()
            return {"label": label, "icon": None, "logo": None, "href": "/"} if label else None
        if isinstance(raw, dict):
            label = raw.get("label")
            icon = raw.get("zIcon") or raw.get("icon")
            logo = raw.get("logo")
            href = raw.get("href") or "/"
            if not label and not icon and not logo:
                return None
            return {"label": label, "icon": icon, "logo": logo, "href": href}
        return None

    @property
    def default_group(self) -> Optional[str]:
        """Name of the first-declared navbar group (what `zNavBar: true` resolves to)."""
        return self._default_group

    @property
    def groups(self) -> Dict[str, Dict[str, Any]]:
        """All named navbar groups as ``{name: {brand, items}}`` (read-only view)."""
        return self._groups

    def get_group_items(self, name: str) -> Optional[List[Any]]:
        """Return parsed item list for a named group, or None if the group is unknown."""
        group = self._groups.get(name)
        return group.get("items") if group else None

    def get_group_brand(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the normalized zBrand dict for a named group, or None."""
        group = self._groups.get(name)
        return group.get("brand") if group else None

    @staticmethod
    def _is_grouped(navbar_raw: Dict[str, Any]) -> bool:
        """Disambiguate grouped (multi-navbar) form from flat (single-bar) form.

        ZNAVBAR is **grouped** only when every top-level value is a plain dict of
        items AND there is no top-level ``zBrand``. Any bare item (null/string) or
        any value carrying item-level keys (zRBAC/zSub/zLink), or a top-level zBrand,
        marks the whole declaration as **flat** (one implicit default group).
        """
        if not isinstance(navbar_raw, dict) or not navbar_raw:
            return False
        if "zBrand" in navbar_raw:
            return False
        for value in navbar_raw.values():
            if not isinstance(value, dict):
                return False  # bare item (null/string) → flat
            if _ITEM_KEYS & set(value.keys()):
                return False  # item config dict → flat
        return True

    def _build_groups(
        self, navbar_raw: Dict[str, Any]
    ) -> "tuple[Dict[str, Dict[str, Any]], Optional[str]]":
        """Build the ``{name: {brand, items}}`` group map from a raw ZNAVBAR dict.

        Flat form collapses into a single ``_DEFAULT_GROUP`` entry; grouped form
        yields one entry per top-level name (insertion order preserved).
        """
        groups: Dict[str, Dict[str, Any]] = {}
        if self._is_grouped(navbar_raw):
            for name, group_dict in navbar_raw.items():
                if not isinstance(group_dict, dict):
                    continue
                groups[name] = {
                    "brand": self._extract_brand(group_dict),
                    "items": self.parse_dict(group_dict),
                }
        else:
            groups[_DEFAULT_GROUP] = {
                "brand": self._extract_brand(navbar_raw),
                "items": self.parse_dict(navbar_raw),
            }
        default_name = next(iter(groups), None)
        return groups, default_name

    def _register_groups(self, navbar_raw: Dict[str, Any]) -> List[Any]:
        """Populate group map + default brand from a raw ZNAVBAR dict; return default items."""
        self._groups, self._default_group = self._build_groups(navbar_raw)
        default = self._groups.get(self._default_group, {}) if self._default_group else {}
        self._brand = default.get("brand")
        return default.get("items", []) or []

    def _expand_group_refs(self, names: List[Any]) -> List[Any]:
        """Expand a list of group-name references into a flat item list.

        Each entry that names a known group contributes that group's items; any
        unknown entry is preserved verbatim as a literal item (back-compat with the
        legacy local-override list form).
        """
        items: List[Any] = []
        for name in names:
            group_items = self.get_group_items(name) if isinstance(name, str) else None
            if group_items is not None:
                items.extend(group_items)
            else:
                items.append(name)
        return items

    def load_global(self) -> Optional[List[Any]]:
        """
        Load global navigation bar from environment configuration.
        
        Delegates to zConfig for loading zEnv YAML files - this method only reads from os.environ.
        zConfig.load_dotenv() loads zEnv.base.yaml + zEnv.{environment}.yaml and injects into os.environ.
        
        Supports multiple formats (priority order):
        1. os.environ["ZNAVBAR"] (from zConfig's zEnv YAML loading) - THE zOS WAY
        2. Legacy .zEnv file parsing (backward compatibility only)
        3. Legacy comma-separated: ZNAVBAR=zVaF,zAbout,zLogin
        
        Returns
        -------
        Optional[List[Any]]
            List of navbar items (strings or dicts with RBAC) or None
        
        Examples
        --------
        YAML dict format (recommended, loaded by zConfig)::
        
            Input (zEnv.base.yaml):
                ZNAVBAR:
                  zVaF:
                  zAccount:
                    zRBAC:
                      require_role: [zAdmin]
            Output: ["zVaF", {"zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}]
        
        Legacy format::
        
            ZNAVBAR=zVaF,zAbout,zRegister,zLogin
            Returns: ["zVaF", "zAbout", "zRegister", "zLogin"]
        
        Notes
        -----
        - Loaded once during initialization
        - Cached in self._global_navbar (unfiltered)
        - RBAC filtering applied later in resolve()
        - zEnv YAML files are loaded by zConfig (config_paths.load_dotenv) and injected into os.environ
        - This method does NOT parse YAML files directly - that's zConfig's responsibility
        """
        import os
        import json
        from pathlib import Path

        # Priority 1: Check os.environ (from zConfig's zEnv YAML loading - THE zOS WAY)
        navbar_env = os.getenv("ZNAVBAR", "").strip()

        # Priority 2: Fallback to legacy .zEnv file (backward compatibility only)
        # Note: This is only for legacy setups. Modern setups use zEnv.*.yaml loaded by zConfig.
        if not navbar_env:
            legacy_env_path = Path(self.zos.config.paths.workspace_dir) / ".zEnv"
            if legacy_env_path.exists():
                try:
                    env_data = self.zos.zparser.parse_file_by_path(str(legacy_env_path))
                    if env_data and "ZNAVBAR" in env_data:
                        navbar_raw = env_data["ZNAVBAR"]
                        if isinstance(navbar_raw, dict):
                            navbar_items = self._register_groups(navbar_raw)
                            if navbar_items:
                                self.logger.framework.info(
                                    f"[NavbarHandler] Loaded navbar from legacy .zEnv "
                                    f"({len(navbar_items)} items)"
                                )
                                return navbar_items
                        elif isinstance(navbar_raw, str):
                            navbar_env = navbar_raw
                except Exception as e:
                    self.logger.framework.debug(f"[NavbarHandler] Failed to parse legacy .zEnv: {e}")

            if not navbar_env:
                self.logger.framework.debug(
                    "[NavbarHandler] No global navbar defined in ZNAVBAR env var "
                    "(zConfig should load from zEnv.*.yaml)"
                )
                return None

        # Parse navbar_env (from os.environ or legacy .zEnv)
        # Check if it's JSON dict format (starts with '{') - FROM zEnv YAML flattening
        if navbar_env.startswith("{"):
            # zEnv flattened dict: Parse as JSON dict
            try:
                navbar_raw = json.loads(navbar_env)

                if not isinstance(navbar_raw, dict):
                    self.logger.framework.warning(f"[NavbarHandler] ZNAVBAR JSON is not a dict: {type(navbar_raw)}")
                    return None

                # Register named groups (SSOT) and derive default items + brand
                navbar_items = self._register_groups(navbar_raw)

                if navbar_items:
                    self.logger.framework.info(
                        f"[NavbarHandler] Loaded navbar from os.environ (zEnv YAML) "
                        f"({len(navbar_items)} items, {len(self._groups)} group(s), "
                        f"default={self._default_group})"
                    )
                    return navbar_items

            except json.JSONDecodeError as e:
                self.logger.framework.error(f"[NavbarHandler] Failed to parse ZNAVBAR JSON dict: {e}")
                return None
            except Exception as e:
                self.logger.framework.error(f"[NavbarHandler] Error processing ZNAVBAR dict: {e}")
                return None

        # Check if it's JSON array format (starts with '[') - LEGACY
        elif navbar_env.startswith("["):
            # Enhanced JSON format: Parse as JSON
            try:
                navbar_raw = json.loads(navbar_env)

                if not isinstance(navbar_raw, list):
                    self.logger.framework.warning(f"[NavbarHandler] ZNAVBAR JSON is not an array: {type(navbar_raw)}")
                    return None

                # Transform JSON format to internal format
                # Input: [{"item": "zVaF"}, {"item": "^logout", "zRBAC": {...}}]
                # Output: ["zVaF", {"^logout": {"zRBAC": {...}}}]
                navbar_items = []
                for entry in navbar_raw:
                    if not isinstance(entry, dict):
                        self.logger.framework.warning(f"[NavbarHandler] Invalid navbar entry (not a dict): {entry}")
                        continue

                    item_name = entry.get("item")
                    if not item_name:
                        self.logger.framework.warning(f"[NavbarHandler] Navbar entry missing 'item' key: {entry}")
                        continue

                    # If entry has zRBAC, convert to dict format: {item_name: {zRBAC: ...}}
                    if "zRBAC" in entry:
                        navbar_items.append({item_name: {"zRBAC": entry["zRBAC"]}})
                    else:
                        # Simple string item (public)
                        navbar_items.append(item_name)

                if navbar_items:
                    self.logger.framework.info(
                        f"[NavbarHandler] Loaded enhanced navbar (JSON) "
                        f"with {len(navbar_items)} items"
                    )
                    return navbar_items

            except json.JSONDecodeError as e:
                self.logger.framework.error(f"[NavbarHandler] Failed to parse ZNAVBAR JSON: {e}")
                return None
            except Exception as e:
                self.logger.framework.error(f"[NavbarHandler] Error processing ZNAVBAR: {e}")
                return None

        else:
            # Legacy format: Split by comma
            navbar_items = [item.strip() for item in navbar_env.split(",") if item.strip()]

            if navbar_items:
                self.logger.framework.info(f"[NavbarHandler] Loaded legacy navbar (comma-separated): {navbar_items}")
                return navbar_items

        return None

    def parse_dict(self, navbar_raw: Dict[str, Any]) -> List[Any]:
        """
        Parse navbar dict format into internal format.
        
        Args
        ----
        navbar_raw : Dict[str, Any]
            Dict with item names as keys and optional metadata as values
        
        Returns
        -------
        List[Any]
            List of navbar items (strings or dicts with RBAC and/or sub-items)
        
        Examples
        --------
        Simple items::
        
            Input: {"zVaF": None, "zAbout": None}
            Output: ["zVaF", "zAbout"]
        
        Items with RBAC::
        
            Input: {"zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}
            Output: [{"zAccount": {"zRBAC": {"require_role": ["zAdmin"]}}}]
        
        Items with sub-items::
        
            Input: {"zProducts": {"zSub": ["zCLI", "zBifrost"]}}
            Output: [{"zProducts": {"zSub": ["zCLI", "zBifrost"]}}]
        """
        navbar_items = []

        for item_name, item_config in navbar_raw.items():
            # zBrand is not a nav item — it is the brand/home element, handled
            # separately via _extract_brand() and exposed as handler.brand.
            if item_name == "zBrand":
                continue
            # Explicit hide: `<name>: false` keeps the declaration but drops the
            # item from render — the on/off complement of null/true (show-by-
            # convention). Composes with zRBAC; toggling a page off is a one-char
            # edit, no need to delete the line. (false is the ONLY boolean that
            # suppresses; null/true/string/dict all fall through as visible.)
            if self._is_hidden(item_config):
                continue
            # If item has metadata (zRBAC, zSub, or an explicit zLink override),
            # include it. zLink is the opt-in escape hatch: structure-by-name is the
            # default, but an explicit zLink lets an item target any file/block —
            # the same mechanism zBrand uses for the home link.
            if item_config and isinstance(item_config, dict):
                metadata = {}
                # zGate is the modern per-item auth gate; zRBAC is its retired
                # predecessor (still carried so gate_predicate can lower + warn).
                # BOTH must survive parse_dict or filter_by_rbac has nothing to
                # gate on and the item leaks to everyone (e.g. Logout shown to
                # logged-out visitors).
                if "zGate" in item_config:
                    metadata["zGate"] = item_config["zGate"]
                if "zRBAC" in item_config:
                    metadata["zRBAC"] = item_config["zRBAC"]
                if "zSub" in item_config:
                    metadata["zSub"] = self._normalize_zsub(item_config["zSub"])
                if "zLink" in item_config:
                    metadata["zLink"] = item_config["zLink"]

                if metadata:
                    navbar_items.append({item_name: metadata})
                else:
                    # Config dict but no recognized metadata
                    navbar_items.append(item_name)
            elif isinstance(item_config, str) and item_config.strip() \
                    and item_config.strip().lower() != "true":
                # A bare STRING value is a zLink shorthand — mirrors the zSub
                # child grammar (_coerce_zsub_child) so a top-level item can point
                # anywhere without the full `zLink:` block:
                #     zStack: @.zViews.zStack.zUI.zStack.zStack
                # The structural sentinels (true / null / blank) stay show-by-
                # convention; `false` was already dropped by _is_hidden above.
                navbar_items.append({item_name: {"zLink": item_config.strip()}})
            else:
                # Simple structural item (public, resolve by convention).
                navbar_items.append(item_name)

        return navbar_items

    @staticmethod
    def _coerce_zsub_child(value: Any) -> Dict[str, Any]:
        """Coerce one zSub child value into a normalized ``{zLink?, zRBAC?}`` dict.

        Authoring forms for a child value:
            true / null  → structural default (resolve by convention) → {}
            "<zPath>"     → shorthand for an explicit zLink override
            {zLink, zRBAC}→ full form (per-child RBAC reserved for the next step)
        """
        if value is None or value is True:
            return {}
        if isinstance(value, str):
            v = value.strip()
            if v.lower() == "true":
                return {}
            return {"zLink": v} if v else {}
        if isinstance(value, dict):
            meta: Dict[str, Any] = {}
            if value.get("zLink"):
                meta["zLink"] = value["zLink"]
            if value.get("zRBAC"):
                meta["zRBAC"] = value["zRBAC"]
            return meta
        return {}

    def _normalize_zsub(self, zsub: Any) -> Dict[str, Dict[str, Any]]:
        """Normalize an authored zSub into an ordered ``{child: {zLink?, zRBAC?}}``.

        Accepts both the list form (all children structural) and the dict form
        (per-child override), so structure-by-convention stays the zero-config
        default while explicit zLink/zRBAC is opt-in — mirroring the top-level
        navbar grammar.

            zSub: [zLSP, zOS]                       # all structural
            zSub: {zLSP: true, zOS: @.UI...}        # mixed: structural + override
        """
        out: Dict[str, Dict[str, Any]] = {}
        if isinstance(zsub, list):
            for child in zsub:
                if isinstance(child, str):
                    out[child] = {}
                elif isinstance(child, dict) and len(child) == 1:
                    name = next(iter(child))
                    if self._is_hidden(child[name]):
                        continue
                    out[name] = self._coerce_zsub_child(child[name])
        elif isinstance(zsub, dict):
            for name, value in zsub.items():
                if self._is_hidden(value):  # `<child>: false` → drop from render
                    continue
                out[name] = self._coerce_zsub_child(value)
        return out

    @staticmethod
    def _is_hidden(value: Any) -> bool:
        """True when an authored value explicitly suppresses the item (`false`).

        The on/off complement of null/true (show-by-convention) — mirrors the
        top-level navbar grammar so a sub-item toggles the same way a top-level
        one does.
        """
        return value is False or (
            isinstance(value, str) and value.strip().lower() == "false"
        )

    @staticmethod
    def resolve_zsub_child_zlink(
        parent_name: str,
        child_name: str,
        child_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """SSOT for a zSub child's navigation target — one authority, both surfaces.

        Resolves a dropdown child to a single canonical zLink that the zCLI menu
        dispatches and the Bifrost builder maps to a route. Resolving here (once,
        at the navbar layer) instead of per-renderer is what keeps CLI ⇄ Bifrost
        from drifting.

            override   — child carries an explicit zLink (zPath) → navigate
                         anywhere, any block (structure-by-name is bypassed)
            structural — fall back to the convention
                         ``@.zViews.{parent}.zUI.{child}.{child}``
                         (parent folder, file ``zUI.{child}``, block ``{child}``)

        Note: NO ``_Details`` suffix — that was a deprecated CLI-only assumption
        that 404'd against real pages (proven in the zCLI baseline). The block is
        the child name; anything off-convention uses an explicit zLink.
        """
        meta = child_meta if isinstance(child_meta, dict) else {}
        override = meta.get("zLink")
        if override:
            return override
        parent = re.sub(r"^[\$\^~]+", "", str(parent_name)).strip()
        child = str(child_name).strip()
        return zpath.join(
            zpath.SIGIL_WORKSPACE, "zViews", parent, "zUI", child, child
        )

    @staticmethod
    def _carry(item_name: str, sub_items: Any, zlink: Any) -> Union[str, Dict[str, Any]]:
        """Rebuild a visible navbar item, preserving zSub and any explicit zLink.

        A bare name stays a bare string (structure-by-convention default). When the
        item carries sub-items and/or an explicit zLink override, wrap it so that
        metadata survives RBAC filtering and reaches the renderers.
        """
        meta: Dict[str, Any] = {}
        if sub_items:
            meta["zSub"] = sub_items
        if zlink:
            meta["zLink"] = zlink
        return {item_name: meta} if meta else item_name

    def filter_by_rbac(self, navbar_items: List[Any]) -> List[Union[str, Dict[str, Any]]]:
        """
        Filter navbar items based on RBAC rules and current user authentication state.
        
        This is the "Terminal First" implementation - filtering happens in the backend
        (zLoader/zNavigation layer) ensuring consistent behavior across Terminal and Bifrost.
        
        Filtering Rules
        ---------------
        1. String items (no zRBAC) → Always visible (public)
        2. Dict items with zRBAC:
            - zGuest: true → Only visible if NOT authenticated
            - authenticated: true → Only visible if authenticated
            - authenticated: false → Only visible if NOT authenticated (same as zGuest)
            - require_role: "role" → Only visible if user has that role
        3. Dict items with zSub → Preserved in output for hierarchical navigation
        4. Invalid items → Filtered out (logged as warnings)
        
        Args
        ----
        navbar_items : List[Any]
            Raw navbar items (strings or dicts with RBAC metadata and/or sub-items)
        
        Returns
        -------
        List[Union[str, Dict[str, Any]]]
            Filtered list of navbar items (strings or dicts with zSub)
        
        Examples
        --------
        Not authenticated::
        
            Input: ["zVaF", {"^logout": {"zRBAC": {"authenticated": true}}}, 
                    {"^zLogin": {"zRBAC": {"authenticated": false}}}]
            Output: ["zVaF", "^zLogin"]
        
        With sub-items::
        
            Input: ["zVaF", {"zProducts": {"zSub": ["zCLI", "zBifrost"]}}]
            Output: ["zVaF", {"zProducts": {"zSub": ["zCLI", "zBifrost"]}}]
        
        Authenticated as zAdmin::
        
            Input: ["zVaF", {"zAccount": {"zRBAC": {"require_role": "zAdmin"}}}, 
                    {"^zLogin": {"zRBAC": {"authenticated": false}}}]
            Output: ["zVaF", "zAccount"]
        
        Notes
        -----
        - Uses zos.auth.is_authenticated() for auth checks
        - Preserves zSub metadata for hierarchical menus
        - Uses zos.auth.has_role() for role checks
        - Returns clean item names (without zRBAC metadata)
        - Logs filtered items at DEBUG level
        """
        if not navbar_items:
            return []

        filtered = []

        for item in navbar_items:
            # Case 1: Simple string item (no RBAC) - always visible
            if isinstance(item, str):
                filtered.append(item)
                continue

            # Case 2: Dict item with potential RBAC metadata and/or sub-items
            if isinstance(item, dict):
                # Extract the item name (key) and metadata (value)
                if len(item) != 1:
                    self.logger.framework.warning(
                        f"[NavbarHandler] Invalid navbar item dict "
                        f"(must have exactly 1 key): {item}"
                    )
                    continue

                item_name = list(item.keys())[0]
                item_metadata = item[item_name]

                # zBrand (home) is always public — preserve its full metadata
                # (label + zLink) so the renderer can show the brand label and
                # navigate to the zSpark root. Never RBAC-filtered.
                if item_name == "zBrand":
                    filtered.append(item)
                    continue

                # Extract sub-items and any explicit zLink override (carried through
                # filtering so a visible item keeps its target).
                sub_items = (
                    item_metadata.get("zSub") if isinstance(item_metadata, dict) else None
                )
                zlink = (
                    item_metadata.get("zLink") if isinstance(item_metadata, dict) else None
                )

                # Extract the authored gate (zGate:) via the SSOT engine. No gate
                # present → public item.
                gate = self.zos.zgate.gate_predicate(item_metadata) \
                    if isinstance(item_metadata, dict) else None
                if gate is None:
                    filtered.append(self._carry(item_name, sub_items, zlink))
                    continue

                # Delegate the per-item decision to the SSOT gate engine
                # (zos.zgate) — the SAME evaluator page access, routes, and the
                # dispatch action gate use. It forwards auth to check_zrbac, so this
                # stays context-aware. This handler used to reimplement auth/role
                # checks inline against the tier-agnostic is_authenticated(), which
                # DIVERGED from the page gate: a Bifrost WS login sets
                # session.zVisitor (context-authed) but not the tier-agnostic flag,
                # so an authed user never saw ^logout. One evaluator now governs
                # page access, navbar visibility, routes, and actions.
                try:
                    granted, reason = self.zos.zgate.evaluate(gate)
                except Exception as exc:  # pylint: disable=broad-except
                    # Never crash the navbar; fail closed on a gated item.
                    granted, reason = False, f"zGate error: {exc}"

                if granted:
                    filtered.append(self._carry(item_name, sub_items, zlink))
                    self.logger.framework.debug(
                        f"[NavbarHandler] Navbar item '{item_name}' visible "
                        f"(check_zrbac granted)"
                    )
                else:
                    self.logger.framework.debug(
                        f"[NavbarHandler] Navbar item '{item_name}' hidden ({reason})"
                    )
                continue

            # Case 3: Invalid item type
            self.logger.framework.warning(f"[NavbarHandler] Invalid navbar item type: {type(item)} ({item})")

        self.logger.framework.debug(f"[NavbarHandler] Filtered navbar: {len(navbar_items)} → {len(filtered)} items")
        return filtered

    def resolve(
        self,
        raw_zFile: Dict[str, Any],
        route_meta: Optional[Dict[str, Any]] = None
    ) -> Optional[List[str]]:
        """
        Resolve navigation bar for a given zVaFile based on meta.zNavBar with route fallback.
        
        Resolution Logic (Priority Chain)
        ----------------------------------
        1. If zVaFile meta.zNavBar is a list → return it (highest priority: local override)
        2. If zVaFile meta.zNavBar: true → return global navbar from .zEnv
        3. If zVaFile meta.zNavBar is false/missing AND route meta.zNavBar: true →
           return global navbar (lowest priority: route fallback)
        4. Otherwise → return None (no navbar)
        
        Args
        ----
        raw_zFile : Dict[str, Any]
            Parsed YAML dictionary from zVaFile
        route_meta : Optional[Dict[str, Any]], default=None
            Optional route metadata from zServer.routes.yaml (for fallback)
        
        Returns
        -------
        Optional[List[str]]
            Resolved navbar items or None
        
        Examples
        --------
        Priority 1: Local override (custom navbar)::
        
            zVaFile meta.zNavBar: ["Custom", "Items"]
            Returns: ["Custom", "Items"]
        
        Priority 2: zVaFile opt-in to global navbar::
        
            zVaFile meta.zNavBar: true
            Returns: ["zVaF", "zAbout", "zRegister", "zLogin"] (from .zEnv)
        
        Priority 3: Route fallback (if zVaFile has no navbar)::
        
            zVaFile meta.zNavBar: missing/false
            Route meta.zNavBar: true
            Returns: ["zVaF", "zAbout", "zRegister", "zLogin"] (from .zEnv)
        
        No navbar::
        
            All meta.zNavBar: false/missing
            Returns: None
        
        Notes
        -----
        - Local navbar always wins (DRY principle with override)
        - Route meta provides fallback for files without navbar
        - zServer routes can enforce navbar for all pages via meta.zNavBar: true
        """
        if not raw_zFile or not isinstance(raw_zFile, dict):
            return None

        # Get zVaFile zMeta section
        meta_section = raw_zFile.get("zMeta", {})
        if not isinstance(meta_section, dict):
            meta_section = {}

        # Get zNavBar value from zVaFile
        navbar_value = meta_section.get("zNavBar")

        # Normalize string 'true'/'false' to boolean (for .zolo file compatibility)
        if isinstance(navbar_value, str):
            navbar_value = navbar_value.lower() == 'true'

        # Priority 1: Named group reference(s) — list form `zNavBar: [Main, Tools]`.
        # Each name expands to its group's items; unknown names pass through as
        # literal items (back-compat with the legacy local-override list form).
        if isinstance(navbar_value, list):
            if len(navbar_value) > 0:
                expanded = self._expand_group_refs(navbar_value)
                self.logger.framework.debug(
                    f"[NavbarHandler] Resolved navbar group refs {navbar_value} "
                    f"-> {expanded}"
                )
                # Return raw (unfiltered) navbar - filtering happens dynamically in zDispatch
                return expanded or None
            else:
                self.logger.framework.debug("[NavbarHandler] Empty local navbar, skipping")
                return None

        # Priority 2: zVaFile opt-in to global navbar (true)
        if navbar_value is True:
            if self._global_navbar:
                self.logger.framework.debug(
                    f"[NavbarHandler] Injecting global navbar from zVaFile (priority 2): "
                    f"{self._global_navbar}"
                )
                # Return raw (unfiltered) navbar - filtering happens dynamically in zDispatch
                return self._global_navbar
            else:
                self.logger.framework.warning(
                    "[NavbarHandler] meta.zNavBar: true but no global navbar defined in .zEnv"
                )
                return None

        # Explicit opt-out (SSOT): a page that sets `zNavBar: false` has DECIDED
        # it wants no navbar — a hard opt-out, not "no opinion". Only a MISSING
        # zNavBar (None) defers to the route-level fallback below. Without this
        # short-circuit a route with `zNavBar: true` would silently override the
        # page's explicit false (the focused-landing leak).
        if navbar_value is False:
            self.logger.framework.debug(
                "[NavbarHandler] zNavBar: false — explicit page opt-out, no navbar "
                "(route fallback skipped)"
            )
            return None

        # Priority 3: Route fallback (if zVaFile has NO zNavBar setting at all)
        # Check if route metadata has zNavBar: true
        if route_meta and isinstance(route_meta, dict):
            route_navbar_value = route_meta.get("zNavBar")

            # Normalize string 'true'/'false' to boolean (for .zolo file compatibility)
            if isinstance(route_navbar_value, str):
                route_navbar_value = route_navbar_value.lower() == 'true'

            if route_navbar_value is True:
                if self._global_navbar:
                    self.logger.framework.debug(
                        f"[NavbarHandler] Injecting global navbar from route fallback "
                        f"(priority 3): {self._global_navbar}"
                    )
                    # Return raw (unfiltered) navbar - filtering happens dynamically in zDispatch
                    return self._global_navbar
                else:
                    self.logger.framework.warning(
                        "[NavbarHandler] Route meta.zNavBar: true but no global navbar "
                        "defined in .zEnv"
                    )
                    return None
            elif isinstance(route_navbar_value, list) and len(route_navbar_value) > 0:
                self.logger.framework.debug(
                    f"[NavbarHandler] Using route navbar fallback (priority 3): "
                    f"{route_navbar_value}"
                )
                # Return raw (unfiltered) navbar - filtering happens dynamically in zDispatch
                return route_navbar_value

        # Case 4: No navbar (false, None, or missing everywhere)
        self.logger.framework.debug("[NavbarHandler] No navbar configured (zVaFile or route)")
        return None

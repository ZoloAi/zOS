"""
Server File Parser - Parse zServer.*.yaml routing files (v1.5.4+)

This module parses declarative HTTP routing files for zServer, enabling
Flask blueprint-style route definitions with integrated RBAC.

Philosophy:
    "Routes are data, not code" - zServer follows zOS's declarative approach

Structure:
    {
        "type": "server",
        "file_path": str,
        "meta": {
            "base_path": "./public",
            "default_route": "index.html",
            "error_pages": {403: "access_denied.html", 404: "404.html"}
        },
        "routes": {
            "/path": {
                "type": "static|dynamic|redirect",
                "file": "page.html",
                "description": "...",
                "zRBAC": {require_role: "admin"} or None
            }
        }
    }

Route Types:
    - static: Serve file from base_path
    - dynamic: Execute zFunc handler (future)
    - redirect: HTTP redirect (future)

RBAC Integration:
    Routes can have inline zRBAC metadata (same as zUI):
    - require_auth: true (or authenticated: true/false)
    - require_role: "admin" or ["admin", "moderator"]  (exact match)

Examples:
    >>> data = {
    ...     "zMeta": {"base_path": "./public"},
    ...     "routes": {
    ...         "/": {"type": "static", "file": "index.html"},
    ...         "/admin": {
    ...             "type": "static",
    ...             "file": "admin.html",
    ...             "zRBAC": {"require_role": "admin"}
    ...         }
    ...     }
    ... }
    >>> result = parse_server_file(data, logger)
    >>> result["type"]
    "server"
    >>> result["routes"]["/admin"]["zRBAC"]
    {"require_role": "admin"}

Integration:
    - Called by parser_file.py when zServer.*.yaml detected
    - Used by zServer.py to load routing configuration
    - RBAC checked by router.py during request handling

Version: v1.5.4 Phase 2
"""

from zOS import Any, Dict, Optional

# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath

# =============================================================================
# MODULE CONSTANTS
# =============================================================================

# Import constants from centralized module (private - internal use only)
from ..shared.parser_constants import (
    _FILE_TYPE_SERVER as FILE_TYPE_SERVER,
    _KEY_META as KEY_META,
    _KEY_ROUTES as KEY_ROUTES,
    _KEY_BASE_PATH as KEY_BASE_PATH,
    _KEY_DEFAULT_ROUTE as KEY_DEFAULT_ROUTE,
    _KEY_ERROR_PAGES as KEY_ERROR_PAGES,
    _KEY_TYPE as KEY_TYPE,
    _KEY_FILE as KEY_FILE,
    _KEY_CONTENT as KEY_CONTENT,
    _KEY_TEMPLATE as KEY_TEMPLATE,
    _KEY_CONTEXT as KEY_CONTEXT,
    _KEY_HANDLER as KEY_HANDLER,
    _KEY_TARGET as KEY_TARGET,
    _KEY_STATUS as KEY_STATUS,
    _KEY_DESCRIPTION as KEY_DESCRIPTION,
    _KEY_RBAC as KEY_RBAC,
    _KEY_ZVAFILE as KEY_ZVAFILE,
    _KEY_ZBLOCK as KEY_ZBLOCK,
    _ROUTE_TYPE_STATIC as ROUTE_TYPE_STATIC,
    _DEFAULT_BASE_PATH as DEFAULT_BASE_PATH,
    _DEFAULT_DEFAULT_ROUTE as DEFAULT_DEFAULT_ROUTE,
    _DEFAULT_ERROR_PAGES as DEFAULT_ERROR_PAGES,
    _LOG_MSG_PARSING_SERVER as LOG_MSG_PARSING_SERVER,
    _LOG_MSG_FOUND_ROUTES as LOG_MSG_FOUND_ROUTES,
    _LOG_MSG_ROUTE_WITH_RBAC as LOG_MSG_ROUTE_WITH_RBAC,
    _LOG_MSG_NO_ROUTES as LOG_MSG_NO_ROUTES,
)


# =============================================================================
# SERVER FILE PARSING
# =============================================================================

def parse_server_file(
    data: Dict[str, Any],
    logger: Any,
    file_path: Optional[str] = None,
    _session: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse server routing file with RBAC extraction.
    
    ⚠️ CRITICAL: This function is called by parser_file.py.
    Signature must remain stable.
    
    Args:
        data: Parsed YAML/JSON data from zServer file
        logger: Logger instance for diagnostic output
        file_path: Optional file path for logging
        _session: Optional session dict (reserved for future use, intentionally unused)
    
    Returns:
        Dict[str, Any]: Parsed server routing structure with format:
            {
                "type": "server",
                "file_path": str or None,
                "meta": {
                    "base_path": str,
                    "default_route": str,
                    "error_pages": {403: str, 404: str}
                },
                "routes": {
                    "/path": {
                        "type": str,
                        "file": str,
                        "description": str,
                        "zRBAC": dict or None
                    }
                }
            }
    
    Process Flow:
        1. Extract Meta section (base_path, default_route, error_pages)
        2. Extract routes section with RBAC metadata
        3. Return structured routing data
    
    Examples:
        >>> data = {
        ...     "zMeta": {"base_path": "./public"},
        ...     "routes": {
        ...         "/": {"type": "static", "file": "index.html"}
        ...     }
        ... }
        >>> result = parse_server_file(data, logger, "zServer.demo.yaml")
        >>> result["type"]
        "server"
        >>> result["meta"]["base_path"]
        "./public"
    
    Notes:
        - Missing Meta uses defaults
        - Routes without zRBAC are public
        - RBAC metadata is preserved for router.py
        - _session parameter reserved for future session-aware parsing
    """
    logger.debug(LOG_MSG_PARSING_SERVER)

    # Extract Meta with defaults. zMeta is the SSOT key across ALL zVaFiles; route
    # files historically used lowercase `meta` (an SSOT leak). Accept `zMeta` first,
    # fall back to `meta` for back-compat with legacy zServer route files.
    meta_raw = data.get("zMeta")
    if not isinstance(meta_raw, dict):
        meta_raw = data.get(KEY_META, {})
    # Preserve the FULL meta block — custom keys (zVaFolder, zAPI, …) included — and
    # only fill the three routing defaults when absent. Rebuilding meta from a fixed
    # whitelist here was the old SSOT leak: it silently dropped custom keys, which
    # forced zServer to re-open + re-parse the raw file to recover them. A faithful
    # parse means ONE read carries everything; downstream reads meta from this dict.
    meta = dict(meta_raw) if isinstance(meta_raw, dict) else {}
    meta.setdefault(KEY_BASE_PATH, DEFAULT_BASE_PATH)
    meta.setdefault(KEY_DEFAULT_ROUTE, DEFAULT_DEFAULT_ROUTE)
    meta.setdefault(KEY_ERROR_PAGES, DEFAULT_ERROR_PAGES.copy())

    # File-wide directives (zVaFolder, zAPI) now survive in `meta` above; they are
    # consumed downstream from the parsed dict (route_manager), never re-read from
    # disk. Only zBlock derivation (below) lives here — it keys off route-level
    # zVaFile.

    # Extract routes with RBAC. Track whether a routes: block was DECLARED at all
    # (vs. a route-less meta-only file): a declared block whose every entry is
    # invalid is a genuine parse failure, not an empty-but-valid config.
    routes_raw = data.get(KEY_ROUTES, {})
    routes_declared = bool(routes_raw)
    if not isinstance(routes_raw, dict):
        routes_raw = {}
    routes = {}

    for route_path, route_data in routes_raw.items():
        if not isinstance(route_data, dict):
            logger.warning(f"[vafile_server] Skipping invalid route: {route_path}")
            continue

        # Extract RBAC metadata
        rbac = route_data.get(KEY_RBAC, None)

        # Build route entry
        route_entry = {
            KEY_TYPE: route_data.get(KEY_TYPE, ROUTE_TYPE_STATIC),
            KEY_RBAC: rbac
        }

        # Add type-specific fields
        if KEY_FILE in route_data:
            route_entry[KEY_FILE] = route_data[KEY_FILE]
        if KEY_CONTENT in route_data:
            route_entry[KEY_CONTENT] = route_data[KEY_CONTENT]
        if KEY_TEMPLATE in route_data:
            route_entry[KEY_TEMPLATE] = route_data[KEY_TEMPLATE]
        if KEY_CONTEXT in route_data:
            route_entry[KEY_CONTEXT] = route_data[KEY_CONTEXT]
        if KEY_HANDLER in route_data:
            route_entry[KEY_HANDLER] = route_data[KEY_HANDLER]
        if KEY_TARGET in route_data:
            route_entry[KEY_TARGET] = route_data[KEY_TARGET]
        if KEY_STATUS in route_data:
            route_entry[KEY_STATUS] = route_data[KEY_STATUS]
        if KEY_DESCRIPTION in route_data:
            route_entry[KEY_DESCRIPTION] = route_data[KEY_DESCRIPTION]
        # View reference (the page to render). `zUI` is the SSOT alias for the
        # legacy `zVaFile`; both accept the agnostic zPath grammar — a single full
        # `@.<folder>.<zUI.File>` (normalized to folder/file/block below) or the
        # bare `zUI.File` + zVaFolder default. zUI wins if both appear.
        view_ref = route_data.get("zUI") if "zUI" in route_data else route_data.get(KEY_ZVAFILE)
        if view_ref is not None:
            route_entry[KEY_ZVAFILE] = view_ref
        if "zVaFolder" in route_data:  # zWalker folder path
            route_entry["zVaFolder"] = route_data["zVaFolder"]
        if KEY_ZBLOCK in route_data:
            route_entry[KEY_ZBLOCK] = route_data[KEY_ZBLOCK]
        # Data reference: route-level `zLoom` (named read, SSOT). The gate for
        # type:zLoom routes, and data injected into ANY route's view context.
        # Alias or full @ zPath — same grammar as a block's zMeta.zLoom.
        if "zLoom" in route_data:
            route_entry["zLoom"] = route_data["zLoom"]
        if "auto_discover_blocks" in route_data:  # Smart Walker Routes (auto-discovery)
            route_entry["auto_discover_blocks"] = route_data["auto_discover_blocks"]
        if "data" in route_data:  # JSON route data
            route_entry["data"] = route_data["data"]
        if "zProxy" in route_data:  # type:zProxy front-door policy (table/key/spark_field)
            route_entry["zProxy"] = route_data["zProxy"]

        # Agnostic zPath normalization for the view ref: a FULL zPath
        #   (@.<folder>.<zUI.File>) is split into folder/file/block so every
        #   downstream consumer keeps its split form — same way `model:` paths
        #   resolve. Filenames are two-part (<prefix>.<Name>), so the LAST two
        #   segments are the file, the rest the folder, the tail the block.
        _vf = route_entry.get(KEY_ZVAFILE)
        if isinstance(_vf, str) and _vf.startswith(zpath.SIGIL_WORKSPACE):
            _parts = zpath.split(_vf)
            _segs = list(_parts.segments)
            if len(_segs) >= 2:
                route_entry[KEY_ZVAFILE] = ".".join(_segs[-2:])
                route_entry["zVaFolder"] = (
                    zpath.join(_parts.symbol, *_segs[:-2]) if len(_segs) > 2 else _parts.symbol
                )
                route_entry.setdefault(KEY_ZBLOCK, _segs[-1])

        # SSOT derivation (bare-ref path) — zBlock defaults to the zVaFile's
        # primary block: zUI.PublicProfile → PublicProfile ; zUI.zVaF → zVaF.
        # Keeps a virtual zLoom route as lean as `type` + `zUI`.
        if KEY_ZBLOCK not in route_entry and route_entry.get(KEY_ZVAFILE):
            route_entry[KEY_ZBLOCK] = str(route_entry[KEY_ZVAFILE]).split(".")[-1]

        routes[route_path] = route_entry

        # Log RBAC routes
        if rbac:
            logger.debug(LOG_MSG_ROUTE_WITH_RBAC, route_path, rbac)

    # Log summary at DEBUG level (route_manager logs the INFO summary)
    route_count = len(routes)
    if route_count > 0:
        logger.debug(LOG_MSG_FOUND_ROUTES, route_count)
    elif routes_declared:
        # A routes: block was declared but EVERY entry was invalid — this is a
        # broken edit, NOT a route-less meta-only file. Return None so the file
        # reads as unparseable: zLoader/route_manager then keep the previous
        # routing table instead of silently degrading to the default / walker.
        logger.error(
            "[vafile_server] Routes declared but none valid — file is unparseable"
        )
        return None
    else:
        logger.warning(LOG_MSG_NO_ROUTES)
    return {
        "type": FILE_TYPE_SERVER,
        "file_path": file_path,
        "meta": meta,
        "routes": routes
    }

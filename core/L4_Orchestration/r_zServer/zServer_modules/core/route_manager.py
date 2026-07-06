 # zOS/core/L4_Orchestration/r_zServer/zServer_modules/core/route_manager.py

"""
RouteManager - Route detection and loading for zServer

Handles:
- Auto-detection of zServer route files (.zolo, .yaml, .json)
- Route loading and merging (blueprint pattern)
- Router initialization
"""

from zOS import os
import glob

from ..utils.zserver_constants import PATTERN_ROUTE_FILES, FOLDER_ROUTES


class RouteManager:
    """
    Manages route detection, loading, and router initialization.
    
    Supports Flask-style blueprints: multiple route files are merged
    into a single router. Auto-detects zServer route files (zVaFiles) 
    in serve_path and routes/ subfolder.
    """

    def __init__(self, serve_path, zos, logger):
        """
        Initialize RouteManager.
        
        Args:
            serve_path: Directory to serve files from
            zos: zOS instance (for auth, data integration)
            logger: zOS logger instance
        """
        self.serve_path = serve_path
        self.zos = zos
        self.logger = logger
        self.router = None
        self.routes_files = []
        # Canonical default-walker coordinates, captured ONCE from the spark at the
        # first (boot) build and reused on every reload. The live session drifts to
        # whatever page was last served; anchoring discovery on it would shrink the
        # route tree a little more each reload (see _spark_walker). Pinning to the
        # boot value keeps the app root immutable — SSOT, drift-proof.
        self._canonical_walker = None

    def auto_detect_routes_files(self):
        """
        Auto-detect ALL zServer routing files in serve_path.
        
        Scans BOTH root folder AND routes/ subfolder for zServer route files,
        following Flask blueprint-style modular routing.
        
        Convention:
            - Root folder: Primary routes (e.g., zServer.routes.zolo)
            - routes/ folder: Modular blueprints (e.g., zServer.api.zolo, zServer.themes.yaml)
        
        Returns:
            list: List of detected routes files (paths relative to serve_path)
        """
        found_files = []

        try:
            # 1. Look for zServer route files in ROOT folder (.zolo, .yaml, .json)
            for pattern in PATTERN_ROUTE_FILES:
                root_pattern = os.path.join(self.serve_path, pattern)
                root_matches = glob.glob(root_pattern)

                for match in root_matches:
                    # Store relative path from serve_path
                    rel_path = os.path.basename(match)
                    if rel_path not in found_files:  # Avoid duplicates
                        found_files.append(rel_path)
                        self.logger.framework.debug(f"[zServer] Found routes file (root): {rel_path}")

            # 2. Look for zServer route files in ROUTES/ subfolder (.zolo, .yaml, .json)
            routes_dir = os.path.join(self.serve_path, FOLDER_ROUTES)
            if os.path.isdir(routes_dir):
                for pattern in PATTERN_ROUTE_FILES:
                    routes_pattern = os.path.join(routes_dir, pattern)
                    routes_matches = glob.glob(routes_pattern)

                    for match in routes_matches:
                        # Store relative path from serve_path (includes "routes/" prefix)
                        rel_path = os.path.relpath(match, self.serve_path)
                        if rel_path not in found_files:  # Avoid duplicates
                            found_files.append(rel_path)
                            self.logger.framework.debug(f"[zServer] Found routes file (routes/): {rel_path}")

            if found_files:
                self.logger.info(f"[zServer] Detected {len(found_files)} route files")
                self.logger.debug(f"[zServer] Route files: {found_files}")
            else:
                self.logger.framework.debug("[zServer] No zServer route files found - static serving only")

            self.routes_files = found_files
            return found_files

        except Exception as e:
            self.logger.framework.debug(f"[zServer] Auto-detection failed: {e}")
            self.routes_files = []
            return []

    def load_and_merge_routes(self, routes_files):
        """
        Load routes and install the router (boot path).

        Thin wrapper over :meth:`_build_router` — builds the router off to the side
        then installs it. Kept as the boot entry point so existing callers and logs
        are unchanged; the fail-safe build/validate lives in ``_build_router`` so the
        hot-reload path (:meth:`reload`) shares the exact same construction.

        Args:
            routes_files: List of route file paths (relative to serve_path)
        """
        if not routes_files or len(routes_files) == 0:
            self.logger.framework.debug("[zServer] No routes files to load - static serving only")
            return

        self.logger.info(f"[zServer] Loading routes from {len(routes_files)} files...")
        router, route_count, zapi_count = self._build_router(routes_files)
        if router is None:
            self.logger.warning("[zServer] No valid routes found - static serving only")
            return

        self.router = router
        self.logger.info(f"[zServer] Loaded {route_count} routes from {len(routes_files)} files")
        if zapi_count:
            self.logger.debug(f"[zServer] Registered {zapi_count} zAPI endpoint(s)")

    def _build_router(self, routes_files):
        """
        Build a fully-wired router OFF TO THE SIDE — never touches ``self.router``.

        This is the SSOT for router construction (boot + reload). It merges every
        route file, normalizes zSpark/default/meta, creates the HTTPRouter, and
        registers zAPI endpoints onto THAT new router. Because it leaves the live
        router untouched until the caller swaps it in, a broken edit during a hot
        reload can never take the running site down — the caller simply discards
        the (None) result and keeps serving the previous router.

        Args:
            routes_files: List of route file paths (relative to serve_path).

        Returns:
            tuple(HTTPRouter|None, route_count, zapi_count). Router is None when no
            valid routes could be built (caller keeps the previous router) — the
            tuple shape is always returned so callers can unpack unconditionally.
        """
        try:
            # Merged routes structure (blueprint pattern)
            merged_data = {"type": "server", "meta": {}, "routes": {}}
            parse_failed = False  # a DETECTED route file that won't parse

            # Load and merge all route files (last file wins on conflict)
            for routes_file in routes_files:
                try:
                    full_path = os.path.join(self.serve_path, routes_file)
                    self.logger.debug(f"[zServer] Loading: {routes_file}")
                    routes_data = self.zos.loader.handle_absolute_path(full_path)

                    if isinstance(routes_data, dict) and routes_data.get("type") == "server":
                        if "meta" in routes_data:
                            merged_data["meta"].update(routes_data["meta"])
                        if "routes" in routes_data:
                            route_count = len(routes_data["routes"])
                            merged_data["routes"].update(routes_data["routes"])
                            self.logger.debug(f"[zServer] Loaded {route_count} routes from: {routes_file}")
                    else:
                        # zParser returns None (or a non-server doc) on a genuine parse
                        # failure — this is the truthful signal that a detected route
                        # file is broken. Flag it; we abort the whole build below so the
                        # caller keeps the previous router instead of silently shrinking
                        # the live table down to the default / walker.
                        self.logger.warning(f"[zServer] Route file failed to parse: {routes_file}")
                        parse_failed = True
                except Exception as e:
                    self.logger.error(f"[zServer] Failed to load routes from {routes_file}: {e}")
                    parse_failed = True

            # Fail-safe: any detected route file that wouldn't parse aborts the rebuild.
            # Losing even one blueprint silently is worse than keeping the prior table —
            # on reload the live router stays; at boot we fall to static (loud signal).
            if routes_files and parse_failed:
                self.logger.error(
                    "[zServer] Route file(s) failed to parse — discarding build "
                    "(previous routes kept)"
                )
                return None, 0, 0

            # zSpark routes → zspark-defaulted zWalkers (self-documenting fallback).
            self._normalize_zspark_routes(merged_data)

            # Auto-inject default zWalker for / when no explicit route is defined.
            if "/" not in merged_data["routes"]:
                merged_data["routes"]["/"] = {"type": "zWalker", "auto_discover_blocks": True}
                self.logger.framework.debug("[zServer] Auto-injected default zWalker for /")

            # File-wide smart-routing meta (zVaFolder default) from the parsed meta.
            self._apply_routing_meta(merged_data)

            total_routes = len(merged_data["routes"])
            if total_routes <= 0:
                return None, 0, 0

            from ..routing.router import HTTPRouter
            new_router = HTTPRouter(merged_data, self.zos, self.logger, serve_path=self.serve_path)

            # Register zAPI endpoints onto the NEW router (not self.router).
            zapi_count = self._register_zapi_endpoints(new_router, merged_data.get("meta"))

            return new_router, total_routes, zapi_count

        except Exception as e:
            self.logger.error(f"[zServer] Failed to build router: {e}")
            return None, 0, 0

    def reload(self) -> dict:
        """
        Hot-reload the route/zAPI table from disk — fail-safe and atomic.

        Re-detects route files, rebuilds the router OFF TO THE SIDE via
        :meth:`_build_router`, and only on success atomically swaps ``self.router``.
        The live socket, WS bridge, and in-memory sessions are untouched — running
        requests keep using the old router until the single-assignment swap, after
        which the NEXT request resolves against the new table (handlers read
        ``route_manager.get_router()`` per request).

        On any failure the previous router is left live (the site never goes dark).

        Returns:
            dict: {"ok": bool, "routes": int, "zapis": int, "error": str|None}
        """
        # ── zEnv refresh ──────────────────────────────────────────────────────
        # zEnv values (ZNAVBAR, ZAUTH_LOGIN_ROUTE, ports, …) are injected into
        # os.environ ONCE at boot; handlers read them live per request. A soft
        # reload must therefore re-inject them so edits to zEnv.base take effect
        # WITHOUT a cold restart — otherwise a moved page (e.g. login relocated
        # under zAuth/, or any navbar retarget) keeps resolving to its old route
        # and the RBAC onDenied redirect still points at a now-dead /Login.
        # Launch-time overrides (ops env / driver-injected ports) are preserved by
        # the loader's process-launch snapshot (see config_zenv._LAUNCH_ENV_KEYS).
        # Then drop the parsed-page cache so the navbar menu — baked into each page
        # at parse time from os.environ[ZNAVBAR] — is re-resolved against the fresh
        # env on the next render. Best-effort: an env refresh must never take the
        # live site down, so failures are logged and the route rebuild proceeds.
        try:
            self.zos.config.paths.load_dotenv()
            self.zos.loader.cache.clear(cache_type="system")
            # The navbar handler parses ZNAVBAR once at boot and caches it; the
            # env refresh above updates os.environ but not that in-memory copy, so
            # without this an edited ZNAVBAR (renamed/retargeted item) would keep
            # rendering its boot-time value (the navbar drift). Re-read via the
            # zNavigation SSOT so reload and boot share one navbar source.
            nav = getattr(self.zos, "navigation", None)
            if nav is not None and hasattr(nav, "reload_navbar"):
                nav.reload_navbar()
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"[zServer] reload: zEnv refresh skipped ({exc})")

        files = self.auto_detect_routes_files()
        new_router, route_count, zapi_count = (
            self._build_router(files) if files else (None, 0, 0)
        )

        if new_router is None:
            return {"ok": False, "routes": 0, "zapis": 0,
                    "error": "no valid routes built (parse error or empty table)"}

        # ── Parse-safety net (zLoader/zParser) ───────────────────────────────
        # Boot discovery is parse-free for speed; a reload is the moment new/edited
        # pages "sync" live, so HERE we actually load every page the new table would
        # expose (through the renderer's own loader path — validates == serves).
        #
        # We abort only on a REGRESSION: a page that fails in the NEW table but was
        # fine in the live one (i.e. something we just broke — e.g. a bad zAbout
        # edit). Pages that already failed before this reload are pre-existing legacy
        # breakage; they're surfaced as a non-blocking warning so a reload elsewhere
        # isn't held hostage to an unrelated broken page. Fix-as-we-reach-them.
        page_errors = self._validate_pages(new_router)
        if page_errors:
            baseline = set()
            if self.router is not None:
                baseline = {e["key"] for e in self._validate_pages(self.router)}
            new_errors = [e for e in page_errors if e["key"] not in baseline]
            if new_errors:
                return {"ok": False, "routes": 0, "zapis": 0,
                        "error": self._format_page_errors(new_errors),
                        "page_errors": new_errors}
            self.logger.warning(
                "[zServer] reload: pre-existing page parse issues (NOT blocking, "
                f"fix when you reach them):\n{self._format_page_errors(page_errors)}"
            )

        # ── Collapse guard ───────────────────────────────────────────────────
        # Defense in depth: if a rebuild yields drastically fewer auto-discovered
        # routes than the live table, treat it as a discovery fault (e.g. a bad
        # anchor) and keep the previous table rather than serving a hollow site.
        prev_auto = len(self.router.auto_discovered_routes) if self.router else 0
        new_auto = len(getattr(new_router, "auto_discovered_routes", {}) or {})
        if prev_auto >= 5 and new_auto * 2 < prev_auto:
            return {"ok": False, "routes": 0, "zapis": 0,
                    "error": (f"route discovery collapsed ({prev_auto} → {new_auto} "
                              f"auto-routes) — keeping previous table. Check the "
                              f"default-walker zVaFolder/zVaFile anchor.")}

        # Atomic swap — single GIL-protected assignment; no request sees a half table.
        self.router = new_router
        self.routes_files = files
        return {"ok": True, "routes": route_count, "zapis": zapi_count, "error": None}

    def _validate_pages(self, router) -> list:
        """
        Load every page the (about-to-go-live) ``router`` would serve and collect
        any that fail to parse. Reload-only — boot stays parse-free.

        Delegates the actual load+inspect to ``HTTPRouter.resolve_first_block`` —
        the SAME method the serve path uses to resolve a page's root block. That
        shared SSOT is what guarantees "validates == serves": a page that resolves
        here is guaranteed to render, and one the loader/parser can't turn into a
        usable block aborts the swap (we never re-implement the check, so the two
        paths can't drift). Static-file and zAPI routes carry no page body and are
        skipped.

        Returns a list of {"route", "file", "key", "reason"} dicts (empty == clean).
        """
        errors: list = []
        seen: set = set()

        for source in (router.route_map, router.auto_discovered_routes):
            for route_path, cfg in source.items():
                if not isinstance(cfg, dict):
                    continue
                zVaFile = cfg.get("zVaFile")
                zVaFolder = cfg.get("zVaFolder")
                # Only walker/page routes carry zVaFolder+zVaFile. Static-file and
                # zAPI routes have no page body to parse — skip them.
                if not (zVaFile and zVaFolder):
                    continue
                key = (zVaFolder, zVaFile)
                if key in seen:
                    continue
                seen.add(key)
                block, reason = router.resolve_first_block(cfg)
                if block is None:
                    errors.append({
                        "route": route_path,
                        "file": cfg.get("_page_path") or f"{zVaFolder}/{zVaFile}",
                        "key": f"{zVaFolder}|{zVaFile}",  # stable identity for regression diff
                        "reason": reason or "page did not resolve to a renderable block",
                    })

        return errors

    @staticmethod
    def _format_page_errors(page_errors: list) -> str:
        """Render page parse failures as a clear, actionable console block."""
        lines = ["page syntax error — reload aborted, previous routes kept live:"]
        for e in page_errors:
            lines.append(f"    • {e['route']}  ({e['file']})")
            lines.append(f"        {e['reason']}")
        lines.append("    fix the syntax (zLSP underlines it), then run `z reload` again.")
        return "\n".join(lines)

    def _register_zapi_endpoints(self, router=None, meta=None) -> int:
        """
        Scan zUI files for zAPI-enabled events and register them on ``router``.

        Args:
            router: Target router to register onto (defaults to ``self.router``).
                    The reload/build path passes the NEW router so the live one is
                    never mutated mid-build.
            meta: The parsed, merged route-file meta. zAPI defaults are read from
                  ``meta["zAPI"]`` — zParser preserves it, so no raw re-read.

        Returns:
            int: Number of zAPI endpoints registered.
        """
        target = router if router is not None else self.router
        if not target:
            return 0

        try:
            from ..routing.zapi_scanner import scan as scan_zapi

            # zAPI defaults come straight from the parsed meta (zParser preserves
            # custom keys) — SSOT, no re-opening the route file.
            api_defaults = (meta or {}).get("zAPI", {}) or {}
            prefix       = api_defaults.get("prefix", "/api")

            endpoints = scan_zapi(self.serve_path, self.zos, api_defaults, prefix)

            for ep in endpoints:
                target.auto_discovered_routes[ep["path"]] = ep["route_data"]

            return len(endpoints)

        except Exception as exc:
            self.logger.error(f"[zServer] zAPI scan failed: {exc}")
            return 0

    def _spark_walker(self) -> dict:
        """
        The active zSpark's default-walker coordinates (SSOT for the root page).

        Pulls zVaFolder/zVaFile/zBlock from the spark object, falling back to the
        live session ONLY on the first resolve (zApp seeds the session from zSpark
        at launch, so the boot session is clean). The result is then CACHED on
        ``self._canonical_walker`` and reused on every subsequent reload.

        Why cache: the live session drifts to whatever page was last served, so a
        reload that re-read it would re-anchor route discovery on a deep subfolder
        and silently shrink the route tree (a little more each reload). Pinning to
        the boot value keeps the app's root immutable across reloads. Used to fill
        `type: zSpark` routes and to default `zVaFolder` when meta omits it.
        """
        if self._canonical_walker is not None:
            return self._canonical_walker

        spark = getattr(self.zos, "spark", None) or getattr(self.zos, "zspark_obj", None) or {}
        if not isinstance(spark, dict):
            spark = {}
        sess = getattr(self.zos, "session", {}) or {}
        if not isinstance(sess, dict):
            sess = {}
        walker = {
            "zVaFolder": spark.get("zVaFolder") or sess.get("zVaFolder"),
            "zVaFile":   spark.get("zVaFile")   or sess.get("zVaFile"),
            "zBlock":    spark.get("zBlock")    or sess.get("zBlock"),
        }
        # Cache once we have a real anchor (avoid pinning empties before the spark
        # has seeded the session). After this, reloads reuse the boot-time truth.
        if walker.get("zVaFolder") or walker.get("zVaFile"):
            self._canonical_walker = walker
        return walker

    def _normalize_zspark_routes(self, merged_data: dict) -> None:
        """
        Expand `type: zSpark` routes into a zspark-defaulted zWalker.

        zSpark is self-documenting sugar for "serve the active zSpark's default
        walker here" — the explicit, discoverable form of the implicit `/` fallback
        (auto-injected when `/` is omitted). It keeps a homepage route VISIBLE in
        the file (new users / zAgents expect one) while carrying zero duplicated
        config: zVaFolder/zVaFile/zBlock come from zSpark, and it fans its blocks
        out like the default walker (auto_discover_blocks). Downstream sees a plain
        zWalker, so routing/discovery/dispatch are untouched.
        """
        routes = merged_data.get("routes", {})
        if not isinstance(routes, dict):
            return
        spark = self._spark_walker()
        for path, cfg in routes.items():
            if not isinstance(cfg, dict) or cfg.get("type") != "zSpark":
                continue
            cfg["type"] = "zWalker"
            cfg["_zspark_default"] = True
            cfg.setdefault("auto_discover_blocks", True)
            for key in ("zVaFolder", "zVaFile", "zBlock"):
                if not cfg.get(key) and spark.get(key):
                    cfg[key] = spark[key]
            self.logger.framework.debug(
                f"[zServer] zSpark route '{path}' → zWalker "
                f"(folder={cfg.get('zVaFolder')}, file={cfg.get('zVaFile')}, block={cfg.get('zBlock')})"
            )

    def _apply_routing_meta(self, merged_data: dict) -> None:
        """
        Apply file-wide smart-routing directives from raw meta to merged routes.

        - zVaFolder: default walker folder → injected into any zWalker/zLoom route
          that doesn't name its own, so routes need only declare their zVaFile.

        NOTE: the legacy `zRouting` meta toggle was removed (2026-06). Folder
        discovery (auto_discover_blocks) is already enabled by the `type: zSpark`
        anchor (_normalize_zspark_routes) and by the implicit `/` fallback, so
        zRouting only ever re-set a flag that was already set. To force discovery on
        a bare `type: zWalker` default route, declare `auto_discover_blocks: true`
        on that route (or use `type: zSpark`).
        """
        routes = merged_data.get("routes", {})
        meta = merged_data.get("meta", {}) or {}
        # zVaFolder default: meta wins, else the zSpark's folder — so a route file
        # need not declare zVaFolder at all (the spark already names it, SSOT).
        # Read from the already-parsed meta (zParser preserves it) — never re-read disk.
        default_zvafolder = meta.get("zVaFolder") or self._spark_walker().get("zVaFolder")

        if default_zvafolder:
            for cfg in routes.values():
                if isinstance(cfg, dict) and "zVaFolder" not in cfg and cfg.get("type") in ("zWalker", "zLoom"):
                    cfg["zVaFolder"] = default_zvafolder

    def get_router(self):
        """
        Get the initialized HTTPRouter instance.
        
        Returns:
            HTTPRouter or None: The router instance if routes were loaded
        """
        return self.router

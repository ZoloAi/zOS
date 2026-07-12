# zOS/core/L4_Orchestration/r_zServer/zServer_modules/core/mount_manager.py

"""
MountManager - Unified mount management for zServer

Handles ALL file serving mounts (default and custom):
- Default mounts: /static/, /templates/, /zViews/ (FOLDER_UI)
- Custom mounts: /plugins/, user-defined mounts
- Single source of truth for URL → filesystem path mapping

Note: Bifrost client mounting removed - use manual ZSERVER_MOUNTS in zEnv
      for Development, or CDN for Production.
"""

from zOS import os, Dict, Optional, Tuple

from ..utils.zserver_constants import (
    MOUNT_PLUGINS,
    FOLDER_PLUGINS,
    MOUNT_STYLES,
    FOLDER_STYLES,
    FOLDER_STATIC,
    FOLDER_TEMPLATES,
    FOLDER_UI,
    MOUNT_UI,
)


class MountManager:
    """
    Manages all file serving mounts for zServer (SSOT for mount logic).
    
    Consolidates default mounts (static, templates, UI) and custom mounts
    into a unified registry with consistent query interface.
    """

    # Default-mount prefixes that custom config mounts may NOT override.
    # /zsyntax/ is reserved as a PREFIX (the actual mount key is versioned,
    # e.g. /zsyntax/1.2.0/), so the refusal check below also rejects any
    # custom mount that starts with it.
    RESERVED_MOUNTS = ("/static/", "/templates/", MOUNT_UI, "/zsyntax/")

    def __init__(self, serve_path, static_mounts, logger):
        """
        Initialize MountManager with default and custom mounts.
        
        Args:
            serve_path: Directory being served
            static_mounts: Initial custom mounts dict from config
            logger: zOS logger instance
        """
        self.serve_path = serve_path
        self.logger = logger
        
        # Initialize unified mount registry with default mounts
        self.mounts = {}
        
        # Add default mounts (URL prefix → filesystem path)
        self._add_default_mount("/static/", FOLDER_STATIC)
        self._add_default_mount("/templates/", FOLDER_TEMPLATES)
        self._add_default_mount(MOUNT_UI, FOLDER_UI)

        # Merge custom mounts from config. Keys arrive ALREADY normalized to the
        # canonical `/…/` URL prefix (bare `downloads` → `/downloads/`) — that is
        # config_http_server._parse_static_mounts' job (the SSOT for mount-key shape);
        # we do NOT re-normalize here. Declared values are zPaths (e.g. `@.files`) or
        # absolute paths; resolve them HERE against serve_path (== the app root zSpace)
        # so every mount — default and custom — shares ONE anchor (SSOT via zOS.zPath).
        # SECURITY: a custom mount must NOT repoint a reserved default prefix
        # (/static/, /templates/, /zViews/) at an arbitrary root — that would let config
        # silently override the app's trusted asset roots; reserved prefixes are refused
        # (and logged). Because keys are pre-normalized, a bare `static` arrives as
        # `/static/` and is correctly caught here.
        if static_mounts:
            from zOS.zPath import resolve_folder
            for url_prefix, fs_path in static_mounts.items():
                if url_prefix in self.RESERVED_MOUNTS or url_prefix.startswith("/zsyntax/"):
                    self.logger.warning(
                        f"[MountManager] Refused custom mount on reserved prefix "
                        f"'{url_prefix}' → {fs_path} (defaults are protected)"
                    )
                    continue
                resolved = resolve_folder(fs_path, self.serve_path)
                if not os.path.isdir(resolved):
                    self.logger.warning(
                        f"[MountManager] Mount path does not exist: {fs_path} → {resolved} "
                        "(will 404 until created)"
                    )
                self.mounts[url_prefix] = resolved
                self.logger.info(f"[MountManager] Custom mount: {url_prefix} → {resolved}")
    
    def _add_default_mount(self, url_prefix: str, folder_name: str):
        """
        Add a default mount (relative to serve_path).
        
        Args:
            url_prefix: URL prefix (e.g., "/static/")
            folder_name: Folder name relative to serve_path (e.g., "static")
        """
        fs_path = os.path.join(self.serve_path, folder_name)
        self.mounts[url_prefix] = fs_path
        self.logger.debug(f"[MountManager] Default mount: {url_prefix} → {fs_path}")

    def auto_mount_styles(self):
        """
        Auto-mount styles folder for per-page CSS access.

        This enables zCanvas auto-injection and zBrush metadata to reference stylesheets via /styles/name.css

        Anchored on serve_path (== the app root zSpace, the SSOT) — no cwd / hardcoded
        "zCloud" fallbacks, which were drift from before serve_path resolved to zSpace.
        """
        if MOUNT_STYLES in self.mounts:
            return  # Already mounted

        style_path = os.path.join(self.serve_path, FOLDER_STYLES)
        if os.path.isdir(style_path):
            self.mounts[MOUNT_STYLES] = style_path
            self.logger.info(f"[MountManager] Auto-mounted styles: {MOUNT_STYLES} → {style_path}")

    def auto_mount_plugins(self):
        """
        Auto-mount plugins folder for JavaScript plugin access.

        This enables _zScripts metadata to reference plugins via /plugins/plugin_name.js

        Anchored on serve_path (== the app root zSpace, the SSOT) — no cwd / hardcoded
        "zCloud" fallbacks, which were drift from before serve_path resolved to zSpace.
        """
        if MOUNT_PLUGINS in self.mounts:
            return  # Already mounted

        plugin_path = os.path.join(self.serve_path, FOLDER_PLUGINS)
        if os.path.isdir(plugin_path):
            self.mounts[MOUNT_PLUGINS] = plugin_path
            self.logger.info(f"[MountManager] Auto-mounted plugins: {MOUNT_PLUGINS} → {plugin_path}")

    def auto_mount_zsyntax(self):
        """Mount the zolo-lsp Prism syntax bundle at its versioned route.

        The bundle is package data inside the installed zolo-lsp (SSOT: the
        grammar the browser highlights with == the parser the engine runs).
        zSys.zsyntax_bundle owns the URL/dir resolution — the SAME module
        html_injectors reads to announce `syntaxBase` in zui-config, so the
        mount and the announcement cannot disagree. No-op (no mount, no log
        noise beyond debug) when the installed zolo-lsp predates the bundle.
        """
        from zSys.zsyntax_bundle import zsyntax_base, zsyntax_dir  # pylint: disable=import-outside-toplevel

        base, bundle_dir = zsyntax_base(), zsyntax_dir()
        if not base or not bundle_dir:
            self.logger.debug(
                "[MountManager] zsyntax not mounted (zolo-lsp lacks bifrost_prism_dir)"
            )
            return
        if base in self.mounts:
            return  # Already mounted
        self.mounts[base] = str(bundle_dir)
        self.logger.info(f"[MountManager] Auto-mounted zsyntax: {base} → {bundle_dir}")

    def get_mount_for_path(self, url_path: str) -> Optional[Tuple[str, str]]:
        """
        Get mount information for a URL path.
        
        Args:
            url_path: URL path to check (e.g., "/static/style.css")
        
        Returns:
            Tuple of (url_prefix, fs_path) if mounted, None otherwise
            Example: ("/static/", "/path/to/serve/static")
        """
        # Longest prefix wins (deterministic): with overlapping prefixes like
        # "/a/" and "/api/", dict iteration order would otherwise decide the match.
        for url_prefix in sorted(self.mounts, key=len, reverse=True):
            if url_path.startswith(url_prefix):
                return (url_prefix, self.mounts[url_prefix])
        return None
    
    def get_folder_path(self, mount_type: str) -> str:
        """
        Get filesystem path for a mount type (for template rendering, etc.).
        
        Args:
            mount_type: Mount type ("static", "templates", "UI")
        
        Returns:
            str: Full filesystem path
        
        Raises:
            KeyError: If mount type not found
        """
        # The URL prefix segment IS the folder name (SSOT) — e.g. logical type
        # "UI" → folder "zViews" → prefix "/zViews/". Resolve through
        # get_folder_name so a renamed FOLDER_UI never desyncs this lookup.
        url_prefix = f"/{self.get_folder_name(mount_type)}/"
        if url_prefix in self.mounts:
            return self.mounts[url_prefix]
        raise KeyError(f"Mount type '{mount_type}' not found in registry")
    
    def get_folder_name(self, mount_type: str) -> str:
        """
        Get folder name for a mount type (for backward compatibility).
        
        Args:
            mount_type: Mount type ("static", "templates", "UI")
        
        Returns:
            str: Folder name (e.g., "static", "templates", "UI")
        """
        # Map mount types to folder names
        folder_map = {
            "static": FOLDER_STATIC,
            "templates": FOLDER_TEMPLATES,
            "UI": FOLDER_UI
        }
        return folder_map.get(mount_type, mount_type)
    
    def get_all_mounts(self) -> Dict[str, str]:
        """
        Get complete mount registry.
        
        Returns:
            dict: Complete mounts mapping (URL prefix -> filesystem path)
        """
        return self.mounts.copy()
    
    def get_static_mounts(self) -> dict:
        """
        Get static mounts registry (backward compatibility).
        
        Returns:
            dict: Static mounts mapping (URL prefix -> filesystem path)
        """
        return self.mounts

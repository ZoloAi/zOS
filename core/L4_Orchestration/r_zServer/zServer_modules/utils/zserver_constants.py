# zOS/core/L4_Orchestration/r_zServer/zServer_modules/utils/zserver_constants.py

"""
zServer Constants - Centralized configuration values

All magic strings, folder names, URL prefixes, and file patterns used
throughout zServer subsystem. Modify here to change conventions globally.
"""

# ============================================================================
# Folder Conventions
# ============================================================================

FOLDER_STATIC = "static"
"""Default folder for static files (CSS, JS, images)."""

FOLDER_TEMPLATES = "templates"
"""Default folder for Jinja2 templates."""

FOLDER_UI = "zViews"
"""Default folder for zUI zVaF files."""

FOLDER_MODELS = "models"
"""Default folder for zSchema files (auto-initialized on startup)."""

FOLDER_ROUTES = "routes"
"""Default subfolder for modular route blueprints."""

FOLDER_PLUGINS = "plugins"
"""Default folder for JavaScript plugins."""

FOLDER_STYLES = "styles"
"""Default folder for per-page CSS stylesheets."""

FOLDER_BIFROST = "bifrost"
"""Default folder name for bifrost client files."""

# ============================================================================
# URL Mount Prefixes
# ============================================================================

MOUNT_BIFROST = "/bifrost/"
"""URL prefix for bifrost client files."""

MOUNT_PLUGINS = "/plugins/"
"""URL prefix for JavaScript plugins."""

MOUNT_STYLES = "/styles/"
"""URL prefix for per-page CSS stylesheets."""

MOUNT_ZTHEME = "/ztheme/"
"""URL prefix for zTheme CSS framework."""

MOUNT_UI = f"/{FOLDER_UI}/"
"""URL prefix for zUI zVaF files (derived from FOLDER_UI — SSOT)."""

# ============================================================================
# Reserved Endpoints
# ============================================================================

# Reserved readiness endpoint (intercepted before routing/RBAC). Returns 200 only
# once the routing table is built and the server can actually serve — a deeper signal
# than a TCP port being open. SSOT lives in the SDK (zos_plugin.drivers) because the
# probers live there (driver wake, blue-green coordinator, prod ingress/k8s probe);
# zServer imports it here to register the served route. Never user-routable.
from zos_plugin import READINESS_PATH as HEALTH_PATH  # noqa: E402,F401  pylint: disable=unused-import

# ============================================================================
# File Patterns (glob-style)
# ============================================================================

PATTERN_ROUTE_FILES = ["zServer.*.zolo", "zServer.*.yaml", "zServer.*.json"]
"""File patterns for auto-detected route files. Supports .zolo, .yaml, .json formats (priority order)."""

PATTERN_SCHEMA_FILES = ["**/zSchema.*.zolo", "**/zSchema.*.yaml", "**/zSchema.*.json"]
"""File patterns for auto-detected schema files. Supports .zolo, .yaml, .json formats (priority order). Recurses into subdirectories."""

# ============================================================================
# Deployment Modes
# ============================================================================

MODE_DEVELOPMENT = "Development"
"""Development mode - uses http.server in background thread."""

MODE_TESTING = "Testing"
"""Testing mode - same as Development but with test-specific config."""

MODE_PRODUCTION = "Production"
"""Production mode - uses Waitress (in-process, cross-platform)."""

# ============================================================================
# Network Defaults
# ============================================================================
#
# REMOVED: DEFAULT_HOST / DEFAULT_PORT. Network defaults have ONE home —
# config_http_server (a_zConfig). These were unused copies that drifted out of
# sight ("keep in sync manually" is not SSOT). Read host/port from the resolved
# HttpServerConfig (mirrored onto ConfigManager), never from a constants twin.

# ============================================================================
# WSGI Configuration
# ============================================================================

# Static WSGI entry-point convention (Flask/Django-style). EXTERNAL hosts import
# `app` from this module to bind the socket themselves:
#     waitress-serve --port=9090 wsgi:app
#     uwsgi --module wsgi:app
# The module exposes zServer.get_wsgi_app() (full pipeline: security + RBAC + routes).
# zOS no longer GENERATES a throwaway module — the app ships a real wsgi.py.
# NOTE: zOS's own runners (dev/waitress) serve in-process; this is only for
# external/self-managed WSGI hosts.
WSGI_ENTRY_MODULE = "wsgi"
"""Static WSGI entry module name (without .py) — imported as `wsgi:app`."""

# ============================================================================
# Bifrost Configuration (Manual Only - No Auto-Mounting)
# ============================================================================

# Note: Bifrost auto-mounting removed. Configure via ZSERVER_MOUNTS in zEnv:
#   Development: ZSERVER_MOUNTS: {"/bifrost/": "/path/to/zOS/bifrost/"}
#   Production: Use CDN in templates
#
# BIFROST_SEARCH_PATHS = [
#     "{zos_root}/bifrost",  # Standard location: zOS/bifrost/
#     "{cwd}/bifrost"        # Fallback location: {cwd}/bifrost
# ]

# ============================================================================
# Plugin / Styles Auto-Mount Locations
# ============================================================================
#
# REMOVED: PLUGIN_SEARCH_PATHS / STYLES_SEARCH_PATHS. They were never read —
# MountManager.auto_mount_plugins / auto_mount_styles build their own
# {serve_path}/zCloud/cwd lists inline. Those inline lists are the single source;
# these template copies only invited drift.

# ============================================================================
# Hot Reload — Console Receipt (mirrors the graceful-shutdown goodbye)
# ============================================================================
#
# A soft reload re-scans zViews/routes/zAPIs + busts the parsed-file cache WITHOUT
# touching the socket, the WS bridge, or live sessions. The receipt mirrors the
# shutdown prints so "turn it off" and "reload it" read as one family. Status
# glyphs are reused from zSys.shutdown (SSOT — one success/fail symbol).

RELOAD_PRINT_INITIATED = "\nzCLI: Reloading zServer (app)..."
"""First line of the reload receipt (stdout)."""

RELOAD_PRINT_ROUTES = "   {ok} Re-scanned zViews/ → {n} routes"
"""Routes re-scanned line (format with ok=glyph, n=route count)."""

RELOAD_PRINT_ZAPIS = "   {ok} Re-scanned zAPIs → {n} endpoints"
"""zAPI re-scan line (format with ok=glyph, n=endpoint count)."""

RELOAD_PRINT_CACHE = "   {ok} Cleared parsed-file cache"
"""Loader cache-bust line (format with ok=glyph)."""

RELOAD_PRINT_SESSIONS = "   {ok} Live sessions preserved — connections held"
"""Continuity line (format with ok=glyph)."""

RELOAD_PRINT_COMPLETE = "{ok} Reload complete — no downtime\n"
"""Final success line (format with ok=glyph)."""

RELOAD_PRINT_ABORTED = "   {fail} {detail} — keeping previous routes live"
"""Fail-safe abort detail (format with fail=glyph, detail=reason)."""

RELOAD_PRINT_ABORTED_TAIL = "{warn} Reload aborted — site unchanged, still serving\n"
"""Fail-safe abort tail (format with warn=glyph)."""

RELOAD_WARN_GLYPH = "[!]"
"""Warning glyph for the abort tail (matches the shutdown family)."""

# Logger messages (framework/info)
RELOAD_LOG_START = "[zServer] Hot reload requested"
RELOAD_LOG_DONE = "[zServer] Hot reload complete — %d routes, %d zAPIs"
RELOAD_LOG_ABORTED = "[zServer] Hot reload aborted (kept previous routes): %s"
RELOAD_LOG_NOT_RUNNING = "[zServer] Reload requested but server is not running — ignored"
RELOAD_LOG_IN_PROGRESS = "[zServer] Reload already in progress — ignored"

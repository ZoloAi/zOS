# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/config_constants.py
"""
Centralized constants for zConfig subsystem.

This module contains all public constants used throughout the zCLI framework
for session management, authentication, caching, and configuration.

Cross-subsystem protocol vocabulary (run modes, the session-dict schema) is
single-sourced in the root ``zVocabulary`` module and re-exported here so
existing ``from ...config_constants import SESSION_KEY_*`` call sites keep
working unchanged. Subsystem-internal values (machine prefs, config filenames,
zSpark/zAuth/zCache/wizard keys) remain defined locally below.
"""

# Canonical cross-subsystem vocabulary (root SSOT). Imported via the submodule
# path so this module stays import-safe during zOS package initialization.
from zOS.zVocabulary import (
    # zMode values
    ZMODE_ZCLI,
    ZMODE_ZBIFROST,
    ZMODE_WEB,
    # Session dictionary keys
    SESSION_KEY_ZS_ID,
    SESSION_KEY_TITLE,
    SESSION_KEY_ZSPACE,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    SESSION_KEY_ZMODE,
    SESSION_KEY_ZLOGGER,
    SESSION_KEY_LOGGER_PATH,
    SESSION_KEY_ZPAGINATE,
    SESSION_KEY_ZMACHINE,
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZCACHE,
    SESSION_KEY_WIZARD_MODE,
    SESSION_KEY_ZSPARK,
    SESSION_KEY_VIRTUAL_ENV,
    SESSION_KEY_SYSTEM_ENV,
    SESSION_KEY_LOGGER_INSTANCE,
    SESSION_KEY_ZVARS,
    SESSION_KEY_ZSHORTCUTS,
    SESSION_KEY_BROWSER,
    SESSION_KEY_IDE,
    SESSION_KEY_SESSION_HASH,
    SESSION_KEY_ZORIGIN,
)

# ============================================================
# Application Identity
# ============================================================

APP_NAME = "zOS"
APP_AUTHOR = "zolo"
DOTENV_FILENAME = ".zEnv"

# ============================================================
# Machine Config — user-editable preference keys (SSOT)
# ============================================================
# The ONLY machine keys a user may override / that get persisted to
# zConfig.machine.zolo. Everything else (os, hostname, MAC, IP, username,
# cpu/memory totals, …) is auto-detected fresh each boot and NEVER written to
# disk — keeping the on-disk file a small prefs file, not a machine fingerprint.
# Consumed by config_persistence (validation) and config_machine (prefs-only write).
EDITABLE_MACHINE_KEYS = (
    # User tool preferences
    "browser", "ide", "terminal", "shell",
    "image_viewer", "video_player", "audio_player",
    # Terminal capability override (emoji output gate SSOT)
    "supports_emoji",
    # Time/date preferences
    "time_format", "date_format", "datetime_format",
    # Resource allocation limits (optional)
    "cpu_cores_limit", "memory_gb_limit",
)

# ============================================================
# zMode Values  →  re-exported from zVocabulary (root SSOT)
# ============================================================
# ZMODE_ZCLI, ZMODE_ZBIFROST imported at top of module.

# ============================================================
# Action Routing
# ============================================================

ACTION_PLACEHOLDER = "#"  # No-op action for development/testing

# ============================================================
# Session Dictionary Keys  →  re-exported from zVocabulary (root SSOT)
# ============================================================
# The SESSION_KEY_* family is single-sourced in zOS.zVocabulary and imported at
# the top of this module. They remain importable from here for back-compat.

# ============================================================
# zSpark Configuration Keys
# ============================================================
# Keys for zSpark boot configuration

ZSPARK_KEY_TITLE = "title"   # display name AND machine identity (SSOT: resolve_app_id slugs it)
ZSPARK_KEY_ZAPP = "zApp"     # deprecated optional override for app identity → derives from title
ZSPARK_KEY_ZSPACE = "zSpace"
ZSPARK_KEY_ZVAFOLDER = "zVaFolder"
ZSPARK_KEY_ZVAFILE = "zVaFile"
ZSPARK_KEY_ZBLOCK = "zBlock"
# zPaginate: zSpark toggle for zData table pagination-pause (default off). Honest
# rename of the former "zTraceback" flag, whose excepthook feature was retired.
ZSPARK_KEY_ZPAGINATE = "zPaginate"
ZSPARK_KEY_ZMODE = "zMode"
ZSPARK_KEY_ZSERVER = "zServer"   # HTTP serving block (host/port/enabled/type/mounts…) — SSOT: config_http_server
ZSPARK_KEY_ZSOCKET = "zSocket"   # WebSocket serving block (host/port/…) the zBifrost bridge rides on — SSOT: config_websocket
ZSPARK_KEY_ZSOCKET_LEGACY = "websocket"  # deprecated alias → use zSocket
ZSPARK_KEY_ZENV   = "zEnv"    # canonical (v1.6+)
ZSPARK_KEY_ZLOG   = "zLog"    # canonical (v1.6+)
ZSPARK_KEY_ZSTATE = "zState"  # deprecated → use zEnv
ZSPARK_KEY_LOGGER = "zScrap"  # deprecated → use zLog
ZSPARK_KEY_LOGGER_PATH = "zLogPath"
ZSPARK_KEY_LOGGER_PATH_ALIAS = "zScrapath"  # deprecated → use zLogPath

# ============================================================
# zAuth Keys — single signed-in identity (zVisitor)
# ============================================================
# One zOS instance = one app = one signed-in caller. The authenticated identity
# is the flat dict at session[SESSION_KEY_ZVISITOR] (root, sibling of zCrumbs).
# These are the fields of that dict:
ZAUTH_KEY_AUTHENTICATED = "authenticated"
ZAUTH_KEY_ID = "id"
ZAUTH_KEY_USERNAME = "username"
ZAUTH_KEY_ROLE = "role"
ZAUTH_KEY_API_KEY = "api_key"

# DEPRECATED multi-app machinery — no longer part of the live session shape.
# Kept defined only so the (now degenerate, single-identity) delegate API stays
# import-safe; full removal is the deferred "applications" cleanup run.
ZAUTH_KEY_APPLICATIONS = "applications"
ZAUTH_KEY_ACTIVE_APP = "active_app"
ZAUTH_KEY_ACTIVE_CONTEXT = "active_context"
ZAUTH_KEY_DUAL_MODE = "dual_mode"
CONTEXT_ZSESSION = "zSession"
CONTEXT_APPLICATION = "application"
CONTEXT_DUAL = "dual"

# ============================================================
# zCache Keys
# ============================================================

ZCACHE_KEY_SYSTEM = "system_cache"
ZCACHE_KEY_PINNED = "pinned_cache"
ZCACHE_KEY_SCHEMA = "schema_cache"
ZCACHE_KEY_PLUGIN = "plugin_cache"

# ============================================================
# Wizard Mode Keys
# ============================================================

WIZARD_KEY_ACTIVE = "active"
WIZARD_KEY_LINES = "lines"
WIZARD_KEY_FORMAT = "format"
WIZARD_KEY_TRANSACTION = "transaction"

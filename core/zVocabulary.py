# zOS/core/zVocabulary.py
"""
zVocabulary — Root SSOT for cross-subsystem protocol vocabulary.

This module is the single source of truth for the string literals that form
zOS's *shared protocol*: the keys, identifiers, and atoms that more than one
subsystem must agree on by definition (session-dict schema, run modes, file
extensions). Subsystems draw these names from here instead of re-declaring
them, so the vocabulary cannot drift and agents have one place to look.

Design contract (do not break)
-------------------------------
- **Dependency-free leaf.** This module imports NOTHING from the ``zOS``
  package. That keeps it importable at any point during package
  initialization without risking a circular import.
- **Consume by submodule path in L1.** Foundation modules that load during
  ``zOS`` boot should import via the submodule path::

      from zOS.zVocabulary import SESSION_KEY_ZVAFILE

  which is safe even while ``zOS/__init__`` is still executing. Later layers
  (L2+) and plugins may use the convenience aggregator re-export::

      from zOS import SESSION_KEY_ZVAFILE

- **Bar is high.** Only *genuine cross-subsystem protocol* belongs here.
  Log messages, colors, error text, and subsystem-internal keys stay local
  to their subsystem. Vocabulary owned by a single subsystem is added only
  when layering forces a shared home (e.g. an L1 module needs a value that
  is conceptually owned by an L2 subsystem).

Migration note
--------------
Existing subsystem constants keep their names and become thin aliases that
re-export from here (e.g. ``loader_constants.SESSION_KEY_VAFILE`` and parser
``file_constants.SESSION_KEY_ZVAFILE`` both resolve to the canonical name
below). No call sites break during migration.
"""

# ============================================================================
# zMODE VALUES  (run mode — output stack selection)
# ============================================================================
# Used across zConfig, zDisplay, zBifrost, zDispatch to branch on run mode.

ZMODE_ZCLI: str = "zCLI"
ZMODE_ZBIFROST: str = "zBifrost"
ZMODE_WEB: str = "Web"

# ============================================================================
# SESSION DICTIONARY KEYS  (the canonical session-state schema)
# ============================================================================
# Keys for reading/writing session state. This is the contract nearly every
# subsystem touches; it is the highest-value shared vocabulary in zOS.

SESSION_KEY_ZS_ID: str = "zS_id"
SESSION_KEY_TITLE: str = "title"
SESSION_KEY_ZSPACE: str = "zSpace"
SESSION_KEY_ZVAFOLDER: str = "zVaFolder"
SESSION_KEY_ZVAFILE: str = "zVaFile"
SESSION_KEY_ZBLOCK: str = "zBlock"
SESSION_KEY_ZMODE: str = "zMode"
SESSION_KEY_ZLOGGER: str = "zLogger"
SESSION_KEY_LOGGER_PATH: str = "zLogPath"
SESSION_KEY_ZPAGINATE: str = "zPaginate"
SESSION_KEY_ZMACHINE: str = "zMachine"
# Single authenticated caller identity ("flask-like" session), root-level sibling
# of zCrumbs. One zOS instance = one app = one signed-in zVisitor (no multi-app).
SESSION_KEY_ZVISITOR: str = "zVisitor"
SESSION_KEY_ZCRUMBS: str = "zCrumbs"
SESSION_KEY_ZCACHE: str = "zCache"
SESSION_KEY_WIZARD_MODE: str = "wizard_mode"
SESSION_KEY_ZSPARK: str = "zSpark"
SESSION_KEY_VIRTUAL_ENV: str = "virtual_env"
SESSION_KEY_SYSTEM_ENV: str = "system_env"
SESSION_KEY_LOGGER_INSTANCE: str = "logger_instance"
SESSION_KEY_ZVARS: str = "zVars"
# zRoute — request-scoped store for dynamic-route params (/users/%username →
# {username: alice}), OWNED by zLoom (RouteOps) and read as the %route.* token.
# Deliberately separate from zVars (durable user vars) so a URL segment can never
# collide with or go stale against a user-set variable — see the zVar-route
# decoupling memo. zServer only FEEDS this via zos.zloom.set_route_params().
SESSION_KEY_ZROUTE: str = "zRoute"
SESSION_KEY_ZSHORTCUTS: str = "zShortcuts"
SESSION_KEY_BROWSER: str = "browser"
SESSION_KEY_IDE: str = "ide"
SESSION_KEY_SESSION_HASH: str = "session_hash"  # frontend cache invalidation (v1.6.0)
# zOrigin — the *true* transport that spawned this session, independent of
# zMode. A zTerminal swap-run emulates zMode: zCLI (so display renders to
# stdout) but is really driven by a remote Bifrost client; the swap stamps
# zOrigin: zBifrost so local-machine gates (zOpen) judge by origin, not the
# emulated mode. Absent/None ⇒ genuine local boot (treated as zCLI). Values
# reuse the ZMODE_* atoms above.
SESSION_KEY_ZORIGIN: str = "zOrigin"

# ============================================================================
# FILE EXTENSION ATOMS  (single-sourced extension literals)
# ============================================================================
# The atomic extension strings. Subsystems compose their own priority lists
# (e.g. zEnv's ZENV_EXTENSIONS, parser's ZVAFILE_EXTENSIONS) from these atoms
# so the literals never drift across zConfig / zParser / zLoader / zFunc.

FILE_EXT_ZOLO: str = ".zolo"
FILE_EXT_JSON: str = ".json"
FILE_EXT_YAML: str = ".yaml"
FILE_EXT_YML: str = ".yml"
FILE_EXT_PY: str = ".py"
FILE_EXT_JS: str = ".js"
FILE_EXT_SH: str = ".sh"
FILE_EXT_MD: str = ".md"
FILE_EXT_TXT: str = ".txt"
FILE_EXT_XML: str = ".xml"
FILE_EXT_HTML: str = ".html"
FILE_EXT_CSS: str = ".css"

# ============================================================================
# FILE TYPE IDENTIFIERS  (zVaFile subtype names)
# ============================================================================
# Canonical subtype ids shared by zLoader (detection/caching) and zParser
# (classification). The value already carries the `z`, so the names omit it
# (FILE_TYPE_UI, not FILE_TYPE_ZUI) — parser's older FILE_TYPE_Z* names alias
# to these.

FILE_TYPE_UI: str = "zUI"
FILE_TYPE_SCHEMA: str = "zSchema"
FILE_TYPE_CONFIG: str = "zConfig"
FILE_TYPE_ZVAFILE: str = "zVaFile"
FILE_TYPE_ZOTHER: str = "zOther"

# ============================================================================
# PATH SYMBOLS  (zPath addressing)
# ============================================================================
# The leading symbols that select a path's resolution base. Used by zLoader,
# zParser, and every zPath consumer.

PATH_SYMBOL_AT: str = "@"      # workspace-relative
PATH_SYMBOL_TILDE: str = "~"   # absolute / home
PATH_SEP_DOT: str = "."        # zPath segment separator (dotted addressing)

# ============================================================================
# ZPATH REFERENCE KEYS  (event-scoped zPath contract — SSOT)
# ============================================================================
# zPath resolution is EVENT-SCOPED, not value-scoped. A value is only treated
# as a zPath when it sits under one of these declared reference-bearing keys.
# Every other property is string-first: its value is never path-resolved, so a
# literal like `suffix: @company.com` or `prompt: ask @handle` stays verbatim.
#
# This is the SSOT that keeps zOS from contradicting its own string-first law.
# Resolvers (zParser.resolve_data_path, link/nav, dialog/auth `model`, transfer,
# media `src`) MUST gate on this set — never scan arbitrary values for `@`/`~`.
# New events that accept a zPath declare their key here; nothing else resolves.
# Lives in zVocabulary (dependency-free atoms) so zOS *and* zGuard share it.
ZPATH_REFERENCE_KEYS: frozenset = frozenset({
    "href",        # links / zURL navigation targets
    "zLink",       # link target alias
    "target",      # explicit navigation target
    "src",         # media sources (zImage / zVideo / zAudio)
    "poster",      # zVideo poster still (a second media asset, like src)
    "model",       # zData / zDialog / zAuth schema references
    "schema",      # explicit schema references (routing)
    "folder",      # navigation folder context
    "zVaFolder",   # walker / navigation folder targets
    "zVaFile",     # walker / navigation file targets
    "_navigate",   # zVar immediate-navigation target
    "path",        # transfer source/target file paths
    "source",      # transfer source paths
    "serve_path",  # zServer mount / serve roots
})

# ============================================================================
# ZMACHINE PREFIXES  (zMachine address forms)
# ============================================================================
# Prefix forms that mark a path as zMachine-scoped. Shared by zLoader and
# zParser path resolution.

ZMACHINE_PREFIX: str = "zMachine."         # short form
ZMACHINE_PREFIX_LONG: str = "~.zMachine."  # tilde-qualified form

# ============================================================================
# CONTROL-FLOW RETURN VALUES  (interactive handler result signals)
# ============================================================================
# Signals returned by interactive handlers (zNavigation, zOpen) to the walker /
# dispatch layer to steer control flow. Shared so the contract cannot drift:
# zNavigation aliases these as NAV_ZBACK / STATUS_STOP, zOpen as
# RETURN_ZBACK / RETURN_STOP.

CONTROL_RETURN_ZBACK: str = "zBack"  # success — return to previous screen
CONTROL_RETURN_STOP: str = "stop"    # failure / halt — stop execution

# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    # zMode values
    "ZMODE_ZCLI",
    "ZMODE_ZBIFROST",
    "ZMODE_WEB",
    # Session dictionary keys
    "SESSION_KEY_ZS_ID",
    "SESSION_KEY_TITLE",
    "SESSION_KEY_ZSPACE",
    "SESSION_KEY_ZVAFOLDER",
    "SESSION_KEY_ZVAFILE",
    "SESSION_KEY_ZBLOCK",
    "SESSION_KEY_ZMODE",
    "SESSION_KEY_ZLOGGER",
    "SESSION_KEY_LOGGER_PATH",
    "SESSION_KEY_ZPAGINATE",
    "SESSION_KEY_ZMACHINE",
    "SESSION_KEY_ZVISITOR",
    "SESSION_KEY_ZCRUMBS",
    "SESSION_KEY_ZCACHE",
    "SESSION_KEY_WIZARD_MODE",
    "SESSION_KEY_ZSPARK",
    "SESSION_KEY_VIRTUAL_ENV",
    "SESSION_KEY_SYSTEM_ENV",
    "SESSION_KEY_LOGGER_INSTANCE",
    "SESSION_KEY_ZVARS",
    "SESSION_KEY_ZSHORTCUTS",
    "SESSION_KEY_BROWSER",
    "SESSION_KEY_IDE",
    "SESSION_KEY_SESSION_HASH",
    "SESSION_KEY_ZORIGIN",
    # File extension atoms
    "FILE_EXT_ZOLO",
    "FILE_EXT_JSON",
    "FILE_EXT_YAML",
    "FILE_EXT_YML",
    "FILE_EXT_PY",
    "FILE_EXT_JS",
    "FILE_EXT_SH",
    "FILE_EXT_MD",
    "FILE_EXT_TXT",
    "FILE_EXT_XML",
    "FILE_EXT_HTML",
    "FILE_EXT_CSS",
    # File type identifiers
    "FILE_TYPE_UI",
    "FILE_TYPE_SCHEMA",
    "FILE_TYPE_CONFIG",
    "FILE_TYPE_ZVAFILE",
    "FILE_TYPE_ZOTHER",
    # Path symbols
    "PATH_SYMBOL_AT",
    "PATH_SYMBOL_TILDE",
    "PATH_SEP_DOT",
    # zMachine prefixes
    "ZMACHINE_PREFIX",
    "ZMACHINE_PREFIX_LONG",
    # Control-flow return values
    "CONTROL_RETURN_ZBACK",
    "CONTROL_RETURN_STOP",
]

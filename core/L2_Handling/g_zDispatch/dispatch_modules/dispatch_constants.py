"""
Dispatch Constants - Centralized constants for zDispatch subsystem

This module provides all constants used across the zDispatch subsystem,
including command prefixes, dict keys, modifiers, labels, log messages,
mode values, and configuration defaults.

Organization:
    - Subsystem Identity
    - Command Prefixes & Dict Keys
    - Modifiers (^, ~, *, !)
    - Mode Values
    - Display Labels
    - Display Event Keys
    - Data Keys (Common dict keys)
    - Navigation
    - Plugins
    - Default Values
    - Styles & Indentation
    - Prompts & Input
    - Log Messages
    - Error Messages

Usage:
    from .dispatch_constants import (
        CMD_PREFIX_ZFUNC,
        KEY_ZFUNC,
        MOD_EXCLAMATION,
        MODE_BIFROST,
    )
"""

from zOS.zVocabulary import (
    ZMODE_ZCLI,
    ZMODE_ZBIFROST,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
)

# ==============================================================================
# SUBSYSTEM IDENTITY
# ==============================================================================

SUBSYSTEM_NAME = "zDispatch"
SUBSYSTEM_COLOR = "DISPATCH"

# Display Messages (INTERNAL - used only within zDispatch)
_MSG_READY = "zDispatch Ready"
_MSG_HANDLE = "handle zDispatch"

# ==============================================================================
# COMMAND PREFIXES (String Format - for parsing)
# ==============================================================================

CMD_PREFIX_ZFUNC = "zFunc("
CMD_PREFIX_ZLINK = "zLink("
# zAlpha — Greek-letter first-class name for the zLink event. The imperative
# wrapper is canonicalized to zLink( at the string router + resolver seams.
CMD_PREFIX_ZALPHA = "zAlpha("
CMD_PREFIX_ZOPEN = "zOpen("
CMD_PREFIX_ZWIZARD = "zWizard("
CMD_PREFIX_ZREAD = "zRead("

# ==============================================================================
# DICT KEYS - Subsystem Commands
# ==============================================================================

KEY_ZFUNC = "zFunc"
KEY_ZLINK = "zLink"
# zAlpha / zOmega — Greek-letter first-class names for the navigation event
# (zLink) and its in-block section property (zPsi). The originals stay permanent
# aliases; authored zAlpha keys are normalized to zLink at the dispatch seam so
# the internal nav-signal protocol ({"zLink": path}) and client stay one spelling.
KEY_ZALPHA = "zAlpha"
KEY_ZOMEGA = "zOmega"
KEY_ZDELTA = "zDelta"
# zMenu — the LONGHAND of the `*` key-modifier. A `Name*: [A, B]` shorthand is
# sugar for a `zMenu: {title, zAnchor, options}` block; the dict form spells the
# title/back-policy out and is the seam that dynamic (%data / &plugin) option
# sources hang off. Both forms funnel through the ONE engine (navigation.create).
KEY_ZMENU = "zMenu"
# zDelegate — first-class dual-mode "internal rewiring" event. A delegating
# carrier (e.g. a zBtn) rewires its activation to run another same-file block
# in place: routeless, AJAX-like (delta semantics), no breadcrumb push. It is a
# real dispatch verb both modes route through (CLI carrier harvest + Bifrost DOM
# click) — NOT presentation-only metadata (contrast the Bifrost-only _zDelegate).
KEY_ZDELEGATE = "zDelegate"
KEY_ZOPEN = "zOpen"
KEY_ZWIZARD = "zWizard"
KEY_ZREAD = "zRead"
KEY_ZDATA = "zData"
KEY_ZDIALOG = "zDialog"
KEY_ZDASH = "zDash"
KEY_ZFLAT = "zFlat"
KEY_ZDISPLAY = "zDisplay"
KEY_ZLOGIN = "zLogin"
KEY_ZLOGOUT = "zLogout"
KEY_ZEXPORT = "zExport"
KEY_ZIMPORT = "zImport"
KEY_ZTRANSFER = "zTransfer"
KEY_ZVAR = "zVar"
KEY_ZLIST = "zList"

# zProgress as an ACTION PROPERTY (not the standalone progress-bar UI element):
# when it sits BESIDE an action subsystem key (e.g. zFunc), it requests a live
# "zOS is processing this event" bar around that action's execution. Standalone
# `zProgress:` blocks (a bar on their own) still expand via the shorthand path.
KEY_ZPROGRESS = "zProgress"

# Action keys eligible for the zProgress journey wrapper. zFunc is the direct
# case; zBtn carries the longer (gated) journey when its action is a plugin call.
# Grows as we generalize the journey to other long-running events (zData, ...).
# zBtn has no KEY_ constant (shorthand element detected by literal name).
PROGRESS_ACTION_KEYS = frozenset({KEY_ZFUNC, "zBtn"})

# ==============================================================================
# EVENT-BINDING KEYS (declarative bindings — NEVER executed inline)  (SSOT)
# ==============================================================================
# These keys attach a handler (zAPI/zFunc/zData/zLink) to a sibling UI element.
# They are consumed declaratively — by the zAPI scanner at boot, by Bifrost
# enrichment (Bifrost stamps the resolved zapi_url onto the input), and
# by the client at interaction time. The dispatch/walker must treat them as
# INERT during render: never recurse into them, never execute their handler.
# (onSubmit lives inside zDialog/zForm, which are subsystem-routed and consume
#  it internally, so it never reaches the organizational walk in practice — it
#  is listed here for completeness / safety.)
EVENT_BINDING_KEYS = frozenset({
    "onChange", "onClick", "onSubmit", "onLoad",
    "onInput", "onFocus", "onBlur",
})

# ==============================================================================
# DICT KEYS - Context & Session
# ==============================================================================
# Note: Mode is now accessed via SESSION_KEY_ZMODE from zConfig (session-level)
# KEY_MODE removed - contexts should not contain mode (session is source of truth)

KEY_ZVAFILE = SESSION_KEY_ZVAFILE  # alias zVocabulary SSOT ("zVaFile")
KEY_ZBLOCK = SESSION_KEY_ZBLOCK    # alias zVocabulary SSOT ("zBlock")

# ==============================================================================
# DICT KEYS - Data Operations (zData integration)
# ==============================================================================

KEY_ACTION = "action"
KEY_MODEL = "model"
KEY_TABLE = "table"
KEY_TABLES = "tables"
KEY_FIELDS = "fields"
KEY_VALUES = "values"
KEY_FILTERS = "filters"
KEY_WHERE = "where"
KEY_ORDER_BY = "order_by"
KEY_LIMIT = "limit"
KEY_OFFSET = "offset"

# ==============================================================================
# DICT KEYS - Display & UI
# ==============================================================================

KEY_CONTENT = "content"
KEY_INDENT = "indent"
KEY_EVENT = "event"
KEY_LABEL = "label"
KEY_COLOR = "color"
KEY_STYLE = "style"
KEY_MESSAGE = "message"

# ==============================================================================
# PLURAL SHORTHAND REGISTRY  (SSOT)
# ==============================================================================
# Maps plural key → {event, defaults} for non-header UI elements.
# PLURAL_HEADER_REGISTRY maps header plural keys → indent level.
# PLURAL_SHORTHAND_KEYS is the combined membership set used across subsystems.
# ==============================================================================

PLURAL_REGISTRY = {
    'zURLs':       {'event': 'zURL',       'defaults': {}},
    'zTexts':      {'event': 'text',        'defaults': {}},
    'zImages':     {'event': 'image',       'defaults': {}},
    'zMDs':        {'event': 'rich_text',   'defaults': {}},
    'zBtns':       {'event': 'button',      'defaults': {'color': 'primary', 'action': '#'}},
    'zInputs':     {'event': 'read_string', 'defaults': {'type': 'text', 'default': '', 'placeholder': '', 'required': False}},
    'zCheckboxes': {'event': 'read_bool',   'defaults': {'checked': False, 'required': False, 'prompt': ''}},
    'zSelects':    {'event': 'selection',   'defaults': {'options': [], 'multi': False, 'default': None, 'prompt': ''}},
    'zRanges':     {'event': 'read_range',  'defaults': {'min': 0, 'max': 100, 'step': 1, 'prompt': '', 'disabled': False}},
    'zIcons':      {'event': 'icon',        'defaults': {}},
}

PLURAL_HEADER_REGISTRY = {
    'zH0s': 0, 'zH1s': 1, 'zH2s': 2, 'zH3s': 3,
    'zH4s': 4, 'zH5s': 5, 'zH6s': 6,
}

PLURAL_SHORTHAND_KEYS = frozenset(PLURAL_REGISTRY.keys()) | frozenset(PLURAL_HEADER_REGISTRY.keys())

# ==============================================================================
# UI EVENT SHORTHAND KEYS  (SSOT)
# ==============================================================================
# The singular display / input / control shorthands — the "bare event" vocabulary.
# A key that IS one of these is an event token, not an author-named step. The
# ShorthandExpander derives its UI_ELEMENT_KEYS from this set (no second copy), and
# the zEngine's wizard borrows it (try-import + literal fallback) to keep a bare
# event out of zHat: an unnamed event renders, but has no name to be recalled by.
# Headers zH0–zH6 are listed; zH{N} beyond that is matched dynamically by callers.
# ==============================================================================

UI_EVENT_SHORTHAND_KEYS = frozenset({
    'zH0', 'zH1', 'zH2', 'zH3', 'zH4', 'zH5', 'zH6',
    'zText', 'zMD', 'zCode', 'zImage', 'zVideo', 'zEmbed', 'zURL',
    'zUL', 'zOL', 'zDL', 'zTable', 'zBtn', 'zCrumbs', 'zInput', 'zCheckbox', 'zSelect',
    'zRange', 'zTerminal', 'zIcon', 'zProgress',
    'zSignal', 'zError', 'zWarning', 'zSuccess', 'zInfo', 'zPrimary', 'zSecondary',
    'zDash', 'zSwiper',
})

# ==============================================================================
# MODIFIERS - Symbols
# ==============================================================================

MOD_CARET = "^"           # zCrumbs bulk-rewind: <key>^: <zPath> → {'zCrumb': zPath}
MOD_TILDE = "~"           # Anchor: Disable back navigation (used with *)
MOD_ASTERISK = "*"        # Menu: Create menu from horizontal data
# MOD_EXCLAMATION ("!") — RETIRED. Gating is an EVENT (zBtn/zDialog), never a
# modifier. Kept defined only so any stray external import doesn't crash; it is
# no longer a recognized modifier (removed from SUFFIX_MODIFIERS below).
MOD_EXCLAMATION = "!"     # RETIRED — see step_is_gate() in zengine/zstride.py

# Modifier Groups
# NOTE: caret (^) is a SUFFIX modifier — `<key>^: <zPath>` sugar for a zCrumbs
# bulk-rewind (the retired prefix `^action` bounce no longer exists).
PREFIX_MODIFIERS = [MOD_TILDE]
SUFFIX_MODIFIERS = [MOD_ASTERISK, MOD_CARET]   # `!` retired — gating is an event
ALL_MODIFIERS = PREFIX_MODIFIERS + SUFFIX_MODIFIERS

# zCrumbs bulk-rewind — SSOT for the verb that both authoring surfaces emit:
#   sugar    : <key>^: <zPath>
#   longhand : zCrumbs: { show: none, zBack: <zPath> }
# Both collapse to {ZCRUMB_SIGNAL: <zPath>}, the existing bulk-back signal the
# walker consumes via zNavigation.handle_zCrumb_back (pop_to_scope + re-walk,
# zLink-forward fallback when the target is not on the trail).
ZCRUMB_SIGNAL = "zCrumb"            # nav signal key consumed by _handle_navigation_result
ZCRUMBS_ADVERB_ZBACK = "zBack"     # zCrumbs longhand adverb carrying the bulk-back zPath
ZCRUMBS_SHOW_NONE = "none"         # show: none → rewind-only, render no banner

# ==============================================================================
# MODE VALUES
# ==============================================================================

MODE_BIFROST = ZMODE_ZBIFROST  # alias zVocabulary SSOT ("zBifrost")
MODE_ZCLI = ZMODE_ZCLI         # alias zVocabulary SSOT ("zCLI")
MODE_WALKER = "Walker"         # dispatch-internal traversal mode (not a session zMode)

# ==============================================================================
# DISPLAY LABELS (zDeclare messages) - INTERNAL
# ==============================================================================

_LABEL_LAUNCHER = "zLauncher"
_LABEL_HANDLE_ZFUNC = "[HANDLE] zFunc"
_LABEL_HANDLE_ZFUNC_DICT = "[HANDLE] zFunc (dict)"
_LABEL_HANDLE_ZLINK = "[HANDLE] zLink"
_LABEL_HANDLE_ZDELTA = "[HANDLE] zDelta"
_LABEL_HANDLE_ZDELEGATE = "[HANDLE] zDelegate"
_LABEL_HANDLE_ZOPEN = "[HANDLE] zOpen"
_LABEL_HANDLE_ZWIZARD = "[HANDLE] zWizard"
_LABEL_HANDLE_ZREAD_STRING = "[HANDLE] zRead (string)"
_LABEL_HANDLE_ZREAD_DICT = "[HANDLE] zRead (dict)"
_LABEL_HANDLE_ZDATA_DICT = "[HANDLE] zData (dict)"
_LABEL_HANDLE_CRUD_DICT = "[HANDLE] zCRUD (dict)"
_LABEL_HANDLE_ZLOGIN = "[HANDLE] zLogin"
_LABEL_HANDLE_ZLOGOUT = "[HANDLE] zLogout"
_LABEL_PROCESS_MODIFIERS = "Process Modifiers"
_LABEL_ZREQUIRED = "zRequired"
_LABEL_ZREQUIRED_RETURN = "zRequired Return"

# ==============================================================================
# DISPLAY EVENT KEYS (Legacy zDisplay format) - INTERNAL
# ==============================================================================

_EVENT_TEXT = "text"
_EVENT_SYSMSG = "sysmsg"
_EVENT_HEADER = "header"
_EVENT_SUCCESS = "success"
_EVENT_ERROR = "error"
_EVENT_WARNING = "warning"
_EVENT_INFO = "info"
_EVENT_LINE = "line"
_EVENT_LIST = "list"

# ==============================================================================
# NAVIGATION
# ==============================================================================

NAV_ZBACK = "zBack"

# ==============================================================================
# PLUGINS
# ==============================================================================

PLUGIN_PREFIX = "&"

# ==============================================================================
# DEFAULT VALUES - INTERNAL
# ==============================================================================

_DEFAULT_ACTION_READ = "read"
_DEFAULT_ZBLOCK = "zVaF"
_DEFAULT_CONTENT = ""
_DEFAULT_INDENT = 0
_DEFAULT_INDENT_LAUNCHER = 4
_DEFAULT_INDENT_HANDLER = 5
_DEFAULT_INDENT_PROCESS = 2
_DEFAULT_INDENT_MODIFIER = 3
_DEFAULT_STYLE_SINGLE = "single"
_DEFAULT_LABEL = ""

# ==============================================================================
# STYLES & INDENTATION - INTERNAL
# ==============================================================================

_STYLE_FULL = "full"
_STYLE_SINGLE = "single"
_STYLE_WAVY = "~"

_INDENT_ROOT = 0
_INDENT_HANDLE = 1

# ==============================================================================
# PROMPTS & INPUT - INTERNAL
# ==============================================================================

_PROMPT_REQUIRED_CONTINUE = "Try again? (press Enter to retry, 'n' or 'stop' to go back): "

# The ! gate's retry prompt is a zBtn (DRY: reuse the button primitive — it already
# returns a bool, y→True retry / n→False exit). No bespoke read_string prompt.
_LABEL_REQUIRED_RETRY = "Try again?"

# The single graceful app-closer. A declined ! gate (n) or Ctrl+C returns this
# engine "exit" signal → routes to zWalker.on_exit (soft unwind). zOS never hard
# exits; "stop" is retired and aliases this same graceful path.
_RETRY_EXIT_RETURN = "exit"

# Input Values
_INPUT_N = "n"
_INPUT_STOP = "stop"

# ==============================================================================
# LOG MESSAGES - zDispatch - INTERNAL
# ==============================================================================

_LOG_PREFIX = "[zDispatch]"
_LOG_MSG_READY = f"{_LOG_PREFIX} Command dispatch subsystem ready"
_LOG_MSG_HORIZONTAL = "zHorizontal: %s"
_LOG_MSG_HANDLE_KEY = "handle zDispatch for key: %s"
_LOG_MSG_PREFIX_MODS = "Prefix modifiers: %s"
_LOG_MSG_SUFFIX_MODS = "Suffix modifiers: %s"
_LOG_MSG_DETECTED_MODS = "Detected modifiers for %s: %s"
_LOG_MSG_MODIFIER_RESULT = "Modifier evaluation result: %s"
_LOG_MSG_DISPATCH_RESULT = "dispatch result: %s"
_LOG_MSG_COMPLETED = "Modifier evaluation completed for key: %s"

# ==============================================================================
# LOG MESSAGES - Modifiers - INTERNAL
# ==============================================================================

_LOG_PREFIX_MODIFIERS = "[MODIFIERS]"
_LOG_MSG_PARSING_PREFIX = "Parsing prefix modifiers for key: %s"
_LOG_MSG_PARSING_SUFFIX = "Parsing suffix modifiers for key: %s"
_LOG_MSG_PRE_MODIFIERS = "pre_modifiers: %s"
_LOG_MSG_SUF_MODIFIERS = "suf_modifiers: %s"
_LOG_MSG_RESOLVED = "Resolved modifiers: %s on key: %s"
_LOG_MSG_MENU_DETECTED = "* Modifier detected for %s - invoking menu (anchor=%s)"
_LOG_MSG_BIFROST_DETECTED = "zBifrost mode detected - returning actual result"
_LOG_MSG_REQUIRED_STEP = "Required step: %s"
_LOG_MSG_REQUIRED_RESULTS = "zRequired results: %s"
_LOG_MSG_REQUIREMENT_NOT_SATISFIED = "Requirement '%s' not satisfied. Retrying..."
_LOG_MSG_REQUIREMENT_SATISFIED = "Requirement '%s' satisfied."
_LOG_MSG_LOOKING_UP_KEY = f"{_LOG_PREFIX_MODIFIERS} Looking up key: '%s' in block_dict keys: %s"
_LOG_MSG_COULD_NOT_LOAD = "Could not load UI block %s from %s"
_LOG_MSG_NO_ZVAFILE = "No zVaFile in zspark_obj"
_LOG_MSG_CANNOT_RESOLVE = "Cannot resolve ^key without walker context"

# ==============================================================================
# ERROR MESSAGES
# ==============================================================================

ERR_NO_ZOS_INSTANCE = "zDispatch requires a zOS instance"
ERR_NO_ZOS_OR_WALKER = "handle_zDispatch requires either zos or walker parameter"

# ==============================================================================
# PUBLIC API EXPORTS
# ==============================================================================
# Note: Only PUBLIC constants are exported. INTERNAL constants (prefixed with _)
# are implementation details and not accessible outside zDispatch subsystem.

__all__ = [
    # Subsystem Identity
    'SUBSYSTEM_NAME',
    'SUBSYSTEM_COLOR',

    # Command Prefixes (PUBLIC - used by parsers and external code)
    'CMD_PREFIX_ZFUNC',
    'CMD_PREFIX_ZLINK',
    'CMD_PREFIX_ZALPHA',
    'CMD_PREFIX_ZOPEN',
    'CMD_PREFIX_ZWIZARD',
    'CMD_PREFIX_ZREAD',

    # Dict Keys - Subsystem Commands (PUBLIC - used to build commands)
    'KEY_ZFUNC',
    'KEY_ZLINK',
    'KEY_ZALPHA',
    'KEY_ZOMEGA',
    'KEY_ZDELTA',
    'KEY_ZDELEGATE',
    'KEY_ZOPEN',
    'KEY_ZWIZARD',
    'KEY_ZREAD',
    'KEY_ZDATA',
    'KEY_ZDIALOG',
    'KEY_ZDASH',
    'KEY_ZFLAT',
    'KEY_ZDISPLAY',
    'KEY_ZLOGIN',
    'KEY_ZLOGOUT',
    'KEY_ZEXPORT',
    'KEY_ZIMPORT',
    'KEY_ZVAR',
    'KEY_ZLIST',
    'KEY_ZPROGRESS',
    'PROGRESS_ACTION_KEYS',

    # Event-Binding Keys (PUBLIC - declarative bindings, never executed inline)
    'EVENT_BINDING_KEYS',

    # Dict Keys - Context & Session (PUBLIC - used by external callers)
    'KEY_ZVAFILE',
    'KEY_ZBLOCK',

    # Dict Keys - Data Operations (PUBLIC - used by zData consumers)
    'KEY_ACTION',
    'KEY_MODEL',
    'KEY_TABLE',
    'KEY_TABLES',
    'KEY_FIELDS',
    'KEY_VALUES',
    'KEY_FILTERS',
    'KEY_WHERE',
    'KEY_ORDER_BY',
    'KEY_LIMIT',
    'KEY_OFFSET',

    # Dict Keys - Display & UI (PUBLIC - used by external code)
    'KEY_CONTENT',
    'KEY_INDENT',
    'KEY_EVENT',
    'KEY_LABEL',
    'KEY_COLOR',
    'KEY_STYLE',
    'KEY_MESSAGE',

    # Plural Shorthand Registry (PUBLIC - SSOT for all plural expansion)
    'PLURAL_REGISTRY',
    'PLURAL_HEADER_REGISTRY',
    'PLURAL_SHORTHAND_KEYS',

    # UI Event Shorthand Keys (PUBLIC - SSOT for the singular "bare event" vocabulary)
    'UI_EVENT_SHORTHAND_KEYS',

    # Modifiers (PUBLIC - used by external code to parse and build commands)
    'MOD_CARET',
    'MOD_TILDE',
    'MOD_ASTERISK',
    'MOD_EXCLAMATION',
    'PREFIX_MODIFIERS',
    'SUFFIX_MODIFIERS',
    'ALL_MODIFIERS',

    # Modes (PUBLIC - used by external code for mode detection)
    'MODE_BIFROST',
    'MODE_ZCLI',
    'MODE_WALKER',

    # Navigation (PUBLIC - used by zWizard, zWalker, and navigation logic)
    'NAV_ZBACK',

    # Plugins (PUBLIC - used by zParser for plugin invocations)
    'PLUGIN_PREFIX',

    # Error Messages (PUBLIC - used by external error handlers)
    'ERR_NO_ZOS_INSTANCE',
    'ERR_NO_ZOS_OR_WALKER',
]

# INTERNAL constants (not exported):
# - _MSG_READY, _MSG_HANDLE - display messages
# - _LABEL_* (17 constants) - internal display labels
# - _EVENT_* (9 constants) - legacy display event keys
# - _DEFAULT_* (10 constants) - implementation defaults
# - _STYLE_*, _INDENT_* (5 constants) - styling details
# - _PROMPT_*, _INPUT_* (3 constants) - input prompts
# - _LOG_* (32 constants) - internal logging messages

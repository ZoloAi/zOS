# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/data_keys.py
"""
Single source of truth for zData request- and schema-key names.

Before this module the request-dict keys (``action``/``model``/``where``/…) and
the reserved schema keys (``zMeta``/``db_path``) were re-declared independently
in ~16 m_zData modules. They now resolve here.

Request keys that are part of the dispatch→data contract are bound to
``g_zDispatch.dispatch_constants`` — the designated cross-subsystem SSOT (the
same module the wizard binds against). Subsystems load in letter order, so
g_zDispatch (L2) is already imported by the time m_zData (L3) loads; the guarded
import therefore hits the module cache. The byte-identical fallback keeps the
subsystem self-contained if the dispatch constants ever move.

Keys that are *not* part of the dispatch contract stay local:
    - ``order``   — the data request uses "order"; dispatch's KEY_ORDER_BY is
                    "order_by" (a deliberately distinct key, NOT aliased here).
    - ``options`` / ``joins`` / ``silent`` — zData-only request shape.

Schema keys (``zMeta`` / ``db_path``) are the m_zData SSOT. d_zParser still
exposes ``SCHEMA_KEY_META = "meta"`` (a deprecated value) while the live runtime
key is ``zMeta``; correcting that and binding both subsystems to one parser
constant is deferred to the d_zParser audit. Until then this module is the
single definition for all of m_zData.
"""

# ──────────────────────────────────────────────────────────────────────────
# Request keys shared with the dispatch→data contract (SSOT: dispatch_constants)
# ──────────────────────────────────────────────────────────────────────────
try:  # pragma: no cover - resolved against live zOS (g_zDispatch loads first)
    from zOS.L2_Handling.g_zDispatch.dispatch_modules.dispatch_constants import (
        KEY_ACTION,
        KEY_MODEL,
        KEY_TABLE,
        KEY_TABLES,
        KEY_FIELDS,
        KEY_VALUES,
        KEY_FILTERS,
        KEY_WHERE,
        KEY_LIMIT,
        KEY_OFFSET,
    )
except ImportError:  # pragma: no cover - defensive fallback if constants move
    KEY_ACTION = "action"
    KEY_MODEL = "model"
    KEY_TABLE = "table"
    KEY_TABLES = "tables"
    KEY_FIELDS = "fields"
    KEY_VALUES = "values"
    KEY_FILTERS = "filters"
    KEY_WHERE = "where"
    KEY_LIMIT = "limit"
    KEY_OFFSET = "offset"

# ──────────────────────────────────────────────────────────────────────────
# zData-only request keys (NOT part of the dispatch contract)
# ──────────────────────────────────────────────────────────────────────────
KEY_OPTIONS = "options"
KEY_ORDER = "order"      # NOTE: distinct from dispatch KEY_ORDER_BY ("order_by")
KEY_JOINS = "joins"
KEY_SILENT = "silent"

# ──────────────────────────────────────────────────────────────────────────
# Reserved schema keys (m_zData SSOT; cross-subsystem unify pending d_zParser)
# ──────────────────────────────────────────────────────────────────────────
SCHEMA_KEY_META = "zMeta"
SCHEMA_KEY_DB_PATH = "db_path"

__all__ = [
    "KEY_ACTION", "KEY_MODEL", "KEY_TABLE", "KEY_TABLES", "KEY_FIELDS",
    "KEY_VALUES", "KEY_FILTERS", "KEY_WHERE", "KEY_LIMIT", "KEY_OFFSET",
    "KEY_OPTIONS", "KEY_ORDER", "KEY_JOINS", "KEY_SILENT",
    "SCHEMA_KEY_META", "SCHEMA_KEY_DB_PATH",
]

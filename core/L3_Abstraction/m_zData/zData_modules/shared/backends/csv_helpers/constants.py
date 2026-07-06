# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/constants.py
"""
Constants for CSV adapter module.

This module contains all constant values used throughout the CSV adapter,
including file extensions, schema keys, operators, error messages, and log messages.
"""

# ============================================================
# File Extensions
# ============================================================

CSV_EXTENSION = ".csv"
CSV_GLOB_PATTERN = "*.csv"

# ============================================================
# Schema Keys (SSOT: shared/validators/constants — re-exported here)
# ============================================================

from ...validators.constants import (  # noqa: F401  pylint: disable=wrong-import-position,unused-import
    SCHEMA_KEY_PRIMARY_KEY,
    SCHEMA_KEY_INDEXES,
    SCHEMA_KEY_TYPE,
    SCHEMA_KEY_PK,
    SCHEMA_KEY_UNIQUE,
    SCHEMA_KEY_REQUIRED,
    SCHEMA_KEY_DEFAULT,
)

# ============================================================
# WHERE Operators
# ============================================================

OP_SUFFIX_GT = "__gt"
OP_SUFFIX_LT = "__lt"
OP_SUFFIX_GTE = "__gte"
OP_SUFFIX_LTE = "__lte"
OP_SUFFIX_LIKE = "__like"
OP_SUFFIX_IN = "__in"
OP_SUFFIX_IS_NULL = "__is_null"
OP_SUFFIX_IS_NOT_NULL = "__is_not_null"
WHERE_KEY_OR = "or"

# ============================================================
# Merge Strategies
# ============================================================

MERGE_INNER = "inner"
MERGE_LEFT = "left"
MERGE_RIGHT = "right"
MERGE_OUTER = "outer"

# ============================================================
# Column Keys
# ============================================================

COL_INDEX = "index"
COL_DEFAULT = "default"
COL_TYPE = "type"

# ============================================================
# Error Messages
# ============================================================

ERR_PANDAS_MISSING = "pandas is required for CSV adapter. Install with: pip install pandas"
ERR_TABLE_NOT_FOUND = "CSV table '%s' not found: %s"
ERR_DIR_CREATE_FAILED = "Failed to create CSV directory: %s"
ERR_TABLE_LOAD_FAILED = "Failed to load CSV table '%s': %s"
ERR_TABLE_SAVE_FAILED = "Failed to save CSV table '%s': %s"
ERR_JOIN_FAILED = "Failed to join tables: %s"
ERR_WHERE_FILTER_FAILED = "Failed to apply WHERE filter: %s"
ERR_TYPE_COERCION_FAILED = "Failed to apply type coercion for table '%s': %s"

# ============================================================
# Log Messages
# ============================================================

LOG_CONNECTED = "Connected to CSV backend: %s"
LOG_DISCONNECTED = "Disconnected from CSV backend: %s"
LOG_TABLE_CREATED = "CSV table created: %s"
LOG_TABLE_LOADED = "Loaded CSV table: %s (%d rows)"
LOG_TABLE_SAVED = "Saved CSV table: %s (%d rows)"
LOG_TABLE_DROPPED = "Dropped CSV table: %s"
LOG_TABLE_ALTERED = "Altered CSV table: %s"
LOG_COLUMN_ADDED = "Added column '%s' to table '%s'"
LOG_COLUMN_DROPPED = "Dropped column '%s' from table '%s'"
LOG_ROW_INSERTED = "Inserted row into CSV table %s (row %d)"
LOG_JOIN_MULTI_TABLE = "[JOIN] Multi-table CSV query: %s"
LOG_TABLE_EXISTS = "CSV table '%s' exists: %s"
LOG_FOUND_TABLES = "Found %d CSV tables: %s"

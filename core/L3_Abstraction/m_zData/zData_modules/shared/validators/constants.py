# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/constants.py
"""
Validation constants for zData schema validation engine.

This module centralizes all constants used across the validation layers:
- Schema structure keys
- Validation rule keys
- Format type identifiers
- Regex patterns for format validation
- Error message templates
- Log message templates
- Plugin system constants
"""

# ============================================================
# Schema Structure Keys
# ============================================================

SCHEMA_KEY_RULES = "rules"
SCHEMA_KEY_REQUIRED = "required"
SCHEMA_KEY_UNIQUE = "unique"
SCHEMA_KEY_PK = "pk"
SCHEMA_KEY_PRIMARY_KEY = "primary_key"   # table-level composite PK declaration
SCHEMA_KEY_INDEXES = "indexes"           # table-level index declarations
SCHEMA_KEY_CONSTRAINTS = "constraints"   # table-level constraint declarations (unique/fk/check)
SCHEMA_KEY_VIEW = "view"                 # entity-level: this entry is a saved read, not a table
SCHEMA_KEY_DEFAULT = "default"
SCHEMA_KEY_ENUM = "enum"
SCHEMA_KEY_NULLABLE = "nullable"
SCHEMA_KEY_IMMUTABLE = "immutable"
SCHEMA_KEY_TRANSFORM = "transform"

# ============================================================
# Session Transport Keys
# ============================================================

# Unified session key for surfacing validation/unique errors to Bifrost.
# Written by crud_insert / crud_update, consumed once by the Bifrost form-submit handler.
SESSION_KEY_ZDATA_ERRORS = "_zdata_errors"

# ============================================================
# Validation Rule Keys
# ============================================================

# String validation rules
RULE_KEY_MIN_LENGTH = "min_length"
RULE_KEY_MAX_LENGTH = "max_length"

# Numeric validation rules
RULE_KEY_MIN = "min"
RULE_KEY_MAX = "max"

# Pattern validation rules
RULE_KEY_PATTERN = "pattern"
RULE_KEY_PATTERN_MESSAGE = "pattern_message"

# Format validation rules
RULE_KEY_FORMAT = "format"

# Plugin validator rules
RULE_KEY_VALIDATOR = "validator"

# Error message override
RULE_KEY_ERROR_MESSAGE = "error_message"

# ============================================================
# Format Type Identifiers
# ============================================================

FORMAT_EMAIL = "email"
FORMAT_URL = "url"
FORMAT_PHONE = "phone"
FORMAT_DATE = "date"
FORMAT_TIME = "time"
FORMAT_DATETIME = "datetime"

# ============================================================
# Regex Patterns
# ============================================================

# Email validation pattern (RFC-compliant)
PATTERN_EMAIL = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# URL validation pattern (HTTP/HTTPS)
PATTERN_URL = r'^https?://[^\s/$.?#].[^\s]*$'

# Phone validation pattern (10-15 digits, optional +)
PATTERN_PHONE = r'^\+?[0-9]{10,15}$'

# Phone cleaning pattern (remove formatting characters)
PATTERN_PHONE_CLEAN = r'[\s\-\(\)\.]'

# ============================================================
# Plugin System Constants
# ============================================================

# Plugin invocation symbol
PLUGIN_SYMBOL = "&"

# Cache type for plugin resolution
CACHE_TYPE_PLUGIN = "plugin"

# ============================================================
# Error Message Templates
# ============================================================

# Required field errors
ERR_FIELD_REQUIRED = "{field_name} is required"

# Unique constraint error
ERR_UNIQUE_VIOLATION = "{field_name} must be unique — '{value}' already exists"

# String validation errors
ERR_MIN_LENGTH = "{field_name} must be at least {min_length} characters"
ERR_MAX_LENGTH = "{field_name} cannot exceed {max_length} characters"

# Type coercion error
ERR_INVALID_TYPE = "{field_name} must be a valid {expected_type} (got: {value!r})"

# Schema type key
SCHEMA_KEY_TYPE = "type"

# Schema types that expect numeric values
NUMERIC_SCHEMA_TYPES = ('int', 'integer', 'float', 'numeric', 'number', 'double')

# Schema types that map directly to a format validator (type: date → format: date, etc.)
# When a field declares one of these types and no explicit `format:` rule is set,
# the type itself is used as the format key — falling back to zMachine config defaults.
TEMPORAL_SCHEMA_TYPES = ('date', 'time', 'datetime')

# Schema types that represent boolean values — coerced from string before validation.
BOOL_SCHEMA_TYPES = ('bool', 'boolean')

# Truthy/falsy string sets for bool coercion
BOOL_TRUTHY_STRINGS = {'true', '1', 'yes', 'on'}
BOOL_FALSY_STRINGS = {'false', '0', 'no', 'off'}

ERR_INVALID_BOOL = "{field_name} must be true or false (got: {value!r})"

# Schema types that represent UUIDs — auto-generated when empty; format-validated when provided.
UUID_SCHEMA_TYPES = ('uuid',)

# UUID v4 regex pattern (case-insensitive)
PATTERN_UUID = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'

ERR_INVALID_UUID = "{field_name} must be a valid UUID v4 (e.g. 550e8400-e29b-41d4-a716-446655440000)"

FORMAT_UUID = "uuid"

# Schema types that represent JSON objects/arrays — parsed from string; validated as JSON.
JSON_SCHEMA_TYPES = ('json',)

ERR_INVALID_JSON = "{field_name} must be valid JSON (got: {value!r})"

# Schema types that represent binary data — stored inline on SQL backends (BLOB/BYTEA),
# sidecar-spilled to a file on CSV. Normalised to bytes upstream (coerce_blob).
BLOB_SCHEMA_TYPES = ('blob', 'bytes', 'binary')

# Blob rule keys
RULE_KEY_MAX_SIZE = "max_size"      # human size cap, e.g. "2MB" — validated on all backends
RULE_KEY_BLOB_INPUT = "blob_input"  # how a STRING input is read: raw | base64 | path

ERR_INVALID_BLOB = "{field_name} must be binary data (got: {value!r})"
ERR_BLOB_TOO_LARGE = "{field_name} exceeds maximum size {max_size} (got {size} bytes)"

# ============================================================
# Foreign Key / Referential Integrity Constants
# ============================================================

SCHEMA_KEY_FK = "fk"
SCHEMA_KEY_ON_DELETE = "on_delete"

ON_DELETE_RESTRICT = "restrict"
ON_DELETE_CASCADE = "cascade"
ON_DELETE_SET_NULL = "set_null"
ON_DELETE_SET_DEFAULT = "set_default"

# Error raised when on_delete: restrict blocks a delete
ERR_FK_RESTRICT = (
    "Cannot delete: {count} row(s) in '{child_table}' reference this record "
    "via '{fk_field}' (on_delete: restrict)"
)

LOG_ON_DELETE_CASCADE = "[on_delete: cascade] Deleting %d child row(s) from '%s' (fk: %s)"
LOG_ON_DELETE_SET_NULL = "[on_delete: set_null] Nulling %d child row(s) in '%s.%s'"
LOG_ON_DELETE_SET_DEFAULT = "[on_delete: set_default] Resetting %d child row(s) in '%s.%s' to default=%r"
LOG_ON_DELETE_RESTRICT = "[on_delete: restrict] Blocked: %d child row(s) exist in '%s.%s'"
LOG_ON_DELETE_SCAN = "[on_delete] Scanning child table '%s' field '%s' → fk: %s"
LOG_ON_DELETE_SKIP = "[on_delete] No parent rows match WHERE — skipping FK checks"

# Nullable constraint error (opt-in nullable: false)
ERR_NULL_NOT_ALLOWED = "{field_name} cannot be null or empty"

# Immutable field error — field is write-once (set on insert, cannot be updated)
ERR_IMMUTABLE_FIELD = "{field_name} is immutable and cannot be changed after insert"

# Numeric validation errors
ERR_MIN_VALUE = "{field_name} must be at least {min_val}"
ERR_MAX_VALUE = "{field_name} cannot exceed {max_val}"

# Enum validation error
ERR_ENUM_VIOLATION = "{field_name} must be one of: {choices}"

# Pattern validation errors
ERR_INVALID_FORMAT = "Invalid format for {field_name}"

# Format validation errors
ERR_EMAIL_FORMAT = "Invalid email address format"
ERR_URL_FORMAT = "Invalid URL format"
ERR_PHONE_FORMAT = "Invalid phone number format"
ERR_DATE_FORMAT = "Invalid date format"
ERR_TIME_FORMAT = "Invalid time format"
ERR_DATETIME_FORMAT = "Invalid datetime format"

# Plugin validator errors
ERR_PLUGIN_INVALID_RETURN = "Plugin validator error: invalid return format"
ERR_PLUGIN_EXECUTION = "Plugin validator error: {error}"

# ============================================================
# Log Message Templates
# ============================================================

LOG_NO_SCHEMA = "No schema found for table: %s"
LOG_VALIDATION_FAILED = "Validation failed with %d error(s)"
LOG_VALIDATION_PASSED = "[OK] Validation passed for table: %s"
LOG_UNKNOWN_FORMAT = "Unknown format type: %s"
LOG_PLUGIN_NO_ZCLI = "Plugin validator specified but zos not provided to DataValidator: %s"
LOG_PLUGIN_INVALID_SYNTAX = "Invalid validator syntax (must start with &): %s"
LOG_PLUGIN_NOT_FOUND = "Plugin validator not found (skipping validation): %s"
LOG_PLUGIN_FUNCTION_MISSING = "Function '%s' not found in plugin '%s'"
LOG_PLUGIN_INVALID_RETURN_FORMAT = "Plugin validator must return (is_valid, error_msg) tuple: %s.%s"
LOG_PLUGIN_EXECUTION_ERROR = "Plugin validator execution error (%s): %s"

# ============================================================
# Plugin Context Keys
# ============================================================

CONTEXT_KEY_TABLE = "table"
CONTEXT_KEY_FULL_DATA = "full_data"

# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/schema_operations.py
"""
Schema operations for CSV adapter.

This module handles schema parsing, type mapping, and type coercion for DataFrames.
"""

from zOS import Dict, Any, List, Tuple
import pandas as pd

from .constants import SCHEMA_KEY_PRIMARY_KEY, SCHEMA_KEY_INDEXES, SCHEMA_KEY_TYPE


def parse_schema_columns(schema: Dict[str, Any]) -> Tuple[List[str], Dict[str, Dict]]:
    """
    Extract column names and field definitions from schema.
    
    Parses schema dict to extract field names (skipping metadata keys like
    primary_key, indexes) and normalizes field definitions to dict format.
    
    Args:
        schema: Schema dictionary with field definitions
    
    Returns:
        Tuple of (column_names, normalized_schema):
            - column_names: List of field names
            - normalized_schema: Dict of {field_name: field_def_dict}
    
    Example:
        >>> schema = {
        ...     "id": {"type": "int", "pk": True},
        ...     "name": "str",
        ...     "primary_key": ["id"]
        ... }
        >>> columns, normalized = parse_schema_columns(schema)
        >>> columns
        ['id', 'name']
        >>> normalized
        {'id': {'type': 'int', 'pk': True}, 'name': {'type': 'str'}}
    
    Note:
        - Skips metadata keys: primary_key, indexes
        - Converts string type shorthand to dict format
        - Returns normalized schema for type coercion
    """
    columns = []
    normalized_schema = {}

    for field_name, attrs in schema.items():
        if field_name in [SCHEMA_KEY_PRIMARY_KEY, SCHEMA_KEY_INDEXES]:
            continue

        if isinstance(attrs, dict):
            columns.append(field_name)
            normalized_schema[field_name] = attrs
        elif isinstance(attrs, str):
            columns.append(field_name)
            normalized_schema[field_name] = {SCHEMA_KEY_TYPE: attrs}

    return columns, normalized_schema


def apply_schema_types(
    df: pd.DataFrame,
    schema: Dict[str, Any],
    logger: Any = None
) -> pd.DataFrame:
    """
    Apply type conversions based on schema.
    
    Coerces DataFrame columns to match schema-defined types using pandas
    type conversion functions.
    
    Args:
        df: DataFrame to apply types to
        schema: Schema dict with field type definitions
        logger: Optional logger for warnings
    
    Returns:
        pd.DataFrame: DataFrame with types applied
    
    Example:
        >>> df = pd.DataFrame({"age": ["25", "30"], "active": ["true", "false"]})
        >>> schema = {"age": {"type": "int"}, "active": {"type": "bool"}}
        >>> df = apply_schema_types(df, schema)
        >>> df.dtypes
        age        Int64
        active    boolean
        dtype: object
    
    Note:
        - Handles int, float, bool, datetime types
        - Uses errors='coerce' for numeric conversions (invalid → NaN)
        - Logs warnings on conversion failures
    """
    for field_name, field_def in schema.items():
        if field_name not in df.columns:
            continue
        if not isinstance(field_def, dict):
            continue

        field_type = field_def.get("type", "str")

        try:
            if field_type in ["int", "integer"]:
                df[field_name] = pd.to_numeric(df[field_name], errors='coerce').astype('Int64')
            elif field_type in ["float", "real"]:
                df[field_name] = pd.to_numeric(df[field_name], errors='coerce')
            elif field_type in ["bool", "boolean"]:
                df[field_name] = df[field_name].astype('boolean')
            elif field_type in ["datetime", "date"]:
                df[field_name] = pd.to_datetime(df[field_name], errors='coerce')
        except Exception as e:
            if logger:
                logger.warning("Failed to convert column '%s' to type '%s': %s",
                             field_name, field_type, e)

    return df


def coerce_int_columns(
    df: pd.DataFrame,
    schema: Dict[str, Any],
    logger: Any = None
) -> pd.DataFrame:
    """Coerce ONLY int-typed columns to pandas nullable ``Int64``.

    This is the surgical sibling of :func:`apply_schema_types`. pandas cannot keep
    NaN in a native ``int64`` column, so a NULLABLE int column (e.g. a foreign key
    that's sometimes empty) is inferred as ``float64`` on ``read_csv`` and its
    values leak as ``2.0`` — poisoning ids written back to the CSV and any
    consumer comparing against ``"2"``. ``Int64`` holds both integers and ``<NA>``,
    so the column round-trips as ``2`` / empty.

    Why int-only (vs. the full type pass): converting bool→``boolean`` or
    str-dates→``datetime`` here would change the EMITTED python types app-wide
    (e.g. ``created_at`` stops being an ISO string), a much larger blast radius.
    The int leak is the only correctness bug, so we fix exactly that.
    """
    for field_name, field_def in schema.items():
        if field_name not in df.columns:
            continue
        if not isinstance(field_def, dict):
            continue
        if field_def.get("type", "str") not in ("int", "integer"):
            continue
        try:
            df[field_name] = pd.to_numeric(df[field_name], errors="coerce").astype("Int64")
        except Exception as e:  # pylint: disable=broad-except
            if logger:
                logger.warning("Failed to coerce int column '%s': %s", field_name, e)
    return df


def sanitize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert pandas/numpy scalars in row dicts to plain Python values.

    ``DataFrame.to_dict('records')`` emits backend-native scalars: ``numpy.int64``,
    ``numpy.float64``, ``pandas.NA``, ``NaN``, ``NaT``. Downstream zOS code (zLoom,
    JSON, ``if row[x] is None``) expects clean Python — and ``pd.NA`` even RAISES in
    a boolean context. Normalize missing → ``None`` and numpy scalars → ``int`` /
    ``float`` / ``bool`` so every read returns ordinary dicts.
    """
    clean_rows: List[Dict[str, Any]] = []
    for row in records:
        clean: Dict[str, Any] = {}
        for key, value in row.items():
            try:
                if pd.isna(value):  # NaN / NaT / pd.NA → None
                    clean[key] = None
                    continue
            except (TypeError, ValueError):
                pass  # non-scalar (list/dict) — leave as-is
            clean[key] = value.item() if hasattr(value, "item") else value
        clean_rows.append(clean)
    return clean_rows


def map_abstract_type_to_pandas(abstract_type: str) -> str:
    """
    Map abstract schema type to pandas dtype.
    
    Converts zCLI abstract types (str, int, float, etc.) to pandas-compatible
    dtype strings.
    
    Args:
        abstract_type: Abstract type (str, int, float, bool, datetime, etc.)
    
    Returns:
        str: Pandas dtype ("object", "Int64", "float64", "boolean")
    
    Example:
        >>> map_abstract_type_to_pandas("int")
        'Int64'
        >>> map_abstract_type_to_pandas("str!")  # Strips '!' required marker
        'object'
        >>> map_abstract_type_to_pandas("unknown")
        'object'
    
    Note:
        - Strips whitespace and required markers (!?)
        - Case-insensitive matching
        - Returns "object" for unknown types
    """
    if not isinstance(abstract_type, str):
        return "object"

    normalized = abstract_type.strip().rstrip("!?").lower()

    type_map = {
        "str": "object",
        "string": "object",
        "int": "Int64",
        "integer": "Int64",
        "float": "float64",
        "real": "float64",
        "bool": "boolean",
        "boolean": "boolean",
        "datetime": "object",
        "date": "object",
        "json": "object",
        # blob cells hold a relative sidecar path string on CSV — stored as object.
        "blob": "object",
        "bytes": "object",
        "binary": "object",
    }

    return type_map.get(normalized, "object")


def introspect_dataframe_schema(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Infer schema from DataFrame dtypes.
    
    Analyzes DataFrame column types and creates a schema dict in zCLI format.
    
    Args:
        df: DataFrame to introspect
    
    Returns:
        Dict[str, Any]: Schema dict with inferred types
    
    Example:
        >>> df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        >>> introspect_dataframe_schema(df)
        {'id': {'type': 'int'}, 'name': {'type': 'str'}}
    
    Note:
        - Maps pandas dtypes to zCLI abstract types
        - int64/int32 → 'int'
        - float64/float32 → 'float'
        - bool → 'bool'
        - datetime64 → 'datetime'
        - object/string → 'str'
    """
    schema = {}

    for col in df.columns:
        col_def = {'type': 'str'}  # Default to string

        # Infer type from pandas dtype
        dtype_str = str(df[col].dtype)

        if 'int' in dtype_str:
            col_def['type'] = 'int'
        elif 'float' in dtype_str:
            col_def['type'] = 'float'
        elif 'bool' in dtype_str:
            col_def['type'] = 'bool'
        elif 'datetime' in dtype_str:
            col_def['type'] = 'datetime'
        else:
            # object, string, or unknown → str
            col_def['type'] = 'str'

        schema[col] = col_def

    return schema

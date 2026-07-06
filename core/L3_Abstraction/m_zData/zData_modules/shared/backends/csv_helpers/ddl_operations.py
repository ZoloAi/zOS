# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv_helpers/ddl_operations.py
"""
DDL (Data Definition Language) operations for CSV adapter.

This module handles table creation, alteration, dropping, and schema introspection.
"""

import json

from zOS import Dict, Any, List, Path
import pandas as pd

from . import constants as csv_const
from . import file_operations as file_ops
from . import schema_operations as schema_ops


def create_table(
    base_path: Path,
    table_name: str,
    schema: Dict[str, Any],
    tables_cache: Dict[str, pd.DataFrame],
    schemas_cache: Dict[str, Dict],
    logger: Any = None
) -> None:
    """
    Create CSV table file with headers based on schema definition.
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table
        schema: Schema dict with field definitions
        tables_cache: Cache dict to store DataFrame
        schemas_cache: Cache dict to store schema
        logger: Optional logger
    """
    if logger:
        logger.info("Creating CSV table: %s", table_name)

    columns, normalized_schema = schema_ops.parse_schema_columns(schema)
    schemas_cache[table_name] = normalized_schema

    df = pd.DataFrame(columns=columns)
    csv_file = file_ops.get_csv_path(base_path, table_name)
    file_ops.save_table_to_csv(csv_file, df, logger)
    tables_cache[table_name] = df

    if logger:
        logger.info(csv_const.LOG_TABLE_CREATED, csv_file)


def alter_table(
    base_path: Path,
    table_name: str,
    changes: Dict[str, Any],
    tables_cache: Dict[str, pd.DataFrame],
    _schemas_cache: Dict[str, Dict],
    load_table_func,
    logger: Any = None
) -> None:
    """
    Alter CSV table structure by adding or dropping columns.
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table to alter
        changes: Dict with operations (add_columns, drop_columns, modify_columns)
        tables_cache: Cache dict to update
        _schemas_cache: Schema cache dict (reserved for future use)
        load_table_func: Function to load table if not cached
        logger: Optional logger
    """
    df = load_table_func(table_name)

    if "rename_columns" in changes:
        for new_name, old_name in changes["rename_columns"].items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
                if logger:
                    logger.info("Renamed column '%s' -> '%s' in table '%s'",
                                old_name, new_name, table_name)

    if "add_columns" in changes:
        for column_name, column_def in changes["add_columns"].items():
            default = column_def.get(csv_const.COL_DEFAULT, None)
            df[column_name] = default
            if logger:
                logger.info(csv_const.LOG_COLUMN_ADDED, column_name, table_name)

    if "drop_columns" in changes:
        for column_name in changes["drop_columns"]:
            if column_name in df.columns:
                df = df.drop(columns=[column_name])
                if logger:
                    logger.info(csv_const.LOG_COLUMN_DROPPED, column_name, table_name)

    if "modify_columns" in changes:
        df = _apply_modify_columns(df, table_name, changes["modify_columns"], logger)

    csv_file = file_ops.get_csv_path(base_path, table_name)
    file_ops.save_table_to_csv(csv_file, df, logger)
    tables_cache[table_name] = df

    if logger:
        logger.info(csv_const.LOG_TABLE_ALTERED, table_name)


def _apply_modify_columns(
    df: pd.DataFrame,
    table_name: str,
    modify_columns: Dict[str, Any],
    logger: Any = None
) -> pd.DataFrame:
    """
    Apply column type changes to a CSV-backed DataFrame.

    A CSV stores every value as a serialized string; the column *type* is enforced
    at the zOS read/validation layer, not at rest. So a type change is only an
    at-rest rewrite when the target dtype changes the serialized form — i.e. the
    numeric/bool families. ``str``/``datetime``/``date``/``json``/``blob`` all map to
    pandas ``object`` and are treated as metadata-only changes (no value rewrite). For
    ``blob`` the cell holds a sidecar path string, so it is object-mapped too. This is
    deliberate: it lets zOS migrate agnostic CSV data types without corrupting
    sentinel/string values (e.g. a ``now`` default being rewritten to a concrete
    timestamp). The transaction snapshot in the adapter still covers rollback.

    Args:
        df: DataFrame to modify (in place / returned)
        table_name: Table being altered (for logging)
        modify_columns: {column: {"old": {...}, "new": {...}}} from the diff engine
        logger: Optional logger

    Returns:
        pd.DataFrame: DataFrame with type coercions applied
    """
    for column_name, change in modify_columns.items():
        if column_name not in df.columns:
            continue

        # Diff format is {"old": {...}, "new": {...}}; tolerate a bare column def too.
        new_def = change.get("new", change) if isinstance(change, dict) else {}
        new_type = (new_def or {}).get(csv_const.COL_TYPE, "str")
        pandas_dtype = schema_ops.map_abstract_type_to_pandas(new_type)

        try:
            if pandas_dtype == "Int64":
                df[column_name] = pd.to_numeric(df[column_name], errors="coerce").astype("Int64")
            elif pandas_dtype == "float64":
                df[column_name] = pd.to_numeric(df[column_name], errors="coerce")
            elif pandas_dtype == "boolean":
                df[column_name] = df[column_name].astype("boolean")
            # object-mapped types (str/datetime/date/json/blob): metadata-only, no rewrite.

            if logger:
                logger.info("Modified column '%s' -> type '%s' in table '%s'",
                            column_name, new_type, table_name)
        except Exception as e:  # pylint: disable=broad-except
            if logger:
                logger.warning("Failed to modify column '%s' to type '%s': %s",
                               column_name, new_type, e)

    return df


def _schema_snapshot_path(base_path: Path, table_name: str) -> Path:
    """Return the path to a table's persisted column-type snapshot."""
    snap_dir = base_path / "zmigrations"
    snap_dir.mkdir(parents=True, exist_ok=True)
    return snap_dir / f"{table_name}.schema.json"


def _load_schema_snapshot(base_path: Path, table_name: str) -> Dict[str, Any]:
    """Return the persisted {column: {type}} snapshot for a table, or {} if none."""
    try:
        path = base_path / "zmigrations" / f"{table_name}.schema.json"
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:  # pylint: disable=broad-except
        return {}


def persist_schema_snapshot(
    base_path: Path,
    table_name: str,
    columns_def: Dict[str, Any],
    logger: Any = None
) -> None:
    """
    Persist a table's declared column types alongside its data.

    CSV headers cannot carry type information, so introspecting a live CSV can only
    *infer* types from sampled rows (e.g. a datetime stored as an ISO string reads
    back as ``str``). That produces phantom ``str -> datetime`` diffs on every run.
    By writing the declared types to ``zmigrations/{table}.schema.json`` at migrate
    time, future introspection becomes type-accurate and repeated migrates are
    idempotent. This is the SSOT for "what the migrated schema says these types are".
    """
    try:
        snapshot: Dict[str, Any] = {}
        for col, col_def in columns_def.items():
            if isinstance(col_def, dict):
                snapshot[col] = {"type": col_def.get("type", "str")}
            elif isinstance(col_def, str):
                snapshot[col] = {"type": col_def}

        path = _schema_snapshot_path(base_path, table_name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2)

        if logger:
            logger.debug("Persisted schema snapshot for %s (%d cols)", table_name, len(snapshot))
    except Exception as e:  # pylint: disable=broad-except
        if logger:
            logger.warning("Failed to persist schema snapshot for %s: %s", table_name, e)


def drop_table(
    base_path: Path,
    table_name: str,
    tables_cache: Dict[str, pd.DataFrame],
    schemas_cache: Dict[str, Dict],
    logger: Any = None
) -> None:
    """
    Drop CSV table by deleting the file and clearing cache.
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table to drop
        tables_cache: Cache dict to clear
        schemas_cache: Schema cache dict to clear
        logger: Optional logger
    """
    csv_file = file_ops.get_csv_path(base_path, table_name)
    if csv_file.exists():
        csv_file.unlink()
        if logger:
            logger.info(csv_const.LOG_TABLE_DROPPED, table_name)

    if table_name in tables_cache:
        del tables_cache[table_name]
    if table_name in schemas_cache:
        del schemas_cache[table_name]


def table_exists(base_path: Path, table_name: str) -> bool:
    """
    Check if CSV table exists by verifying file existence.
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table to check
    
    Returns:
        bool: True if CSV file exists
    """
    csv_file = file_ops.get_csv_path(base_path, table_name)
    return csv_file.exists()


def list_tables(base_path: Path, logger: Any = None) -> List[str]:
    """
    List all CSV tables in base_path directory.
    
    Args:
        base_path: Base directory for CSV files
        logger: Optional logger
    
    Returns:
        List[str]: List of table names (without .csv extension)
    """
    csv_files = list(base_path.glob(csv_const.CSV_GLOB_PATTERN))
    tables = [f.stem for f in csv_files]
    if logger:
        logger.debug(csv_const.LOG_FOUND_TABLES, len(tables), tables)
    return tables


def introspect_schema(base_path: Path, table_name: str, logger: Any = None) -> Dict[str, Any]:
    """
    Introspect CSV file to get actual columns and infer types.
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table to introspect
        logger: Optional logger
    
    Returns:
        Dict[str, Any]: Schema dict in zCLI format
    """
    csv_file = file_ops.get_csv_path(base_path, table_name)

    if not csv_file.exists():
        if logger:
            logger.warning(f"Cannot introspect non-existent table: {table_name}")
        return {}

    try:
        # Read just header + 10 rows for type inference
        df = pd.read_csv(csv_file, nrows=10)
        schema = schema_ops.introspect_dataframe_schema(df)

        # Overlay declared types from the persisted snapshot (SSOT). CSV headers
        # can't carry types, so inference alone yields phantom diffs (e.g. a
        # datetime read back as str). The snapshot — written at migrate time —
        # is authoritative for columns that exist on disk.
        snapshot = _load_schema_snapshot(base_path, table_name)
        if snapshot:
            for col, col_def in schema.items():
                snap = snapshot.get(col)
                if isinstance(snap, dict) and snap.get("type"):
                    col_def["type"] = snap["type"]

        if logger:
            logger.debug(f"Introspected schema for {table_name}: {len(schema)} columns")

        return schema

    except Exception as e:
        if logger:
            logger.error(f"Failed to introspect table {table_name}: {e}")
        return {}

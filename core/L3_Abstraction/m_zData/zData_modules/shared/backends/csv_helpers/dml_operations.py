# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv_helpers/dml_operations.py
"""
DML (Data Manipulation Language) operations for CSV adapter.

This module handles insert, select, update, delete, upsert, and aggregate operations.
"""

from zOS import Dict, Any, List, Optional
import pandas as pd

from . import constants as csv_const
from . import dataframe_utils as df_utils
from . import where_filtering as where_ops
from . import order_operations as order_ops
from . import join_operations as join_ops
from . import schema_operations as schema_ops


def insert(
    table: str,
    fields: List[str],
    values: List[Any],
    schemas_cache: Dict[str, Dict],
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> int:
    """
    Insert a row into CSV table and save to disk.
    
    Args:
        table: Table name
        fields: List of field names
        values: List of values
        schemas_cache: Schema cache dict
        load_table_func: Function to load table
        save_table_func: Function to save table
        tables_cache: Cache dict to update
        logger: Optional logger
    
    Returns:
        int: Auto-generated ID or row count
    """
    df = load_table_func(table)

    if values is None:
        values = []
    if fields is None:
        fields = []

    new_row = {field: value for field, value in zip(fields, values)}

    # Handle auto_increment
    schema = schemas_cache.get(table, {})
    auto_id_field = df_utils.detect_auto_id_field(schema, df)

    if auto_id_field and (auto_id_field not in new_row or not new_row.get(auto_id_field)):
        next_id = df_utils.calculate_next_auto_id(df, auto_id_field)
        new_row[auto_id_field] = next_id
        row_id = next_id
        if logger:
            logger.info(f"Auto-generated ID for {table}: {next_id}")
    else:
        row_id = len(df) + 1

    df = df_utils.append_row_to_df(df, new_row)

    save_table_func(table, df)
    tables_cache[table] = df

    if logger:
        logger.info(csv_const.LOG_ROW_INSERTED, table, row_id)
    return row_id


def insert_many(
    table: str,
    rows_data: List[Dict[str, Any]],
    schemas_cache: Dict[str, Dict],
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> List[int]:
    """
    Insert multiple rows into a CSV table in one write pass.

    Each row dict must already be fully processed (UUID, hash, transform applied).
    Auto-increment IDs are assigned sequentially starting after the current max.
    The DataFrame is saved to disk once after all rows are appended.

    Returns:
        List[int]: Auto-generated IDs for each inserted row, in order.
    """
    df = load_table_func(table)
    schema = schemas_cache.get(table, {})
    auto_id_field = df_utils.detect_auto_id_field(schema, df)

    row_ids = []
    new_rows = []
    next_id = df_utils.calculate_next_auto_id(df, auto_id_field) if auto_id_field else None

    for row in rows_data:
        new_row = dict(row)
        if auto_id_field and (auto_id_field not in new_row or not new_row.get(auto_id_field)):
            new_row[auto_id_field] = next_id
            row_ids.append(next_id)
            if logger:
                logger.info(f"Auto-generated ID for {table}: {next_id}")
            next_id += 1
        else:
            row_ids.append(new_row.get(auto_id_field, len(df) + len(new_rows) + 1))
        new_rows.append(new_row)

    new_df = pd.DataFrame(new_rows)
    df = pd.concat([df, new_df], ignore_index=True)

    save_table_func(table, df)
    tables_cache[table] = df

    if logger:
        logger.info(f"Bulk-inserted {len(row_ids)} row(s) into {table}: ids {row_ids}")
    return row_ids


def select(
    table,
    fields: Optional[List[str]],
    where: Optional[Dict[str, Any]],
    joins: Optional[List[Dict]],
    order: Optional[Any],
    limit: Optional[int],
    offset: int,
    auto_join: bool,
    schema: Optional[Dict],
    load_table_func,
    logger: Any = None,
    distinct: bool = False
) -> List[Dict[str, Any]]:
    """
    Select rows from CSV table(s) with WHERE, JOINs, ORDER BY, LIMIT.
    
    Args:
        table: Table name (str) or list of tables
        fields: List of field names or ["*"]
        where: WHERE conditions
        joins: Manual JOIN conditions
        order: ORDER BY clauses
        limit: Max rows to return
        offset: Number of rows to skip
        auto_join: Auto-detect JOINs from schema
        schema: Schema for AUTO JOIN detection
        load_table_func: Function to load table
        logger: Optional logger
    
    Returns:
        List[Dict[str, Any]]: List of row dicts
    """
    tables = [table] if isinstance(table, str) else table
    is_multi_table = len(tables) > 1 or joins

    if is_multi_table:
        if logger:
            logger.info(csv_const.LOG_JOIN_MULTI_TABLE, " + ".join(tables))
        df = join_ops.join_tables(
            load_table_func, tables, joins=joins, schema=schema,
            auto_join=auto_join, logger=logger
        )

        if fields and fields != ["*"]:
            fields = join_ops.resolve_field_names(fields, df.columns.tolist())
    else:
        df = load_table_func(table)

    if where:
        df = where_ops.apply_where_filter(df, where, logger)

    if fields and fields != ["*"]:
        available_fields = [f for f in fields if f in df.columns]
        if available_fields:
            df = df[available_fields]

    if distinct:
        df = df.drop_duplicates()

    if order:
        df = order_ops.apply_order(df, order)

    # Apply LIMIT + OFFSET pagination
    if limit is not None:
        end = offset + limit
        df = df.iloc[offset:end]
    elif offset > 0:
        df = df.iloc[offset:]

    # Emit plain Python: pd.NA/NaN/NaT → None, numpy scalars → int/float/bool.
    rows = schema_ops.sanitize_records(df.to_dict('records'))

    table_name = " + ".join(tables) if is_multi_table else table
    if logger:
        logger.info("Selected %d rows from %s", len(rows), table_name)
    return rows


def _dtype_safe_assignment(df: pd.DataFrame, field: str, value: Any) -> Any:
    """Make a cell assignment dtype-safe instead of letting pandas raise (zOS#59).

    A digits-only string submitted from a form can arrive here as ``int`` (the
    token-injection round trip drops the quotes on numeric-looking text), and
    pandas' string dtype (``string`` extension / the ``str`` default that
    ``read_csv`` infers from pandas 3) REJECTS non-string scalars at ``.loc``
    assignment — the field-reported ``TypeError: Invalid value '182' for dtype
    'str'``. Symmetric guards, schema-true storage:

      - non-string scalar → string-dtype column: store ``str(value)`` (a str
        column holds the string form; the CSV round-trip is identical)
      - string value → non-object (numeric/bool) column: relax the column to
        ``object`` first (pre-existing behavior, unchanged)

    Returns the (possibly coerced) value; may relax the column dtype in place.
    """
    dtype = df[field].dtype
    if isinstance(value, str):
        if dtype != object:
            df[field] = df[field].astype(object)
        return value
    if value is not None and isinstance(dtype, pd.StringDtype):
        return str(value)
    return value


def update(
    table: str,
    fields: List[str],
    values: List[Any],
    where: Dict[str, Any],
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> int:
    """
    Update rows in CSV table matching WHERE condition.
    
    Args:
        table: Table name
        fields: List of fields to update
        values: List of new values
        where: WHERE condition dict
        load_table_func: Function to load table
        save_table_func: Function to save table
        tables_cache: Cache dict to update
        logger: Optional logger
    
    Returns:
        int: Number of rows updated
    """
    df = load_table_func(table)

    if where:
        mask = where_ops.create_where_mask(df, where, logger)
    else:
        mask = pd.Series([True] * len(df), index=df.index)

    for field, value in zip(fields, values):
        if field in df.columns:
            value = _dtype_safe_assignment(df, field, value)
            df.loc[mask, field] = value

    rows_affected = mask.sum()

    save_table_func(table, df)
    tables_cache[table] = df

    if logger:
        logger.info("Updated %d rows in CSV table %s", rows_affected, table)
    return int(rows_affected)


def delete(
    table: str,
    where: Dict[str, Any],
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> int:
    """
    Delete rows from CSV table matching WHERE condition.
    
    Args:
        table: Table name
        where: WHERE condition dict
        load_table_func: Function to load table
        save_table_func: Function to save table
        tables_cache: Cache dict to update
        logger: Optional logger
    
    Returns:
        int: Number of rows deleted
    """
    df = load_table_func(table)
    original_count = len(df)

    if where:
        mask = where_ops.create_where_mask(df, where, logger)
        df = df.loc[~mask]
    else:
        df = pd.DataFrame(columns=df.columns)

    rows_deleted = original_count - len(df)

    save_table_func(table, df)
    tables_cache[table] = df

    if logger:
        logger.info("Deleted %d rows from CSV table %s", rows_deleted, table)
    return rows_deleted


def truncate(
    table: str,
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> int:
    """
    Truncate a CSV table: remove all rows and preserve column headers.

    Unlike delete-all-rows, truncate also resets the auto-increment PK sequence —
    the next insert will receive id=1 because calculate_next_auto_id reads max(id)
    on an empty table and falls back to 1.

    Args:
        table: Table name
        load_table_func: Function to load table DataFrame
        save_table_func: Function to persist table DataFrame
        tables_cache: In-memory cache to update
        logger: Optional logger

    Returns:
        int: Number of rows removed
    """
    df = load_table_func(table)
    original_count = len(df)

    empty_df = pd.DataFrame(columns=df.columns)

    save_table_func(table, empty_df)
    tables_cache[table] = empty_df

    if logger:
        logger.info("[TRUNCATE] Removed %d rows from '%s'; PK sequence reset to 1", original_count, table)
    return original_count


def _extract_inserted_row_id(new_row: Dict[str, Any], conflict_fields: List[str], df,
                              fallback: int = None) -> int:
    """
    Return the actual id of an upserted row.

    Prefers the value from the first conflict field (e.g. `id`) when the row
    carries an explicit id, so callers like RETURNING can re-fetch by the
    correct key.  Falls back to `fallback` if provided, otherwise len(df).
    """
    if conflict_fields:
        id_field = conflict_fields[0]
        val = new_row.get(id_field)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return fallback if fallback is not None else len(df)


def upsert(
    table: str,
    fields: List[str],
    values: List[Any],
    conflict_fields: List[str],
    load_table_func,
    save_table_func,
    tables_cache: Dict[str, pd.DataFrame],
    logger: Any = None
) -> int:
    """
    Insert or update row with conflict resolution.
    
    Args:
        table: Table name
        fields: List of fields
        values: List of values
        conflict_fields: Fields to check for conflicts
        load_table_func: Function to load table
        save_table_func: Function to save table
        tables_cache: Cache dict to update
        logger: Optional logger
    
    Returns:
        int: Row ID
    """
    df = load_table_func(table)
    new_row = {field: value for field, value in zip(fields, values)}

    if conflict_fields and len(df) > 0:
        mask = pd.Series([True] * len(df), index=df.index)
        for conflict_field in conflict_fields:
            if conflict_field in new_row and conflict_field in df.columns:
                mask = mask & (df[conflict_field] == new_row[conflict_field])

        if mask.any():
            for field, value in zip(fields, values):
                if field in df.columns:
                    value = _dtype_safe_assignment(df, field, value)
                    df.loc[mask, field] = value
            if logger:
                logger.info("Updated existing row in CSV table %s", table)
            row_id = _extract_inserted_row_id(new_row, conflict_fields, df,
                                              fallback=int(df[mask].index[0]) + 1)
        else:
            df = df_utils.append_row_to_df(df, new_row)
            row_id = _extract_inserted_row_id(new_row, conflict_fields, df)
            if logger:
                logger.info("Inserted new row into CSV table %s", table)
    else:
        df = df_utils.append_row_to_df(df, new_row)
        row_id = _extract_inserted_row_id(new_row, conflict_fields, df)
        if logger:
            logger.info("Inserted new row into CSV table %s", table)

    save_table_func(table, df)
    tables_cache[table] = df

    return int(row_id)


def aggregate(
    table: str,
    function: str,
    field: Optional[str],
    where: Optional[Dict[str, Any]],
    group_by,   # Optional[Union[str, List[str]]]
    load_table_func,
    logger: Any = None,
    alias: Optional[str] = None
) -> Any:
    """
    Perform aggregation function on table data using pandas.
    
    Args:
        table: Table name
        function: Aggregation function (count, sum, avg, min, max)
        field: Field name to aggregate
        where: Optional WHERE clause
        group_by: Optional field(s) to group by — str or list of str
        load_table_func: Function to load table
        logger: Optional logger
    
    Returns:
        Scalar value or dict/list for GROUP BY aggregation
    """
    # Validate function
    valid_functions = ["count", "sum", "avg", "min", "max"]
    function_lower = function.lower()
    if function_lower not in valid_functions:
        raise ValueError(f"Invalid aggregate function '{function}'. Must be one of: {valid_functions}")

    # Validate field requirement
    if function_lower != "count" and not field:
        raise ValueError(f"Aggregate function '{function}' requires a field name")

    # Load table
    try:
        df = load_table_func(table)
    except Exception as e:
        if logger:
            logger.error(f"Failed to load table {table}: {e}")
        raise RuntimeError(f"Failed to load table {table}: {e}") from e

    # Apply WHERE filter
    if where:
        try:
            mask = where_ops.create_where_mask(df, where, logger)
            df = df[mask].copy()
        except Exception as e:
            if logger:
                logger.error(f"WHERE clause filtering failed: {e}")
            raise RuntimeError(f"WHERE clause filtering failed: {e}") from e

    # Perform aggregation
    try:
        if group_by:
            # Normalise to list — supports single str or list of str
            group_fields = [group_by] if isinstance(group_by, str) else list(group_by)
            missing = [f for f in group_fields if f not in df.columns]
            if missing:
                raise ValueError(f"GROUP BY field(s) {missing} not found in table")

            if function_lower == "count":
                if field and field in df.columns:
                    result_series = df.groupby(group_fields)[field].count()
                else:
                    result_series = df.groupby(group_fields).size()
            elif function_lower == "sum":
                result_series = df.groupby(group_fields)[field].sum()
            elif function_lower == "avg":
                result_series = df.groupby(group_fields)[field].mean()
            elif function_lower == "min":
                result_series = df.groupby(group_fields)[field].min()
            elif function_lower == "max":
                result_series = df.groupby(group_fields)[field].max()
            else:
                raise ValueError(f"Unsupported aggregate function: {function}")

            result = result_series.to_dict()

            if logger:
                logger.info(
                    f"Aggregation {function}({field or '*'}) on {table} "
                    f"grouped by {group_fields}: {len(result)} groups"
                )

            # Reshape to row dicts when alias is provided.
            # Multi-field keys arrive as tuples; single-field keys are scalars.
            if alias:
                result = [
                    {**dict(zip(group_fields, k if isinstance(k, tuple) else (k,))), alias: v}
                    for k, v in result.items()
                ]

            return result
        else:
            # Simple aggregation
            if function_lower == "count":
                if field and field in df.columns:
                    result = int(df[field].count())
                else:
                    result = len(df)
            elif function_lower == "sum":
                if field not in df.columns:
                    raise ValueError(f"Field '{field}' not found in table")
                result = df[field].sum()
                result = int(result) if pd.api.types.is_integer_dtype(df[field]) else float(result)
            elif function_lower == "avg":
                if field not in df.columns:
                    raise ValueError(f"Field '{field}' not found in table")
                result = float(df[field].mean()) if len(df) > 0 else None
            elif function_lower == "min":
                if field not in df.columns:
                    raise ValueError(f"Field '{field}' not found in table")
                result = df[field].min() if len(df) > 0 else None
            elif function_lower == "max":
                if field not in df.columns:
                    raise ValueError(f"Field '{field}' not found in table")
                result = df[field].max() if len(df) > 0 else None

            # Handle empty results
            if result is None or (isinstance(result, float) and pd.isna(result)):
                result = 0 if function_lower == "count" else None

            if logger:
                logger.info(f"Aggregation {function}({field or '*'}) on {table}: {result}")
            return result

    except Exception as e:
        if logger:
            logger.error(f"Aggregation failed: {e}")
        raise RuntimeError(f"Aggregation query failed: {e}") from e

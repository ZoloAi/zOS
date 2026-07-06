# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/join_operations.py
"""
JOIN operations for CSV adapter.

This module handles multi-table JOIN logic including manual JOINs,
auto-detected JOINs from foreign keys, and field name resolution.
"""

from zOS import List, Dict, Any, Optional, Tuple
import pandas as pd

from ..join_policy import resolve_auto_join, to_pandas_how, DEFAULT_AUTO_JOIN


def join_tables(
    load_table_func,
    tables: List[str],
    joins: Optional[List[Dict]] = None,
    schema: Optional[Dict] = None,
    auto_join: bool = False,
    logger: Optional[Any] = None
) -> pd.DataFrame:
    """
    Join multiple CSV tables using pandas merge.
    
    Main orchestrator for multi-table JOINs. Supports manual JOIN definitions,
    auto-detection from foreign keys, and cross joins.
    
    Args:
        load_table_func: Function to load a table (returns DataFrame)
        tables: List of table names to join
        joins: Optional list of manual JOIN definitions
        schema: Optional schema dict for auto-join FK detection
        auto_join: Whether to auto-detect JOINs from schema
        logger: Optional logger for diagnostic output
    
    Returns:
        pd.DataFrame: Joined DataFrame with prefixed columns
    
    Example:
        >>> joins = [{"table": "orders", "on": "users.id = orders.user_id"}]
        >>> df = join_tables(load_func, ["users", "orders"], joins=joins)
    
    Note:
        - Adds table prefixes to all columns (table.column)
        - Supports inner, left, right, outer, cross joins
        - Falls back to cross join if no join conditions specified
    """
    if not tables or len(tables) < 2:
        return load_table_func(tables[0]) if tables else pd.DataFrame()

    # Load base table (copy to avoid mutating the adapter's in-memory cache)
    base_table = tables[0]
    result_df = load_table_func(base_table).copy()

    # Add table prefix to columns to avoid conflicts
    result_df.columns = [f"{base_table}.{col}" for col in result_df.columns]

    remaining_tables = tables[1:]

    auto_enabled, auto_join_type = resolve_auto_join(auto_join)
    if auto_enabled and schema:
        # Auto-detect joins from FK relationships (SSOT: join_policy → pandas how)
        if logger:
            logger.info("[JOIN] Auto-joining CSV tables (FK, %s) based on relationships", auto_join_type)
        result_df = auto_join_tables(
            result_df, base_table, remaining_tables, schema, load_table_func, logger,
            how=to_pandas_how(auto_join_type)
        )
    elif joins:
        # Manual join definitions
        if logger:
            logger.info("[JOIN] Building manual JOINs for CSV")
        result_df = manual_join_tables(
            result_df, base_table, joins, load_table_func, logger
        )
    else:
        # Cross join (Cartesian product)
        if logger:
            logger.warning("[JOIN] Multiple tables without JOIN specification - using CROSS JOIN")
        for table_name in remaining_tables:
            right_df = load_table_func(table_name).copy()
            right_df.columns = [f"{table_name}.{col}" for col in right_df.columns]
            result_df['_join_key'] = 1
            right_df['_join_key'] = 1
            result_df = result_df.merge(right_df, on='_join_key', how='outer')
            result_df = result_df.drop('_join_key', axis=1)

    return result_df


def auto_join_tables(
    base_df: pd.DataFrame,
    base_table: str,
    remaining_tables: List[str],
    schema: Dict,
    load_table_func,
    logger: Optional[Any] = None,
    how: str = "left"
) -> pd.DataFrame:
    """
    Auto-join CSV tables based on FK relationships.
    
    Detects foreign key relationships from schema and automatically joins tables.
    Tries forward joins (new table has FK to joined table) and reverse joins
    (joined table has FK to new table).
    
    Args:
        base_df: Base DataFrame with prefixed columns
        base_table: Name of base table
        remaining_tables: List of tables to join
        schema: Schema dict with FK definitions
        load_table_func: Function to load a table
        logger: Optional logger for diagnostic output
    
    Returns:
        pd.DataFrame: Joined DataFrame
    
    Note:
        - Tries forward join first (new table → joined table)
        - Falls back to reverse join (joined table → new table)
        - Logs warning if no FK relationship found
    """
    result_df = base_df
    joined_tables = [base_table]

    for table_name in remaining_tables:
        right_df = load_table_func(table_name).copy()
        right_df.columns = [f"{table_name}.{col}" for col in right_df.columns]

        ctx = {
            "right_df": right_df,
            "joined_tables": joined_tables,
            "schema": schema,
            "logger": logger,
            "how": how
        }

        # Try forward join (this table has FK to joined table)
        result_df, join_found = try_forward_join(result_df, table_name, ctx)

        # Try reverse join (joined table has FK to this table)
        if not join_found:
            result_df, join_found = try_reverse_join(result_df, table_name, ctx)

        if join_found:
            joined_tables.append(table_name)
        else:
            if logger:
                logger.warning("[JOIN] Could not auto-detect join for CSV table: %s", table_name)

    return result_df


def try_forward_join(
    result_df: pd.DataFrame,
    table_name: str,
    ctx: Dict[str, Any]
) -> Tuple[pd.DataFrame, bool]:
    """
    Try to join table that has FK to already-joined tables.
    
    Checks if the new table has a foreign key pointing to any already-joined table.
    
    Args:
        result_df: Current joined DataFrame
        table_name: Name of table to join
        ctx: Context dict with right_df, joined_tables, schema, logger
    
    Returns:
        Tuple of (updated_df, join_found)
    
    Example:
        Schema: orders.user_id → users.id
        If users is already joined, can join orders via user_id FK
    
    Note:
        - Looks for "fk" field in schema pointing to joined table
        - Uses inner join by default
    """
    right_df = ctx["right_df"]
    joined_tables = ctx["joined_tables"]
    schema = ctx["schema"]
    logger = ctx.get("logger")
    how = ctx.get("how", "left")

    table_schema = schema.get(table_name, {})

    for field_name, field_def in table_schema.items():
        if not isinstance(field_def, dict):
            continue

        fk = field_def.get("fk")
        if not fk:
            continue

        try:
            ref_table, ref_column = fk.split(".", 1)
        except ValueError:
            continue

        if ref_table in joined_tables:
            left_on = f"{ref_table}.{ref_column}"
            right_on = f"{table_name}.{field_name}"

            if left_on in result_df.columns and right_on in right_df.columns:
                result_df = result_df.merge(
                    right_df, left_on=left_on, right_on=right_on, how=how
                )
                if logger:
                    logger.debug("  Auto-detected CSV %s JOIN: %s.%s = %s.%s",
                               how, ref_table, ref_column, table_name, field_name)
                return result_df, True

    return result_df, False


def try_reverse_join(
    result_df: pd.DataFrame,
    table_name: str,
    ctx: Dict[str, Any]
) -> Tuple[pd.DataFrame, bool]:
    """
    Try to join when already-joined table has FK to this table.
    
    Checks if any already-joined table has a foreign key pointing to the new table.
    
    Args:
        result_df: Current joined DataFrame
        table_name: Name of table to join
        ctx: Context dict with right_df, joined_tables, schema, logger
    
    Returns:
        Tuple of (updated_df, join_found)
    
    Example:
        Schema: users.company_id → companies.id
        If users is already joined, can join companies via reverse FK
    
    Note:
        - Looks for FK in already-joined tables pointing to new table
        - Uses inner join by default
    """
    right_df = ctx["right_df"]
    joined_tables = ctx["joined_tables"]
    schema = ctx["schema"]
    logger = ctx.get("logger")
    how = ctx.get("how", "left")

    for already_joined in joined_tables[:]:
        joined_schema = schema.get(already_joined, {})

        for field_name, field_def in joined_schema.items():
            if not isinstance(field_def, dict):
                continue

            fk = field_def.get("fk")
            if not fk:
                continue

            try:
                ref_table, ref_column = fk.split(".", 1)
            except ValueError:
                continue

            if ref_table == table_name:
                left_on = f"{already_joined}.{field_name}"
                right_on = f"{table_name}.{ref_column}"

                if left_on in result_df.columns and right_on in right_df.columns:
                    result_df = result_df.merge(
                        right_df, left_on=left_on, right_on=right_on, how=how
                    )
                    if logger:
                        logger.debug("  Auto-detected CSV %s JOIN (reverse): %s.%s = %s.%s",
                                   how, already_joined, field_name, table_name, ref_column)
                    return result_df, True

    return result_df, False


def manual_join_tables(
    base_df: pd.DataFrame,
    _base_table: str,
    joins: List[Dict],
    load_table_func,
    logger: Optional[Any] = None
) -> pd.DataFrame:
    """
    Perform manual joins on CSV tables.
    
    Executes explicit JOIN definitions with specified conditions and types.
    
    Args:
        base_df: Base DataFrame with prefixed columns
        _base_table: Name of base table (unused, kept for signature consistency)
        joins: List of JOIN definitions:
            - table: Table name to join
            - on: Join condition (e.g., "users.id = orders.user_id")
            - type: Join type (INNER, LEFT, RIGHT, FULL, CROSS)
        load_table_func: Function to load a table
        logger: Optional logger for diagnostic output
    
    Returns:
        pd.DataFrame: Joined DataFrame
    
    Example:
        >>> joins = [
        ...     {"table": "orders", "on": "users.id = orders.user_id", "type": "LEFT"},
        ...     {"table": "products", "on": "orders.product_id = products.id"}
        ... ]
        >>> df = manual_join_tables(base_df, "users", joins, load_func)
    
    Note:
        - Parses ON clause to extract left_on and right_on
        - Supports INNER, LEFT, RIGHT, FULL (outer), CROSS joins
        - Defaults to INNER join if type not specified
    """
    result_df = base_df

    for join_def in joins:
        join_type = join_def.get("type", "INNER").lower()
        table_name = join_def.get("table")
        on_clause = join_def.get("on")
        if isinstance(on_clause, str):
            on_clause = on_clause.strip().strip('"').strip("'")

        if not table_name or not on_clause:
            if logger:
                logger.warning("[JOIN] Skipping invalid CSV join: %s", join_def)
            continue

        right_df = load_table_func(table_name).copy()
        right_df.columns = [f"{table_name}.{col}" for col in right_df.columns]

        # Parse ON clause: "users.id = posts.user_id"
        try:
            left_part, right_part = on_clause.split("=", 1)
            left_on = left_part.strip()
            right_on = right_part.strip()

            # Map SQL join types to pandas how parameter
            how_map = {
                "inner": "inner",
                "left": "left",
                "right": "right",
                "full": "outer",
                "cross": "cross"
            }
            how = how_map.get(join_type, "inner")

            if how == "cross":
                result_df['_join_key'] = 1
                right_df['_join_key'] = 1
                result_df = result_df.merge(right_df, on='_join_key', how='outer')
                result_df = result_df.drop('_join_key', axis=1)
            else:
                result_df = result_df.merge(
                    right_df,
                    left_on=left_on,
                    right_on=right_on,
                    how=how
                )

            if logger:
                logger.debug("  Added CSV %s JOIN %s", join_type.upper(), table_name)
        except Exception as e:
            if logger:
                logger.error("Failed to parse CSV join ON clause '%s': %s", on_clause, e)

    return result_df


def resolve_field_names(
    fields: List[str],
    available_columns: List[str]
) -> List[str]:
    """
    Resolve field names for multi-table queries.
    
    Matches requested fields to available columns, handling table prefixes.
    
    Args:
        fields: List of requested field names
        available_columns: List of available column names (with table prefixes)
    
    Returns:
        List[str]: Resolved field names
    
    Example:
        >>> fields = ["id", "name"]
        >>> available = ["users.id", "users.name", "orders.id"]
        >>> resolve_field_names(fields, available)
        ['users.id', 'users.name']
    
    Note:
        - Exact matches preferred
        - Falls back to suffix matching (table.field)
        - Logs warning if field not found
    """
    resolved = []
    for field in fields:
        if field in available_columns:
            resolved.append(field)
        else:
            # Try to find a match with table prefix
            matches = [col for col in available_columns if col.endswith(f".{field}")]
            if matches:
                resolved.append(matches[0])
            # Note: Warning would be logged by caller if needed
    return resolved

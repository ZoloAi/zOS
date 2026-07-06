# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/where_filtering.py
"""
WHERE clause filtering for CSV adapter.

This module handles WHERE clause parsing and boolean mask creation for DataFrame filtering.
Supports complex operators (gt, lt, like, in, etc.) and OR conditions.
"""

from zOS import Dict, Any, List, Optional
import pandas as pd

try:
    from ...operators import (
        normalize_operator,
        OP_LIKE, OP_NOTLIKE, OP_NIN, OP_NOTBETWEEN, OP_IN,
        OP_EQ, OP_NE, OP_GT, OP_GTE, OP_LT, OP_LTE, OP_NULL, OP_NOTNULL,
        OP_AND, OP_OR,
    )
except ImportError:  # pragma: no cover - flat import fallback
    from operators import (
        normalize_operator,
        OP_LIKE, OP_NOTLIKE, OP_NIN, OP_NOTBETWEEN, OP_IN,
        OP_EQ, OP_NE, OP_GT, OP_GTE, OP_LT, OP_LTE, OP_NULL, OP_NOTNULL,
        OP_AND, OP_OR,
    )


def create_where_mask(
    df: pd.DataFrame,
    where: Any,
    logger: Optional[Any] = None
) -> pd.Series:
    """
    Create boolean mask for WHERE clause with operator support.
    
    Parses WHERE conditions and builds a pandas boolean Series for filtering.
    Supports equality, comparison, LIKE, IN, IS NULL, and OR conditions.
    
    Args:
        df: DataFrame to filter
        where: WHERE condition (dict, str, or None)
        logger: Optional logger for warnings
    
    Returns:
        pd.Series: Boolean mask (True for matching rows)
    
    Example:
        >>> df = pd.DataFrame({"age": [18, 25, 30], "city": ["NYC", "LA", "NYC"]})
        >>> mask = create_where_mask(df, {"age__gt": 20, "city": "NYC"})
        >>> df[mask]
           age city
        2   30  NYC
    
    Note:
        - Returns all True if where is None/empty
        - Supports dict format (recommended) and simple string format
        - Handles type coercion for CSV string columns
    """
    if not where or len(df) == 0:
        return pd.Series([True] * len(df), index=df.index)

    # Handle string WHERE clauses (simple equality only)
    if isinstance(where, str):
        if logger:
            logger.warning(
                "String WHERE clauses not fully supported in CSV adapter. "
                "Use dict format for complex queries."
            )
        # Parse simple "field = 'value'" format
        if " = " in where:
            field, value = where.split(" = ", 1)
            field = field.strip()
            value = value.strip().strip("'\"")
            where = {field: value}
        else:
            if logger:
                logger.error("Cannot parse WHERE clause: %s", where)
            return pd.Series([True] * len(df), index=df.index)

    mask = pd.Series([True] * len(df), index=df.index)

    for field, condition in where.items():
        # Handle AND conditions (grouped precedence: {"$and": [cond1, cond2]})
        if normalize_operator(field) == OP_AND:
            if isinstance(condition, list) and condition:
                and_mask = create_and_mask(df, condition, logger)
                mask = mask & and_mask
            continue

        # Handle OR conditions
        if normalize_operator(field) == OP_OR:
            if isinstance(condition, list) and condition:
                or_mask = create_or_mask(df, condition, logger)
                mask = mask & or_mask
            continue

        if field not in df.columns:
            if logger:
                logger.warning("Field '%s' not in table columns", field)
            continue

        # Handle IS NULL
        if condition is None:
            mask = mask & df[field].isna()
            continue

        # Handle IN operator (list values) with type coercion
        if isinstance(condition, list):
            # Fix: Ensure condition values match column dtype
            try:
                col_dtype = df[field].dtype
                if col_dtype == 'object':  # String column
                    # Convert all list values to strings
                    coerced_list = [str(v) for v in condition]
                    mask = mask & df[field].astype(str).isin(coerced_list)
                else:
                    mask = mask & df[field].isin(condition)
            except (ValueError, TypeError):
                # Fallback: convert to strings
                coerced_list = [str(v) for v in condition]
                mask = mask & df[field].astype(str).isin(coerced_list)
            continue

        # Handle complex operators (dict values)
        if isinstance(condition, dict):
            mask = apply_operator_conditions(df, field, condition, mask, logger)
            continue

        # Simple equality with type coercion
        # Fix: CSV stores everything as strings, but WHERE may use ints/floats
        try:
            # Try to match the column's dtype
            col_dtype = df[field].dtype
            if col_dtype == 'object':  # String column
                # Convert condition to string for comparison
                mask = mask & (df[field].astype(str) == str(condition))
            else:
                # Numeric column - coerce condition to column dtype before comparing
                try:
                    condition_converted = col_dtype.type(condition)
                    mask = mask & (df[field] == condition_converted)
                except (ValueError, TypeError):
                    # Fallback: string comparison
                    mask = mask & (df[field].astype(str) == str(condition))
        except (ValueError, TypeError):
            # Fallback: convert both to strings and compare
            mask = mask & (df[field].astype(str) == str(condition))

    return mask


def apply_operator_conditions(
    df: pd.DataFrame,
    field: str,
    condition: Dict[str, Any],
    mask: pd.Series,
    logger: Optional[Any] = None
) -> pd.Series:
    """
    Apply complex operator conditions to mask with type coercion.
    
    Handles operators like $GT, $LT, $LIKE, $IN, $NULL with proper type handling.
    
    Args:
        df: DataFrame being filtered
        field: Field name to apply operators to
        condition: Dict of {operator: value} pairs
        mask: Current boolean mask
        logger: Optional logger for warnings
    
    Returns:
        pd.Series: Updated boolean mask
    
    Example:
        >>> df = pd.DataFrame({"age": [18, 25, 30]})
        >>> mask = pd.Series([True, True, True])
        >>> condition = {"$GT": 20, "$LT": 28}
        >>> mask = apply_operator_conditions(df, "age", condition, mask)
        >>> df[mask]
           age
        1   25
    
    Note:
        - Supports $EQ, $NE, $GT, $GTE, $LT, $LTE, $LIKE, $IN, $NULL, $NOTNULL
        - Also supports symbolic operators: =, !=, >, >=, <, <=
        - Handles type coercion for string/numeric comparisons
    """
    for op, value in condition.items():
        n_op = normalize_operator(op)

        # Special case: LIKE requires pattern conversion
        # Use fullmatch so anchoring works correctly for prefix (%val), suffix (val%),
        # and contains (%val%) patterns — str.match only anchors at the start.
        if n_op == OP_LIKE:
            pattern = value.replace("%", ".*").replace("_", ".")
            mask = mask & df[field].astype(str).str.fullmatch(pattern, na=False)
            continue

        # Special case: NOT LIKE — negated pattern match
        if n_op == OP_NOTLIKE:
            pattern = value.replace("%", ".*").replace("_", ".")
            mask = mask & ~df[field].astype(str).str.fullmatch(pattern, na=False)
            continue

        # Special case: NIN (NOT IN) — list exclusion
        if n_op == OP_NIN and isinstance(value, list):
            try:
                col_dtype = df[field].dtype
                if col_dtype == 'object':
                    coerced_list = [str(v) for v in value]
                    mask = mask & ~df[field].astype(str).isin(coerced_list)
                else:
                    mask = mask & ~df[field].isin(value)
            except (ValueError, TypeError):
                coerced_list = [str(v) for v in value]
                mask = mask & ~df[field].astype(str).isin(coerced_list)
            continue

        # Special case: NOTBETWEEN — range exclusion
        if n_op == OP_NOTBETWEEN and isinstance(value, list) and len(value) == 2:
            min_val, max_val = value[0], value[1]
            try:
                mask = mask & ~((df[field] >= min_val) & (df[field] <= max_val))
            except (ValueError, TypeError):
                pass
            continue

        # Special case: IN requires list check with type coercion
        if n_op == OP_IN and isinstance(value, list):
            try:
                col_dtype = df[field].dtype
                if col_dtype == 'object':  # String column
                    coerced_list = [str(v) for v in value]
                    mask = mask & df[field].astype(str).isin(coerced_list)
                else:
                    mask = mask & df[field].isin(value)
            except (ValueError, TypeError):
                coerced_list = [str(v) for v in value]
                mask = mask & df[field].astype(str).isin(coerced_list)
            continue

        # Helper to apply operator with type coercion
        # pylint: disable=unused-argument,eval-used
        # Note: value used in eval; eval safe here (op_func_str is from predefined set)
        def apply_op(field, op_func_str, value):
            try:
                col_dtype = df[field].dtype
                if col_dtype == 'object':  # String column
                    # For comparison ops on strings, convert value to string
                    if op_func_str in ['==', '!=']:
                        return eval(f"df[field].astype(str) {op_func_str} str(value)")
                    else:
                        # For >, <, >=, <= on strings, use lexicographic comparison
                        return eval(f"df[field].astype(str) {op_func_str} str(value)")
                else:
                    # Numeric column - use as-is
                    return eval(f"df[field] {op_func_str} value")
            except (ValueError, TypeError):
                # Fallback: string comparison
                return eval(f"df[field].astype(str) {op_func_str} str(value)")

        # Standard operators map with type coercion — keyed by canonical token
        # (symbolic/uppercase forms are folded in via normalize_operator above).
        # pylint: disable=cell-var-from-loop
        op_map = {
            OP_EQ: lambda f, v: apply_op(f, '==', v),
            OP_NE: lambda f, v: apply_op(f, '!=', v),
            OP_GT: lambda f, v: apply_op(f, '>', v),
            OP_GTE: lambda f, v: apply_op(f, '>=', v),
            OP_LT: lambda f, v: apply_op(f, '<', v),
            OP_LTE: lambda f, v: apply_op(f, '<=', v),
            OP_NULL: lambda f, v: df[f].isna(),
            OP_NOTNULL: lambda f, v: df[f].notna(),
        }

        op_func = op_map.get(n_op)
        if op_func:
            mask = mask & op_func(field, value)
        else:
            if logger:
                logger.warning("Unsupported operator: %s", op)

    return mask


def create_and_mask(
    df: pd.DataFrame,
    and_list: List[Dict[str, Any]],
    logger: Optional[Any] = None
) -> pd.Series:
    """
    Create AND mask from list of condition dicts (grouped precedence).

    All conditions must match — used for {"$and": [cond1, cond2]} nodes
    produced by the parentheses grouping parser.

    Args:
        df: DataFrame to filter
        and_list: List of WHERE condition dicts
        logger: Optional logger for warnings

    Returns:
        pd.Series: Boolean mask (True if all conditions match)

    Example:
        >>> and_list = [{"$or": [{"country": "USA"}, {"country": "Ireland"}]}, {"score": {"$gt": 85}}]
        >>> mask = create_and_mask(df, and_list)
    """
    and_mask = pd.Series([True] * len(df), index=df.index)
    for condition_dict in and_list:
        if not isinstance(condition_dict, dict):
            continue
        cond_mask = create_where_mask(df, condition_dict, logger)
        and_mask = and_mask & cond_mask
    return and_mask


def create_or_mask(
    df: pd.DataFrame,
    or_list: List[Dict[str, Any]],
    logger: Optional[Any] = None
) -> pd.Series:
    """
    Create OR mask from list of condition dicts.
    
    Builds a boolean mask where any of the conditions in the list match.
    
    Args:
        df: DataFrame to filter
        or_list: List of WHERE condition dicts
        logger: Optional logger for warnings
    
    Returns:
        pd.Series: Boolean mask (True if any condition matches)
    
    Example:
        >>> df = pd.DataFrame({"city": ["NYC", "LA", "SF"]})
        >>> or_list = [{"city": "NYC"}, {"city": "LA"}]
        >>> mask = create_or_mask(df, or_list)
        >>> df[mask]
          city
        0  NYC
        1   LA
    
    Note:
        - Combines conditions with logical OR
        - Returns all False if or_list is empty
    """
    or_mask = pd.Series([False] * len(df), index=df.index)

    for condition_dict in or_list:
        if not isinstance(condition_dict, dict):
            continue

        cond_mask = create_where_mask(df, condition_dict, logger)
        or_mask = or_mask | cond_mask

    return or_mask


def apply_where_filter(
    df: pd.DataFrame,
    where: Any,
    logger: Optional[Any] = None
) -> pd.DataFrame:
    """
    Apply WHERE clause filtering to DataFrame.
    
    Convenience function that creates mask and applies it to DataFrame.
    
    Args:
        df: DataFrame to filter
        where: WHERE condition
        logger: Optional logger for warnings
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    
    Example:
        >>> df = pd.DataFrame({"age": [18, 25, 30]})
        >>> filtered = apply_where_filter(df, {"age__gt": 20})
        >>> len(filtered)
        2
    
    Note:
        - Uses .loc to avoid index alignment issues
        - Returns original DataFrame if where is None
    """
    mask = create_where_mask(df, where, logger)
    # Use .loc to avoid index alignment issues
    return df.loc[mask]

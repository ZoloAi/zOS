# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/order_operations.py
"""
ORDER BY operations for CSV adapter.

This module handles ORDER BY clause parsing and DataFrame sorting.
Supports string, list, and dict formats.
"""

from zOS import Union, List, Dict
import pandas as pd


def apply_order(
    df: pd.DataFrame,
    order: Union[str, List, Dict]
) -> pd.DataFrame:
    """
    Apply ORDER BY to DataFrame.
    
    Routes to appropriate handler based on order format (string, list, or dict).
    
    Args:
        df: DataFrame to sort
        order: ORDER BY specification (str, list, or dict)
    
    Returns:
        pd.DataFrame: Sorted DataFrame
    
    Example:
        >>> df = pd.DataFrame({"name": ["Bob", "Alice"], "age": [30, 25]})
        >>> apply_order(df, "name ASC")
           name  age
        1  Alice   25
        0    Bob   30
    
    Note:
        - String format: "field ASC" or "field DESC"
        - List format: [("field", "asc"), ...] or ["field ASC", ...]
        - Dict format: {"field": "asc", ...}
        - Returns original DataFrame if order format is unrecognized
    """
    if isinstance(order, str):
        return apply_order_string(df, order)
    if isinstance(order, list):
        return apply_order_list(df, order)
    if isinstance(order, dict):
        return apply_order_dict(df, order)
    return df


def apply_order_string(df: pd.DataFrame, order: str) -> pd.DataFrame:
    """
    Apply ORDER BY from string format.
    
    Parses "field [ASC|DESC]" format and sorts DataFrame.
    
    Args:
        df: DataFrame to sort
        order: String like "name ASC" or "age DESC"
    
    Returns:
        pd.DataFrame: Sorted DataFrame
    
    Example:
        >>> df = pd.DataFrame({"age": [30, 25, 35]})
        >>> apply_order_string(df, "age DESC")
           age
        2   35
        0   30
        1   25
    
    Note:
        - Default direction is ASC if not specified
        - Returns original DataFrame if field not found
    """
    parts = order.split()
    field = parts[0]
    ascending = len(parts) == 1 or parts[1].upper() == "ASC"
    if field in df.columns:
        return df.sort_values(by=field, ascending=ascending)
    return df


def apply_order_list(df: pd.DataFrame, order: List) -> pd.DataFrame:
    """
    Apply ORDER BY from list format.
    
    Handles multiple sort fields with individual directions.
    
    Args:
        df: DataFrame to sort
        order: List of sort specs:
            - Strings: ["name ASC", "age DESC"]
            - Dicts: [{"name": "asc"}, {"age": "desc"}]
            - Mixed formats
    
    Returns:
        pd.DataFrame: Sorted DataFrame
    
    Example:
        >>> df = pd.DataFrame({"city": ["NYC", "LA", "NYC"], "age": [30, 25, 25]})
        >>> apply_order_list(df, ["city ASC", "age DESC"])
           city  age
        1    LA   25
        2   NYC   30
        0   NYC   25
    
    Note:
        - Supports multi-field sorting
        - Returns original DataFrame if no valid fields found
    """
    sort_fields = []
    sort_ascending = []

    for item in order:
        if isinstance(item, str):
            parts = item.split()
            field = parts[0]
            ascending = len(parts) == 1 or parts[1].upper() == "ASC"
            if field in df.columns:
                sort_fields.append(field)
                sort_ascending.append(ascending)
        elif isinstance(item, dict):
            for field, direction in item.items():
                if field in df.columns:
                    sort_fields.append(field)
                    sort_ascending.append(direction.upper() != "DESC")

    if sort_fields:
        return df.sort_values(by=sort_fields, ascending=sort_ascending)
    return df


def apply_order_dict(df: pd.DataFrame, order: Dict[str, str]) -> pd.DataFrame:
    """
    Apply ORDER BY from dict format.
    
    Parses dict of {field: direction} pairs and sorts DataFrame.
    
    Args:
        df: DataFrame to sort
        order: Dict like {"name": "asc", "age": "desc"}
    
    Returns:
        pd.DataFrame: Sorted DataFrame
    
    Example:
        >>> df = pd.DataFrame({"name": ["Bob", "Alice"], "age": [30, 25]})
        >>> apply_order_dict(df, {"name": "asc"})
           name  age
        1  Alice   25
        0    Bob   30
    
    Note:
        - Direction values: "asc" or "desc" (case-insensitive)
        - Supports multi-field sorting
        - Returns original DataFrame if no valid fields found
    """
    sort_fields = []
    sort_ascending = []

    for field, direction in order.items():
        if field in df.columns:
            sort_fields.append(field)
            sort_ascending.append(direction.upper() != "DESC")

    if sort_fields:
        return df.sort_values(by=sort_fields, ascending=sort_ascending)
    return df

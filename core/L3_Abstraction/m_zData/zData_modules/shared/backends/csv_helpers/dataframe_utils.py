# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/dataframe_utils.py
"""
DataFrame manipulation utilities for CSV adapter.

This module provides helper functions for common DataFrame operations including
row appending, auto-increment ID handling, and field detection.
"""

from zOS import Dict, Any, Optional
import pandas as pd


def append_row_to_df(df: pd.DataFrame, new_row: Dict[str, Any]) -> pd.DataFrame:
    """
    Safely append a row to DataFrame (avoids FutureWarning).
    
    Ensures all columns are present in the new row, creates a new DataFrame
    with the single row, and concatenates with the original.
    
    Args:
        df: Original DataFrame
        new_row: Dictionary of column_name: value pairs
    
    Returns:
        pd.DataFrame: DataFrame with new row appended
    
    Example:
        >>> df = pd.DataFrame({"id": [1], "name": ["Alice"]})
        >>> new_row = {"id": 2, "name": "Bob"}
        >>> df = append_row_to_df(df, new_row)
        >>> len(df)
        2
    
    Note:
        - Fills missing columns with None
        - Uses pd.concat to avoid FutureWarning
        - Returns new DataFrame if original is empty
    """
    # Ensure all columns present in new row
    for col in df.columns:
        if col not in new_row:
            new_row[col] = None

    new_df = pd.DataFrame([new_row], columns=df.columns)

    # If original is empty, return new one (avoids pandas FutureWarning)
    if len(df) == 0:
        return new_df

    return pd.concat([df, new_df], ignore_index=True, sort=False)


def detect_auto_id_field(schema: Dict[str, Any], df: pd.DataFrame) -> Optional[str]:
    """
    Detect auto-increment ID field from schema or DataFrame conventions.
    
    Checks schema for explicit auto_increment field with pk=True, then falls back
    to convention-based detection (looks for 'id' column in DataFrame).
    
    Args:
        schema: Schema dictionary with field definitions
        df: DataFrame to check for conventional 'id' column
    
    Returns:
        str: Name of auto-increment field, or None if not found
    
    Example:
        >>> schema = {"id": {"type": "int", "pk": True, "auto_increment": True}}
        >>> df = pd.DataFrame(columns=["id", "name"])
        >>> detect_auto_id_field(schema, df)
        'id'
    
    Note:
        - Checks schema first for explicit auto_increment
        - Falls back to 'id' column if present in DataFrame
        - Returns None if no auto-increment field found
    """
    auto_id_field = None

    # Check schema for explicit auto_increment field
    for field_name, field_def in schema.items():
        if isinstance(field_def, dict):
            is_pk = field_def.get('pk', False) or field_def.get('primary_key', False)
            is_auto = field_def.get('auto_increment', False) or field_def.get('autoincrement', False)
            if is_pk and is_auto:
                auto_id_field = field_name
                break

    # Fallback: If no schema, check for 'id' column in DataFrame (convention-based)
    if not auto_id_field and 'id' in df.columns:
        auto_id_field = 'id'

    return auto_id_field


def calculate_next_auto_id(df: pd.DataFrame, auto_id_field: str) -> int:
    """
    Calculate next auto-increment ID value.
    
    Finds the maximum value in the auto-increment field and returns max + 1.
    Returns 1 if table is empty or field has no valid values.
    
    Args:
        df: DataFrame containing the auto-increment field
        auto_id_field: Name of the auto-increment field
    
    Returns:
        int: Next ID value (max + 1, or 1 if empty)
    
    Example:
        >>> df = pd.DataFrame({"id": [1, 2, 5]})
        >>> calculate_next_auto_id(df, "id")
        6
        
        >>> df = pd.DataFrame({"id": []})
        >>> calculate_next_auto_id(df, "id")
        1
    
    Note:
        - Handles NaN and None values gracefully
        - Returns 1 for empty tables
        - Falls back to len(df) + 1 on type errors
    """
    if len(df) > 0 and auto_id_field in df.columns:
        try:
            max_id = df[auto_id_field].max()
            # Handle NaN or None
            next_id = int(max_id) + 1 if pd.notna(max_id) else 1
        except (ValueError, TypeError):
            next_id = len(df) + 1
    else:
        next_id = 1

    return next_id

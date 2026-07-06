# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/file_operations.py
"""
File I/O operations for CSV adapter.

This module handles all file system operations including path management,
CSV reading/writing, and directory creation.
"""

from zOS import Dict, Any, Optional, Path
import pandas as pd

from .constants import CSV_EXTENSION


def get_csv_path(base_path: Path, table_name: str) -> Path:
    """
    Get CSV file path for table.
    
    For migration tables, uses zmigrations/ subfolder to keep Data/ directory clean.
    For regular tables, uses base_path/{table}.csv
    
    Args:
        base_path: Base directory for CSV files
        table_name: Name of the table
    
    Returns:
        Path: Full path to CSV file
    
    Example:
        >>> base_path = Path("/data")
        >>> get_csv_path(base_path, "users")
        PosixPath('/data/users.csv')
        
        >>> get_csv_path(base_path, "__zmigration_users")
        PosixPath('/data/zmigrations/users.zMigration.csv')
    
    Note:
        - Migration tables: __zmigration_{table} → zmigrations/{table}.zMigration.csv
        - Global migrations: _zdata_migrations → zmigrations/_zdata_migrations.csv
        - Regular tables: {table} → {table}.csv
    """
    # Per-table migration history: __zmigration_{table} → zmigrations/{table}.zMigration.csv
    # Mirrors the SQL design where _zmigrations lives inside the DB — here it lives
    # inside the same "database" (Data/ folder), just in a tidy zmigrations/ subfolder.
    if table_name.startswith("__zmigration_"):
        actual_table = table_name.replace("__zmigration_", "")
        migration_dir = base_path / "zmigrations"
        migration_dir.mkdir(parents=True, exist_ok=True)
        return migration_dir / f"{actual_table}.zMigration{CSV_EXTENSION}"

    # Global SQL-style migration log redirected to zmigrations/ for CSV fallback
    if table_name == "_zdata_migrations":
        migration_dir = base_path / "zmigrations"
        migration_dir.mkdir(parents=True, exist_ok=True)
        return migration_dir / f"_zdata_migrations{CSV_EXTENSION}"

    # Regular tables use base_path
    return base_path / f"{table_name}{CSV_EXTENSION}"


def load_table_from_csv(
    csv_path: Path,
    _schema: Optional[Dict[str, Any]] = None,
    logger: Optional[Any] = None
) -> pd.DataFrame:
    """
    Load table from CSV file into DataFrame.
    
    Reads CSV file and optionally applies schema type coercion.
    
    Args:
        csv_path: Path to CSV file
        _schema: Optional schema dict for type coercion (reserved for future use)
        logger: Optional logger for diagnostic output
    
    Returns:
        pd.DataFrame: Loaded DataFrame
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        Exception: If CSV reading fails
    
    Example:
        >>> path = Path("/data/users.csv")
        >>> df = load_table_from_csv(path)
        >>> len(df)
        10
    
    Note:
        - Checks file existence before reading
        - Applies schema types if provided (via external function)
        - Logs debug info if logger provided
    """
    if not csv_path.exists():
        if logger:
            logger.error("CSV table does not exist: %s", csv_path)
        raise FileNotFoundError(f"Table at '{csv_path}' not found")

    try:
        df = pd.read_csv(csv_path)

        if logger:
            logger.debug("Loaded CSV table %s (%d rows)", csv_path.stem, len(df))

        return df

    except Exception as e:
        if logger:
            logger.error("Failed to load CSV table %s: %s", csv_path.stem, e)
        raise


def save_table_to_csv(
    csv_path: Path,
    df: pd.DataFrame,
    logger: Optional[Any] = None
) -> None:
    """
    Save DataFrame to CSV file.
    
    Writes DataFrame to CSV with standard formatting (no index, UTF-8).
    
    Args:
        csv_path: Path to CSV file
        df: DataFrame to save
        logger: Optional logger for diagnostic output
    
    Raises:
        Exception: If CSV writing fails
    
    Example:
        >>> df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        >>> path = Path("/data/users.csv")
        >>> save_table_to_csv(path, df)
    
    Note:
        - Uses index=False (no row index in CSV)
        - UTF-8 encoding by default
        - Logs debug info if logger provided
    """
    try:
        # Lazy-create the data directory on first write (connect() no longer does
        # it eagerly) — the single SSOT seam for "the folder appears when you
        # actually save", covering both create_table headers and row inserts.
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        if logger:
            logger.debug("Saved CSV table %s (%d rows)", csv_path.stem, len(df))
    except Exception as e:
        if logger:
            logger.error("Failed to save CSV table %s: %s", csv_path.stem, e)
        raise


def ensure_directory(path: Path) -> None:
    """
    Ensure directory exists, creating it if necessary.
    
    Args:
        path: Path to directory
    
    Raises:
        Exception: If directory creation fails
    
    Example:
        >>> path = Path("/data/myapp")
        >>> ensure_directory(path)
        >>> path.exists()
        True
    
    Note:
        - Creates parent directories as needed
        - Idempotent: safe to call multiple times
    """
    path.mkdir(parents=True, exist_ok=True)

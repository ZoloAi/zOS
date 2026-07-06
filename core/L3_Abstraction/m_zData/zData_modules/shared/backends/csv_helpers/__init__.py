# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv/__init__.py
"""
CSV adapter helper modules.

This package contains helper modules for the CSV adapter, providing focused
functionality for constants, file operations, schema handling, WHERE filtering,
ORDER BY operations, JOIN operations, and DataFrame utilities.

Modules:
    - constants: All constant values (error messages, operators, etc.)
    - file_operations: File I/O and path management
    - schema_operations: Schema parsing and type handling
    - where_filtering: WHERE clause parsing and filtering
    - order_operations: ORDER BY handling
    - join_operations: Multi-table JOIN logic
    - dataframe_utils: DataFrame manipulation utilities

Usage:
    from .csv import constants
    from .csv.file_operations import load_table_from_csv
    from .csv.where_filtering import create_where_mask
"""

__version__ = "1.0.0"

# Import all helper modules for convenient access
from . import constants
from . import dataframe_utils
from . import file_operations
from . import schema_operations
from . import where_filtering
from . import order_operations
from . import join_operations
from . import ddl_operations
from . import dml_operations

# Expose commonly used functions at package level
from .constants import (
    CSV_EXTENSION,
    CSV_GLOB_PATTERN,
    ERR_PANDAS_MISSING,
    LOG_CONNECTED,
    LOG_DISCONNECTED,
)

from .dataframe_utils import (
    append_row_to_df,
    detect_auto_id_field,
    calculate_next_auto_id,
)

from .file_operations import (
    get_csv_path,
    load_table_from_csv,
    save_table_to_csv,
    ensure_directory,
)

from .schema_operations import (
    parse_schema_columns,
    apply_schema_types,
    coerce_int_columns,
    sanitize_records,
    map_abstract_type_to_pandas,
    introspect_dataframe_schema,
)

from .where_filtering import (
    create_where_mask,
    apply_operator_conditions,
    create_or_mask,
    apply_where_filter,
)

from .order_operations import (
    apply_order,
    apply_order_string,
    apply_order_list,
    apply_order_dict,
)

from .join_operations import (
    join_tables,
    auto_join_tables,
    try_forward_join,
    try_reverse_join,
    manual_join_tables,
    resolve_field_names,
)

__all__ = [
    # Version
    "__version__",
    
    # Constants
    "CSV_EXTENSION",
    "CSV_GLOB_PATTERN",
    "ERR_PANDAS_MISSING",
    "LOG_CONNECTED",
    "LOG_DISCONNECTED",
    
    # DataFrame utilities
    "append_row_to_df",
    "detect_auto_id_field",
    "calculate_next_auto_id",
    
    # File operations
    "get_csv_path",
    "load_table_from_csv",
    "save_table_to_csv",
    "ensure_directory",
    
    # Schema operations
    "parse_schema_columns",
    "apply_schema_types",
    "coerce_int_columns",
    "sanitize_records",
    "map_abstract_type_to_pandas",
    "introspect_dataframe_schema",
    
    # WHERE filtering
    "create_where_mask",
    "apply_operator_conditions",
    "create_or_mask",
    "apply_where_filter",
    
    # ORDER operations
    "apply_order",
    "apply_order_string",
    "apply_order_list",
    "apply_order_dict",
    
    # JOIN operations
    "join_tables",
    "auto_join_tables",
    "try_forward_join",
    "try_reverse_join",
    "manual_join_tables",
    "resolve_field_names",
]

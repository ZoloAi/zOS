# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/csv_adapter.py
"""
CSV database backend adapter with pandas-powered DataFrames and in-memory caching.

See csv_helpers/README.md for full documentation.
"""

from zOS import Dict, List, Optional, Any
from .base_adapter import BaseDataAdapter
from . import blob_storage
from ..blob import BlobRef

try:
    import pandas  # pylint: disable=unused-import
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Import helper modules
from .csv_helpers import constants as csv_const
from .csv_helpers import file_operations as file_ops
from .csv_helpers import schema_operations as schema_ops
from .csv_helpers import ddl_operations as ddl_ops
from .csv_helpers import dml_operations as dml_ops

__all__ = ["CSVAdapter"]


class CSVAdapter(BaseDataAdapter):
    """
    CSV backend adapter with pandas DataFrames, in-memory caching, and multi-table JOINs.
    
    This is a thin orchestration layer that delegates to helper modules in csv_helpers/.
    See csv_helpers/README.md for complete documentation.
    
    Key Features:
    - Pandas-powered DataFrames for efficient data manipulation
    - In-memory table caching for performance
    - Multi-table JOIN support (manual and auto-detected)
    - Comprehensive WHERE clause filtering
    - Schema-based type coercion
    - UPSERT support with conflict resolution
    
    Methods:
    - DDL: create_table, alter_table, drop_table, table_exists, list_tables, introspect_schema
    - DML: insert, select, update, delete, upsert, aggregate
    - Connection: connect, disconnect, get_cursor
    - Transaction: begin_transaction, commit, rollback (no-ops for CSV)
    - Type mapping: map_type
    """

    def __init__(self, config: Dict[str, Any], logger=None) -> None:
        """Initialize CSV adapter with pandas check and in-memory caching."""
        if not PANDAS_AVAILABLE:
            raise ImportError(csv_const.ERR_PANDAS_MISSING)

        super().__init__(config, logger)
        self.tables: Dict[str, Any] = {}  # Cache: {table_name: DataFrame}
        self.schemas: Dict[str, Dict] = {}  # Schema: {table_name: schema_dict}

    # ============================================================
    # Connection Management
    # ============================================================

    def connect(self) -> bool:
        """Logical connect — arm the adapter WITHOUT creating the data directory.

        The data folder is born on the first WRITE (``save_table_to_csv`` ensures
        it), so merely loading a schema at boot never leaves an empty directory on
        disk. Reads of a not-yet-created table fall through to the normal
        "table does not exist" path.
        """
        self.connection = True
        return True

    def disconnect(self) -> None:
        """Disconnect from CSV backend by flushing all cached tables to disk."""
        if self.tables:
            for table_name, df in self.tables.items():
                self._save_table(table_name, df)
            self.tables.clear()
            self._log('info', csv_const.LOG_DISCONNECTED, self.base_path)
        self.connection = None

    def get_cursor(self):
        """Return self as cursor (CSV has no cursor concept)."""
        return self

    # ============================================================
    # DDL Operations (Schema Management)
    # ============================================================

    def create_table(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Create CSV table file with headers based on schema definition."""
        ddl_ops.create_table(
            self.base_path, table_name, schema,
            self.tables, self.schemas, self.logger
        )

    def register_schema(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Make the adapter type-aware for an EXISTING (on-disk) table.

        ``create_table`` only runs for MISSING tables, so a table already on disk
        never registered its schema here — and ``_load_table`` then loaded it
        schema-less, leaking nullable int columns as float64 ("2.0"). The
        orchestrator calls this once at connect for every schema table so reads
        AND writes are typed from the first access. Drops any df cached before the
        schema was known so it re-types on next load.
        """
        self.schemas[table_name] = schema
        self.tables.pop(table_name, None)

    def alter_table(self, table_name: str, changes: Dict[str, Any]) -> None:
        """Alter CSV table structure by adding or dropping columns."""
        ddl_ops.alter_table(
            self.base_path, table_name, changes,
            self.tables, self.schemas, self._load_table, self.logger
        )

    def drop_table(self, table_name: str) -> None:
        """Drop CSV table by deleting the file and clearing cache."""
        ddl_ops.drop_table(
            self.base_path, table_name,
            self.tables, self.schemas, self.logger
        )

    def table_exists(self, table_name: str) -> bool:
        """Check if CSV table exists by verifying file existence."""
        return ddl_ops.table_exists(self.base_path, table_name)

    def list_tables(self) -> List[str]:
        """List all CSV tables in base_path directory."""
        return ddl_ops.list_tables(self.base_path, self.logger)

    def introspect_schema(self, table_name: str) -> Dict[str, Any]:
        """Introspect CSV file to get actual columns and infer types."""
        return ddl_ops.introspect_schema(self.base_path, table_name, self.logger)

    # ============================================================
    # DML Operations (Data Manipulation)
    # ============================================================

    def insert(self, table: str, fields: List[str], values: List[Any]) -> int:
        """Insert a row into CSV table and save to disk."""
        return dml_ops.insert(
            table, fields, values, self.schemas,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def insert_many(self, table: str, rows_data: List[Dict[str, Any]]) -> List[int]:
        """Insert multiple pre-processed rows in a single write pass."""
        return dml_ops.insert_many(
            table, rows_data, self.schemas,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def select(self, table, fields: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        """Select rows from CSV table(s) with WHERE, JOINs, ORDER BY, LIMIT."""
        where = kwargs.get('where')
        joins = kwargs.get('joins')
        order = kwargs.get('order')
        limit = kwargs.get('limit')
        offset = kwargs.get('offset', 0)
        auto_join = kwargs.get('auto_join', False)
        schema = kwargs.get('schema')
        distinct = kwargs.get('distinct', False)

        return dml_ops.select(
            table, fields, where, joins, order, limit, offset,
            auto_join, schema, self._load_table, self.logger, distinct
        )

    def update(self, table: str, fields: List[str], values: List[Any], where: Dict[str, Any]) -> int:
        """Update rows in CSV table matching WHERE condition."""
        return dml_ops.update(
            table, fields, values, where,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def delete(self, table: str, where: Dict[str, Any]) -> int:
        """Delete rows from CSV table matching WHERE condition."""
        return dml_ops.delete(
            table, where,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def truncate(self, table: str) -> int:
        """Truncate CSV table: remove all rows and reset PK auto-increment sequence."""
        return dml_ops.truncate(
            table,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def upsert(self, table: str, fields: List[str], values: List[Any], conflict_fields: List[str]) -> int:
        """Insert or update row with conflict resolution."""
        return dml_ops.upsert(
            table, fields, values, conflict_fields,
            self._load_table, self._save_table, self.tables, self.logger
        )

    def aggregate(
        self,
        table: str,
        function: str,
        field: Optional[str] = None,
        where: Optional[Dict[str, Any]] = None,
        group_by=None,   # Optional[Union[str, List[str]]]
        alias: Optional[str] = None
    ) -> Any:
        """Perform aggregation function on table data using pandas."""
        return dml_ops.aggregate(
            table, function, field, where, group_by,
            self._load_table, self.logger, alias
        )

    # ============================================================
    # Blob storage (sidecar spill — CSV can't hold binary inline)
    # ============================================================

    def store_blob(self, table_name: str, field: str, data: bytes) -> Any:
        """Spill blob bytes to a sidecar file; store the relative path in the cell."""
        if data is None or data == "":
            return data
        return blob_storage.spill(self.base_path, table_name, field, data)

    def load_blob(self, table_name: str, field: str, cell: Any) -> Any:
        """Resolve a stored relative sidecar path into a lazy ``BlobRef``."""
        if cell is None or cell == "":
            return None
        if isinstance(cell, BlobRef):
            return cell
        if isinstance(cell, (bytes, bytearray, memoryview)):
            return BlobRef(data=bytes(cell))
        return BlobRef(path=blob_storage.resolve(self.base_path, str(cell)))

    def delete_blob(self, table_name: str, field: str, cell: Any) -> None:
        """Remove the sidecar file backing a blob cell on row delete."""
        if cell and not isinstance(cell, (bytes, bytearray, memoryview, BlobRef)):
            blob_storage.unlink(self.base_path, str(cell))

    # ============================================================
    # Type Mapping
    # ============================================================

    def map_type(self, abstract_type: str) -> str:
        """Map abstract schema type to pandas dtype."""
        return schema_ops.map_abstract_type_to_pandas(abstract_type)

    # ============================================================
    # Transaction Control
    # ============================================================

    def begin_transaction(self) -> None:
        """Snapshot current in-memory state so rollback can restore it atomically."""
        self._pre_tx_snapshot: Dict[str, Any] = {
            name: df.copy() for name, df in self.tables.items()
        }
        self._log('debug', "CSV adapter: begin_transaction (snapshot taken)")

    def commit(self) -> None:
        """Flush all cached tables to disk and clear the pre-transaction snapshot."""
        for table_name, df in self.tables.items():
            self._save_table(table_name, df)
        self._pre_tx_snapshot = {}
        self._log('debug', "CSV adapter: commit (saved all tables)")

    def rollback(self) -> None:
        """Restore pre-transaction snapshot, discarding any in-flight DDL/DML changes."""
        snapshot = getattr(self, '_pre_tx_snapshot', {})
        if snapshot:
            self.tables.update(snapshot)
            self._pre_tx_snapshot = {}
            self._log('warning', "CSV adapter: rollback (restored pre-transaction state)")
        else:
            self.tables.clear()
            self._log('warning', "CSV adapter: rollback (no snapshot — cleared cache)")

    # -- Savepoints (best-effort, mirrors the snapshot model above) ------------
    # CSV has no engine, so a savepoint is a named copy of the in-memory tables.
    # rollback_to restores that copy; release just drops the marker.

    def savepoint(self, name: str) -> None:
        """Snapshot current in-memory tables under ``name`` (nested rollback point)."""
        if not hasattr(self, '_savepoints'):
            self._savepoints: Dict[str, Any] = {}
        self._savepoints[name] = {n: df.copy() for n, df in self.tables.items()}
        self._log('debug', "CSV adapter: savepoint '%s' taken", name)

    def release_savepoint(self, name: str) -> None:
        """Drop a savepoint marker — the current state stays."""
        getattr(self, '_savepoints', {}).pop(name, None)
        self._log('debug', "CSV adapter: savepoint '%s' released", name)

    def rollback_to_savepoint(self, name: str) -> None:
        """Restore the tables captured at ``name``; outer transaction snapshot stays."""
        snap = getattr(self, '_savepoints', {}).get(name)
        if snap is not None:
            self.tables.update(snap)
            self._savepoints.pop(name, None)
            self._log('warning', "CSV adapter: rolled back to savepoint '%s'", name)

    # ============================================================
    # Internal Helpers
    # ============================================================

    def _load_table(self, table_name):
        """Load table from CSV file (with caching)."""
        # Check cache first
        if table_name in self.tables:
            return self.tables[table_name]

        csv_file = file_ops.get_csv_path(self.base_path, table_name)
        df = file_ops.load_table_from_csv(csv_file, logger=self.logger)

        # Coerce nullable int columns to Int64 so they round-trip as "2", not the
        # float64 "2.0" pandas infers when NaN is present. Int-only on purpose —
        # see coerce_int_columns (full type pass would change bool/datetime emit).
        if table_name in self.schemas:
            df = schema_ops.coerce_int_columns(df, self.schemas[table_name], self.logger)

        # Cache for reuse
        self.tables[table_name] = df

        return df

    def _save_table(self, table_name, df):
        """Save DataFrame to CSV file."""
        csv_file = file_ops.get_csv_path(self.base_path, table_name)
        file_ops.save_table_to_csv(csv_file, df, self.logger)

    def get_connection_info(self):
        """Get connection information for CSV adapter."""
        return {
            "adapter": "CSVAdapter",
            "connected": self.is_connected(),
            "path": str(self.base_path),
            "tables_cached": len(self.tables),
            "tables_available": len(self.list_tables()) if self.base_path.exists() else 0,
        }

# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/postgresql_adapter.py
"""
PostgreSQL database backend adapter with network-based connections and advanced features.

This module implements a production-grade PostgreSQL adapter that extends SQLAdapter
with PostgreSQL-specific features including SERIAL types, RETURNING clauses, database
auto-creation, and project metadata tracking via a .pginfo.zolo sidecar file.

Architecture Overview
--------------------
PostgreSQLAdapter sits at the concrete layer of the adapter hierarchy:

    BaseDataAdapter (ABC)
           ↓
      SQLAdapter (SQL operations + builders)
           ↓
    PostgreSQLAdapter (PostgreSQL-specific implementation)

**Design Philosophy:**
- **Network-based:** Connects to PostgreSQL server via host:port
- **Database auto-creation:** Creates database on first connect if missing
- **SERIAL types:** Auto-incrementing primary keys (SERIAL, BIGSERIAL)
- **RETURNING clause:** Get inserted row ID without separate query
- **Project info files:** Track database schema in YAML files
- **Smart user detection:** Falls back to system user if not specified

PostgreSQL-Specific Features
---------------------------
**1. Connection Management:**
- Connects to PostgreSQL server (not file-based like SQLite)
- Auto-creates database if it doesn't exist
- Connection params: host, port, user, password, database
- Default database: "postgres" (used for initial connection)

**2. SERIAL Types (Auto-Increment):**
PostgreSQL uses SERIAL for auto-incrementing primary keys:
- SERIAL: 4-byte integer (1 to 2,147,483,647)
- BIGSERIAL: 8-byte integer (1 to 9,223,372,036,854,775,807)

```python
schema = {
    "id": {"type": "int", "pk": True},  # → SERIAL PRIMARY KEY
    "name": {"type": "str", "required": True}
}
```

**3. RETURNING Clause:**
Get last inserted row ID efficiently:
```sql
INSERT INTO users (name, age) VALUES ('John', 30) RETURNING id;
```

**4. information_schema:**
PostgreSQL provides comprehensive metadata via information_schema:
- table_exists(): Query information_schema.tables
- list_tables(): Query information_schema.tables
- Schema: 'public' (default schema)

**5. Project Info Files:**
Tracks database metadata in a sidecar file at base_path:
- .pginfo.zolo: project, connection, server, tables, last_updated
- Auto-updated on table creation/drop

Connection Parameters
--------------------
**Configuration (via config dict):**
```python
config = {
    "path": "/data/myapp",      # Base path for info files
    "label": "mydb",             # Database name
    "meta": {
        "Data_Host": "localhost",     # Default: localhost
        "Data_Port": 5432,            # Default: 5432
        "Data_User": "postgres",      # Default: system user
        "Data_Password": "secret"     # Optional
    }
}
```

**Smart User Detection:**
If Data_User not specified, falls back to system username (via getpass.getuser()).
This works seamlessly with macOS Homebrew PostgreSQL installations.

Database Auto-Creation
---------------------
On first connect():
1. Connect to "postgres" database (always exists)
2. Check if target database exists (pg_database catalog)
3. If not, create database using CREATE DATABASE
4. Close temp connection, connect to target database

Type Mapping
-----------
Maps abstract types to PostgreSQL types:
- str → TEXT or VARCHAR
- int → INTEGER or SERIAL (for PKs)
- float → REAL or DOUBLE PRECISION
- bool → BOOLEAN
- datetime → TIMESTAMP
- json → JSONB (binary JSON)

Placeholder Format
-----------------
PostgreSQL (psycopg2) uses %s placeholders (not ?):
```python
cursor.execute("SELECT * FROM users WHERE age > %s", (18,))
```

Usage Examples
-------------
Basic connection and CRUD:
    >>> from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.postgresql_adapter import PostgreSQLAdapter
    >>> config = {
    ...     "path": "/data/myapp",
    ...     "label": "mydb",
    ...     "meta": {"Data_Host": "localhost", "Data_Port": 5432}
    ... }
    >>> adapter = PostgreSQLAdapter(config, logger=logger)
    >>> adapter.connect()
    >>> 
    >>> # Create table with SERIAL PK
    >>> schema = {
    ...     "id": {"type": "int", "pk": True},  # → SERIAL PRIMARY KEY
    ...     "name": {"type": "str", "required": True},
    ...     "age": {"type": "int"}
    ... }
    >>> adapter.create_table("users", schema)
    >>> 
    >>> # Insert (returns ID via RETURNING clause)
    >>> row_id = adapter.insert("users", ["name", "age"], ["John", 30])
    >>> 
    >>> # Select
    >>> rows = adapter.select("users", where={"age__gte": 18})
    >>> 
    >>> # Upsert
    >>> adapter.upsert(
    ...     "users",
    ...     ["id", "name", "age"],
    ...     [1, "John Doe", 35],
    ...     conflict_fields=["id"]
    ... )
    >>> 
    >>> adapter.disconnect()

Project Info Files:
    >>> # After connecting, sidecar file created at:
    >>> # /data/myapp/.pginfo.zolo  (YAML-syntax on disk)
    >>> with open(f"{config['path']}/.pginfo.zolo") as f:
    ...     info = yaml.safe_load(f)
    >>> print(info['tables'])
    ['users']

Dependencies
-----------
**Required:**
- psycopg2 or psycopg2-binary

**Installation:**
```bash
pip install zolo-zos[postgresql]
# or
pip install psycopg2-binary
```

Integration
----------
This adapter is used by:
- classical_data.py: CRUD orchestration
- data_operations.py: High-level operations
- quantum_data.py: Abstracted data structures (if PostgreSQL backend selected)

See Also
--------
- sql_adapter.py: SQL base class with builder methods
- base_adapter.py: Abstract adapter interface
- sqlite_adapter.py: SQLite implementation (file-based)
"""

from zOS import datetime, yaml, Dict, Optional, Any
import getpass
from .sql_adapter import SQLAdapter
from .type_mapping import resolve_sql_type, POSTGRESQL_TYPE_MAP, SQL_DEFAULT_TYPE

# Try to import psycopg2
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# ============================================================
# Module Constants - Connection Parameters
# ============================================================

_CONN_HOST = "host"
_CONN_PORT = "port"
_CONN_USER = "user"
_CONN_PASSWORD = "password"
_CONN_DATABASE = "database"
_CONN_AUTOCOMMIT = "autocommit"

# ============================================================
# Module Constants - Default Values
# ============================================================

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 5432
_DEFAULT_DATABASE = "postgres"  # Default DB for initial connection
_META_KEY_HOST = "Data_Host"
_META_KEY_PORT = "Data_Port"
_META_KEY_USER = "Data_User"
_META_KEY_PASSWORD = "Data_Password"

# ============================================================
# Module Constants - SQL Queries
# ============================================================

_SQL_CHECK_DB_EXISTS = "SELECT 1 FROM pg_database WHERE datname = %s"
_SQL_CREATE_DATABASE = "CREATE DATABASE {}"
_SQL_TABLE_EXISTS = """SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND table_name = %s
)"""
_SQL_LIST_TABLES = """SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name"""

# ============================================================
# Module Constants - PostgreSQL Types
# ============================================================

_TYPE_SERIAL = "SERIAL"
_TYPE_BIGSERIAL = "BIGSERIAL"
_TYPE_RETURNING = "RETURNING"
_SCHEMA_PUBLIC = "public"

# ============================================================
# Module Constants - Schema Keys (SSOT: shared/validators/constants)
# ============================================================

from ..validators.constants import (  # pylint: disable=wrong-import-position
    SCHEMA_KEY_PRIMARY_KEY as _SCHEMA_KEY_PRIMARY_KEY,
    SCHEMA_KEY_INDEXES as _SCHEMA_KEY_INDEXES,
    SCHEMA_KEY_TYPE as _SCHEMA_KEY_TYPE,
    SCHEMA_KEY_PK as _SCHEMA_KEY_PK,
    SCHEMA_KEY_UNIQUE as _SCHEMA_KEY_UNIQUE,
    SCHEMA_KEY_REQUIRED as _SCHEMA_KEY_REQUIRED,
    SCHEMA_KEY_FK as _SCHEMA_KEY_FK,
)

# ============================================================
# Module Constants - Info File Keys
# ============================================================

_INFO_KEY_DATABASE = "database"
_INFO_KEY_TABLES = "tables"
_INFO_KEY_CREATED_AT = "created_at"
_INFO_KEY_UPDATED_AT = "updated_at"
# Project sidecar tracking file (zolo convention; YAML-syntax on disk)
_PGINFO_FILENAME = ".pginfo.zolo"

# ============================================================
# Module Constants - Error Messages
# ============================================================

_ERR_PSYCOPG2_MISSING = "psycopg2 is required for PostgreSQL adapter.\nInstall with: pip install zolo-zos[postgresql]"
_ERR_CONNECTION_FAILED = "PostgreSQL connection failed: %s"
_ERR_DISCONNECT_FAILED = "Error closing PostgreSQL connection: %s"
_ERR_DB_CREATE_FAILED = "Failed to create database %s: %s"
_ERR_TABLE_CREATE_FAILED = "Failed to create table %s: %s"
_ERR_UPSERT_FAILED = "UPSERT failed for table %s: %s"

# ============================================================
# Module Constants - Log Messages
# ============================================================

_LOG_CONNECTING_SERVER = "Connecting to PostgreSQL server at %s:%s"
_LOG_CREATING_DB = "Creating database: %s"
_LOG_DB_CREATED = "[OK] Created database: %s"
_LOG_DB_EXISTS = "Database already exists: %s"
_LOG_CONNECTED = "Connected to PostgreSQL database: %s"
_LOG_DISCONNECTED = "Disconnected from PostgreSQL: %s"
_LOG_USER_FALLBACK = "No Data_User specified, using system user: %s"
_LOG_CONFIG_DEBUG = "PostgreSQL config - database: %s, host: %s, port: %s, user: %s"
_LOG_TABLE_EXISTS = "Table '%s' exists: %s"
_LOG_FOUND_TABLES = "Found %d tables: %s"
_LOG_COMPOSITE_PK = "Composite primary key detected: %s"
_LOG_ADD_COMPOSITE_PK = "Adding composite PRIMARY KEY (%s)"

# ============================================================
# Public API
# ============================================================

__all__ = ["PostgreSQLAdapter"]


class PostgreSQLAdapter(SQLAdapter):
    """
    PostgreSQL backend adapter with network connections and advanced features.
    
    This class extends SQLAdapter to provide PostgreSQL-specific implementations
    including SERIAL types for auto-increment, RETURNING clauses for efficient
    ID retrieval, database auto-creation, and project metadata tracking.
    
    Architecture
    -----------
    PostgreSQLAdapter provides:
    - **Initialization (1 method):** __init__() - Connection params, user detection
    - **Connection Management (3 methods):** connect(), disconnect(), get_cursor()
    - **DDL Operations (4 methods):** create_table(), table_exists(), list_tables(), _after_drop_table()
    - **DDL Helpers (2 methods):** _get_composite_pk(), _build_field_definitions()
    - **DML Operations (2 methods):** insert(), upsert()
    - **Type Mapping (1 method):** map_type()
    - **Dialect Hooks (3 methods):** _get_placeholders(), _get_single_placeholder(), _get_last_insert_id()
    - **Project Info (2 methods):** _write_project_info(), update_project_info()
    
    Key Features
    -----------
    **1. Network-Based Connection:**
    Connects to PostgreSQL server (not file-based):
    - host:port/{database_name}
    - Default: localhost:5432
    
    **2. Database Auto-Creation:**
    Automatically creates database if it doesn't exist on first connect
    
    **3. SERIAL Types:**
    Integer PKs automatically use SERIAL (auto-increment):
    - {"type": "int", "pk": True} → SERIAL PRIMARY KEY
    - Eliminates need for manual ID management
    
    **4. RETURNING Clause:**
    INSERT returns ID efficiently without separate query:
    - INSERT...RETURNING id
    - No need for SELECT CURRVAL or similar
    
    **5. information_schema:**
    Uses PostgreSQL's information_schema for metadata:
    - table_exists(), list_tables()
    - Schema: 'public' (default)
    
    **6. Project Info Files:**
    Tracks database schema in a sidecar at base_path:
    - .pginfo.zolo (YAML-syntax on disk)
    - Contains: project, connection, server, tables, last_updated
    
    **7. Smart User Detection:**
    Falls back to system user if Data_User not specified:
    - Uses getpass.getuser()
    - Works with Homebrew PostgreSQL on macOS
    
    Attributes:
        database_name (str): Database name (from data_label)
        host (str): PostgreSQL server host
        port (int): PostgreSQL server port
        user (str): Database user
        password (str): Database password (optional)
        db_path (str): Connection string (host:port/database)
        All BaseDataAdapter attributes
    
    Example:
        >>> config = {
        ...     "path": "/data",
        ...     "label": "mydb",
        ...     "meta": {"Data_Host": "localhost", "Data_Port": 5432}
        ... }
        >>> adapter = PostgreSQLAdapter(config, logger=logger)
        >>> adapter.connect()
        >>> # Database auto-created if needed
    """

    # ============================================================
    # Initialization
    # ============================================================

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[Any] = None
    ) -> None:
        """
        Initialize PostgreSQL adapter with connection parameters.
        
        Extracts connection params from config and performs smart user detection.
        Raises ImportError if psycopg2 not installed.
        
        Args:
            config: Configuration dict with path, label, and meta
            logger: Optional logger instance
        
        Raises:
            ImportError: If psycopg2 not available
        
        Attributes Set:
            database_name: Database name (from data_label)
            host: Server host (from meta, default: localhost)
            port: Server port (from meta, default: 5432)
            user: Database user (from meta or system user)
            password: Database password (from meta, optional)
            db_path: Connection string (host:port/database)
        
        Example:
            >>> config = {
            ...     "path": "/data/myapp",
            ...     "label": "mydb",
            ...     "meta": {
            ...         "Data_Host": "192.168.1.100",
            ...         "Data_Port": 5433,
            ...         "Data_User": "postgres",
            ...         "Data_Password": "secret"
            ...     }
            ... }
            >>> adapter = PostgreSQLAdapter(config, logger)
        
        Notes:
            - If Data_User not specified, uses getpass.getuser()
            - Password is optional (useful for trust auth or .pgpass)
            - db_path is informational only (not used for connection)
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError(_ERR_PSYCOPG2_MISSING)

        # Call parent init (sets base_path, data_label, and db_path)
        super().__init__(config, logger)

        # PostgreSQL uses Data_Label as database name (not filename)
        self.database_name = self.data_label

        # Connection parameters from Meta
        meta = config.get("meta", {})
        self.host = meta.get(_META_KEY_HOST, _DEFAULT_HOST)
        self.port = meta.get(_META_KEY_PORT, _DEFAULT_PORT)

        # Smart user detection: try specified user, fallback to system user
        specified_user = meta.get(_META_KEY_USER)
        if specified_user:
            self.user = specified_user
        else:
            # Auto-detect: use system username (works on macOS Homebrew)
            self.user = getpass.getuser()
            self._log('debug', _LOG_USER_FALLBACK, self.user)

        self.password = meta.get(_META_KEY_PASSWORD)

        # Override db_path to be connection string (not file path)
        self.db_path = f"{self.host}:{self.port}/{self.database_name}"

        self._log('debug', _LOG_CONFIG_DEBUG,
                self.database_name, self.host, self.port, self.user)

    # ============================================================
    # Connection Management
    # ============================================================

    def connect(self) -> Any:
        """
        Establish PostgreSQL connection (creates database if needed).
        
        This method performs a three-step connection process:
        1. Connect to 'postgres' database (always exists)
        2. Check if target database exists, create if needed
        3. Connect to target database
        
        Returns:
            psycopg2.connection: Database connection
        
        Raises:
            Exception: If connection fails or database creation fails
        
        Example:
            >>> adapter = PostgreSQLAdapter(config, logger)
            >>> conn = adapter.connect()
            >>> # Database auto-created if it didn't exist
        
        Notes:
            - Uses 'postgres' database for initial connection
            - Creates database with psycopg2.sql.Identifier for safe quoting
            - Writes project info file after successful connection
            - Sets autocommit=False for normal transaction mode
        """
        try:
            # Step 1: Connect to default 'postgres' database to create our database
            self._log('info', _LOG_CONNECTING_SERVER, self.host, self.port)

            conn_params = {
                _CONN_HOST: self.host,
                _CONN_PORT: self.port,
                _CONN_USER: self.user,
                _CONN_DATABASE: _DEFAULT_DATABASE  # Default database always exists
            }

            if self.password:
                conn_params[_CONN_PASSWORD] = self.password

            temp_conn = psycopg2.connect(**conn_params)
            temp_conn.autocommit = True  # Need autocommit to create database
            temp_cursor = temp_conn.cursor()

            # Step 2: Check if our database exists
            temp_cursor.execute(_SQL_CHECK_DB_EXISTS, (self.database_name,))

            if not temp_cursor.fetchone():
                # Database doesn't exist - create it
                self._log('info', _LOG_CREATING_DB, self.database_name)
                # Use sql.Identifier to safely quote database name
                temp_cursor.execute(
                    sql.SQL(_SQL_CREATE_DATABASE).format(
                        sql.Identifier(self.database_name)
                    )
                )
                self._log('info', _LOG_DB_CREATED, self.database_name)
            else:
                self._log('debug', _LOG_DB_EXISTS, self.database_name)

            temp_cursor.close()
            temp_conn.close()

            # Step 3: Connect to our actual database
            conn_params[_CONN_DATABASE] = self.database_name
            self.connection = psycopg2.connect(**conn_params)
            self.connection.autocommit = False  # Normal transaction mode

            self._log('info', _LOG_CONNECTED, self.database_name)

            # Write project info file to Data_path
            self._write_project_info()

            return self.connection

        except Exception as e:  # pylint: disable=broad-except
            self._log('error', _ERR_CONNECTION_FAILED, e)
            raise

    def disconnect(self) -> None:
        """
        Close PostgreSQL connection and release resources.
        
        Closes the cursor (if open) and then the connection. Handles errors
        gracefully and logs any issues during disconnect.
        
        Raises:
            Exception: Logged but not raised if disconnect fails
        
        Example:
            >>> adapter.disconnect()
            >>> # adapter.connection is now None
        
        Notes:
            - Safe to call multiple times (checks if connection exists)
            - Closes cursor before connection
            - Sets connection and cursor to None after closing
        """
        if self.connection:
            try:
                if self.cursor:
                    self.cursor.close()
                    self.cursor = None
                self.connection.close()
                self.connection = None
                self._log('info', _LOG_DISCONNECTED, self.database_name)
            except Exception as e:  # pylint: disable=broad-except
                self._log('error', _ERR_DISCONNECT_FAILED, e)

    def get_cursor(self) -> Any:
        """
        Get or create a database cursor (lazy initialization).
        
        Creates a cursor on first call, then returns cached cursor on
        subsequent calls. This enables efficient cursor reuse.
        
        Returns:
            psycopg2.cursor: Database cursor for query execution
        
        Example:
            >>> cur = adapter.get_cursor()
            >>> cur.execute("SELECT * FROM users")
        
        Notes:
            - Cursor created lazily (only when needed)
            - Cached for reuse across operations
            - Automatically closed during disconnect()
        """
        if not self.cursor and self.connection:
            self.cursor = self.connection.cursor()
        return self.cursor

    # ============================================================
    # DDL Operations
    # ============================================================

    def create_table(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Create table with PostgreSQL-specific features (SERIAL for PKs)."""
        self._log('info', "Creating table: %s", table_name)

        cur = self.get_cursor()
        composite_pk = self._get_composite_pk(schema)
        field_defs, foreign_keys = self._build_field_definitions(schema, composite_pk)

        # Add composite primary key as table-level constraint
        table_constraints = []
        if composite_pk:
            pk_columns = ", ".join(composite_pk)
            table_constraints.append(f"PRIMARY KEY ({pk_columns})")
            self._log('info', "Adding composite PRIMARY KEY (%s)", pk_columns)

        # Build and execute DDL
        all_defs = field_defs + table_constraints + foreign_keys
        ddl = f"CREATE TABLE {table_name} ({', '.join(all_defs)});"

        self._log('info', "Executing DDL: %s", ddl)
        cur.execute(ddl)
        if self.connection:
            self.connection.commit()
        self._log('info', "Table created: %s", table_name)

        # Create indexes if specified
        if "indexes" in schema:
            self._create_indexes(table_name, schema["indexes"])

        # Update project info file with new table
        self.update_project_info()

    def _get_composite_pk(self, schema):
        """Extract composite primary key from schema."""
        if "primary_key" in schema:
            pk_value = schema["primary_key"]
            if isinstance(pk_value, list) and len(pk_value) > 0:
                self._log('info', "Composite primary key detected: %s", pk_value)
                return pk_value
        return None

    def _build_field_definitions(self, schema, composite_pk):
        """Build field definitions and foreign keys for CREATE TABLE."""
        field_defs = []
        foreign_keys = []

        for field_name, attrs in schema.items():
            if field_name in ["primary_key", "indexes"] or not isinstance(attrs, dict):
                continue

            field_type = self._map_field_type(attrs.get("type", "str"))

            # PostgreSQL: Use SERIAL for integer primary keys (auto-increment)
            if attrs.get("pk") and not composite_pk:
                if attrs.get("type") in ["int", "integer"]:
                    field_type = "SERIAL"
                column = f"{field_name} {field_type}"
                if attrs.get("pk"):
                    column += " PRIMARY KEY"
            else:
                column = f"{field_name} {field_type}"

            # Add constraints (not needed for SERIAL PKs)
            if not (attrs.get("pk") and field_type == "SERIAL"):
                if attrs.get("unique"):
                    column += " UNIQUE"
                if attrs.get("required") is True:
                    column += " NOT NULL"

            field_defs.append(column)

            # Handle foreign keys
            if "fk" in attrs:
                fk_clause = self._build_foreign_key_clause(field_name, attrs)
                if fk_clause:
                    foreign_keys.append(fk_clause)

        return field_defs, foreign_keys

    def table_exists(self, table_name):
        """Check if a table exists in PostgreSQL."""
        cur = self.get_cursor()
        cur.execute(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = %s
            )""",
            (table_name,)
        )
        result = cur.fetchone()
        exists = result[0] if result else False
        self._log('debug', "Table '%s' exists: %s", table_name, exists)
        return exists

    def list_tables(self):
        """List all tables in the database."""
        cur = self.get_cursor()
        cur.execute(
            """SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name"""
        )
        tables = [row[0] for row in cur.fetchall()]
        self._log('debug', "Found %d tables: %s", len(tables), tables)
        return tables

    # alter_table() - inherited from SQLAdapter (PostgreSQL supports DROP COLUMN)
    # drop_table() - inherited from SQLAdapter with hook override below

    def introspect_schema(self, table_name):
        """
        Read a table's ACTUAL columns from information_schema (live DB truth).

        Returns {col: {"type": <abstract>}} via the reverse type map; the migration
        engine reconciles these against the declared schema before diffing so
        spelling variants (character varying ↦ str, timestamp… ↦ datetime) don't
        surface as phantom changes. Missing table → {} (diff treats as CREATE).
        """
        from .type_mapping import reverse_sql_type
        cur = self.get_cursor()
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            (table_name,),
        )
        return {name: {"type": reverse_sql_type(dtype)} for name, dtype in cur.fetchall()}

    def introspect_indexes(self, table_name):
        """
        Return user-created index names on a table (pg_indexes), excluding the
        primary-key index (``*_pkey``) and unique-constraint-backed indexes so the
        migration engine only manages indexes declared via ``indexes:``.
        """
        cur = self.get_cursor()
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = %s AND schemaname NOT IN ('pg_catalog')",
            (table_name,),
        )
        return [row[0] for row in cur.fetchall() if not str(row[0]).endswith("_pkey")]

    def _build_modify_column_sql(self, table_name, column_name, new_def):
        """
        PostgreSQL type change uses ALTER COLUMN … TYPE … USING (not MySQL's
        MODIFY COLUMN). The USING cast lets Postgres convert existing values
        instead of erroring on incompatible types.
        """
        if isinstance(new_def, dict) and "new" in new_def:
            new_def = new_def["new"]
        sql_type = self._map_field_type(new_def.get("type", "str"))
        return (f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                f"TYPE {sql_type} USING {column_name}::{sql_type}")

    def _after_drop_table(self, table_name):
        """PostgreSQL-specific cleanup - updates .pginfo.zolo tracking file."""
        self.update_project_info()

    # Most CRUD inherited from SQLAdapter

    def upsert(self, table, fields, values, conflict_fields):
        """Insert or update row using PostgreSQL ON CONFLICT syntax."""
        cur = self.get_cursor()

        # Build INSERT clause
        placeholders = self._get_placeholders(len(fields))
        sql_stmt = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})"

        # Build ON CONFLICT clause
        if conflict_fields:
            conflict_cols = ", ".join(conflict_fields)
            update_set = ", ".join([f"{f} = EXCLUDED.{f}" for f in fields if f not in conflict_fields])
            if update_set:
                sql_stmt += f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}"
            else:
                sql_stmt += f" ON CONFLICT ({conflict_cols}) DO NOTHING"

        # Add RETURNING clause to get row ID
        sql_stmt += " RETURNING *"

        self._log('debug', "Executing UPSERT: %s with values: %s", sql_stmt, values)
        cur.execute(sql_stmt, values)
        # Fetch the RETURNING row before committing, then honor any open transaction.
        result = cur.fetchone()
        row_id = result[0] if result else None
        self._maybe_commit()

        self._log('info', "Upserted row into %s with ID: %s", table, row_id)
        return row_id

    def truncate(self, table: str) -> int:
        """Clear a table and reset its SERIAL identity so the next id starts at 1.

        Uses ``DELETE FROM`` (not ``TRUNCATE``) to avoid PostgreSQL's "cannot
        truncate a table referenced in a foreign key constraint" restriction on
        parent tables — matching the portable clear the other adapters use — then
        restarts the table's owned identity sequence(s). This mirrors the SQLite
        ``sqlite_sequence`` reset without cascading into child tables.
        """
        cur = self.get_cursor()
        cur.execute(f"DELETE FROM {table}")
        count = cur.rowcount
        # Reset each SERIAL column's sequence so the next insert restarts at 1.
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_default LIKE 'nextval(%%'",
            (table,),
        )
        for (col,) in cur.fetchall():
            cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (table, col))
            row = cur.fetchone()
            seq = row[0] if row else None
            if seq:
                cur.execute(f"ALTER SEQUENCE {seq} RESTART WITH 1")
        self._maybe_commit()
        self._log('info', "Cleared %d row(s) from %s (identity reset)", count, table)
        return count

    # ============================================================
    # Transaction control (psycopg2 needs a cursor, not connection.execute)
    # ============================================================

    def begin_transaction(self) -> None:
        """Open a transaction. psycopg2 auto-starts one on the next statement, so
        we only flip autocommit off (remembering the prior mode to restore it) and
        mark ``_in_transaction`` so per-write commits are suppressed."""
        if not self.connection:
            return
        self._txn_prev_autocommit = self.connection.autocommit
        if self.connection.autocommit:
            self.connection.autocommit = False
        self._in_transaction = True
        self._log('debug', "Transaction started")

    def _restore_autocommit(self) -> None:
        """Restore the autocommit mode that was in effect before begin_transaction.

        Keeps production connections (which connect with autocommit=False) exactly
        as they were, while letting the per-statement harness mode return to True.
        """
        prev = getattr(self, "_txn_prev_autocommit", None)
        if prev is not None and self.connection and self.connection.autocommit != prev:
            self.connection.autocommit = prev

    def commit(self):
        """Commit the open transaction and restore the prior autocommit mode."""
        if self.connection:
            self.connection.commit()
            self._in_transaction = False
            self._restore_autocommit()
            self._log('debug', "Transaction committed")

    def rollback(self):
        """Roll back the open transaction and restore the prior autocommit mode."""
        if self.connection:
            self.connection.rollback()
            self._in_transaction = False
            self._restore_autocommit()
            self._log('debug', "Transaction rolled back")

    def savepoint(self, name: str) -> None:
        """Create a SAVEPOINT within the current transaction (via a cursor)."""
        if self.connection:
            self.get_cursor().execute(f"SAVEPOINT {self._safe_savepoint(name)}")
            self._log('debug', "Savepoint created: %s", name)

    def release_savepoint(self, name: str) -> None:
        """RELEASE a SAVEPOINT — its work merges into the enclosing transaction."""
        if self.connection:
            self.get_cursor().execute(f"RELEASE SAVEPOINT {self._safe_savepoint(name)}")
            self._log('debug', "Savepoint released: %s", name)

    def rollback_to_savepoint(self, name: str) -> None:
        """ROLLBACK TO a SAVEPOINT — undo work since it; outer transaction lives on."""
        if self.connection:
            self.get_cursor().execute(f"ROLLBACK TO SAVEPOINT {self._safe_savepoint(name)}")
            self._log('debug', "Rolled back to savepoint: %s", name)

    def map_type(self, abstract_type):
        """Map abstract schema type to PostgreSQL type."""
        if not isinstance(abstract_type, str):
            self._log('debug', "Non-string type received (%r); defaulting to TEXT.", abstract_type)
            return SQL_DEFAULT_TYPE

        return resolve_sql_type(abstract_type, POSTGRESQL_TYPE_MAP)

    def _get_placeholders(self, count):
        """Get parameter placeholders for PostgreSQL (%s, not $1)."""
        return ", ".join(["%s" for _ in range(count)])

    def _get_single_placeholder(self):
        """Get single parameter placeholder for PostgreSQL (%s)."""
        return "%s"

    def _get_last_insert_id(self, cursor):
        """Get last inserted row ID (PostgreSQL uses RETURNING clause instead)."""
        # PostgreSQL doesn't have lastrowid like SQLite
        # We use RETURNING clause in INSERT instead
        self._log('debug', "_get_last_insert_id called (PostgreSQL uses RETURNING clause)")

    def insert(self, table, fields, values):
        """Insert row and return ID using RETURNING clause."""
        cur = self.get_cursor()
        placeholders = self._get_placeholders(len(fields))

        # PostgreSQL: Use RETURNING to get inserted ID
        sql_stmt = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders}) RETURNING *"

        self._log('debug', "Executing INSERT: %s with values: %s", sql_stmt, values)
        cur.execute(sql_stmt, values)
        # Get the returned row BEFORE committing (RETURNING is on the open cursor).
        result = cur.fetchone()
        row_id = result[0] if result else None
        # Honor an open transaction — commit only when not inside begin_transaction.
        self._maybe_commit()

        self._log('info', "Inserted row into %s with ID: %s", table, row_id)
        return row_id

    def _write_project_info(self):
        """Write PostgreSQL connection info to .pginfo.zolo in Data_path."""
        try:
            # Ensure directory exists
            self._ensure_directory()

            info_file = self.base_path / _PGINFO_FILENAME

            # Get PostgreSQL version
            pg_version = "Unknown"
            try:
                cur = self.get_cursor()
                cur.execute("SELECT version();")
                version_string = cur.fetchone()[0]
                # Extract version number (e.g., "PostgreSQL 14.10")
                if "PostgreSQL" in version_string:
                    pg_version = version_string.split()[1]
            except Exception as e:  # pylint: disable=broad-except
                self._log('debug', "Could not get PostgreSQL version: %s", e)

            # Get data directory from server
            data_dir = "Unknown"
            try:
                cur = self.get_cursor()
                cur.execute("SHOW data_directory;")
                data_dir = cur.fetchone()[0]
            except Exception as e:  # pylint: disable=broad-except
                self._log('debug', "Could not get data_directory: %s", e)

            # Gather project information
            info = {
                "project": {
                    "name": self.database_name,
                    "created": datetime.now().isoformat(),
                },
                "connection": {
                    "database": self.database_name,
                    "host": self.host,
                    "port": self.port,
                    "user": self.user,
                    "connection_string": f"postgresql://{self.user}@{self.host}:{self.port}/{self.database_name}"
                },
                "server": {
                    "data_directory": data_dir,
                    "version": pg_version,
                },
                "tables": self.list_tables() if self.is_connected() else [],
                "schema_version": 1,
                "last_updated": datetime.now().isoformat()
            }

            # Write to file
            with open(info_file, 'w', encoding='utf-8') as f:
                yaml.dump(info, f, default_flow_style=False, sort_keys=False)

            self._log('debug', "Written PostgreSQL project info to: %s", info_file)

        except Exception as e:  # pylint: disable=broad-except
            self._log('warning', "Could not write PostgreSQL project info: %s", e)

    def update_project_info(self):
        """Update tables list in .pginfo.zolo."""
        try:
            info_file = self.base_path / _PGINFO_FILENAME

            if not info_file.exists():
                # File doesn't exist, create it
                self._write_project_info()
                return

            # Read existing file
            with open(info_file, 'r', encoding='utf-8') as f:
                info = yaml.safe_load(f)

            # Update tables list and timestamp
            info['tables'] = self.list_tables() if self.is_connected() else []
            info['last_updated'] = datetime.now().isoformat()

            # Write back
            with open(info_file, 'w', encoding='utf-8') as f:
                yaml.dump(info, f, default_flow_style=False, sort_keys=False)

            self._log('debug', "Updated PostgreSQL project info: %s", info_file)

        except Exception as e:  # pylint: disable=broad-except
            self._log('warning', "Could not update PostgreSQL project info: %s", e)

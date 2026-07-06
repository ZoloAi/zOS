# zOS/core/L4_Orchestration/r_zServer/zServer_modules/core/schema_manager.py

"""
SchemaManager - Database schema REGISTRATION on zServer boot ("schema on boot").

Handles:
- Auto-detection of zSchema files (.zolo, .yaml, .json) in models/ folder
- Schema loading via zLoader
- Database adapter initialization (open the connection)
- Registering the schema in memory so `$table` resolves and zData read/write work

Does NOT create tables. Table DDL is materialized lazily by `ensure_tables()` on the
first read/update/delete/upsert/create (see zData data_operations + the adapters:
a table "is born on the first read / write / ensure_tables, never before"), or
explicitly (and versioned) via `z migrate`. Boot-time eager table creation was
retired — boot only REGISTERS.
"""

from zOS import os
import glob

from ..utils.zserver_constants import PATTERN_SCHEMA_FILES, FOLDER_MODELS


class SchemaManager:
    """
    Manages automatic database schema initialization.
    
    Auto-detects and initializes database schemas from models/ folder.
    Convention: models/zSchema files (zVaFiles) are auto-initialized on server start.
    """
    
    def __init__(self, serve_path, zos, logger):
        """
        Initialize SchemaManager.
        
        Args:
            serve_path: Directory being served
            zos: zOS instance (for data subsystem access)
            logger: zOS logger instance
        """
        self.serve_path = serve_path
        self.zos = zos
        self.logger = logger

    def auto_detect_and_initialize(self):
        """
        Auto-detect and initialize database schemas from models/ folder.
        
        Convention: models/zSchema files (zVaFiles) are auto-initialized on server start.
        This follows the same pattern as zServer route file auto-detection.
        
        For each schema found:
        1. Load schema via zLoader
        2. Initialize the database adapter (open the connection)
        3. Register the schema in memory (columns known, `$table` resolves)

        Note:
            - Errors are logged but don't stop server startup
            - Multiple databases are supported (different Data_Path per schema)
            - This does NOT create tables. Tables are created lazily on first
              data op (ensure_tables) or explicitly via `z migrate`.
        """
        # Find models folder
        models_path = os.path.join(self.serve_path, FOLDER_MODELS)
        if not os.path.exists(models_path):
            self.logger.debug(f"[zServer] No {FOLDER_MODELS}/ folder found, skipping schema auto-initialization")
            return

        # Find all schema files (.zolo, .yaml, .json)
        schema_files = []
        for pattern in PATTERN_SCHEMA_FILES:
            pattern_path = os.path.join(models_path, pattern)
            matches = glob.glob(pattern_path, recursive=True)
            for match in matches:
                if match not in schema_files:  # Avoid duplicates
                    schema_files.append(match)

        if not schema_files:
            self.logger.debug("[zServer] No zSchema files found in models/")
            return

        # Log start of schema loading (INFO level summary)
        self.logger.info(f"[zServer] Loading {len(schema_files)} schemas...")
        
        # Track statistics for final summary
        total_tables = 0
        backend_types = set()

        # Initialize each schema
        for schema_file in schema_files:
            try:
                # Extract filename
                filename = os.path.basename(schema_file)

                # Load schema using zLoader (maintains SSOT/DRY)
                self.logger.debug(f"[zServer] Loading schema: {filename}")

                # Use zLoader's absolute path method
                # zLoader delegates to zParser for format detection and parsing
                schema = self.zos.loader.handle_absolute_path(schema_file)

                if not schema or schema == "error":
                    self.logger.warning(f"[zServer] Failed to load schema: {filename}")
                    continue

                # Initialize database adapter
                self.zos.data.load_schema(schema)
                
                # Track backend type for summary
                if hasattr(self.zos.data.adapter, '__class__'):
                    backend_name = self.zos.data.adapter.__class__.__name__.replace('Adapter', '').lower()
                    backend_types.add(backend_name)

                # Count tables for summary (exclude Meta)
                table_names = [k for k in schema.keys() if k != "zMeta"]
                total_tables += len(table_names)
                self.logger.debug(f"[zServer] Schema registered: {filename} ({len(table_names)} table(s))")

            except Exception as e:
                self.logger.warning(f"[zServer] Failed to initialize schema {filename}: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
        
        # Log final summary at INFO level
        backend_str = ", ".join(sorted(backend_types)) if backend_types else "unknown"
        self.logger.info(f"[zServer] Registered {len(schema_files)} schemas ({total_tables} tables) - {backend_str} backend")

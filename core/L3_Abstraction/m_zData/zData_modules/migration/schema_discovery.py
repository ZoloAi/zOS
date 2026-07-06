# zOS/core/L3_Abstraction/m_zData/zData_modules/migration/schema_discovery.py
"""
SchemaDiscovery - Automatic schema discovery from environment.

Handles schema discovery operations including:
- Scanning ZDATA_*_URL environment variables
- Loading schemas via zLoader
- Filtering by zMigration flag
- Providing schema metadata

Architecture:
    - Scans zConfig.environment.env for ZDATA_* vars
    - Constructs schema paths following convention
    - Loads schemas via zLoader
    - Returns metadata for migration operations
"""

from zOS import Any, Dict, List, Optional, os

from zOS.zVocabulary import FILE_TYPE_SCHEMA
from ..shared.data_keys import SCHEMA_KEY_META

# Module Constants
_LOG_PREFIX = "[SchemaDiscovery]"
_META_KEY = SCHEMA_KEY_META
_META_KEY_DATA_TYPE = "Data_Type"
_META_KEY_ZMIGRATION = "zMigration"
_META_KEY_ZMIGRATION_VERSION = "zMigrationVersion"


class SchemaDiscovery:
    """
    Discovers schemas from environment variables.
    
    Responsibilities:
        - Scan ZDATA_*_URL environment variables
        - Load schemas via zLoader
        - Extract metadata for migration
        - Filter by zMigration flag
    
    Attributes:
        zos: zOS framework instance
        logger: Logger instance
    """

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize SchemaDiscovery.
        
        Args:
            zos: zOS framework instance
            logger: Logger instance
        """
        self.zos = zos
        self.logger = logger

    def discover_schemas(self, app_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover all schemas with zMigration enabled.

        Discovery order:
          1. File-based: scan <app_dir>/models/ (or Models/) for *.zolo when
             app_file is provided — covers CSV/SQLite apps with local schema files.
          2. Env-var-based: scan ZDATA_*_URL variables — covers remote DB setups.

        Returns:
            List of discovered schemas with metadata
        """
        schemas: List[Dict[str, Any]] = []

        # ── 1. File-based discovery ──────────────────────────────────────────
        if app_file:
            from pathlib import Path as _Path  # pylint: disable=import-outside-toplevel
            app_path = _Path(app_file)
            models_dir = None
            for candidate in (app_path.parent / "models", app_path.parent / "Models"):
                if candidate.exists():
                    models_dir = candidate
                    break

            if models_dir:
                self.logger.debug(f"{_LOG_PREFIX} Scanning file-based schemas in: {models_dir}")
                for schema_file in sorted(models_dir.glob("*.zolo")):
                    schema_name = schema_file.stem   # e.g. "zSchema.crm"
                    schema_path = f"@.models.{schema_name}"
                    try:
                        schema = self.zos.loader.handle(schema_path)
                        if not schema:
                            self.logger.warning(f"{_LOG_PREFIX} Failed to load: {schema_path}")
                            continue
                        meta = schema.get(_META_KEY, {})
                        migration_enabled = meta.get(_META_KEY_ZMIGRATION, False)
                        version = meta.get(_META_KEY_ZMIGRATION_VERSION, "none")
                        data_type = meta.get(_META_KEY_DATA_TYPE, "unknown")
                        schemas.append({
                            "name": schema_name,
                            "env_var": None,
                            "data_type": data_type,
                            "version": version,
                            "migration_enabled": migration_enabled,
                            "schema": schema,
                        })
                        self.logger.debug(
                            f"{_LOG_PREFIX} File-discovered: {schema_name} "
                            f"(v{version}, {data_type}, migration={migration_enabled})"
                        )
                    except Exception as exc:  # pylint: disable=broad-except
                        self.logger.warning(f"{_LOG_PREFIX} Error loading {schema_path}: {exc}")
            else:
                self.logger.debug(f"{_LOG_PREFIX} No models/ dir found next to: {app_file}")

        # ── 2. Env-var-based discovery ───────────────────────────────────────
        env = self.zos.config.environment.env
        if not any(k.startswith("ZDATA_") for k in env.keys()):
            env = os.environ
            self.logger.debug(f"{_LOG_PREFIX} Using os.environ as fallback for ZDATA_* vars")

        for key, _ in env.items():
            if key.startswith("ZDATA_") and key.endswith("_URL"):
                schema_name_upper = key[6:-4]
                schema_name = f"{FILE_TYPE_SCHEMA}.{schema_name_upper.lower()}"
                # skip if already discovered from file
                if any(s["name"] == schema_name for s in schemas):
                    continue
                schema_path = f"@.models.{schema_name}"
                try:
                    schema = self.zos.loader.handle(schema_path)
                    if not schema:
                        self.logger.warning(f"{_LOG_PREFIX} Failed to load schema: {schema_path}")
                        continue
                    meta = schema.get(_META_KEY, {})
                    data_type = meta.get(_META_KEY_DATA_TYPE, "unknown")
                    migration_enabled = meta.get(_META_KEY_ZMIGRATION, True)
                    version = meta.get(_META_KEY_ZMIGRATION_VERSION, "none")
                    schemas.append({
                        "name": schema_name,
                        "env_var": key,
                        "data_type": data_type,
                        "version": version,
                        "migration_enabled": migration_enabled,
                        "schema": schema,
                    })
                    self.logger.debug(
                        f"{_LOG_PREFIX} Env-discovered: {schema_name} "
                        f"(v{version}, {data_type}, migration={migration_enabled})"
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning(f"{_LOG_PREFIX} Error loading schema for {key}: {exc}")

        self.logger.info(
            f"{_LOG_PREFIX} Found {len(schemas)} schema(s), "
            f"{sum(1 for s in schemas if s['migration_enabled'])} migration-enabled"
        )
        return schemas

    def migrate_app(
        self,
        orchestrator: Any,
        _app_file: Optional[str] = None,
        auto_approve: bool = False,
        dry_run: bool = False,
        specific_schema: Optional[str] = None,
        force_version: Optional[str] = None,
        plan: bool = False,
        rollback: bool = False
    ) -> Dict[str, Any]:
        """
        Execute migrations for all schemas in an application.
        
        Args:
            orchestrator: DataOrchestrator instance
            _app_file: Optional app file path (for display only, unused)
            auto_approve: If True, skip confirmation prompts
            dry_run: If True, preview changes without executing
            specific_schema: If provided, migrate only this schema
            force_version: If provided, force this version for all migrations
            plan: If True, print the DDL plan without executing (--plan / --sql)
            rollback: If True, restore each schema from its last backup (--rollback)
            
        Returns:
            Dict with success, failed, skipped, up_to_date, total, schemas
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'up_to_date': 0,
            'total': 0,
            'schemas': []
        }

        # Discover all schemas (file-based first, then env-var)
        discovered_schemas = self.discover_schemas(app_file=_app_file)

        if not discovered_schemas:
            self.logger.warning(f"{_LOG_PREFIX} No schemas found with ZDATA_*_URL environment variables")
            return results

        # Filter by zMigration: true
        migration_enabled_schemas = [s for s in discovered_schemas if s['migration_enabled']]

        if not migration_enabled_schemas:
            results['skipped'] = len(discovered_schemas)
            results['total'] = len(discovered_schemas)
            self.logger.info(f"{_LOG_PREFIX} No schemas enabled for migration (zMigration: false)")
            return results

        # Filter by specific_schema if provided
        if specific_schema:
            migration_enabled_schemas = [
                s for s in migration_enabled_schemas
                if s['name'].split('.')[-1].lower() == specific_schema.lower()
            ]
            if not migration_enabled_schemas:
                self.logger.warning(f"{_LOG_PREFIX} Schema '{specific_schema}' not found or not migration-enabled")
                return results

        results['total'] = len(migration_enabled_schemas)
        results['skipped'] = len(discovered_schemas) - len(migration_enabled_schemas)

        self.logger.info(f"{_LOG_PREFIX} Migrating {len(migration_enabled_schemas)} schema(s)")

        # Migrate each schema
        from .migration_engine import MigrationEngine
        migration_engine = MigrationEngine(self.zos, self.logger)

        for schema_info in migration_enabled_schemas:
            schema_name = schema_info['name']
            schema_path = f"@.models.{schema_name}"
            current_version = schema_info['version']

            # Use force_version if provided
            target_version = (
                force_version if force_version
                else (current_version if current_version != 'none' else None)
            )

            # Normalise the version prefix to exactly one leading 'v'. zMigrationVersion
            # already carries the 'v' (e.g. v1.0.0), so re-adding it printed "vv1.0.0" (BUG 2).
            version_label = (
                current_version if current_version in (None, '', 'none')
                else f"v{str(current_version).lstrip('v')}"
            )
            self.logger.info(f"{_LOG_PREFIX} Migrating {schema_name} ({version_label})")

            try:
                # Load schema into orchestrator so the adapter is initialised
                # for this specific data source before diffing/migrating.
                orchestrator.load_schema(schema_info["schema"])

                if rollback:
                    migration_result = migration_engine.rollback(orchestrator)
                else:
                    migration_result = migration_engine.migrate(
                        orchestrator=orchestrator,
                        new_schema_path=schema_path,
                        auto_approve=auto_approve,
                        dry_run=dry_run,
                        schema_version=target_version,
                        plan=plan
                    )

                # Track results
                schema_result = {
                    'name': schema_name,
                    'version': current_version,
                    'result': migration_result
                }

                if migration_result.get('success'):
                    ops_executed = migration_result.get('operations_executed', 0)
                    # Dry-run executes nothing (ops_executed is always 0), so classifying by
                    # ops_executed bucketed pending changes as "up to date" (BUG 1). In dry-run
                    # classify by the PLANNED diff instead (has_changes / change_count).
                    _diff = migration_result.get('diff') or {}
                    _cc = (_diff.get('change_count') or {}) if isinstance(_diff, dict) else {}
                    _planned = (
                        bool(_diff.get('has_changes'))
                        if isinstance(_diff, dict) and 'has_changes' in _diff
                        else any(
                            int(_cc.get(k, 0) or 0)
                            for k in ('tables_added', 'tables_dropped', 'tables_modified')
                        )
                    )

                    if dry_run:
                        if _planned:
                            results['success'] += 1
                            schema_result['status'] = 'would_change'
                            self.logger.info(f"{_LOG_PREFIX} {schema_name}: Would change (dry-run preview)")
                        else:
                            results['up_to_date'] += 1
                            schema_result['status'] = 'up_to_date'
                            self.logger.info(f"{_LOG_PREFIX} {schema_name}: Up to date (no changes)")
                    elif ops_executed == 0:
                        results['up_to_date'] += 1
                        schema_result['status'] = 'up_to_date'
                        self.logger.info(f"{_LOG_PREFIX} {schema_name}: Up to date (no changes)")
                    else:
                        results['success'] += 1
                        schema_result['status'] = 'success'
                        self.logger.info(f"{_LOG_PREFIX} {schema_name}: Success ({ops_executed} operation(s))")
                else:
                    results['failed'] += 1
                    schema_result['status'] = 'failed'
                    error = migration_result.get('error', 'Unknown error')
                    self.logger.error(f"{_LOG_PREFIX} {schema_name}: Failed - {error}")

                results['schemas'].append(schema_result)

            except Exception as e:
                results['failed'] += 1
                schema_result = {
                    'name': schema_name,
                    'version': current_version,
                    'status': 'failed',
                    'result': {'success': False, 'error': str(e)}
                }
                results['schemas'].append(schema_result)
                self.logger.error(f"{_LOG_PREFIX} {schema_name}: Exception - {e}", exc_info=True)

        # Log summary
        self.logger.info(
            f"{_LOG_PREFIX} Complete: {results['success']} success, "
            f"{results['failed']} failed, {results['up_to_date']} up-to-date, "
            f"{results['skipped']} skipped"
        )

        return results

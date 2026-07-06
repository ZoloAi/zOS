# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_import.py
"""
ImportHandler — zImport dispatch event (sugar over zTransfer).

zImport is the symmetric counterpart to zExport. It is a thin convenience layer
that builds a zTransfer spec (file source → model target) and delegates the
actual data movement to the shared TransferEngine, then renders the CLI/Bifrost
result message. All format decoding, path resolution and row insertion live in
zTransfer (the SSOT I/O primitive).

Syntax:
    ^Import_Contacts:
        zDialog:
            title:  Import Contacts
            fields: [filename]
            onSubmit:
                zImport:
                    format:  csv
                    source:  @.Data.imports.zConv.filename
                    target:  @.models.zSchema.crm.contacts
                    mode:    append

    # Hardcoded source variant
    ^Import_Contacts:
        zImport:
            format:  csv
            source:  @.Data.imports.contacts_import.csv
            target:  @.models.zSchema.crm.contacts
            mode:    append

mode options:
    append   — insert all rows (default)
    replace  — truncate existing rows, then insert
"""

from typing import Any, Dict, Optional

from ..dispatch_constants import KEY_ZIMPORT

_LOG_PREFIX = "[zImport]"
_DEFAULT_FORMAT = "csv"
_DEFAULT_MODE = "append"


class ImportHandler:
    """Handles zImport dispatch events by delegating to the TransferEngine."""

    def __init__(self, zos: Any, display: Any, logger: Any, transfer_engine: Any) -> None:
        self.zos = zos
        self.display = display
        self.logger = logger
        self.transfer = transfer_engine

    def handle_import(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any] = None,
    ) -> Optional[Any]:
        cfg = zHorizontal.get(KEY_ZIMPORT) or {}
        if not isinstance(cfg, dict):
            self.logger.error(f"{_LOG_PREFIX} zImport value must be a dict")
            return {"success": False, "error": "zImport value must be a dict"}

        fmt    = str(cfg.get("format", _DEFAULT_FORMAT)).lower()
        source = cfg.get("source")
        target = cfg.get("target")
        mode   = str(cfg.get("mode", _DEFAULT_MODE)).lower()

        if not source:
            return {"success": False, "error": "zImport: 'source' is required"}
        if not target:
            return {"success": False, "error": "zImport: 'target' is required"}

        resolved_source = self._resolve_zconv(source, context)

        spec = {
            "format": fmt,
            "mode":   mode,
            "source": {"from": "file", "path": resolved_source},
            "target": {"to": "model", "model": target},
        }
        result = self.transfer.run(spec, context=context, walker=walker)

        # ── Render result message (UX preserved from the original handler) ───
        display = walker.display if walker else self.display
        if result.get("success"):
            count = result.get("count", 0)
            if count == 0:
                display.text("⚠️  Import file is empty — nothing inserted.")
            else:
                msg = f"✅  Imported {count} row(s) from source"
                display.text(msg)
                self.logger.info(f"{_LOG_PREFIX} {msg}")
        else:
            err = result.get("error", "unknown")
            display.text(f"❌  Import failed: {err}")
            self.logger.error(f"{_LOG_PREFIX} {err}")
        return result

    def _resolve_zconv(self, source: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Substitute any zConv.key tokens in source with values from context.
        e.g. @.Data.imports.zConv.filename → @.Data.imports.myfile.csv
        """
        if not context or not isinstance(context, dict):
            return source
        zconv = context.get("zConv") or {}
        if not isinstance(zconv, dict):
            return source
        result = source
        for key, val in zconv.items():
            result = result.replace(f"zConv.{key}", str(val))
        return result

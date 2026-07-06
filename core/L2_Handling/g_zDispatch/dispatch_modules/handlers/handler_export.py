# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/handlers/handler_export.py
"""
ExportHandler — zExport dispatch event (sugar over zTransfer).

zExport sources data from an owned sub-block (zData: silent read, or content:)
and delivers it mode-correctly. It is a thin convenience layer that builds a
zTransfer spec (model|inline source → response target) and delegates encoding +
delivery to the shared TransferEngine (the SSOT I/O primitive):

    zCLI    → writes to @.Data/exports/{filename}.{format}, prints path
    zBifrost → pushes a download event over WebSocket

Syntax:
    ^Export_Contacts:
        zExport:
            format:   csv
            filename: contacts_export        # no extension — added by handler
            zData:
                action:  read
                model:   @.models.zSchema.crm.contacts
                columns: [id, name, email, phone, company, status]

    # Raw content variant (no zData sub-block)
    ^Export_Note:
        zExport:
            format:   txt
            filename: my_note
            content:  Some plain text to export.
"""

from typing import Any, Dict, Optional

from ..dispatch_constants import KEY_ZEXPORT, KEY_ZDATA

_LOG_PREFIX = "[zExport]"
_DEFAULT_FORMAT = "csv"


class ExportHandler:
    """Handles zExport dispatch events by delegating to the TransferEngine."""

    def __init__(self, zos: Any, display: Any, logger: Any, transfer_engine: Any) -> None:
        self.zos = zos
        self.display = display
        self.logger = logger
        self.transfer = transfer_engine

    def handle_export(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any] = None,
    ) -> Optional[Any]:
        cfg = zHorizontal.get(KEY_ZEXPORT) or {}
        if not isinstance(cfg, dict):
            self.logger.error(f"{_LOG_PREFIX} zExport value must be a dict")
            return {"success": False, "error": "zExport value must be a dict"}

        fmt      = str(cfg.get("format", _DEFAULT_FORMAT)).lower()
        filename = str(cfg.get("filename", "export"))
        output   = cfg.get("output")   # zPath dot-notation (e.g. @.Data.exports)
        content  = cfg.get("content")
        zdata_cfg = cfg.get(KEY_ZDATA)

        # ── Source resolution ─────────────────────────────────────────────────
        if isinstance(zdata_cfg, dict):
            source = {"from": "model", "query": zdata_cfg}
        elif content is not None:
            source = {"from": "inline", "content": content}
        else:
            return {"success": False, "error": "zExport: no data source (zData or content)"}

        spec = {
            "format": fmt,
            "source": source,
            "target": {"to": "response", "filename": filename, "output": output},
        }
        return self.transfer.run(spec, context=context, walker=walker)

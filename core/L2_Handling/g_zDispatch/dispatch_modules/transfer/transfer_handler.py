# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_handler.py
"""
TransferHandler — dispatch entry point for the ``zTransfer`` grammar.

Thin glue between the dispatch layer and the TransferEngine. It unwraps the
``zTransfer`` block and delegates to the shared engine, so ``zTransfer`` authored
directly in zUI uses the exact same path as the zImport / zExport sugar.
"""

from typing import Any, Dict, Optional

from ..dispatch_constants import KEY_ZTRANSFER

_LOG_PREFIX = "[zTransfer]"


class TransferHandler:
    def __init__(self, engine: Any, logger: Any) -> None:
        self.engine = engine
        self.logger = logger

    def handle(
        self,
        zHorizontal: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        walker: Optional[Any] = None,
    ) -> Optional[Any]:
        cfg = zHorizontal.get(KEY_ZTRANSFER) or {}
        if not isinstance(cfg, dict):
            self.logger.error(f"{_LOG_PREFIX} zTransfer value must be a dict")
            return {"success": False, "error": "zTransfer value must be a dict"}
        return self.engine.run(cfg, context=context, walker=walker)

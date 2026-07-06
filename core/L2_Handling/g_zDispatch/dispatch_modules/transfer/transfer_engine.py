# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_engine.py
"""
TransferEngine — the SSOT primitive for moving data in and out of zOS.

A transfer is always: a *source* produces a payload, an optional *codec*
bridges its nature, and a *target* consumes it.

    source ──(read)──▶ payload ──(codec bridge)──▶ target ──(write)──▶ result

This single engine backs every I/O grammar:
    zImport   = transfer(file|storage|bytes  → model)      [decode]
    zExport   = transfer(model|inline         → response|file)  [encode]
    upload    = transfer(bytes                → storage)   [passthrough]
    download  = transfer(storage              → response)  [passthrough]

It is deliberately decoupled from zData and zComm: it only talks to them
through the model / storage adapters, so any subsystem can reuse it.

Spec (a plain zUI dict — file-type agnostic):
    zTransfer:
        format:  csv            # codec format when natures differ (default csv)
        mode:    append         # model target write mode (append|replace)
        source:  {from: file,  path: @.Data.imports.contacts.csv}
        target:  {to:   model, model: @.models.zSchema.crm.contacts}
"""

from typing import Any, Dict, Optional

from . import transfer_codec as codec
from .transfer_adapters import ADAPTER_REGISTRY
from .transfer_payload import NATURE_BLOB, NATURE_ROWS

_LOG_PREFIX = "[zTransfer]"
_DEFAULT_FORMAT = "csv"
_DEFAULT_MODE = "append"


class TransferEngine:
    """Backend-agnostic source→target data transfer."""

    def __init__(self, zos: Any, display: Any, logger: Any) -> None:
        self.zos = zos
        self.display = display
        self.logger = logger
        self._adapters: Dict[str, Any] = {
            kind: cls(self) for kind, cls in ADAPTER_REGISTRY.items()
        }

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def run(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        walker: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute a transfer spec. Returns a structured result dict."""
        if not isinstance(spec, dict):
            return {"success": False, "error": "zTransfer spec must be a dict"}

        source = spec.get("source")
        target = spec.get("target")
        if not isinstance(source, dict):
            return {"success": False, "error": "zTransfer: 'source' dict is required"}
        if not isinstance(target, dict):
            return {"success": False, "error": "zTransfer: 'target' dict is required"}

        fmt = str(spec.get("format", _DEFAULT_FORMAT)).lower()
        mode = str(spec.get("mode", _DEFAULT_MODE)).lower()

        try:
            src_adapter = self._adapter(source, role="source")
            tgt_adapter = self._adapter(target, role="target")
        except KeyError as exc:
            return {"success": False, "error": f"zTransfer: unknown adapter {exc}"}

        self.logger.framework.debug(
            f"{_LOG_PREFIX} {source.get('from')} → {target.get('to')} "
            f"(format={fmt} mode={mode})"
        )

        try:
            payload = src_adapter.read(source, context, walker)
            self._bridge(payload, tgt_adapter.WANTS, fmt, source.get("content"))
            return tgt_adapter.write(payload, target, mode, fmt, context, walker)
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.error(f"{_LOG_PREFIX} transfer failed: {exc}")
            return {"success": False, "error": str(exc)}

    # =========================================================================
    # PRIVATE
    # =========================================================================

    def _adapter(self, spec: Dict[str, Any], role: str):
        kind = spec.get("from") if role == "source" else spec.get("to")
        if not kind:
            raise KeyError(f"'{role}' missing '{'from' if role == 'source' else 'to'}'")
        return self._adapters[kind]

    def _bridge(self, payload, target_wants: str, fmt: str, content: Any) -> None:
        """Insert the codec only when the target's nature differs from the payload's."""
        if target_wants == NATURE_ROWS and payload.rows is None:
            raw = payload.text if payload.text is not None else (payload.data or b"")
            payload.rows = codec.decode(raw, fmt)
        elif target_wants == NATURE_BLOB and payload.data is None and payload.text is None:
            payload.text = codec.encode(payload.rows, content, fmt)

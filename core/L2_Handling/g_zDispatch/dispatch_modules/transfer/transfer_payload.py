# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_payload.py
"""
TransferPayload — the unit that flows from a source adapter to a target adapter.

A payload carries data in one of two natures:
    rows : List[Dict]   (tabular — model rows, parsed csv/json, …)
    blob : bytes / text (opaque bytes or encoded text — files, images, …)

The codec bridges the two natures only when source and target disagree.
`meta` carries side-band info (filename, mime type, source key/path).
"""

from typing import Any, Dict, List, Optional

NATURE_ROWS = "rows"
NATURE_BLOB = "blob"


class TransferPayload:
    __slots__ = ("rows", "data", "text", "meta")

    def __init__(
        self,
        rows: Optional[List[Dict]] = None,
        data: Optional[bytes] = None,
        text: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.rows = rows          # tabular nature
        self.data = data          # raw bytes (blob nature)
        self.text = text          # decoded/encoded text (blob nature)
        self.meta = meta or {}

    @property
    def nature(self) -> str:
        return NATURE_ROWS if self.rows is not None else NATURE_BLOB

    def as_bytes(self) -> bytes:
        """Best-effort bytes view for blob targets."""
        if self.data is not None:
            return self.data
        if self.text is not None:
            return self.text.encode("utf-8")
        return b""

    def as_text(self) -> str:
        """Best-effort text view for blob targets."""
        if self.text is not None:
            return self.text
        if self.data is not None:
            return self.data.decode("utf-8", errors="replace")
        return ""

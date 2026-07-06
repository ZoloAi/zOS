# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_codec.py
"""
TransferCodec — the format boundary for zTransfer.

A codec converts between a *blob* nature (bytes/text) and a *rows* nature
(List[Dict]). It is the single place that knows how csv / tsv / json / txt
serialize, so every adapter stays format-agnostic:

    blob  --decode(fmt)-->  rows      (import: file/storage bytes → model)
    rows  --encode(fmt)-->  text      (export: model rows → file/response)

Binary payloads (images, archives, …) never touch the codec: when source and
target are both blob-nature, the engine passes bytes straight through.
"""

import csv
import io
import json
from typing import Any, Dict, List, Optional

ROW_FORMATS = {"csv", "tsv", "json", "txt"}


class TransferCodecError(Exception):
    """Raised when a format is unsupported or content cannot be parsed."""


# ─────────────────────────────────────────────────────────────────────────────
# Decode: blob (bytes/str) → rows (List[Dict])
# ─────────────────────────────────────────────────────────────────────────────

def decode(raw: Any, fmt: str) -> List[Dict]:
    """Parse a text/bytes payload into a list of row dicts."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    fmt = (fmt or "csv").lower()

    if fmt == "csv":
        return _parse_delimited(text, ",")
    if fmt == "tsv":
        return _parse_delimited(text, "\t")
    if fmt == "json":
        return _parse_json(text)
    raise TransferCodecError(f"unsupported decode format '{fmt}'")


def _parse_delimited(text: str, delimiter: str) -> List[Dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]


def _parse_json(text: str) -> List[Dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TransferCodecError(f"invalid JSON: {exc}") from exc
    return data if isinstance(data, list) else [data]


# ─────────────────────────────────────────────────────────────────────────────
# Encode: rows (List[Dict]) or raw content → text
# ─────────────────────────────────────────────────────────────────────────────

def encode(rows: Optional[List[Dict]], content: Any, fmt: str) -> str:
    """Serialize rows (or raw content when rows is None) into a format string."""
    fmt = (fmt or "csv").lower()

    if fmt == "csv":
        return _encode_delimited(rows or [], ",")
    if fmt == "json":
        data = rows if rows is not None else content
        return json.dumps(data, indent=2, default=str)
    if fmt in ("tsv", "txt"):
        if rows is not None:
            return _encode_delimited(rows, "\t")
        return str(content or "")
    raise TransferCodecError(f"unsupported encode format '{fmt}'")


def _encode_delimited(rows: List[Dict], delimiter: str) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()

# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/__init__.py
"""
zTransfer — backend-agnostic data I/O primitive.

The single source of truth for moving data in and out of zOS (import, export,
upload, download) across file / model / storage / bytes endpoints. zImport and
zExport are thin sugar layered on top of the TransferEngine.
"""

from .transfer_engine import TransferEngine
from .transfer_handler import TransferHandler
from .transfer_payload import TransferPayload
from . import transfer_codec

__all__ = [
    "TransferEngine",
    "TransferHandler",
    "TransferPayload",
    "transfer_codec",
]

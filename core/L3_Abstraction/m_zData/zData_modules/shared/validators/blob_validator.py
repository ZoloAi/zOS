# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/blob_validator.py
"""
Blob field validation — Layer 0 size/shape checks on a binary value.

The value reaching this layer has already been normalised to ``bytes`` (or a
``BlobRef`` on the read path) by ``coerce_blob`` in the insert/update pipeline.
This validator only enforces the declarative rules that apply uniformly across
backends — currently ``max_size``. ``mime`` is enforced at coercion time when an
upload object carries a content type, so it is not re-checked here.
"""

from zOS import Any, Dict, Optional

from .constants import RULE_KEY_MAX_SIZE, ERR_BLOB_TOO_LARGE
from ..blob import BlobRef, parse_size

__all__ = ["check_blob_rules"]


def _byte_length(value: Any) -> Optional[int]:
    """Return the byte length of a binary value, or ``None`` if not measurable."""
    if isinstance(value, BlobRef):
        return value.size
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)
    return None


def check_blob_rules(
    field_name: str,
    value: Any,
    rules: Dict[str, Any],
) -> Optional[str]:
    """Validate a blob value against size rules.

    Returns an error string on violation, or ``None`` when valid. Non-binary
    value forms (e.g. an uncoerced string) are normalised upstream, so there is
    nothing to size-check here and the function returns ``None``.
    """
    size = _byte_length(value)
    if size is None:
        return None

    max_size = parse_size(rules.get(RULE_KEY_MAX_SIZE))
    if max_size is not None and size > max_size:
        return ERR_BLOB_TOO_LARGE.format(
            field_name=field_name,
            max_size=rules.get(RULE_KEY_MAX_SIZE),
            size=size,
        )
    return None

# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/parser.py
"""zRaven .zolo parser — thin wrapper around the canonical zlsp parser.

SSOT: the same zlsp.parser.loads path used by zLoader and zParser.
No YAML fallback — .zolo files must be parsed with zlsp or tests abort.
"""

from __future__ import annotations

try:
    from zlsp import parser as _zolo_parser
    _ZOLO_AVAILABLE = True
except ImportError:
    _zolo_parser = None  # type: ignore
    _ZOLO_AVAILABLE = False


def zparse(content: str, filename: str | None = None) -> dict:
    """
    Parse a .zolo file using the canonical zOS parser (zlsp.parser.loads).

    Returns an empty dict on parse error — callers must treat that as fatal
    (empty test block dict means no tests run, not silent success).
    """
    if not _ZOLO_AVAILABLE or _zolo_parser is None:
        print("  [FATAL] zlsp not installed — cannot parse zRaven file.", flush=True)
        return {}
    try:
        result = _zolo_parser.loads(content, filename=filename)
        return result if isinstance(result, dict) else {}
    except Exception as exc:  # pylint: disable=broad-except
        print(f"  [zParse ERROR] {exc}", flush=True)
        return {}


def strip_sel(s):
    """Strip outer quotes the zolo parser may leave on selectors starting with [.

    SSOT for both the assertion evaluator and the WS runner.
    """
    if isinstance(s, str) and len(s) >= 2 and s[0] in ("'", '"') and s[-1] == s[0]:
        return s[1:-1]
    return s


# ── Raven-file extraction (SSOT) ──────────────────────────────────────────────

# Top-level keys that are configuration, not test blocks.
_NON_BLOCK_KEYS = ("zConnect", "zRavenOptions", "zMeta")


def parse_raven_file(content: str, filename: str, default_timeout: float):
    """Parse a zRaven file and extract the common run inputs in one place.

    Returns a dict:
        {
          "data":          full parsed mapping,
          "connect":       zConnect dict (ws/http overrides),
          "raven_opts":    zRavenOptions dict,
          "stop_on_error": bool,
          "timeout":       float,
          "blocks":        {name: steps} with config keys removed,
        }

    Used by entry.py and the in-process runner so the extraction rules live in
    exactly one place.
    """
    data        = zparse(content, filename)
    connect     = data.get("zConnect") if isinstance(data.get("zConnect"), dict) else {}
    raven_opts  = data.get("zRavenOptions") if isinstance(data.get("zRavenOptions"), dict) else {}
    zmeta       = data.get("zMeta") if isinstance(data.get("zMeta"), dict) else {}
    stop_on_err = bool(raven_opts.get("stop_on_error", True))
    timeout     = float(zmeta.get("timeout", default_timeout))
    blocks      = {k: v for k, v in data.items() if k not in _NON_BLOCK_KEYS}
    return {
        "data":          data,
        "connect":       connect or {},
        "raven_opts":    raven_opts or {},
        "stop_on_error": stop_on_err,
        "timeout":       timeout,
        "blocks":        blocks,
    }

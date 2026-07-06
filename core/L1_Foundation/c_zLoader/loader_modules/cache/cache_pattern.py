# zOS/core/L1_Foundation/c_zLoader/loader_modules/cache/cache_pattern.py

"""
Single source of truth for cache-key wildcard matching.

Shared by SystemCache, PinnedCache, and PythonModuleCache so the four cache
tiers agree on exactly one matching semantics (previously each reimplemented
its own, with subtle divergence on multi-wildcard patterns).

Supported patterns:
    - Prefix:    "ui_*"      → keys starting with "ui_"
    - Suffix:    "*_plugin"  → keys ending with "_plugin"
    - Contains:  "*test*"    → keys containing "test"
    - Exact:     "ui_main"   → exact match (no wildcard)
"""


def matches_pattern(key: str, pattern: str) -> bool:
    """Return True if ``key`` matches the wildcard ``pattern`` (see module doc)."""
    if "*" not in pattern:
        return key == pattern

    starts = pattern.startswith("*")
    ends = pattern.endswith("*")

    if starts and ends:
        # Contains: "*test*"
        return pattern[1:-1] in key
    if starts:
        # Suffix: "*_plugin"
        return key.endswith(pattern[1:])
    if ends:
        # Prefix: "ui_*"
        return key.startswith(pattern[:-1])
    # Interior wildcard only (e.g. "a*b") — fall back to literal-without-* contains
    return pattern.replace("*", "") in key


__all__ = ["matches_pattern"]

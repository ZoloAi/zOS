# zOS/core/zSys/nav_aliases.py

"""
Navigation event alias SSOT (Greek-letter rename seam).

zOS internal navigation events carry Greek-letter first-class names with their
original spellings kept as permanent legacy aliases:

    zAlpha  →  zLink   (cross-file navigation event)
    zOmega  →  zPsi    (in-block section pin — a property of the nav event)

``zDelta`` and ``zURL`` are unchanged (they already read cleanly). This module is
the ONE place the alias mapping lives, so every consumer — the parser (file seam),
zDispatch (routing), the zNavigation resolver, and the Bifrost serializer — speaks
a single canonical spelling.

Design note
-----------
The aliases are normalized to canonical at the *parser boundary*
(``parse_ui_file``), which means everything downstream — the zCLI walker/dispatch
AND the Bifrost chunk handed to the (compiled) serializer — receives ``zLink`` /
``zPsi`` already. This avoids a binary rebuild and keeps the frozen Bifrost client
(which only understands ``zLink(`` / ``zDelta(`` / ``zURL(``) working unchanged.
"""

from typing import Any

# Canonical-key map: authored alias key → canonical event key.
NAV_KEY_ALIASES = {
    "zAlpha": "zLink",
    "zOmega": "zPsi",
}

# Imperative-wrapper map: authored "zAlpha(...)" string → canonical "zLink(...)".
NAV_IMPERATIVE_ALIASES = {
    "zAlpha(": "zLink(",
}


def canonicalize_nav_token(text: str) -> str:
    """Rewrite a leading imperative alias wrapper (``zAlpha(``) to canonical.

    Leaves any other string (``zLink(`` / ``zDelta(`` / ``@.path`` / URL) as-is.
    """
    if isinstance(text, str):
        for alias, canonical in NAV_IMPERATIVE_ALIASES.items():
            if text.startswith(alias):
                return canonical + text[len(alias):]
    return text


def canonicalize_nav_aliases(node: Any) -> Any:
    """Deep-rewrite navigation aliases to their canonical spelling.

    Returns a NEW structure (never mutates the input) with:
      * dict keys ``zAlpha``/``zOmega`` renamed to ``zLink``/``zPsi`` (recursively)
      * string values starting ``zAlpha(`` rewritten to ``zLink(``

    When a canonical key already exists alongside its alias (authoring quirk), the
    pre-existing canonical value wins and the alias is dropped.
    """
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            canon_key = NAV_KEY_ALIASES.get(key, key) if isinstance(key, str) else key
            canon_value = canonicalize_nav_aliases(value)
            if canon_key != key and canon_key in node:
                # Canonical spelling authored too — keep it, drop the alias.
                continue
            out[canon_key] = canon_value
        return out
    if isinstance(node, list):
        return [canonicalize_nav_aliases(item) for item in node]
    if isinstance(node, str):
        return canonicalize_nav_token(node)
    return node

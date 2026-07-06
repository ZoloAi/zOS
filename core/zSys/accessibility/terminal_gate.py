"""
Terminal Emoji Gate (SSOT) — capability-aware emoji output for zCLI.

The single chokepoint for emoji/pictographs reaching the terminal.

Policy (2026-06): the terminal is emoji-free, ALWAYS — every pictograph written
to stdout/stderr is downgraded to its ``[description]`` (via emoji_descriptions),
the symmetrical twin of the zIcon ``[name]`` rule. This keeps output predictable,
ANSI-safe on legacy consoles, and free of glyphs hardcore terminal users dislike.
``supports_emoji`` (zMachine capability) is retained for callers that want to ask
the question, but it no longer gates output.

Design
------
- ``supports_emoji()`` — resolved capability (pinned by zConfig from zMachine; if
  unresolved, auto-detected from ``sys.stdout.encoding``).
- ``emoji_safe(text)`` — passthrough when supported (zero-cost fast path); else
  replaces pictograph runs with ``[description]``.
- ``install_stream_gate()`` — wraps ``sys.stdout`` / ``sys.stderr`` once so EVERY
  writer (zDisplay primitives, scattered ``print()``, logging StreamHandlers,
  zRaven) is gated at the stream boundary — no per-call-site changes required.
- ``icon_mapper`` reads the same ``supports_emoji()`` so zIcon chooses ``[name]``
  proactively rather than relying on the downgrade.

This is intentionally scoped to EMOJI / symbol pictographs. Box-drawing (U+2500–
257F) and accented text are left untouched so terminal layout is not mangled.
"""

import re
import sys
from typing import Any, Optional

from .emoji_descriptions import get_emoji_descriptions

# ---------------------------------------------------------------------------
# Capability state (pinned by zConfig from zMachine; None = auto-detect)
# ---------------------------------------------------------------------------
_supports_emoji: Optional[bool] = None


def _auto_detect() -> bool:
    """Best-effort fallback when zMachine has not pinned the capability yet.

    Conservative: only trusts a UTF-8 stdout encoding. zConfig later overrides
    this with the full zMachine detection (os + terminal + user preference).
    """
    enc = str(getattr(sys.stdout, "encoding", "") or "").lower()
    # ``cp65001`` is the Windows UTF-8 code page (Windows Terminal, modern consoles).
    # It carries no "utf" substring, so trust the 65001 marker explicitly.
    return "utf" in enc or "65001" in enc


def set_supports_emoji(value: Optional[bool]) -> None:
    """Pin the emoji capability (called by zConfig once zMachine is resolved).

    ``None`` resets to auto-detect (used by tests to clear state).
    """
    global _supports_emoji  # pylint: disable=global-statement
    _supports_emoji = None if value is None else bool(value)


def supports_emoji() -> bool:
    """Return the resolved emoji capability (auto-detects if not yet pinned)."""
    if _supports_emoji is None:
        return _auto_detect()
    return _supports_emoji


# ---------------------------------------------------------------------------
# Emoji → [description] downgrade
# ---------------------------------------------------------------------------
# Pictograph / symbol ranges we degrade. Deliberately EXCLUDES box-drawing
# (U+2500–257F) and arrows used for layout so the terminal UI stays intact.
# Variation selectors (FE00–FE0F) + zero-width joiner (200D) glue emoji clusters
# (skin-tone, ZWJ families, keycaps). Consumed greedily so a whole cluster maps
# to ONE description instead of leaking dangling joiners onto a legacy console.
_SELECTORS = "\U0000FE00-\U0000FE0F\U0000200D"
_EMOJI_RE = re.compile(
    "(?:"
    "[\U0001F000-\U0001FAFF"   # symbols & pictographs, emoticons, transport, supplemental
    "\U00002600-\U000027BF"    # misc symbols + dingbats (✓ ✗ ⚡ ✏ ➡ …)
    "\U00002300-\U000023FF"    # misc technical (⌨ ⏳ ⏎ …)
    "\U00002B00-\U00002BFF"    # misc symbols & arrows (⭐ …)
    "\U00002100-\U0000214F"    # letterlike symbols (™ ℹ № …) — not encodable on cp437/ascii
    "\U000020D0-\U000020FF]"   # combining marks incl. enclosing keycap (U+20E3)
    "[" + _SELECTORS + "]*"    # trailing selectors / joiners (repeatable across the cluster)
    ")+"
)

# Stray selectors/joiners left after a non-pictograph base (e.g. the ASCII '1' of
# the keycap '1️⃣') — scrubbed so nothing zero-width reaches a strict codec.
_STRAY_SELECTOR_RE = re.compile("[" + _SELECTORS + "]")

# Curated descriptions for high-traffic zOS UI glyphs that may be absent from the
# CLDR emoji dataset (light check/cross, lightning, etc.).
_SYMBOL_DESCRIPTIONS = {
    "\u2713": "ok",        # ✓ check mark
    "\u2714": "ok",        # ✔ heavy check mark
    "\u2717": "fail",      # ✗ ballot x
    "\u2718": "fail",      # ✘ heavy ballot x
    "\u274C": "fail",      # ❌ cross mark
    "\u26A1": "fast",      # ⚡ high voltage
    "\u2728": "new",       # ✨ sparkles
    "\u2705": "ok",        # ✅ check mark button
    "\u26A0": "warning",   # ⚠ warning
    "\u2139": "info",      # ℹ information
}


def _describe(cluster: str) -> str:
    """Map one matched pictograph cluster to an ANSI-safe ``[description]``."""
    if cluster in _SYMBOL_DESCRIPTIONS:
        return f"[{_SYMBOL_DESCRIPTIONS[cluster]}]"
    desc = get_emoji_descriptions().emoji_to_description(cluster)
    if desc != cluster:
        return f"[{desc}]"
    # Unknown pictograph — emit codepoint(s), skipping joiners/selectors.
    cps = "+".join(
        f"U+{ord(c):04X}" for c in cluster if c not in ("\uFE0F", "\u200D")
    )
    return f"[{cps}]" if cps else ""


def emoji_safe(text: str) -> str:
    """Downgrade ALL pictographs to ``[description]`` for the terminal.

    Decision (2026-06): terminal output is emoji-free, ALWAYS — the symmetrical
    twin of the zIcon ``[name]`` rule. Hardcore terminal users don't want emoji,
    and the old ``supports_emoji()`` gate produced inconsistent output (emoji on
    modern consoles, text on legacy ones). A single ``[description]`` form is
    predictable everywhere and screen-reader-clean. Box-drawing and layout arrows
    are excluded by ``_EMOJI_RE``, so the terminal UI stays intact.
    """
    if not text:
        return text
    text = _EMOJI_RE.sub(lambda m: _describe(m.group(0)), text)
    # Scrub any dangling variation-selector / ZWJ (e.g. keycap '1️⃣' → '1' + selector).
    return _STRAY_SELECTOR_RE.sub("", text)


def _is_unicode_encoding(enc: str) -> bool:
    """True when the console codec can carry the full Unicode repertoire."""
    return (not enc) or ("utf" in enc) or ("65001" in enc)


def _encode_safe(text: str, stream: Any) -> str:
    """Final safety-net: guarantee ``text`` is encodable by ``stream``'s codec.

    The pictograph regex is best-effort and can never cover every glyph (™, ®,
    keycaps, ZWJ families, future Unicode). On a strict legacy console (cp1252,
    cp437, ascii) a single stray codepoint raises ``UnicodeEncodeError`` and the
    write crashes — exactly the Windows nightmare this gate exists to prevent.

    This pass is codec-aware: a character is downgraded ONLY when the actual
    console codec cannot encode it. So ™/® survive on cp1252 (where they exist)
    yet are downgraded on cp437/ascii. UTF consoles take the zero-cost fast path.
    """
    if not text:
        return text
    enc = str(getattr(stream, "encoding", "") or "").lower()
    if _is_unicode_encoding(enc):
        return text
    try:
        text.encode(enc)
        return text  # whole string already safe for this console
    except (UnicodeEncodeError, LookupError):
        pass
    out = []
    for ch in text:
        if ch in ("\uFE0F", "\u200D"):
            continue  # zero-width variation selector / ZWJ joiner — drop silently
        try:
            ch.encode(enc)
            out.append(ch)
        except UnicodeEncodeError:
            out.append(_describe(ch))
    return "".join(out)


# ---------------------------------------------------------------------------
# Stream gate (the universal chokepoint)
# ---------------------------------------------------------------------------
class EmojiSafeStream:
    """Transparent ``sys.stdout``/``sys.stderr`` proxy that applies ``emoji_safe``.

    Delegates every attribute to the wrapped stream; only ``write``/``writelines``
    are intercepted. Every pictograph is downgraded to ``[description]`` (the
    terminal is emoji-free by policy); ``_encode_safe`` is the codec backstop.
    """

    def __init__(self, stream: Any) -> None:
        self._zgate_stream = stream

    def write(self, s: Any) -> int:
        if isinstance(s, str):
            s = _encode_safe(emoji_safe(s), self._zgate_stream)
        return self._zgate_stream.write(s)

    def writelines(self, lines: Any) -> None:
        self._zgate_stream.writelines(
            _encode_safe(emoji_safe(l), self._zgate_stream) if isinstance(l, str) else l
            for l in lines
        )

    def __getattr__(self, name: str) -> Any:
        # Reached only for attributes not defined on the proxy itself.
        return getattr(self._zgate_stream, name)


def install_stream_gate() -> None:
    """Wrap stdout/stderr once so all terminal writers are emoji-gated (idempotent)."""
    if not isinstance(sys.stdout, EmojiSafeStream):
        sys.stdout = EmojiSafeStream(sys.stdout)
    if not isinstance(sys.stderr, EmojiSafeStream):
        sys.stderr = EmojiSafeStream(sys.stderr)

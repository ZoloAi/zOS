# zSys Accessibility — Emoji Descriptions Guide

> **Module:** `core/zSys/accessibility/emoji_descriptions.py`
> **Purpose:** Map emoji (or Unicode codepoints) to human-readable descriptions for screen readers and zCLI `[bracketed]` fallbacks, using official Unicode CLDR data.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

Emoji are opaque to screen readers and frequently mis-render in terminals. `EmojiDescriptions` converts them to words — `"📱"` → `"mobile phone"` — so accessible output and zCLI degrade gracefully to text.

```
emoji_to_description("📱")            → "mobile phone"
codepoint_to_description("1F4F1")     → "mobile phone"
codepoint_to_description("U+1F4F1")   → "mobile phone"
format_for_terminal("📱")             → "[mobile phone]"
has_description("📱")                  → True
```

Data source: `core/zSys/accessibility/data/emoji-a11y.en.json` (Unicode CLDR, ~2k entries), loaded **lazily** through the shared `_data.load_data_json` resolver.

---

## Behavior

| Method | Returns | Notes |
|--------|---------|-------|
| `emoji_to_description(emoji)` | description, or the emoji itself if unknown | strips the `U+FE0F` variation selector before lookup |
| `codepoint_to_description(cp)` | description, or the original string if invalid | accepts `1F4F1`, `U+1F4F1`, `\U0001F4F1`, `0X…`; handles ZWJ/flag sequences split on `_`/`-` |
| `format_for_terminal(emoji)` | `"[description]"`, or the emoji as-is | only brackets when a real description was found |
| `has_description(emoji)` | `bool` | variation-selector-insensitive |
| `get_stats()` | `{total_emojis, loaded, data_size_kb}` | forces a load |

**Fallback rule:** every lookup degrades to the input — an unknown emoji returns the emoji, an invalid codepoint returns the original string. Nothing raises.

---

## Lazy load + singleton

```python
def load(self):
    if self._loaded:
        return
    self._data = load_data_json(EMOJI_A11Y_FILE)   # shared resolver (A1/A2)
    self._loaded = True
```

- **No file access at import** — `load()` runs on first method call only.
- **One copy in memory** — `get_emoji_descriptions()` returns a process-wide singleton.
- **Graceful degradation** — a missing/invalid data file resolves to `{}` (every method then returns its input), so the subsystem never hard-fails on data problems (A1).

---

## Trust notes

- **No exec / no network / no file-write.** Pure dict lookups + string ops; the only I/O is the read-only data load.
- **Inert output.** Descriptions are terminal/screen-reader text, never interpolated into markup — this module has no web seam (contrast `icon_mapper`).
- **A1/A2:** the data-dir walk + `try/except → {}` boilerplate that used to be duplicated here and in `icon_mapper` now lives once in `_data.py`; this module just names `EMOJI_A11Y_FILE`.
- **A6:** docstrings corrected to the real import path — `from zSys.accessibility import get_emoji_descriptions`.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

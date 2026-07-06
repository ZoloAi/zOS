# zSys Accessibility Guide

**[Home](../../README.md) | [zSys Overview](README.md)**

> **Accessible-output + icon rendering SSOT — Layer 0**
> Turns machine glyphs into human/screen-reader text (emoji → description), renders Bootstrap Icons per output mode (web HTML vs terminal emoji), and — because the web path emits raw markup from `.zolo` content — owns the **allowlist sanitizers** that close the only zGuard/V3 seam in this pass.

---

## What It Does

`zSys.accessibility` is the runtime's **accessible-output floor**: emoji descriptions for screen readers / zCLI, a mode-aware Bootstrap-Icons mapper, and the sanitizers that make the web-rendering path safe to interpolate.

- ✅ **Emoji → text** — `emoji_descriptions` maps emoji to human-readable names (Unicode CLDR data) for screen readers and `[bracketed]` zCLI fallbacks
- ✅ **Mode-aware icons** — `icon_mapper.render_for_mode` emits `<i class="bi bi-…">` HTML in **zBifrost** (web) and emoji/Unicode/`[text]` in **zCLI** (terminal)
- ✅ **Lazy + singleton** — both data files (`emoji-a11y.en.json`, `bootstrap-icons.json`) load **once, on first use**, through one shared loader; no file access at import
- ✅ **Trust seam (A4)** — `sanitize.py` is the **single source of truth** for what may be interpolated into web markup: icon names (`^[a-z0-9-]+$`) and CSS class tokens (`^[A-Za-z0-9_-]+$`), **fail-closed**
- ✅ **Canonical zMode** — render mode compares against `zVocabulary.ZMODE_ZBIFROST` (lazy, per the L0 rule), not a string literal

**Status:** ✅ Audited + fixed. Findings A1–A6 resolved — shared JSON loader (A1) + data SSOT (A2), canonical zMode constant (A3), **A4 stored-XSS closed** via allowlist sanitizers at both emission seams, test moved out of the wheel (A5), docstrings/exports corrected (A6).

> This is a **facade overview**. For emoji descriptions, the icon mapper, and the sanitizers, see the [`accessibility_Guides/`](accessibility_Guides/) folder.

---

## Architecture Overview

Two public renderers over one internal loader, plus the sanitizer SSOT the web path depends on:

| Cluster | Module | Responsibility | Guide |
|---------|--------|----------------|-------|
| **emoji** | `emoji_descriptions.py` | `EmojiDescriptions` — emoji/codepoint → human description (CLDR), `[text]` terminal format | [emoji_descriptions_GUIDE](accessibility_Guides/emoji_descriptions_GUIDE.md) |
| **icons** | `icon_mapper.py` | `IconMapper.render_for_mode` — Bootstrap Icons → web HTML / terminal emoji·Unicode·text | [icon_mapper_GUIDE](accessibility_Guides/icon_mapper_GUIDE.md) |
| **sanitize** | `sanitize.py` | `safe_icon_name` / `safe_class_attr` — allowlist, fail-closed, the A4 trust boundary | [sanitize_GUIDE](accessibility_Guides/sanitize_GUIDE.md) |
| _(internal)_ | `_data.py` | `load_data_json(filename)` + `EMOJI_A11Y_FILE` / `BOOTSTRAP_ICONS_FILE` — single data-dir resolver (A1/A2) | — |

```
_data.load_data_json                 ← accessibility/data resolver + graceful {} fallback (leaf)
   ├── emoji_descriptions  (singleton, lazy)   emoji → description
   └── icon_mapper         (singleton, lazy)   render_for_mode(name, mode, size, color)
            └── sanitize.safe_icon_name / safe_class_attr   ← web emission boundary
                                                  (also called by e_zDisplay icon_renderer
                                                   for the _zClass wrap)
```

---

## Quick Start

```python
from zSys.accessibility import (
    get_emoji_descriptions,
    get_icon_mapper,
    safe_icon_name, safe_class_attr,   # the A4 sanitizers (SSOT)
)

# Emoji → human text (screen readers / zCLI)
get_emoji_descriptions().emoji_to_description("📱")        # "mobile phone"
get_emoji_descriptions().format_for_terminal("📱")         # "[mobile phone]"

# Icons — web vs terminal
icons = get_icon_mapper()
icons.render_for_mode("bi-tools", mode="zBifrost")          # '<i class="bi bi-tools"></i>'
icons.render_for_mode("bi-tools", mode="zCLI")              # '🔧'

# Foreign content is neutralized at the boundary (fail-closed)
icons.render_for_mode('x"><script>…', mode="zBifrost")      # inert escaped text, no markup
safe_class_attr('zText "><script>')                          # 'zText'  (bad token dropped)
```

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `get_emoji_descriptions()` → `EmojiDescriptions` | Lazy singleton; `emoji_to_description` / `codepoint_to_description` / `format_for_terminal` / `has_description` / `get_stats` |
| `get_icon_mapper()` → `IconMapper` | Lazy singleton; `render_for_mode(name, mode=None, size=None, color=None)` / `get_codepoint` / `has_emoji_fallback` |
| `safe_icon_name(name)` | Strip `bi-`, return the name iff `^[a-z0-9-]+$`, else `""` (fail-closed) |
| `safe_class_attr(value)` | Keep only `^[A-Za-z0-9_-]+$` class tokens; drop the rest |

---

## Trust posture — hardened web seam (A4)

`zSys.accessibility` is **open-core**, but unlike its siblings it is **not "no-seam"**: the zBifrost path emits raw HTML built from `.zolo`-authored values (icon `name` / `size` / `color` / `_zClass`), which are **foreign content** (V2/Type-B) flowing to a **network-served page** (V3). Left unescaped, a value like `tools"></i><script>…` is stored XSS.

- **Allowlist at the emission boundary** — every value interpolated into web markup passes through `sanitize.py`. Icon names must match `^[a-z0-9-]+$` (the Bootstrap-Icons charset); class hints keep only `^[A-Za-z0-9_-]+$` tokens. The bounded character set *is* the sanitizer.
- **Fail-closed, not escape-and-pass** — an invalid icon name yields **no markup**: `render_for_mode` returns inert, HTML-escaped `[name]` text instead of an `<i>` tag; invalid class tokens are dropped, not emitted.
- **Both seams covered** — the mapper itself **and** the cross-subsystem caller (`e_zDisplay/.../icon_renderer.py`, the `_zClass` wrap) both route through `safe_class_attr`, so there is no second unescaped path.
- **Terminal path is inert** — zCLI output is plain text/emoji (no markup), so it needs no sanitization; the guard is scoped to the web path only.
- **No code-exec / no network / no file-write** — no `eval`/`exec`/`subprocess`/`pickle`/socket. Data files load read-only through one fixed-name resolver, degrading to `{}` on any error.
- **Layer-0 discipline** — top-level imports are stdlib (`html`/`json`/`re`/`typing`) + siblings (`._data`, `.sanitize`); the canonical `zVocabulary.ZMODE_ZBIFROST` is **lazy-imported inside** `render_for_mode` (A3), never at module top.

---

## Summary

`zSys.accessibility` is the **accessible-output floor**: emoji → human text, mode-aware Bootstrap Icons, and the allowlist sanitizers that make the web render path injection-safe. It is the **first zSys util with a real V3 seam**, and that seam is now closed at a single SSOT.

| Go deeper | Guide |
|-----------|-------|
| Emoji/codepoint → description, terminal `[text]` format, CLDR data | [emoji_descriptions_GUIDE](accessibility_Guides/emoji_descriptions_GUIDE.md) |
| `render_for_mode` — web vs terminal, fallback chain, fail-closed web path | [icon_mapper_GUIDE](accessibility_Guides/icon_mapper_GUIDE.md) |
| The allowlist sanitizers — charsets, fail-closed contract, both seams | [sanitize_GUIDE](accessibility_Guides/sanitize_GUIDE.md) |

**Architecture:** two singleton renderers over one data loader, fronted by a sanitizer SSOT (emoji · icons → sanitize)
**Status:** ✅ Audited + fixed (open-core; **A4 XSS seam hardened**, allowlist + fail-closed)

---

**[Home](../../README.md) | [zSys Overview](README.md)**

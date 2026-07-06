# zSys Formatting — zTheme→ANSI Guide

> **Module:** `core/zSys/formatting/ztheme_to_ansi.py`
> **Purpose:** Bridge web styling to the terminal — map zTheme CSS classes (`zText-error`, `zLink-info`, `zFont-bold`, `zBg-*`) to ANSI codes for the zDisplay markdown renderer.

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

When zDisplay renders markdown/HTML in the terminal, inline `<span class="zText-error">` styling has no meaning — there is no CSS. This module converts those classes into the equivalent ANSI sequences so styled web content degrades gracefully to colored terminal text.

```
map_ztheme_class_to_ansi('zText-error')        → Colors.zError
map_ztheme_classes_to_ansi(['zText-error',
                            'zFont-bold'])       → Colors.zError + Colors.BOLD
colorize_with_class('Error!', 'zText-error')    → f"{Colors.zError}Error!{Colors.RESET}"
get_reset_code()                                 → Colors.RESET
```

Consumed by `e_zDisplay/.../markdown/html_processor.py` and `inline_transformer.py`.

---

## The three maps

Every value is a `Colors.*` attribute — **no raw escapes** (F1). Lookups go text → weight → style.

| Map | Classes | → |
|-----|---------|---|
| `ZTHEME_TEXT_COLOR_MAP` | `zText-error/danger/success/warning/info`, `zText-primary/secondary/accent`, `zText-muted/white/dark`, **`zLink-info/success/warning/error/primary/secondary`**, `zBg-error/warning/success/info/light/dark` | semantic/brand/utility colors + link + backgrounds |
| `ZTHEME_FONT_WEIGHT_MAP` | `zFont-bold` / `zFw-bold`, `zFont-normal` / `zFw-normal` | `Colors.BOLD` / `Colors.NORMAL_WEIGHT` |
| `ZTHEME_FONT_STYLE_MAP` | `zFont-italic` / `zFs-italic`, `zFont-normal` | `Colors.ITALIC` / `Colors.NORMAL_STYLE` |

> **`zLink-*` (F4):** the `inline_transformer` requested `zLink-info`, but no `zLink-*` key existed → links rendered **uncolored** (`''`). The link classes were added mirroring the `zText` semantic palette, so `map_ztheme_classes_to_ansi(['zLink-info'])` now returns `Colors.zInfo`.
>
> **`zFont-normal` precedence (pre-existing):** the key appears in both the weight map (→ `NORMAL_WEIGHT`) and the style map (→ `NORMAL_STYLE`); since lookup checks weight before style, `zFont-normal` always resolves to normal-weight. Behavior preserved verbatim through the F1 repoint.

---

## The allowlist property (trust)

`map_ztheme_class_to_ansi` returns a code **only for a known class**; anything else returns `''`:

```python
if class_name in ZTHEME_TEXT_COLOR_MAP:   return ZTHEME_TEXT_COLOR_MAP[class_name]
if class_name in ZTHEME_FONT_WEIGHT_MAP:  return ZTHEME_FONT_WEIGHT_MAP[class_name]
if class_name in ZTHEME_FONT_STYLE_MAP:   return ZTHEME_FONT_STYLE_MAP[class_name]
return ''
```

This makes the mapper a **sanitizer**: foreign zTheme/`.zolo` content cannot smuggle arbitrary ANSI escape sequences through it, because only the fixed, audited class→code table can produce output. The bounded table *is* the allowlist.

---

## Trust notes

- **No exec / no network / no file-write.** Dict lookups + string concatenation only.
- **Escape-injection safe** — unknown classes → `''` (the allowlist property above).
- **F3 cleanup:** the legacy `try: from .colors / except ImportError: from colors` fallback (dead in package context) was removed; a single `from .colors import Colors` remains.
- **F5:** `map_ztheme_class_to_ansi`, `map_ztheme_classes_to_ansi`, `get_reset_code`, `colorize_with_class` are now exported from `zSys.formatting` (no more deep-path-only access).

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**

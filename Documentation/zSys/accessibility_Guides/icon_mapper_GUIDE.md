# zSys Accessibility — Icon Mapper Guide

> **Module:** `core/zSys/accessibility/icon_mapper.py`
> **Purpose:** Render Bootstrap Icons appropriately per output mode — HTML `<i>` tags for zBifrost (web), emoji/Unicode/`[text]` for zCLI (terminal) — with a fail-closed web emission path.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

A `.zolo` icon event names a Bootstrap Icon (`bi-tools`, `tools`). The same name must become real `<i class="bi bi-tools">` markup on the web and a sensible glyph in the terminal. `IconMapper.render_for_mode` is that switch.

```
render_for_mode("bi-tools", mode="zBifrost")                       → '<i class="bi bi-tools"></i>'
render_for_mode("tools",    mode="zBifrost", size="zTitle-2",
                                              color="zText-primary") → '<span class="zTitle-2 zText-primary"><i class="bi bi-tools"></i></span>'
render_for_mode("bi-tools", mode="zCLI")                            → '🔧'
render_for_mode("unmapped", mode="zCLI")                            → '[unmapped]'
```

Codepoint data: `core/zSys/accessibility/data/bootstrap-icons.json`, loaded lazily via the shared `_data.load_data_json` resolver. `mode` defaults to the canonical `zVocabulary.ZMODE_ZBIFROST` (lazy-imported — A3).

---

## The zCLI fallback chain

Terminal rendering tries, in order:

1. **Curated emoji** — `ICON_TO_EMOJI_FALLBACK` (best UX: `tools → 🔧`, `search → 🔍`, `check → ✓`, …)
2. **Unicode codepoint** — `chr(bootstrap-icons.json[name])` (guarded against `ValueError`/`OverflowError`)
3. **Text** — `[name]` as an inert last resort

All three are plain text, so the terminal path needs no sanitization.

---

## The zBifrost (web) path — fail-closed

The web branch emits raw HTML, so it is the **trust boundary**. Every interpolated value is validated through `sanitize.py` first:

```python
from zOS.zVocabulary import ZMODE_ZBIFROST          # canonical zMode (lazy, L0 rule)

if mode == ZMODE_ZBIFROST:
    safe_name = safe_icon_name(icon_name)           # ^[a-z0-9-]+$ or ""
    if not safe_name:
        return html.escape(f"[{clean_name}]")       # fail-closed: inert text, NO <i> tag
    icon_html = f'<i class="bi bi-{safe_name}"></i>'
    classes = [c for c in (safe_class_attr(size or ""), safe_class_attr(color or "")) if c]
    if classes:
        return f'<span class="{" ".join(classes)}">{icon_html}</span>'
    return icon_html
```

- **Invalid name → no markup.** A name with quotes/angle-brackets never produces an `<i>`; it becomes HTML-escaped `[name]` text the browser renders inertly.
- **`size`/`color` are token-filtered.** `safe_class_attr` keeps only well-formed class tokens, dropping anything that could break out of the attribute.
- **The `_zClass` wrap is sanitized too** — but in the **caller** (`e_zDisplay/.../icon_renderer.py`), which routes `event_data['_zClass']` through the same `safe_class_attr` before wrapping. Both seams share the one SSOT.

> Before A4 these values were interpolated unescaped (`f'<i class="bi bi-{clean_name}">'`), so `tools"></i><script>…` yielded stored XSS on the network-served page. The allowlist closes that.

---

## Other members

| Method | Returns |
|--------|---------|
| `get_codepoint(name)` | the int codepoint from the JSON, or `None` |
| `has_emoji_fallback(name)` | whether a curated emoji exists |

Both strip the prefix with `removeprefix("bi-")` (A3 — not the old `.replace("bi-","")`, which would have mangled any inner `bi-`).

---

## Trust notes

- **Web emission is allowlisted + fail-closed** (A4) — see above; the only V3/zGuard seam in this pass, now hardened.
- **Terminal output is inert** — text/emoji only, no markup.
- **No exec / no network / no file-write** — read-only data load through the shared resolver; degrades to `{}` (A1).
- **Layer-0 discipline** — stdlib (`html`/`typing`) + siblings (`._data`, `.sanitize`) at top; `ZMODE_ZBIFROST` lazy-imported inside the method (A3).
- **A6:** docstrings corrected to `from zSys.accessibility import get_icon_mapper`.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

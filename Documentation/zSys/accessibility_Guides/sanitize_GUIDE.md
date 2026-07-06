# zSys Accessibility — Sanitize Guide

> **Module:** `core/zSys/accessibility/sanitize.py`
> **Purpose:** The single source of truth for what may be interpolated into accessibility-emitted web markup — allowlist validators for Bootstrap-Icons names and CSS class hints, fail-closed.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

---

## Why this exists (A4)

Icon names and CSS class hints originate from `.zolo` content authored **outside the open-core trust boundary** (agent/author-controlled). When rendered for zBifrost they are interpolated into raw HTML. Without validation, a crafted value escapes the attribute and injects script — **stored XSS** on a network-served, potentially multi-tenant (zCloud) page.

These two functions are the **one place** that decides what is safe to emit. Everything on the web path goes through them.

---

## The contract

```python
_ICON_NAME_RE  = re.compile(r"^[a-z0-9-]+$")     # Bootstrap-Icons charset
_CLASS_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$") # one CSS class token

def safe_icon_name(icon_name: str) -> str:
    if not icon_name:
        return ""
    clean = icon_name.removeprefix("bi-")
    return clean if _ICON_NAME_RE.match(clean) else ""   # else → "" (fail-closed)

def safe_class_attr(value: str) -> str:
    if not value:
        return ""
    return " ".join(t for t in value.split() if _CLASS_TOKEN_RE.match(t))  # drop bad tokens
```

| Function | Input | Output |
|----------|-------|--------|
| `safe_icon_name` | a Bootstrap-Icons name (`bi-` optional) | the name iff `^[a-z0-9-]+$`, else `""` |
| `safe_class_attr` | a space-separated class string | only the `^[A-Za-z0-9_-]+$` tokens, space-joined (`""` if none) |

**Examples**

```
safe_icon_name("bi-arrow-up")       → "arrow-up"
safe_icon_name('x"><script>')       → ""              # rejected whole
safe_class_attr("zText-primary")    → "zText-primary"
safe_class_attr('a "><b c')         → "a c"           # bad token dropped, good kept
```

---

## Design principles

- **Allowlist, not denylist.** We permit a known-safe charset rather than trying to strip known-bad sequences — no bypass via novel payloads.
- **Fail-closed.** An invalid icon name returns `""`; the caller then emits **no markup** (inert escaped text). We never escape-and-pass a questionable value through.
- **Per-token for classes.** A class string can carry several tokens; one bad token doesn't poison the rest — the bad token is dropped, the valid ones survive.
- **The character set *is* the sanitizer.** No HTML parsing, no escaping heuristics — just a bounded grammar.

---

## Who calls it

| Caller | Use |
|--------|-----|
| `icon_mapper.render_for_mode` (web branch) | `safe_icon_name(name)` gates the `<i>` tag; `safe_class_attr(size/color)` filters the `<span>` classes |
| `e_zDisplay/.../basic/outputs/icon_renderer.py` | `safe_class_attr(event_data['_zClass'])` before the `_zClass` wrap |

Two emission seams, **one SSOT** — there is no third unescaped path.

---

## Trust notes

- **No exec / no network / no file-write / no state.** Pure functions over `re` — deterministic, side-effect-free.
- **Layer-0 clean.** Imports `re` only; no `zOS.*`, no siblings.
- **Exported from the package** — `from zSys.accessibility import safe_icon_name, safe_class_attr` (A6), so future web-emitting call sites reuse the SSOT instead of re-inventing validation.

**[← Back to Accessibility Guide](../accessibility_GUIDE.md) | [Home](../../../README.md)**

# zLoom Dye Module Guide

> **Module:** `n_zLoom/zLoom_modules/value_ops.py` (dye chain)
> **Purpose:** Finish a resolved value on its way to the page — zLoom's `{{ x | f }}`.

---

## Overview

A **dye** finishes a value. It never fetches — the reel is the [spool](spool_GUIDE.md), the finish is the dye. This is jinja's filter pipe, kept verbatim because `|` is already declarative and free in the grammar.

```yaml
content: %data.user.name | title          # "alice" → "Alice"
content: %data.post.body | truncate(140)  # clip long prose
content: %data.user.nickname | default(friend)   # rescue a miss
```

Chain as many as you like — read left-to-right:

```yaml
content: %data.user.handle | trim | lower
```

---

## The dye set

| Dye | Effect | Notes |
|-----|--------|-------|
| `default(text)` | value, or `text` if missing/blank | runs **before** the literal-on-miss rule — rescues a miss |
| `upper` / `lower` / `title` | case transforms | |
| `trim` | strip surrounding whitespace | |
| `truncate(n)` | clip to `n` chars | |
| `round(n)` | round a number to `n` places | |
| `date(fmt)` | format a date/timestamp | `fmt` is a strftime-style pattern |

---

## Behavior rules

- **`default` rescues only a real miss** — a missing/blank value. It never overrides a genuine `0` or `false` (those are values, not misses).
- **Unknown dye is left as plain text** — `%x | typo` renders literally, a visible clue, never silently eaten.
- **A dye finishes ONE value** — it does not reach across tokens or fetch data.

---

## Module internals

The chain lives in `value_ops.py`: after `resolve_value` pulls the raw value off its reel, it splits the string on `|`, matches each segment against the dye table, and applies them in order. A dye with an argument (`truncate(140)`, `default(friend)`) is parsed for its inner literal. The result is a finished string dropped back into `content` / `label` / wherever the token sat.

Because dyes run **inside** `resolve_value` — the same call zCLI and Bifrost both use — a `| title` looks identical in the terminal and the browser.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

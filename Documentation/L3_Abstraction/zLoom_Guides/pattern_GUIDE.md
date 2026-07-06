# zLoom Pattern Module Guide

> **Modules:** `n_zLoom/zLoom_modules/{structure_ops,component_expand}.py`
> **Purpose:** A shape you write once and reuse — zLoom's `{% macro %}` / `{% include %}`.

---

## Overview

A **pattern** is a reusable UI shape. Where a [spool](spool_GUIDE.md) weaves a live *value* into a slot, a pattern weaves a live *shape* — a whole block subtree — into the tree. This is jinja's macro, and it is what turns near-identical leaves (drifting, DRY-violating) into one definition invoked many times.

Patterns expand at **load time** (before render), so by the time a value token is resolved the shape is already in place.

---

## Grammar

**Define** under `zLoom/patterns/` (each top-level key IS a pattern name). A `%<param>` marks a slot:

```yaml
# zLoom/patterns/zUI.shop.zolo
productCard:
    _zClass: zc-card
    Title:
        zText:
            content: %title          # slot
    Price:
        zText:
            content: %price          # slot
```

**Invoke** in **key position** — a `%<name>:` key whose children fill the slots:

```yaml
Grid:
    %productCard:
        title: Wireless Buds
        price: $59
```

→ expands **in place** into the full `productCard` subtree with the slots filled.

---

## Slot rules

- A slot value that is **exactly** `%param` is replaced **whole** — a scalar OR a whole block subtree.
- `%param` **inside a longer string** is textual-substituted (`content: Buy %title now`).
- **Render tokens pass through** — a `%session.*` / `%data.*` inside a pattern is NOT a slot; it is left untouched for render-time resolution.

---

## Module internals

| Module | Role |
|--------|------|
| `component_expand.py` | Pure engine — takes a pattern def + a slot dict, deep-copies the def, substitutes each `%param` (whole-value or in-string), returns the expanded subtree. Knows nothing about the registry. |
| `structure_ops.py` | `StructureOps.expand_components` — walks a block, finds `%name:` keys, looks the name up in the `zLoom/patterns/` registry, calls `component_expand`, and splices the result in place. |

**Fails open:** an unknown `%name:` is left as-is with a warning; a missing slot leaves its `%param` literal — a clue, never a crash.

---

## Relationship to Shuttle

One pattern across a **list** is a [shuttle](shuttle_GUIDE.md) (`zShuttle`) — it names a reel + this pattern and weaves one copy per row, auto-filling each slot from the matching column.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

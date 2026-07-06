# zLoom Shuttle Module Guide

> **Modules:** `n_zLoom/zLoom_modules/{shuttle_expand,loop_ops}.py`
> **Purpose:** One pattern across a whole list — zLoom's `{% for %}`.

---

## Overview

A **shuttle** weaves one [pattern](pattern_GUIDE.md) across every row of a list. It is jinja's `{% for item in items %}` — but you never write the loop variable. You name the reel and the shape; zLoom reads the pattern's slots and feeds each `%item.<slot>` from the matching **column**.

```yaml
Grid:
    zShuttle:
        zSpool: products        # the list reel
        zPattern: productCard   # the shape (one copy per row)
```

→ four products in the reel = four `productCard` blocks, each slot filled from its row.

---

## Per-row gate

Add a `zGate:` to keep only rows that pass — the [gate](gate_GUIDE.md) decides, once per row:

```yaml
zShuttle:
    zSpool: products
    zPattern: productCard
    zGate: {%item.stock: {zAbove: 0}}     # only in-stock rows get a card
```

A **bare token** (`zGate: %item.stock`) is a truthiness test; a **dict** filters by value.

---

## Lowering pipeline

A shuttle is sugar. It lowers, at **load time**, to the raw loop primitive:

```yaml
# authored
zShuttle: {zSpool: products, zPattern: productCard}

# lowers to (shuttle_expand.py)
zList:
    source: %data.products
    each:
        %productCard: {title: %item.title, price: %item.price_usd, ...}   # slots auto-filled
```

Then, at **bind time**, `loop_ops` expands the `zList`: one `zListItem__N` block per row, each `%item.*` baked into its copy. There is **no render-time loop** left to reason about.

---

## Module internals

| Module | Role |
|--------|------|
| `shuttle_expand.py` | `expand_shuttles` — finds `zShuttle:`, reads the named pattern's slots, auto-builds the `each:` template (one `%item.<slot>` per slot), emits a `zList`. |
| `loop_ops.py` | `LoopOps` — `expand_list_bindings` iterates `source`, pushes an `%item` frame per row (`_push_row`/`_pop_row`, a render-scoped frame stack — **not** the session), resolves the row's tokens, and bakes per-row [knots](knot_GUIDE.md) *while the frame is live*. |

**Raw form:** write `zList` directly (a `source:` + a hand-wired `each:` template) when you need a per-row structure that isn't a named pattern.

**`%item` ownership:** the loop cursor is loop-scoped and owned here — it is **not** a `zVar` and never touches the session.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

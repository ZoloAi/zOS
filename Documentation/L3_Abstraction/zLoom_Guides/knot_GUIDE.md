# zLoom Knot Module Guide

> **Modules:** `n_zLoom/zLoom_modules/{knot_ops,knot_eval}.py`
> **Purpose:** A value COMPUTED on the spot — zLoom's `{{ a+b }}` / ternary.

---

## Overview

A **knot** ties `%` threads and literals into **one computed value**, declared as a step. It is jinja's inline expression (`{{ price * 2 }}`, `A if C else B`) — but there is **no formula string and no `eval`**. Every operation is a named, declarative op, so a knot is safe by construction and reads the same to a human and an agent.

```yaml
# "Buy 2 for $118"
zKnot:
    zJoin: [Buy 2 for $, {zMul: [%item.price_usd, 2]}]
```

---

## Ops

| Op | Effect | Notes |
|----|--------|-------|
| `zAdd` `zSub` `zMul` `zDiv` | arithmetic | `zDiv` by 0 → empty |
| `zJoin` | concatenate | optional `sep:` |
| `zIf` | ternary | condition delegates to [zGate](gate_GUIDE.md) |

**Operands** are `%` threads, literals, or **nested knots** — compose freely.

**Ternary reuses the gate:** a `zIf` *condition* is a `zGate` predicate. zKnot only **selects** `then` / `else`; zGate **decides** — so `zAbove` / `zSet` / `zAll` all work inside a knot:

```yaml
zKnot:
    zIf: {%item.stock: {zAbove: 0}}
    then: In stock
    else: Sold out
```

---

## Two authored forms (a grammar constraint)

`content` / `label` are **prose slots** — the parser slurps whatever is under them into text. So a knot cannot sit *directly* under `content:`. Two forms:

**Element-child form** (for prose slots) — write the knot as a `zKnot:` **child** of the element; zLoom writes the result into `content`, keeping siblings like `_zClass`:

```yaml
Stock:
    zText:
        _zClass: zc-eyebrow
        zKnot:
            zIf: {%item.stock: {zAbove: 0}}
            then: In stock
            else: Sold out
```

**Short value form** (any non-prose slot) — put the op-dict inline:

```yaml
label: {zAdd: [%a, %b]}
```

---

## Module internals

| Module | Role |
|--------|------|
| `knot_eval.py` | Pure engine — `evaluate_knot` unwraps the IR and dispatches to `_eval_arith` / `_eval_join` / `_eval_if`; `is_op_ir` / `is_knot` detect a knot node. A `zIf` condition is handed to `zos.zgate.evaluate`. |
| `knot_ops.py` | `KnotOps` mixin — `resolve_knot` (one expr) and `expand_knots` (walk a block, collapse every knot node into its computed value). |

**Where it collapses:** page-scoped knots collapse in `prepare_block_render` **after** loops; per-row knots collapse inside `loop_ops` **while the `%item` frame is live** (so each card sees its own row). Bifrost mirrors the exact same `expand_knots` call — no CLI⇄Bifrost drift.

**Fail-safe:** a bad op / missing operand / non-number / ÷0 → **empty**. Never a wrong value, never a crash.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

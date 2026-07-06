# zGate Module Guide (folded into zLoom)

> **Modules:** `n_zLoom/zGate.py` (facade, `zos.zgate`) + `zLoom_modules/{gate_evaluator,gate_lowering}.py`
> **Purpose:** ONE decision engine for every gate — zLoom's `{% if %}` / tests.

---

## Overview

**zGate** answers every yes/no in zOS with one grammar: an authed page, a per-row filter, a wizard branch, a ternary condition. Before, gating was scattered across `zRBAC` blocks and freeform `if:` expressions; zGate unifies them. It is a **second facade in the `n_zLoom` package** (`zos.zgate`) — folded in, not a separate subsystem — because gating is **pure composition over zLoom-resolved values**: zLoom weaves, zGate decides.

```yaml
# gate a nav item / page / block
zGate: {authed: true}                       # must be logged in
zGate: {role: admin}                        # ... with a role
zGate: {%data.cart.total: {zAbove: 100}}    # a business value
zGate: {zAll: [{authed: true}, {%item.tier: {zIN: [gold, plat]}}]}
```

---

## Vocabulary

**Combinators:**

| Token | Meaning |
|-------|---------|
| `zAll` | every child must pass (AND) |
| `zAny` | at least one passes (OR) |
| `zNot` | negate |

**Comparators** (`{%token: {op: operand}}`):

| Token | Test |
|-------|------|
| `zSet` / `zNotSet` | token has / lacks a value |
| `zNull` | token is null/empty |
| `zAbove` / `zBelow` | numeric `>` / `<` |
| `zIN` | value in a list |
| `zBetween` | value within a range |

**Auth keys** (delegate to identity): `authed` / `require_auth`, `role` / `require_role`, `zGuest`.

A **bare token** is a truthiness test (`zGate: %item.stock`).

---

## The trust invariant (never violate)

Every `authed` / `role` / `require_*` predicate delegates to **`zos.auth.check_zrbac`**, which owns the zGuard identity seam. zGate holds no secrets and makes **no identity decision inline** — which is exactly why it is safe in the public runtime.

- ✅ **Trust checks** use the auth keys: `{role: admin}`.
- ❌ **Never** fake a trust check with a value compare: `{%session.is_admin: true}`.
- `%token` comparators (`zAbove`, `zIN`, …) are for **business** values — cart total, tier, stock — resolved through `zos.zloom.resolve_value`, reusing zData's comparator vocabulary.

---

## Public API (`zos.zgate`)

```python
gate.evaluate(predicate, context)   # predicate IR → (granted: bool, reason: str)
gate.gate_predicate(container)      # pull the authored zGate: (or transitional zRBAC:) off a block
gate.check(container, context)      # extract + evaluate in one call
zGate.references_zhat(predicate)    # static — is this a wizard-local %zHat gate?
gate.lower_zrbac(block)             # migration bridge: zRBAC block → zGate IR
gate.lower_if(expression)           # migration bridge: legacy if: expr → zGate IR
```

---

## Module internals

| Module | Role |
|--------|------|
| `gate_evaluator.py` | Pure engine — `evaluate_gate(ir, resolver, context)` walks the predicate tree, resolves `%tokens` through the given resolver (normally `zos.zloom`), applies combinators + comparators, delegates auth keys to `check_zrbac`, returns `(granted, reason)`. |
| `gate_lowering.py` | Migration bridge — lowers legacy `zRBAC:` blocks and freeform `if:` expressions into zGate IR so old leaves keep working during the cutover. |
| `zGate.py` | Facade — thin wrappers + `references_zhat` (a `%zHat.*` gate is **wizard-local**, resolved against the wizard hat context, not a zLoom namespace). |

---

## Where zGate is consumed

- **Render gate** — a block/nav item with `zGate:` is filtered before display (`gate_predicate`).
- **Per-row filter** — a [shuttle](shuttle_GUIDE.md)'s `zGate:` runs once per row.
- **Ternary** — a [knot](knot_GUIDE.md)'s `zIf` condition is a zGate predicate.
- **Wizard branch** — a step's `zGate:` (with `%zHat.*`) decides whether the step runs (evaluated via a hat-backed resolver shim in the wizard runtime).
- **Data access** — zData's fail-closed access guard reads the same `zRBAC` vocabulary through `check_zrbac`.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

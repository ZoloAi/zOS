**[← Back to zData Guide](zData_GUIDE.md) | [Home](../../README.md) | [Next: zBifrost Guide →](zBifrost_GUIDE.md)**

---

# zLoom

**zLoom** is a **Layer 3 abstraction subsystem** in **zOS**.
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

zLoom is the **dynamic-grammar layer** — everything that makes a page *live* rather than *hardcoded*. You mark a spot with the `%` sigil, name what goes there, and zLoom weaves in a real value **before** the page renders. It is zOS's answer to a template engine (jinja's `{{ }}` / `{% %}`), reframed the declarative way: a live value **always has a declared source**, so one sigil covers them all.

You get:

- **One sigil, two positions** — `%token` (value) and `%name:` (shape)
- **A declared source for every value** — a named `zSpool`, an inline `_data`, or an ambient reel (`%session` / `%auth` / `%route` / `%item` / `%var`)
- **Value finishes** — the `|` pipe (`zDye`: upper/lower/title/trim/truncate/round/date/default)
- **Reusable shapes** — `zPattern` (jinja `{% macro %}`), expanded at load
- **Loops** — `zShuttle` (jinja `{% for %}`), lowered to `zList`
- **Computed values** — `zKnot` (jinja `{{ a+b }}` / ternary), declared, eval-free
- **One decision engine** — `zGate` (folded in): every yes/no gate (auth / conditional / value), one grammar
- **Same result in zCLI and zBifrost** — the `%` is resolved before the render split

---

## Architecture Overview

zLoom follows the **facade + mixins** pattern. The `zLoom` facade composes one mixin per responsibility; pure engines sit behind them. `zGate` is a **second facade in the same package** (folded in, not a separate subsystem) because gating is pure composition over zLoom-resolved values — zLoom weaves, zGate decides.

### Facade Layer

```
zLoom (zLoom.py)  →  zos.zloom        weave: spool · dye · pattern · shuttle · knot · route
zGate (zGate.py)  →  zos.zgate        decide: one predicate engine for every gate
```

### Facets (author-facing) → module map

| Facet | Author writes | jinja analogue | Engine module | Guide |
|-------|---------------|----------------|---------------|-------|
| **Spool** | `%data.<name>.<field>` | `{{ x }}` | `value_ops` + `token_resolver` + `query_ops` | [spool_GUIDE.md](zLoom_Guides/spool_GUIDE.md) |
| **Dye** | `%value \| finish` | `{{ x \| f }}` | `value_ops` (dye chain) | [dye_GUIDE.md](zLoom_Guides/dye_GUIDE.md) |
| **Pattern** | `%name:` (key position) | `{% macro %}` | `structure_ops` + `component_expand` | [pattern_GUIDE.md](zLoom_Guides/pattern_GUIDE.md) |
| **Shuttle** | `zShuttle: {zSpool, zPattern}` | `{% for %}` | `shuttle_expand` → `loop_ops` (`zList`) | [shuttle_GUIDE.md](zLoom_Guides/shuttle_GUIDE.md) |
| **Knot** | `zKnot: {zAdd/zJoin/zIf…}` | `{{ a+b }}` / ternary | `knot_ops` + `knot_eval` | [knot_GUIDE.md](zLoom_Guides/knot_GUIDE.md) |
| **Gate** | `zGate: {authed/role/%…}` | `{% if %}` / tests | `gate_evaluator` + `gate_lowering` (`zGate` facade) | [gate_GUIDE.md](zLoom_Guides/gate_GUIDE.md) |

> Two ambient stores round out the sigil: **`%route.*`** (request-scoped, fed by zServer → `route_ops`) and **`%item.*`** (loop-scoped row cursor, owned by `loop_ops` — a render-scoped frame stack, not the session). Neither is a `zVar`.

This guide is the **facade overview**. For deep dives into each facet, see the guides in `zLoom_Guides/`.

---

## Module Structure

```
n_zLoom/                                  (core/L3_Abstraction/n_zLoom)
├── zLoom.py                              Facade — composes the 7 mixins below
├── zGate.py                              zGate facade (folded in) — zos.zgate
└── zLoom_modules/
    ├── value_ops.py                      ValueOps  — %token resolution (render + gates + WHERE) + dye chain
    ├── query_ops.py                      QueryOps  — build + execute a block's declared reads (→ zData)
    ├── binding_ops.py                    BindingOps — zLoom/ registry + the prepare_block_render SSOT seam
    ├── loop_ops.py                       LoopOps   — zList loop expansion + %item frame stack
    ├── structure_ops.py                  StructureOps — zPattern component (structure) expansion
    ├── route_ops.py                      RouteOps  — dynamic-route params store (%route.*), fed by zServer
    ├── knot_ops.py                       KnotOps   — zKnot computed-value collapse (two authored forms)
    ├── token_resolver.py                 pure engine — the ONE %token lookup SSOT (every namespace)
    ├── component_expand.py               pure engine — zPattern structure expansion
    ├── shuttle_expand.py                 zShuttle → zList lowering (load-time)
    ├── knot_eval.py                      pure engine — zKnot evaluator (zAdd/zSub/zMul/zDiv/zJoin/zIf)
    ├── gate_evaluator.py                 pure engine — zGate predicate → (granted, reason)   [folded]
    └── gate_lowering.py                  zRBAC / if: → zGate IR lowering (migration bridge)   [folded]
```

---

## The `%` grammar (quick reference)

The whole subsystem is one character — `%` — read by **position**:

```
value position   %token      → a live VALUE, woven at render time   (spool · dye · knot)
key position     %name:      → a reusable SHAPE, woven at load time  (pattern · shuttle)
```

**Contract:** mark the spot, name the value, zLoom fills it before the page is real. A miss is left **literal** in text (a visible clue) / resolves to nothing in a decision — never a crash. A token *inside* a resolved value is never re-scanned (single-pass — user data can't smuggle in a second token).

**Reels a `%token` can pull from:**

| Reel | Token | Scope | Owner |
|------|-------|-------|-------|
| declared spool | `%data.<name>.<field>` | page | `binding_ops` (via `zMeta.zSpool` / `zLoom/spools/`) |
| inline read | `%data.<key>.<field>` | block | `query_ops` (`_data:` sibling) |
| session | `%session.*` | session | Identity (read-only) |
| auth | `%auth.*` | session | Identity (read-only) |
| route param | `%route.<param>` | request | `route_ops` (fed by zServer) |
| loop row | `%item.<field>` | loop | `loop_ops` (frame stack) |
| durable set | `%var.<name>` / `%name` | session | `zVar` (author/session set) |

---

## Trust Model & zGuard Seams

zLoom is **fully open-core** — there is no sealed engine here. It is a thin declarative layer that **borrows the muscle**: it declares the grammar and touches no DB or file itself.

- **A spool query** is handed to **`zData`** (`zos.data.handle_request`) to run — the raw row executes server-side and never ships to the browser.
- **A `%session.*` / `%auth.*` read** comes off the live session **Identity** owns.
- **A gate** (`zGate`) delegates trust to **`zos.auth.check_zrbac`** and resolves values through `zos.zloom.resolve_value`, reusing zData's comparator vocabulary. It holds no secrets and makes **no identity decision inline** — which is exactly why it is safe to live in the public runtime.

> **THE trust invariant (never violate):** every `authed` / `role` / `require` predicate delegates to `check_zrbac` (which owns the zGuard identity seam). `%token` comparisons are for **business** values (cart total, tier) — a trust check must use the auth keys, never `%session.is_admin == true`. See [gate_GUIDE.md](zLoom_Guides/gate_GUIDE.md).

**Single-pass safety.** Token resolution is one pass; a value woven in from user data is never re-scanned for a second `%token`, so there is no injection-by-interpolation surface (safe by construction, not policy).

---

## Initialization Order

zLoom is constructed **after `m_zData`** (it runs zData reads at resolve time) and **before `o_zBifrost`**; `zGate` is constructed **right after `zLoom`** (it delegates to `check_zrbac` and reads values through `zloom`, so both must exist first):

```
l_zEngine → m_zData → zLoom (zos.zloom) → zGate (zos.zgate) → o_zBifrost → p_zShell
```

**Usage:**
```python
from zOS import zOS

z = zOS()                 # framework booted
loom = z.zloom            # weave facade
gate = z.zgate            # decide facade (folded into the same package)

# resolve a single live value
name = loom.resolve_value("%data.current_user.username", context)

# answer a gate
granted, reason = gate.check({"zGate": {"role": "admin"}})
```

---

## Facade API Reference

**Render seam (the one place every path goes through):**
```python
# Bind declared reads, resolve %tokens, expand loops + knots — the SSOT seam
loom.prepare_block_render(block, context)
```

**Value resolution:**
```python
loom.resolve_value("%data.cart.total", context)   # → live value (render / gate / WHERE)
```

**Loops & structure (usually invoked inside prepare_block_render):**
```python
loom.expand_shuttles(block)          # zShuttle → zList (load-time lowering)
loom.expand_list_bindings(block, resolved)   # zList → per-row blocks (bind-time)
loom.expand_knots(block, context)    # zKnot value-dict → computed scalar
loom.expand_components(block)        # %name: pattern → expanded subtree
```

**Route params (fed by zServer):**
```python
loom.set_route_params({"contact_id": "42"})   # request scope
loom.get_route_params()
loom.clear_route_params()
```

**Gating (`zos.zgate`):**
```python
gate.evaluate(predicate, context)    # predicate IR → (granted, reason)
gate.gate_predicate(container)       # extract authored zGate: from a block
gate.check(container, context)       # extract + evaluate in one call
zGate.references_zhat(predicate)     # is this a wizard-local %zHat gate?
```

---

## What's Next?

You've mastered **zLoom** (dynamic grammar — weave + decide). Continue to **zBifrost** — the Terminal↔Web bridge that renders zLoom-woven blocks in the browser exactly as the terminal sees them.

**→ Continue to [zBifrost Guide](zBifrost_GUIDE.md)**

---

**[← Back to zData Guide](zData_GUIDE.md) | [Home](../../README.md) | [Next: zBifrost Guide →](zBifrost_GUIDE.md)**

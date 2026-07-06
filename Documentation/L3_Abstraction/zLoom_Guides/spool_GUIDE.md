# zLoom Spool Module Guide

> **Modules:** `n_zLoom/zLoom_modules/{value_ops,token_resolver,query_ops,binding_ops}.py`
> **Purpose:** Resolve a `%token` to a live value off its declared reel — zLoom's `{{ x }}`.

---

## Overview

A **spool** is *where a live value comes from*. In jinja, `{{ x }}` prints whatever `x` happens to be in the template context — the source is implicit. zLoom's twist: **a value always has a declared source**, so one `%` sigil covers a DB read, the session, a route param, and a loop row alike.

```
Welcome back, %data.current_user.username
```

When the block is prepared, zLoom walks each `%token`, looks the name up in its reel, and drops the answer in. Find a value → the token becomes it. Miss → the token is left **literal** (a visible clue), never a crash.

---

## Grammar

```yaml
# declared reel — a file under zLoom/spools/ (top-level key = reel name)
# a block opts in:
zMeta:
    zSpool: [products]          # this block can read %data.products.*

Card:
    zText:
        content: %data.products.name         # field off the reel

# inline read — a one-off, no file
List:
    _data:
        recent:
            model: @.models.zSchema.crm.contacts
            where: {owner: %session.user_id}
            options: {limit: 5}
    # → %data.recent.* available in this block
```

**Ambient reels** (always carried, nothing to declare): `%session.*` · `%auth.*` · `%route.<param>` · `%item.<field>` · `%var.<name>` (or bare `%name`).

**Style-B full ref** when you want the exact def: `@.zLoom.spools.zUI.<file>.<reel>`.

---

## Module internals

| Module | Role |
|--------|------|
| `token_resolver.py` | **The SSOT** — `_lookup` resolves every namespace (`data` / `session` / `auth` / `route` / `item` / bare `var`). One navigator, one place a namespace is added. |
| `value_ops.py` | `ValueOps.resolve_value` — public entry; walks a string for `%tokens`, applies the [dye](dye_GUIDE.md) chain, returns the finished value. |
| `query_ops.py` | `QueryOps.resolve_block_data` — builds + runs a block's declared reads by handing the query to **zData** (`zos.data.handle_request`); `_interpolate_session_values` fills `%route.*` / bare `%var` in WHERE clauses via the resolver. |
| `binding_ops.py` | `BindingOps` — loads the `zLoom/` registry, assembles the binding block from `zMeta.zSpool`, and owns `prepare_block_render` (the one seam every render path calls). |

**Miss contract:** a `%token` that resolves to nothing is left literal in text; in a gate/decision it resolves to `None` (fails the test). `default` ([dye](dye_GUIDE.md)) is the clean rescue for a miss.

---

## Boundary

zLoom owns the **binding grammar**; zData **only executes** the query. The raw row runs server-side and never ships to the browser — the page receives the resolved scalar, not the query. Resolution happens **before** the zCLI/Bifrost render split, so both surfaces weave in byte-identical values.

---

**[← Back to zLoom Guide](../zLoom_GUIDE.md)**

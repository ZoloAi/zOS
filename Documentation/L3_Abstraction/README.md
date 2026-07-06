# L3 Abstraction — Documentation

Technical index for the **Abstraction layer** documentation cluster: the subsystems that sit on top of the Handling layer (L2) and compose its primitives into higher-order capabilities — declarative multi-step workflows, full data orchestration, the dynamic-content grammar (weave + decide), the Terminal↔Web bridge, and the interactive command center.

This README is the **technical entry point** to the L3 guides. For a high-level, code-side orientation of the layer, see [`core/L3_Abstraction/README.md`](../../core/L3_Abstraction/README.md). For the Handling layer beneath it, see [L2 Handling docs](../L2_Handling/README.md).

| Order | Subsystem | Facade | Main guide | Status |
|-------|-----------|--------|------------|--------|
| **l** | `l_zWizard` | `z.wizard` | [zWizard_GUIDE](zWizard_GUIDE.md) | **Migrated** — behaviour-only (engine sealed in zGuard) |
| **m** | `m_zData` | `z.data` | [zData_GUIDE](zData_GUIDE.md) · [zData_Guides/](zData_Guides/) | **Migrated + refreshed** |
| **n** | `n_zLoom` | `z.zloom` · `z.zgate` | [zLoom_GUIDE](zLoom_GUIDE.md) · [zLoom_Guides/](zLoom_Guides/) | **Migrated + refreshed** |
| **o** | `o_zBifrost` | `z.bifrost` | [zBifrost_GUIDE](zBifrost_GUIDE.md) | **Migrated** — behaviour-only (runtime sealed in zGuard) |
| **p** | `p_zShell` | `z.shell` | [zShell_GUIDE](zShell_GUIDE.md) · [zShell_Guides/](zShell_Guides/) | **Migrated + refreshed** |

> **Open / closed split:** `l_zWizard` and `o_zBifrost` are **sealed** — their open-core guides document *behaviour* only; the engine/runtime mechanisms live in the private zGuard docs. `m_zData`, `n_zLoom`, and `p_zShell` are **fully open-core** and each ship a `*_Guides/` deep-dive set. The bridge *client* is documented in its own public repo, [`zbifrost-client`](https://github.com/zolo-media/zbifrost-client).

> **zGate folded in:** gating is not a standalone subsystem — it is a second facade (`z.zgate`) inside `n_zLoom`, because every gate is pure composition over zLoom-resolved values. zLoom weaves, zGate decides. See [gate_GUIDE](zLoom_Guides/gate_GUIDE.md).

> **Root vocabulary:** cross-subsystem protocol literals (session-dict keys, run modes, file-type ids, path symbols, control-flow returns) are single-sourced in the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) module (`core/zVocabulary.py`). L3 subsystems draw from it instead of re-declaring.

---

## l_zWizard — workflow loop engine (`z.wizard`)

The declarative wizard engine: iterate steps from a `.zolo` definition, dispatch each action, and handle navigation signals (`zBack`/exit/stop/error) with step-result accumulation, interpolation, and transaction management. **The first L3 subsystem migrated as behaviour-only** — its engine is sealed in zGuard.

**Public surface (selected):** `handle(zWizard_obj)` (high-level entry), `execute_loop(items_dict, dispatch_fn, navigation_callbacks, context, start_key, …)` (core iterator).

> **Sealed (fail-closed):** `l_zWizard` ships as an `__init__.py` shim that re-exports `zguard.wizard.zWizard`; without zGuard, first use raises `ImportError` ("z patch") — it never degrades to a stub engine. The loop algorithm, RBAC, transactions, and interpolation are **proprietary — see the private zGuard wizard docs**.

**Code:** `core/L3_Abstraction/l_zWizard/__init__.py` (shim) → `zguard.wizard` (sealed wheel).

---

## m_zData — data orchestration (`z.data`)

Full data subsystem: declarative CRUD, DDL/schema management, aggregations, and migrations across multiple backends (SQLite, PostgreSQL, CSV) behind one facade. Parses the data command contract, validates against zSchema, and orchestrates the owning backend.

**Public surface (selected):** `z.data.handle(...)` (data command contract — `action`/`model`/`table`/`data`/`where`/…), plus the CRUD/DDL/aggregation/migration operations.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `orchestrator` | request coordination, schema/connection/lifecycle | [orchestrator_GUIDE](zData_Guides/orchestrator_GUIDE.md) |
| `crud` | create / read / update / delete operations | [crud_operations_GUIDE](zData_Guides/crud_operations_GUIDE.md) |
| `ddl` | table/schema definition operations | [ddl_operations_GUIDE](zData_Guides/ddl_operations_GUIDE.md) |
| `aggregations` | grouping, counts, rollups | [aggregations_GUIDE](zData_Guides/aggregations_GUIDE.md) |
| `migration` | schema/data migration | [migration_GUIDE](zData_Guides/migration_GUIDE.md) |
| `backends` | SQLite / PostgreSQL / CSV drivers | [backends_GUIDE](zData_Guides/backends_GUIDE.md) |
| `parsers` | data-command + schema parsing | [parsers_GUIDE](zData_Guides/parsers_GUIDE.md) |
| `schema_manager` | zSchema management | [schema_manager_GUIDE](zData_Guides/schema_manager_GUIDE.md) |
| `validators` | input/constraint validation | [validators_GUIDE](zData_Guides/validators_GUIDE.md) |

> **Trust:** modern zData ops are **structured / parameterized** (no raw-string SQL on the happy path); prefer `data:`/`where:` dicts over raw `query:` strings. Backend credentials flow through `z.config`/`z.comm`. No code-exec surface of its own.

**Code:** `core/L3_Abstraction/m_zData/zData.py` (facade) + `zData_modules/`.

---

## n_zLoom — dynamic grammar: weave + decide (`z.zloom` · `z.zgate`)

The dynamic-content layer: everything that makes a page *live* rather than *hardcoded*. Mark a spot with the `%` sigil, name a declared source, and zLoom weaves in the real value **before** the render split — so zCLI and zBifrost paint identical content. `zGate` is folded in as a second facade: one predicate engine for every yes/no (auth, per-row filter, wizard branch, ternary).

**Public surface (selected):** `z.zloom.prepare_block_render(block, context)` (the SSOT render seam), `resolve_value(...)`, `expand_shuttles/expand_list_bindings/expand_knots/expand_components(...)`, `set_route_params(...)`; `z.zgate.evaluate/gate_predicate/check(...)`.

| Facet | Author writes | jinja analogue | Sub-guide |
|-------|---------------|----------------|-----------|
| Spool | `%data.<name>.<field>` | `{{ x }}` | [spool_GUIDE](zLoom_Guides/spool_GUIDE.md) |
| Dye | `%value \| finish` | `{{ x \| f }}` | [dye_GUIDE](zLoom_Guides/dye_GUIDE.md) |
| Pattern | `%name:` (key position) | `{% macro %}` | [pattern_GUIDE](zLoom_Guides/pattern_GUIDE.md) |
| Shuttle | `zShuttle: {zSpool, zPattern}` | `{% for %}` | [shuttle_GUIDE](zLoom_Guides/shuttle_GUIDE.md) |
| Knot | `zKnot: {zAdd/zJoin/zIf…}` | `{{ a+b }}` / ternary | [knot_GUIDE](zLoom_Guides/knot_GUIDE.md) |
| Gate | `zGate: {authed/role/%…}` | `{% if %}` / tests | [gate_GUIDE](zLoom_Guides/gate_GUIDE.md) |

> **Trust:** zLoom is fully open-core and touches no DB/file itself — a spool query is handed to `z.data`, a `%session.*` is read off Identity, and every `authed`/`role` gate delegates to `z.auth.check_zrbac` (which owns the zGuard identity seam). Token resolution is **single-pass** — a value woven from user data is never re-scanned, so there is no injection-by-interpolation surface.

**Code:** `core/L3_Abstraction/n_zLoom/zLoom.py` (facade) + `zGate.py` + `zLoom_modules/`.

---

## o_zBifrost — Terminal↔Web bridge (`z.bifrost`)

Orchestrates the live zCLI↔browser bridge over WebSocket (built on `z.comm`): a remote web client renders zOS UI and drives a **sandboxed** session. **Migrated as behaviour-only** — the bridge runtime and anything that reveals zolo's rendering mechanism are sealed in zGuard; the browser client is the public `zbifrost-client` repo.

**Public surface (selected):** `z.bifrost` session orchestration (start/route bridge sessions) — a thin facade over the sealed runtime.

> **Sealed (fail-closed):** `o_zBifrost/__init__.py` re-exports `zguard.bifrost`; without zGuard it fails closed ("z patch") — the bridge is a **live network surface**, so there is no anonymous degrade. Bifrost sessions are **always sandboxed**, with operator-trust gating via zEnv. The protocol, chunk rendering, and connection bridge are **proprietary — see the private zGuard bifrost docs**; the client is documented in [`zbifrost-client`](https://github.com/zolo-media/zbifrost-client).

**Code:** `core/L3_Abstraction/o_zBifrost/__init__.py` (shim) → `zguard.bifrost` (sealed wheel).

---

## p_zShell — interactive command center (`z.shell`)

The zOS REPL: a facade over the runner (input loop, history, redaction), executor (parse → route → enforce), command modules, wizard canvas, and a two-tier help system. Drives every subsystem from one command line; renders through `z.display` so it behaves in terminal **and** Bifrost modes.

**Public surface (selected):** `z.shell.run()` (REPL), command modules (`auth`/`config`/`data`/`wizard`/`ls`/`cd`/`open`/`func`/`comm`/`session`/`shortcut`/…), the wizard canvas, and the mode-aware help system.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `shell_runner` | REPL loop, prompt, history + credential redaction | [runner_GUIDE](zShell_Guides/runner_GUIDE.md) |
| `shell_executor` | parse → route → **Bifrost-seal** enforcement | [executor_GUIDE](zShell_Guides/executor_GUIDE.md) |
| `commands/` | per-command modules (UI-adapter pattern) | [commands_GUIDE](zShell_Guides/commands_GUIDE.md) |
| `wizard_canvas` | interactive staging of multi-step workflows | [wizard_canvas_GUIDE](zShell_Guides/wizard_canvas_GUIDE.md) |
| `shell_help` | two-tier, mode-aware help (hides sealed surfaces) | [help_GUIDE](zShell_Guides/help_GUIDE.md) |
| `shell_policy` | Bifrost seal + credential-redaction SSOT | [security_GUIDE](zShell_Guides/security_GUIDE.md) |
| `shell_paths` / `command_helpers` / `*_constants` | shared helpers & vocabulary | [internals_GUIDE](zShell_Guides/internals_GUIDE.md) |

> **Trust — fail-closed in remote sessions.** The executor enforces a **Bifrost seal** (`shell_policy`): destructive `data:` ops (delete/drop/migrate) and `config set/reset` are **blocked unconditionally** in Bifrost sessions. Credentials are **never accepted on argv** (always `getpass`) and are redacted from readline history; shortcut files are **path-contained** to `user_data_dir` (`.json` only, no traversal); host installs (`comm install`) are **operator-gated** (local zCLI + `ZTERMINAL_MODE: trusted`). The help system **hides sealed surfaces** from remote clients. Open-core documents the fail-closed *behaviour*; the seal **mechanisms** are in the private zGuard docs.

**Code:** `core/L3_Abstraction/p_zShell/zShell.py` (facade) + `shell_modules/`.

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to its `*_modules/`. Change behavior in the modules, not the facade signature.
- **Sealed vs open:** `l_zWizard` and `o_zBifrost` are behaviour-only (engine/runtime in zGuard, fail-closed shims); `m_zData`, `n_zLoom`, and `p_zShell` are fully open-core with `*_Guides/` sets.
- **zGate is folded, not separate:** it lives in `n_zLoom` as the `z.zgate` facade — every gate is composition over zLoom-resolved values; auth predicates delegate to `z.auth.check_zrbac`.
- **Constants are SSOT:** cross-subsystem protocol vocabulary is single-sourced in root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); subsystem-internal values stay in each subsystem's `*_constants.py`. No magic strings.
- **Docs ↔ code parity:** every guide here maps 1:1 to the code; the `zVault-zCode/` graph mirrors both (`[doc]`/`[logic]`/`[folder]`/`[subsystem]` tags, wikilinked). Vault links mirror the **repo tree** (structure), not domain/logic.
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported).

**See also:** [Home](../../README.md) · [code-side L3 overview](../../core/L3_Abstraction/README.md) · [L4 Orchestration docs](../L4_Orchestration/README.md) · [L2 Handling docs](../L2_Handling/README.md) · [L0 Core docs](../L0_Core/README.md)

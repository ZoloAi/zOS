# L3 — Abstraction Layer

The **abstraction tier** of zOS. These subsystems sit on top of the Handling layer (L2) and compose its primitives into higher-order capabilities: declarative multi-step workflows, full data orchestration across backends, the Terminal↔Web bridge, and the interactive command center. The Orchestration layer above (L4: zWalker, zServer, zRaven) drives them.

They initialize in **alphabetical order** during `zOS()` boot, each reachable as a facade on the live instance:

| Order | Subsystem | Facade | In one line | Guide |
|------|-----------|--------|-------------|-------|
| **l** | `l_zWizard` | `z.wizard` | Declarative multi-step workflow loop engine (`.zolo` wizards) — **behaviour-only; engine sealed in zGuard** | [zWizard_GUIDE](../../Documentation/L3_Abstraction/zWizard_GUIDE.md) |
| **m** | `m_zData` | `z.data` | Full data orchestration — CRUD/DDL/aggregations/migration across SQLite/PostgreSQL/CSV behind one facade | [zData_GUIDE](../../Documentation/L3_Abstraction/zData_GUIDE.md) |
| **n** | `n_zLoom` | `z.zloom` + `z.zgate` | Dynamic-grammar layer — **weave** (`%` sigil: spool / dye / pattern / shuttle / knot) + **decide** (`zGate:` — one predicate engine for every yes/no gate, folded in as a module) | [zLoom_GUIDE](../../Documentation/L3_Abstraction/zLoom_GUIDE.md) |
| **o** | `o_zBifrost` | `z.bifrost` | Terminal↔Web bridge orchestrator (zCLI↔browser over WebSocket) — **behaviour-only; runtime sealed in zGuard** | [zBifrost_GUIDE](../../Documentation/L3_Abstraction/zBifrost_GUIDE.md) |
| **p** | `p_zShell` | `z.shell` | Interactive command center (REPL) — routes every subsystem from one command line; dual-mode (zCLI / zBifrost) | [zShell_GUIDE](../../Documentation/L3_Abstraction/zShell_GUIDE.md) |

> Init order follows the dependency chain: the walk engine first (no upper deps); `zData` next; `zLoom` after `zData` (it runs zData reads at resolve time) and `zGate` right after `zLoom` (it delegates trust to `check_zrbac` and value resolution to `zloom`); `zBifrost` rides `z.comm`; `zShell` comes last (depends on the engine + `zData`). All build on the L1/L2 facades (`z.config`/`z.comm`/`z.loader`, `z.parser`/`z.display`/`z.dispatch`/…).
>
> **zGate is not its own subsystem** — it is folded into `n_zLoom` as a module-set (`zLoom_modules/gate_evaluator.py` + `gate_lowering.py`, facade `n_zLoom/zGate.py`). It owns no state; it is pure composition over zLoom-resolved values (zLoom weaves, zGate decides), so it lives with the resolver it depends on. It keeps its own public facade `z.zgate` and authored `zGate:` surface.

> **Open / closed split:** two of the four are **sealed** — `l_zWizard` and `o_zBifrost` ship as thin `__init__.py` shims that `try: from zguard.… import …` and **fail closed** ("z patch") without the zGuard binary wheel. The other two (`m_zData`, `p_zShell`) are **fully open-core**. The bridge *client* is a separate public repo (`zbifrost-client`).

> **Root vocabulary:** shared protocol literals (session-dict keys, run modes, file-type ids, path symbols, control-flow returns) are single-sourced in `core/zVocabulary.py` — a dependency-free leaf re-exported via the `zOS` aggregator. These subsystems draw from it rather than re-declaring. See [zVocabulary_GUIDE](../../Documentation/L0_Core/zVocabulary_GUIDE.md).

---

## l_zWizard — workflow loop engine (`z.wizard`)

The declarative wizard engine: iterate steps from a `.zolo` definition, dispatch each action, and handle navigation signals (`zBack`/exit/stop/error) with step-result accumulation, interpolation, and transaction management. **Behaviour-only in open-core** — the engine itself is sealed in zGuard.

- **Surface:** `handle(zWizard_obj)` (high-level entry) and `execute_loop(items_dict, …)` (core iterator); plus `SUBSYSTEM_NAME`/`SUBSYSTEM_COLOR`/`NAVIGATION_SIGNALS`.
- **Security (sealed, fail-closed):** `l_zWizard/__init__.py` re-exports `zguard.wizard.zWizard`; without zGuard, first use raises `ImportError` ("z patch") — it never degrades to a stub engine. Mechanisms (RBAC, transactions, interpolation) are **proprietary — see the private zGuard wizard docs**.
- **Code:** `l_zWizard/__init__.py` (shim) → `zguard.wizard` (sealed wheel)

## m_zData — data orchestration (`z.data`)

Full data subsystem: declarative CRUD, DDL/schema management, aggregations, and migrations across multiple backends (SQLite, PostgreSQL, CSV) behind one facade. Parses the data command contract, validates against zSchema, and orchestrates the owning backend. **Fully open-core.**

- **Surface:** `z.data.handle(...)` (data command contract — `action`/`model`/`table`/`data`/`where`/…), CRUD/DDL/aggregation/migration operations via `zData_modules/`.
- **Security:** structured/parameterized operations (no raw-string SQL on the happy path); backend credentials flow through `z.config`/`z.comm`. No code-exec surface of its own.
- **Code:** `m_zData/zData.py` (facade) + `zData_modules/`
- **Deep dives:** [zData_Guides/](../../Documentation/L3_Abstraction/zData_Guides/)

## o_zBifrost — Terminal↔Web bridge (`z.bifrost`)

Orchestrates the live zCLI↔browser bridge over WebSocket (built on `z.comm`): a remote web client renders zOS UI and drives a sandboxed session. **Behaviour-only in open-core** — the bridge runtime (chunk rendering, protocol, anything that reveals zolo mechanism) is sealed in zGuard; the browser client is the public `zbifrost-client` repo.

- **Surface:** `z.bifrost` session orchestration (start/route bridge sessions); thin facade over the sealed runtime.
- **Security (sealed, fail-closed):** `o_zBifrost/__init__.py` re-exports `zguard.bifrost`; without zGuard it fails closed ("z patch") — the bridge is a **live network surface**, so there is no anonymous degrade. Bifrost sessions are **always sandboxed** (operator-trust gating via zEnv). Mechanisms are **proprietary — see the private zGuard bifrost docs**.
- **Code:** `o_zBifrost/__init__.py` (shim) → `zguard.bifrost` (sealed wheel); client → [`zbifrost-client`](https://github.com/zolo-media/zbifrost-client) repo

## p_zShell — interactive command center (`z.shell`)

The zOS REPL: a facade over the runner (input loop, history, redaction), executor (parse → route → enforce), command modules, wizard canvas, and help system. Drives every subsystem from one command line; renders through `z.display` so it behaves in terminal **and** Bifrost modes. **Fully open-core.**

- **Surface:** `z.shell.run()` (REPL), command modules (`auth`/`config`/`data`/`wizard`/`ls`/`cd`/`open`/`func`/`comm`/…), the wizard canvas, and a two-tier mode-aware help system.
- **Security (fail-closed in remote sessions):** the executor enforces a **Bifrost seal** (destructive `data:` ops and `config set/reset` blocked in remote sessions); credentials are **never accepted on argv** (always `getpass`) and are redacted from readline history; shortcut files are **path-contained** to `user_data_dir` (`.json` only); host installs (`comm install`) are **operator-gated** (`ZTERMINAL_MODE: trusted`, local zCLI only). The seal **mechanisms** are documented privately in zGuard; open-core documents the fail-closed *behaviour*.
- **Code:** `p_zShell/zShell.py` (facade) + `shell_modules/`
- **Deep dives:** [zShell_Guides/](../../Documentation/L3_Abstraction/zShell_Guides/)

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to `*_modules/`. Touch the modules, not the facade signature, for behavior changes.
- **Sealed seams:** `l_zWizard` and `o_zBifrost` are `try: from zguard… / except ImportError:` shims that **fail closed** (they are an engine and a live network surface — no permissive stub). `m_zData` and `p_zShell` are fully functional open-core.
- **Constants are SSOT:** cross-subsystem protocol vocabulary lives in root `core/zVocabulary.py`; subsystem-internal values + exception hierarchies live in each subsystem's `*_constants.py`. No magic strings.
- **Docs ↔ code parity:** every guide under `Documentation/L3_Abstraction/` is kept 1:1 with the code here; sealed subsystems carry a behaviour-only `*_GUIDE.md` (deep dives live in zGuard), open-core ones add a `*_Guides/` set. The `zVault-zCode/` graph mirrors the **repo tree** (tags `[logic]`/`[doc]`/`[folder]`/`[subsystem]`, wikilinked).
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported).

**See also:** [Home](../../README.md) · [L2 Handling overview](../L2_Handling/README.md) · [L4 Orchestration overview](../L4_Orchestration/README.md) · [L3 Abstraction docs](../../Documentation/L3_Abstraction/README.md)

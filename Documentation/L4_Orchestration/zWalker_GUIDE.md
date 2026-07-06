# zWalker Guide

**[← Back to zShell Guide](../L3_Abstraction/zShell_GUIDE.md) | [Home](../../README.md) | [Next: zServer Guide →](zServer_GUIDE.md)**

> **Declarative UI orchestration** — turn a `.zolo` file into an interactive, navigable app (menus, wizards, breadcrumbs) that runs the same in the terminal **and** in the browser (zBifrost).

`zWalker` (`z.walker`) is the **Layer 4 orchestrator**: it loads a declarative UI definition (a *zVaFile*), runs the wizard loop over it, and tracks navigation — by **delegating** to the lower layers. It adds no logic of its own.

---

## What it is (and isn't)

zWalker is a **pure orchestrator**. It `extends` the L3 `zWizard` loop engine and adds only **navigation callbacks**; everything else is delegated:

- **Loads** the zVaFile → `z.loader`
- **Iterates** blocks, resolves `_data`, dispatches actions, enforces RBAC → inherited from `z.wizard`
- **Routes** each command → `z.dispatch`
- **Tracks breadcrumbs / back navigation** → `z.navigation`
- **Renders** output (terminal or HTML) → `z.display`

What zWalker does **not** do: path construction, dispatch logic, `_data` resolution, validation, or any code execution. If a change needs logic, it belongs in a lower layer — not here.

---

## The flow: `run()`

`z.walker.run()` is the single entry point. It detects the session mode and delegates:

```text
run()
 ├─ zMode == zBifrost ?
 │    └─ yes → hand `walker=self` to the sealed bridge runtime
 │             (z.bifrost.orchestrator.start) — it drives execution
 └─ no (zCLI)
      ├─ read zVaFile from zSpark   (boot config)
      ├─ z.loader.handle(...)        load + validate the zVaFile
      ├─ ensure session.zCrumbs      (breadcrumb store)
      └─ execute_loop(items_dict, navigation_callbacks, block_name)
                                      (inherited from z.wizard)
```

The session keys it reads (`zVaFile`, `zBlock`, `zMode`, `zCrumbs`) are the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) atoms — not local literals.

### Navigation callbacks

zWalker's only addition to the wizard loop is a set of thin **delegation wrappers**:

| Callback | Delegates to |
|----------|--------------|
| `on_continue(result, key)` | `z.navigation.handle_zCrumbs(key)` (track breadcrumb) |
| `on_back(result)` | `z.navigation.handle_zBack()` → re-`execute_loop()` |
| `on_exit(result)` | display + return `{exit: completed}` (soft return to caller) |
| `on_stop(result)` | display + `sys.exit()` (hard stop) |
| `on_error(error, key)` | display + `sys.exit()` |
| `on_get_trail()` / `on_pop_trail(key)` | breadcrumb trail read/rewind (zBounce) |

---

## Authoring a zVaFile

Define the UI declaratively (`.zolo` shown; `.yaml`/`.json` also work). Menu anchors and reserved keywords drive navigation:

```yaml
zVaF:
  ~Root*: [View Data, Add Record, Settings, stop]

  View Data:
    zData: {action: read, table: users, limit: 10}

  Add Record:
    zWizard:
      collect:
        zDialog: {model: User, fields: [name, email]}
      save:
        zData: {action: create, table: users, data: zHat}

  Settings:
    ~Menu*: [Change Theme, zBack]
    Change Theme:
      zDisplay: {event: info, content: Theme settings...}
```

Run it:

```python
from zOS import zOS

z = zOS()
z.zspark_obj['zVaFile'] = '@.zUI.my_app'
z.zspark_obj['zBlock'] = 'zVaF'
z.walker.run()
```

### Anchors & reserved keywords

| Token | Meaning |
|-------|---------|
| `~Root*` | Root menu anchor (entry block) |
| `~Menu*` | Sub-menu anchor |
| `zBack` | Return to the previous menu |
| `stop` | Exit the walker |
| `zHat` | Access accumulated wizard step results |
| `$Name` | Delta link — jump to block `Name` (same file) |
| `$File.Block` | Cross-file delta link |

### Delta links & wizards

```yaml
# same-file jump
~Root*: [Main, $SubMenu, stop]
SubMenu:
  ~Root*: [Options, zBack]

# multi-step workflow (results flow via zHat)
Workflow:
  zWizard:
    validate: {zFunc: "&plugin.validate()"}
    process:  {zData: {action: create, table: jobs, data: zHat}}
    confirm:  {zDisplay: {event: success, content: Done}}
```

---

## Dual-mode (zCLI / zBifrost)

The **same** zVaFile runs in both modes — the mode is read from the session (`zMode`), and zWalker only chooses *who to delegate to*:

- **zCLI** (default): readline input, ASCII rendering, synchronous `execute_loop`.
- **zBifrost**: the sealed bridge runtime takes `walker=self` and streams chunked HTML to the browser client; it calls `execute_loop(block_dict)` itself. See [zBifrost Guide](../L3_Abstraction/zBifrost_GUIDE.md).

---

## Safety / trust

- **No code-exec surface.** zWalker has no `eval`/`exec`/`subprocess`; all execution is delegated to the sealed `z.wizard` engine and the gated `z.dispatch`/`z.func`.
- **Fails closed without zGuard.** zWalker subclasses the **sealed** `zWizard`; if the engine wheel is absent, construction raises `ImportError` ("z patch"). There is no stub engine.
- **Remote sessions can't kill the host.** The process-terminating callbacks (`on_stop`/`on_error` → `sys.exit`) exist **only on the local zCLI path**. In zBifrost the sealed runtime drives `execute_loop(block_dict)` with **no** navigation callbacks, so a remote client cannot reach them.

> The data/RBAC enforcement and network hardening that make remote sessions safe live in the lower layers (the m_zData access gate, the Bifrost acting-principal) and the zGuard-sealed runtime — see the project trust model.

---

## Module map

| Path | Role |
|------|------|
| `core/L4_Orchestration/p_zWalker/zWalker.py` | The orchestrator: `run()` + navigation callbacks (extends `z.wizard`) |
| `core/L4_Orchestration/p_zWalker/__init__.py` | Package facade + metadata |

zWalker is single-file **by design** — a pure orchestrator stays minimal. The capabilities it composes are documented in their own guides: [zWizard](../L3_Abstraction/zWizard_GUIDE.md) (loop engine), [zNavigation](../L2_Handling/zNavigation_GUIDE.md) (breadcrumbs), [zDispatch](../L2_Handling/zDispatch_GUIDE.md) (routing), [zLoader](../L1_Foundation/zLoader_GUIDE.md) (zVaFiles), [zDisplay](../L2_Handling/zDisplay_GUIDE.md) (rendering).

---

**[← Back to zShell Guide](../L3_Abstraction/zShell_GUIDE.md) | [Home](../../README.md) | [Next: zServer Guide →](zServer_GUIDE.md)**

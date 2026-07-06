# zVocabulary — Root Protocol Vocabulary

`core/zVocabulary.py` is the **single source of truth (SSOT)** for the string literals that form zOS's *shared protocol* — the keys, identifiers, and atoms that more than one subsystem must agree on by definition.

It is a **package-root module** (it lives at `core/`, beneath every layer), so it is documented here in **L0_Core** — the cross-app primitives cluster — rather than under any single layer. The **Foundation layer (L1) is its first consumer** (`a_zConfig`, `c_zLoader` already draw from it), and every higher layer draws from it too.

> **Why it exists:** before this module, the session-dict schema, run-mode strings, file extensions, and path symbols were re-declared in each subsystem's `*_constants.py`. The literals drifted (`FILE_TYPE_UI` vs `FILE_TYPE_ZUI`, `SESSION_KEY_VAFILE` vs `SESSION_KEY_ZVAFILE`, `DEFAULT_PATH_SYMBOL` vs `SYMBOL_AT`) and agents had no single place to look. `zVocabulary` makes that vocabulary **single-sourced and discoverable**.

---

## Design contract

| Rule | Why |
|------|-----|
| **Dependency-free leaf** — imports nothing from the `zOS` package | Importable at any point during package init without circular-import risk |
| **L1 consumes by submodule path:** `from zOS.zVocabulary import SESSION_KEY_ZVAFILE` | Safe even while `zOS/__init__` is still executing during boot |
| **L2+/plugins consume via aggregator:** `from zOS import SESSION_KEY_ZVAFILE` | Convenience; re-exported through the `zOS` public API |
| **Bar is high** — only *genuine cross-subsystem protocol* lives here | Log messages, colors, error text, and single-subsystem keys stay local |

---

## Vocabulary families

| Family | Examples | Primary consumers |
|--------|----------|-------------------|
| **zMode values** | `ZMODE_ZCLI`, `ZMODE_ZBIFROST` | zConfig, zDisplay, zBifrost, zDispatch |
| **Session keys** (`SESSION_KEY_*`, 24) | `SESSION_KEY_ZSPACE`, `…_ZVAFILE`, `…_ZMODE`, `…_ZMACHINE` | nearly every subsystem — the session-state schema |
| **File extension atoms** (`FILE_EXT_*`, 12) | `FILE_EXT_ZOLO`, `…_YAML`, `…_PY` | zConfig (zEnv), zParser, zLoader, zFunc |
| **File-type ids** (`FILE_TYPE_*`, 5) | `FILE_TYPE_UI`, `…_SCHEMA`, `…_CONFIG`, `…_ZVAFILE`, `…_ZOTHER` | zLoader (detection/caching), zParser (classification) |
| **Path symbols** | `PATH_SYMBOL_AT` (`@`), `PATH_SYMBOL_TILDE` (`~`) | zLoader, zParser, every zPath consumer |
| **zMachine prefixes** | `ZMACHINE_PREFIX` (`zMachine.`), `ZMACHINE_PREFIX_LONG` (`~.zMachine.`) | zLoader, zParser path resolution |

> Extension **atoms** are intentionally separate from extension **lists**: subsystems compose their own priority lists (zEnv's `ZENV_EXTENSIONS`, parser's `ZVAFILE_EXTENSIONS`) from the shared atoms, so the literals never drift.

---

## Migration & aliases

Subsystems keep their historical constant names — those names become **thin aliases** that re-export the canonical root value. No call sites break.

```python
# c_zLoader/loader_modules/loader_constants.py
from zOS.zVocabulary import SESSION_KEY_ZVAFILE, PATH_SYMBOL_AT, FILE_EXT_PY

SESSION_KEY_VAFILE = SESSION_KEY_ZVAFILE   # historical loader name → root canon
DEFAULT_PATH_SYMBOL = PATH_SYMBOL_AT        # historical loader name → root canon
PLUGIN_EXTENSION = FILE_EXT_PY              # composed from a shared atom
```

**Canonicalization rule:** pick the *best existing* name as canonical and alias the rest — fresh names are minted only when no good winner exists.

| Subsystem | Status | Drawn from root |
|-----------|--------|-----------------|
| `a_zConfig` | ✅ migrated | session keys, zMode, zEnv extension atoms |
| `b_zComm` | ✅ clean (no-op) | none — transport/network/storage vocab is comm-owned |
| `c_zLoader` | ✅ migrated | session keys, file-type ids, path symbol, zMachine prefix, plugin extension |
| `d_zParser` | ⏳ pending | session keys, file-type ids, path symbols, zMachine prefixes, extension atoms |

---

## What belongs here

**Yes** — vocabulary multiple subsystems must agree on: session-dict keys, run modes, file extensions, file-type ids, path symbols, zMachine prefixes.

**No** — keep these local to their subsystem's `*_constants.py`: log/error messages, display colors and styles, cache-internal keys, network defaults, and any key owned and used by a single subsystem.

---

**See also:** [L0 Core index](README.md) · [L1 Foundation docs](../L1_Foundation/README.md) · code: `core/zVocabulary.py`, [`core/L1_Foundation/README.md`](../../core/L1_Foundation/README.md)

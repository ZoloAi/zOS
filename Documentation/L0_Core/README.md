# L0 Core — Documentation

Technical index for the **package-root primitives** — the cross-cutting modules that live directly at `core/` (beneath the layered subsystems L1–L4) and are shared by the entire app.

Unlike the layer clusters (L1 Foundation, L2 Handling, …), L0 is not a runtime boot stage. It is the **kernel surface** every layer imports from: the `zOS` aggregator and the shared protocol vocabulary. Documenting it separately keeps cross-app primitives from being mistaken for any single layer's concern.

| Member | Code | What it is | Guide |
|--------|------|------------|-------|
| **Root vocabulary** | `core/zVocabulary.py` | SSOT for cross-subsystem protocol literals: session-dict keys, run modes, file extensions, file-type ids, path symbols, zMachine prefixes | [zVocabulary_GUIDE](zVocabulary_GUIDE.md) |
| **Plugin SDK** | `core/zos_plugin/` | The Python authorship SDK plugins are written against (`@zfunc` DI + return contract + facades) plus the compute/hosting seams that run and release apps | [zPlugin_GUIDE](zPlugin_GUIDE.md) |

> **Re-export:** L0 modules are surfaced through the `zOS` aggregator (`core/__init__.py`). L1 modules consume by submodule path (`from zOS.zVocabulary import …`, boot-safe); L2+/plugins use the aggregator (`from zOS import …`). The plugin SDK is the exception — it is a **standalone package** imported directly (`from zos_plugin import zfunc`) and deliberately avoids deep `zOS.*` imports so it stays portable.

---

## zos-plugin — the plugin authorship SDK (`from zos_plugin import zfunc`)

A package-root SDK (`core/zos_plugin/`) consumed by `zCloud/plugins/*`, demo/test plugins, and the open-core server (`r_zServer` `zProxy`/`zAPI`). **Distinct from `i_zFunc`** (the L2 subsystem that *dispatches* a zFunc call): `zos_plugin` is the contract the plugin is *written against*. `@zfunc` injects connection points by parameter name (`user`/`files`/`data`/`transfer`/`instance`/`proxy`/…), preserves the truthy/falsy/`"error"`/`ZAbort` return contract, and routes `input()` per session. It also carries the env-selected compute (`drivers`) and hosting (`bundle_store`/`session_store`/`release`) seams that run and release apps — local in dev, cloud in prod.

> **Trust:** open-core, hardened for tenant/author-input — no shell/eval (only `Popen([zolo,…], shell=False)`), capped + path-contained bundle unpack, validated uploads, parameterized data, session-isolated `input()`. **Compute is a trust boundary**: waking an app runs its code; multi-tenant isolation is the prod driver's job (V3 — zCloud + zGuard). Deep dives + posture: [zPlugin_GUIDE](zPlugin_GUIDE.md) and [`zPlugin_Guides/`](zPlugin_Guides/).

---

## Conventions (for agents)

- **Dependency-free leaves:** L0 vocabulary/primitive modules import nothing from the `zOS` package, so they stay importable at any point during init.
- **Bar is high:** only *genuine cross-app* primitives belong at L0. Layer- or subsystem-specific values stay with their owner (`*_constants.py`).
- **Aliases, not breaks:** when a subsystem adopts a root primitive, its historical name becomes a thin alias — no call sites break.
- **Vault parity:** the `zVault-zCode/` graph mirrors these files; links follow the **repo tree** (structure), not domain/logic.

**See also:** [L1 Foundation docs](../L1_Foundation/README.md) · code-side: `core/zVocabulary.py`, `core/zos_plugin/`, `core/__init__.py`

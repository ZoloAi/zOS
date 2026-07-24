# zos-plugin SDK Guide

**[Home](../../README.md) | [L0 Core overview](README.md)**

> **The Python authorship SDK for zOS plugins**
> A plugin author writes *intent* (`@zfunc def upload(user, files, data): ...`); the SDK wires it to zOS via signature-based dependency injection, a uniform return contract, and declarative facades over zOS primitives — plus the compute/hosting seams that run and release apps.

---

## What It Is

**`zos_plugin`** is a **package-root SDK** (`core/zos_plugin/`, beneath the layers) imported by plugin code as `from zos_plugin import zfunc`. It is consumed by `zCloud/plugins/*` (avatar, zpush, zHost, …), the demo/test plugins, and the open-core server (`r_zServer` `zProxy` + `zAPI`).

> **Not to be confused with `i_zFunc`.** `i_zFunc` (L2) is the framework subsystem that *dispatches/executes* a zFunc call; `zos_plugin` is the **author-facing SDK** the plugin is written against. One routes, the other is the contract. See [zFunc_GUIDE](../L2_Handling/zFunc_GUIDE.md).

`@zfunc` does two jobs:

1. **Dependency injection** — inspects the plugin signature and injects, *by parameter name*, whatever zOS connection points it asked for (`user`, `files`, `data`, `transfer`, `session`, `log`, `params`, `instance`, `proxy`, `zos`). No deep `from zOS...` imports; identical whether the call came from CLI/wizard (the SSOT base) or zAPI (a transport adapter feeding the same flow).
2. **Contract + safety** — preserves the return contract and contains failures:

```
truthy   → success (! satisfied, ^ bounces)
falsy    → retriable failure
"error"  → hard abort
raise ZAbort("...", status=4xx)  → structured ZResult failure (right HTTP status)
unhandled exception              → logged + contained as "error"
```

**Status:** ✅ Audited + hardened (test/tenant-input trust baseline)

> This is a **facade overview**. Per-cluster deep dives live in [`zPlugin_Guides/`](#architecture-overview).

---

## Architecture Overview

```
@zfunc (entry: DI + contract + input routing)
│
├── contract ... Invocation env (contextvars) · provider registry · ZResult / ZAbort
├── facades .... user · files · data · transfer · instance · proxy  (+ Row/Stored/UploadedFile)
├── compute .... ComputeDriver → LocalProcessDriver (dev) | K8sDriver (prod)   · AppSpec/Instance
└── hosting .... BundleStore (push) · SessionStore (scale-to-zero) · ReleaseManager (blue/green)

Each seam is env-selected (local in dev, cloud in prod) so the control flow never changes.
```

| Cluster | Modules | Responsibility | Guide |
|---------|---------|----------------|-------|
| **contract** | `__init__.py` (`zfunc`), `context.py`, `result.py` | Signature-based DI, the invocation env, the `ZResult`/`ZAbort` envelope, session-safe `input()` | [contract_GUIDE](zPlugin_Guides/contract_GUIDE.md) |
| **facades** | `facades.py` | The declarative connection points a plugin names (`user`/`files`/`data`/`transfer`/`instance`/`proxy`) + value objects | [facades_GUIDE](zPlugin_Guides/facades_GUIDE.md) |
| **compute** | `drivers.py` | Run / reach a zOS app instance — swappable `ComputeDriver` (local process → k8s) behind `instance`/`proxy` | [compute_GUIDE](zPlugin_Guides/compute_GUIDE.md) |
| **hosting** | `bundle_store.py`, `session_store.py`, `release.py` | zCloud seams: persist a pushed bundle, externalize sessions (scale-to-zero), blue/green release | [hosting_GUIDE](zPlugin_Guides/hosting_GUIDE.md) |

---

## Quick Start

```python
from zos_plugin import zfunc

@zfunc
def upload(user, files, transfer, data):
    img = files.image("avatar", max_mb=5)        # validated → 4xx on policy miss
    user.require()                                # linear guard → 401 if anon
    stored = transfer.store(img.bytes, key=f"users/{user.id}/avatar.{img.ext}",
                            mime=img.mime, filename=img.filename)
    media = data.upsert("media", where={"user_id": user.id, "kind": "avatar"},
                        values={"storage_key": stored.key, "file_size": img.size})
    data.update("users", {"avatar_media_id": media.id}, where={"id": user.id})
    return {"ok": True, "message": "Avatar updated",
            "data": {"media_id": media.id, "url": stored.cache_busted_url}}
```

The author declares only the parameters they need; `@zfunc` resolves them. Caller-supplied args always win over injected providers (no double-injection).

---

## Trust posture — tenant/author-input trust

`zos_plugin` is **fully open-core**. Its risk surface is that it (a) executes app code and (b) ingests untrusted bytes (uploads, pushed bundles), so the hardening is about containing those:

- **No shell, no eval** — the only subprocess is the compute driver's `Popen([zolo, <spark>], shell=False)`; nothing is `eval`/`exec`'d.
- **Untrusted bundles are capped + contained** — `unpack` enforces size/count caps (zip-bomb/OOM) and `realpath`-contained writes; sym/hardlinks are never extracted.
- **Uploads are validated** — `files.image()` enforces mime-allowlist + size cap, aborting 4xx.
- **Sessions don't cross** — `input()` is routed per-invocation via a `ContextVar`, never a global patch that races across the bridge's worker threads.
- **Data is parameterized** — `DataFacade` builds structured zData ops, never raw SQL.

> **Compute is a trust boundary (T1).** Waking an app *runs its code*. In dev `LocalProcessDriver` spawns a child that inherits the host environment with **no sandbox** — fine for self-hosted/dev, where the registry that supplies the app folder is trusted. Multi-tenant isolation (scoped env, network, FS) is the **prod driver's** responsibility (k8s/pod), the V3 concern owned by zCloud + the zGuard-sealed runtime — not provided by the local dev driver.

> **SSOT decoupling (D1).** The SDK deliberately avoids deep `from zOS...` imports so it stays a portable package; a few zEnv literals (server-bind keys) are kept as a local copy rather than imported across the layer boundary. zConfig remains the canonical owner.

---

## Summary

| Go deeper | Guide |
|-----------|-------|
| `@zfunc` DI, invocation env, `ZResult`/`ZAbort`, input routing | [contract_GUIDE](zPlugin_Guides/contract_GUIDE.md) |
| The connection points (`user`/`files`/`data`/`transfer`/`instance`/`proxy`) | [facades_GUIDE](zPlugin_Guides/facades_GUIDE.md) |
| Compute drivers (run/reach an app instance) | [compute_GUIDE](zPlugin_Guides/compute_GUIDE.md) |
| Hosting seams (push bundles, sessions, blue/green release) | [hosting_GUIDE](zPlugin_Guides/hosting_GUIDE.md) |

**Code:** `core/zos_plugin/` · **Imported as:** `from zos_plugin import zfunc`
**Status:** ✅ Audited + hardened (open-core authorship SDK)

---

**[Home](../../README.md) | [L0 Core overview](README.md)**

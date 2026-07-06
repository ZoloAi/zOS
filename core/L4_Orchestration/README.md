# L4 — Orchestration Layer

The **orchestration tier** of zOS — the top layer. These subsystems do not add new primitives; they **drive** the lower layers (L1 Foundation → L2 Handling → L3 Abstraction) into complete experiences: an interactive declarative-UI session, a web server that serves the same `.zolo` apps over HTTP, and an end-to-end test runner that exercises both.

They initialize in **alphabetical order** during `zOS()` boot, each reachable as a facade on the live instance:

| Order | Subsystem | Facade | In one line | Guide |
|------|-----------|--------|-------------|-------|
| **q** | `q_zWalker` | `z.walker` | Declarative UI orchestrator — loads a zVaFile, runs the wizard loop, tracks breadcrumbs; dual-mode (zCLI / zBifrost) | [zWalker_GUIDE](../../Documentation/L4_Orchestration/zWalker_GUIDE.md) |
| **r** | `r_zServer` | `z.server` | HTTP/WSGI server — declarative routing + template/static serving; one request pipeline behind `dev` (`http.server`) + `waitress` runners | [zServer_GUIDE](../../Documentation/L4_Orchestration/zServer_GUIDE.md) |
| **s** | `s_zRaven` | `z.raven` | Automated test subsystem — drives zWalker + zServer + zBifrost end-to-end; zSpark-activated, **off by default** | [zRaven_GUIDE](../../Documentation/L4_Orchestration/zRaven_GUIDE.md) |

> Init order follows the dependency chain: `zWalker` first (it extends the L3 `zWizard` engine and coordinates L1/L2/L3 facades); `zServer` next (auto-starts when `config.http_server.enabled`); `zRaven` last (it connects *to* a running server + Bifrost, so both must be ready). All build on the lower-layer facades (`z.config`/`z.comm`/`z.loader`, `z.parser`/`z.display`/`z.dispatch`/`z.navigation`/…, `z.wizard`/`z.data`/`z.bifrost`/`z.shell`).

> **Open / closed split:** all three subsystems are **open-core**. The web-/network-**hardening** that `zServer` and the Bifrost runtime rely on (TLS, endpoint auth, origin/CORS, message/input validation, rate limiting, the remote `execute_code` enforcement) is the **V3 network-safety concern** owned by the zGuard-sealed runtime and zCloud — it is *not* re-derived here (see the project trust model). Open-core keeps the server/orchestration **behaviour** + clean network *config*; production hardening = zGuard.

> **Root vocabulary:** shared protocol literals (session-dict keys like `zVaFile`/`zBlock`/`zMode`/`zCrumbs`, run modes `ZMODE_*`, file-type ids, path symbols) are single-sourced in `core/zVocabulary.py` (re-exported via `a_zConfig`). L4 subsystems draw from it rather than re-declaring. See [zVocabulary_GUIDE](../../Documentation/L0_Core/zVocabulary_GUIDE.md).

---

## q_zWalker — declarative UI orchestrator (`z.walker`)

A **pure orchestrator** (single file, ~720 LOC): it `extends` the L3 `zWizard` engine and adds only navigation callbacks. `run()` detects the session mode and delegates — zCLI loads a zVaFile via `z.loader` and runs `execute_loop(...)`; zBifrost hands `walker=self` to the sealed bridge runtime, which drives `execute_loop(block_dict)` directly. **No business logic of its own** (no path construction, dispatch, validation, or code-exec — all delegated).

- **Surface:** `run()` (entry: detect mode → delegate) and the navigation callbacks (`on_continue`/`on_back`/`on_exit`/`on_stop`/`on_error` + `on_get_trail`/`on_pop_trail` for zBounce).
- **Security:** no eval/exec/subprocess. **Fails closed without zGuard** — it subclasses the sealed `zWizard`, whose `__init__` raises `ImportError` ("z patch") when the engine wheel is absent. The process-terminating callbacks (`on_stop`/`on_error` → `sys.exit`) exist **only on the local zCLI path**; the sealed Bifrost runtime never wires them, so a remote client cannot reach them.
- **Code:** `q_zWalker/zWalker.py` (facade extends `z.wizard`) + `__init__.py`

## r_zServer — HTTP/WSGI server (`z.server`)

Serves the same declarative `.zolo` apps over HTTP: declarative routing from zServer-type zVaFiles, Jinja2 template rendering, static-file serving, JSON/API endpoints, zDialog-pattern web forms, and RBAC via `z.auth`. **One request pipeline for every transport** (`WSGIBridgeHandler`) — a `dev` `http.server` thread and the in-process **Waitress** WSGI server run the *same* code path; external hosts import `z.server.get_wsgi_app()`. The runner is an explicit `zServer.type` (SSOT: zSpark → `ZSERVER_TYPE` → `dev`). Auto-starts at boot when `config.http_server.enabled`.

- **Surface:** `z.server.start()` / `stop()` / `wait()` / `get_url()` / `get_wsgi_app()` / `health_check()`; route auto-detection + dispatch via `zServer_modules/`.
- **Security (V3 — "trust zServer like Flask"):** open-core ships a **safe-by-default web baseline** — verb-agnostic sensitive-path block, request-body cap (→413), `realpath`+`commonpath` static containment, always-on security headers, **same-origin CORS by default** (opt-in, never wildcard), fail-closed zAPI auth, CRLF-safe redirects, escaped output. **Production hardening stays at the edge** (TLS, rate limiting, WAF) — the V3 concern owned by the zGuard-sealed runtime + zCloud, not re-derived here.
- **Code:** `r_zServer/zServer.py` (facade) + `zServer_modules/` (+ `static/`)
- **Deep dives:** [zServer_Guides/](../../Documentation/L4_Orchestration/zServer_Guides/)

## s_zRaven — automated test subsystem (`z.raven`)

A first-class subsystem that mirrors the zServer lifecycle (created at boot, run when activated) and acts as zOS's **end-to-end harness**: a CLI runner drives a zCLI app over stdin/stdout and a WS/browser runner (Playwright + bifrost WebSocket) drives `zWalker` + `zServer` + `zBifrost`, with declarative assertions/primitives from one `.zolo` grammar. **Disabled by default** — activated only via zSpark (`zRaven: <suite>`); `zRaven: false` (default) leaves it dormant.

- **Surface:** `z.raven` (`is_enabled` / `start()` / `wait()` / `shutdown()`); `ZRavenRunner` selects a transport runner; activated by the `zRaven` zSpark key.
- **Security (test-input trust):** test-only orchestration, **inert** unless the operator activates it; **connects out only** (never binds), **no `eval`/`exec`**. Hardened so a hostile `.zolo` can't weaponize the harness — same-origin `zFetch`/`zOpen` (opt-in `allow_external`), fail-closed + path-contained `zClean`, secret redaction in logs, injection-safe `zWait`. WS auth-token send (bifrost `require_auth`) is the deferred V3/Track-3 concern — fail-safe, not a bypass.
- **Code:** `s_zRaven/zRaven.py` (facade) + `zRaven_modules/` (`runner`, `ws`, `cli`, `assertions`, `utils`)
- **Deep dives:** [zRaven_Guides/](../../Documentation/L4_Orchestration/zRaven_Guides/)

---

## Conventions (for agents)

- **Orchestrators, not primitives:** L4 subsystems coordinate lower layers — they should contain *delegation*, not business logic. `zWalker` is the canonical example (a pure orchestrator; logic belongs in L1–L3).
- **Facade pattern:** each subsystem is a thin public class delegating to its `*_modules/`. Touch the modules, not the facade signature.
- **Network safety is V3 (sealed):** keep web/network *hardening* mechanisms out of open-core; open-core keeps behaviour + clean config and exposes the seams the zGuard runtime consumes.
- **Constants are SSOT:** cross-subsystem protocol vocabulary lives in root `core/zVocabulary.py`; subsystem-internal values stay in each subsystem's `*_constants.py`. No magic strings.
- **Docs ↔ code parity:** each guide under `Documentation/L4_Orchestration/` maps 1:1 to the code here — `zWalker` is a single facade guide; `zServer` and `zRaven` add a facade + a `*_Guides/` deep-dive set. The `zVault-zCode/` graph mirrors the **repo tree** (tags `[logic]`/`[doc]`/`[folder]`/`[subsystem]`, wikilinked).

**See also:** [Home](../../README.md) · [L3 Abstraction overview](../L3_Abstraction/README.md) · [L4 Orchestration docs](../../Documentation/L4_Orchestration/README.md)

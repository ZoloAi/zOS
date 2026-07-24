# L4 Orchestration — Documentation

Technical index for the **Orchestration layer** documentation cluster — the top tier of zOS. These subsystems add no new primitives; they **drive** the layers beneath them (L1 Foundation → L2 Handling → L3 Abstraction) into complete experiences: an interactive declarative-UI session, a web server that serves the same `.zolo` apps over HTTP, an end-to-end test runner that exercises both, and a control plane that hosts many such apps behind one front door.

This README is the **technical entry point** to the L4 guides. For a high-level, code-side orientation of the layer, see [`core/L4_Orchestration/README.md`](../../core/L4_Orchestration/README.md). For the Abstraction layer beneath it, see [L3 Abstraction docs](../L3_Abstraction/README.md).

| Order | Subsystem | Facade | Main guide | Status |
|-------|-----------|--------|------------|--------|
| **q** | `q_zWalker` | `z.walker` | [zWalker_GUIDE](zWalker_GUIDE.md) | **Audited + refreshed** — pure orchestrator, fully open-core |
| **r** | `r_zServer` | `z.server` | [zServer_GUIDE](zServer_GUIDE.md) | **Audited + hardened** — open-core baseline ("trust like Flask"); web-hardening is V3 / zGuard |
| **s** | `s_zRaven` | `z.raven` | [zRaven_GUIDE](zRaven_GUIDE.md) | **Audited + hardened** — test subsystem, off by default; test-input-trust baseline |
| **t** | `t_zHost` | `zHost` (not yet an engine facade) | *(guide pending)* | **New** — control plane above zServer: front door, instance lifecycle (driver seams documented in [compute_GUIDE](../L0_Core/zPlugin_Guides/compute_GUIDE.md) / [hosting_GUIDE](../L0_Core/zPlugin_Guides/hosting_GUIDE.md)) |

> **Open / closed split:** all three subsystems are **open-core**. The web-/network-**hardening** that `zServer` and the Bifrost runtime depend on (TLS, endpoint auth, origin/CORS, message/input validation, rate limiting, the remote `execute_code` enforcement) is the **V3 network-safety concern** — owned by the zGuard-sealed runtime + zCloud, documented privately, and *not* re-derived in these open-core guides. Open-core documents server/orchestration **behaviour** and keeps network *config* clean.

> **Root vocabulary:** cross-subsystem protocol literals (session-dict keys `zVaFile`/`zBlock`/`zMode`/`zCrumbs`, run modes `ZMODE_*`, file-type ids, path symbols) are single-sourced in the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) module (`core/zVocabulary.py`). L4 subsystems draw from it instead of re-declaring.

---

## q_zWalker — declarative UI orchestrator (`z.walker`)

A **pure orchestrator** (single file): it extends the L3 `zWizard` loop engine and adds only navigation callbacks. `run()` detects the session mode and delegates — in **zCLI** it loads a zVaFile via `z.loader` and runs the inherited `execute_loop(...)`; in **zBifrost** the sealed bridge runtime drives `execute_loop(block_dict)` directly. zWalker holds **no business logic of its own** — path construction, dispatch, validation, and execution are all delegated to lower layers.

**Public surface (selected):** `z.walker.run()` (entry: detect mode → delegate); navigation callbacks (`on_continue`/`on_back`/`on_exit`/`on_stop`/`on_error`, plus `on_get_trail`/`on_pop_trail` for zBounce).

> **Trust:** no eval/exec/subprocess (100% delegation). **Fails closed without zGuard** — zWalker subclasses the sealed `zWizard`, whose `__init__` raises `ImportError` ("z patch") when the engine wheel is absent. The process-terminating callbacks (`on_stop`/`on_error` → `sys.exit`) live **only on the local zCLI path**; the sealed Bifrost runtime never wires them, so a remote client cannot reach them.

**Code:** `core/L4_Orchestration/q_zWalker/zWalker.py` (facade extends `z.wizard`) + `__init__.py`.

---

## r_zServer — HTTP/WSGI server (`z.server`)

Serves the same declarative `.zolo` apps over HTTP: declarative routing from zServer-type zVaFiles, Jinja2 template rendering, static-file serving, JSON/API endpoints, zDialog-pattern web forms, and RBAC via `z.auth`. **One request pipeline for every transport** (`WSGIBridgeHandler`) — a lightweight `http.server` thread (`dev`) and the cross-platform in-process **Waitress** WSGI server (`waitress`) run the *same* code path; external WSGI hosts import a static `wsgi.py` (`z.server.get_wsgi_app()`). The runner is chosen by an explicit `zServer.type` (SSOT: zSpark → `ZSERVER_TYPE` → `dev`), decoupled from the environment name. Auto-starts at boot when `config.http_server.enabled`. Pairs with **zBifrost** (HTTP page frame + WebSocket live session).

**Public surface (selected):** `z.server.start()` / `stop()` / `wait()` / `is_running()` / `get_url()` / `health_check()` / `get_wsgi_app()`; route auto-detection + dispatch via `zServer_modules/`.

**Guide split:** the [zServer_GUIDE](zServer_GUIDE.md) is a facade overview; per-cluster deep dives live in [`zServer_Guides/`](zServer_Guides/) — [routing](zServer_Guides/routing_GUIDE.md), [rendering](zServer_Guides/rendering_GUIDE.md), [core](zServer_Guides/core_GUIDE.md), [lifecycle](zServer_Guides/lifecycle_GUIDE.md), [caching](zServer_Guides/caching_GUIDE.md).

> **Trust (V3 — "trust zServer like Flask"):** open-core ships the **baseline web layer** and now hardens its safe-by-default posture to Flask/Werkzeug norms — verb-agnostic path blocking, a request-body cap (`max_body_bytes`), `realpath`+`commonpath` static containment, always-on security headers, **same-origin CORS by default** (opt-in, never wildcard), RBAC parity on the config API, fail-closed zAPI auth, CRLF-safe redirects, escaped render/error HTML. **Production-grade hardening stays at the edge** (TLS termination, rate limiting / WAF, abuse control) — the V3 concern owned by the zGuard-sealed runtime + zCloud / ingress, documented privately, not re-derived here.

**Code:** `core/L4_Orchestration/r_zServer/zServer.py` (facade) + `zServer_modules/`.

---

## s_zRaven — automated test subsystem (`z.raven`)

zOS's **end-to-end harness**, and a first-class subsystem that mirrors the zServer lifecycle (created at boot, run when activated). It spins zCLI test targets and a WebSocket test client to drive `zWalker` + `zServer` + `zBifrost` together, with declarative assertions and primitives. **Disabled by default** — activated only via zSpark (`zRaven: <suite>` runs that suite; `zRaven: false`, the default, leaves it dormant).

**Public surface (selected):** `z.raven` (`is_enabled` / `start()` / `wait()` / `shutdown()`); `ZRavenRunner` selects a transport runner; activated by the `zRaven` zSpark key.

**Guide split:** the [zRaven_GUIDE](zRaven_GUIDE.md) is a facade overview; per-cluster deep dives live in [`zRaven_Guides/`](zRaven_Guides/) — [runner](zRaven_Guides/runner_GUIDE.md), [cli](zRaven_Guides/cli_GUIDE.md), [browser](zRaven_Guides/browser_GUIDE.md), [assertions](zRaven_Guides/assertions_GUIDE.md), [reporting](zRaven_Guides/reporting_GUIDE.md).

> **Trust (test-input-trust):** test-only orchestration, **inert unless** the operator activates it via zSpark — no always-on surface. It **connects out only** (never binds), has **no `eval`/`exec`**, and is hardened so a hostile `.zolo` suite can't weaponize the harness: same-origin `zFetch`/`zOpen` (opt-in `allow_external`), fail-closed + path-contained `zClean`, secret redaction in logs, injection-safe `zWait`. WS auth-token send (when bifrost `require_auth=true`) is the deferred V3/Track-3 concern — fail-safe, not a bypass.

**Code:** `core/L4_Orchestration/s_zRaven/zRaven.py` (facade) + `zRaven_modules/` (`runner`, `ws`, `cli`, `assertions`, `utils`).

---

## t_zHost — control plane (`zHost`)

zServer serves *one* app (the data plane). **zHost decides which app**, brings
it up, and hands the visitor off (the control plane): the front door
(`slug#build` routing, waking interstitial, owner-scoped tenants), instance
lifecycle via the compute drivers, and — later — fleet blue-green + deploy.

**Guide split:** no dedicated hub yet; the driver/hosting seams it drives are
documented in [compute_GUIDE](../L0_Core/zPlugin_Guides/compute_GUIDE.md) and
[hosting_GUIDE](../L0_Core/zPlugin_Guides/hosting_GUIDE.md).

**Code:** `core/L4_Orchestration/t_zHost/zHost.py` (facade) + `zHost_modules/`.

---

## Conventions (for agents)

- **Orchestrators, not primitives:** L4 coordinates lower layers — guides describe *what gets driven and how*, not new primitive mechanics (those live in the L1–L3 guides).
- **Network safety is V3 (sealed):** web/network hardening mechanisms are **not** published here — open-core guides document behaviour + config and point to the private zGuard docs for mechanism.
- **Facade pattern:** each subsystem is a thin public class delegating to its `*_modules/`. Change behaviour in the modules, not the facade signature.
- **Constants are SSOT:** cross-subsystem protocol vocabulary is single-sourced in root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); subsystem-internal values stay in each subsystem's `*_constants.py`. No magic strings.
- **Docs ↔ code parity:** every guide here maps 1:1 to the code; the `zVault-zCode/` graph mirrors both (`[doc]`/`[logic]`/`[folder]`/`[subsystem]` tags, wikilinked). Vault links mirror the **repo tree** (structure), not domain/logic.
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported).

**See also:** [Home](../../README.md) · [code-side L4 overview](../../core/L4_Orchestration/README.md) · [L3 Abstraction docs](../L3_Abstraction/README.md)

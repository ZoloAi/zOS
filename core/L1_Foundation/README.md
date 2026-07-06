# L1 — Foundation Layer

The **lowest infrastructure tier** of zOS. These subsystems come up first, depend only on the Python stdlib and each other, and provide the configuration, communication, and file-loading backbone that every higher layer (L2 Handling, L3 Abstraction, L4 Orchestration) builds on.

They initialize in **alphabetical order** during `zOS()` boot, each reachable as a facade on the live instance:

| Order | Subsystem | Facade | In one line | Guide |
|------|-----------|--------|-------------|-------|
| **a** | `a_zConfig` | `z.config` | Cross-platform configuration: machine/env/session settings, paths, secrets, logger, server/ws config | [zConfig_GUIDE](../../Documentation/L1_Foundation/zConfig_GUIDE.md) |
| **b** | `b_zComm`   | `z.comm`   | Communication backbone: HTTP client, local service management (PostgreSQL/Redis/…), object storage, WebSocket, network probes | [zComm_GUIDE](../../Documentation/L1_Foundation/zComm_GUIDE.md) |
| **c** | `c_zLoader` | `z.loader` | Intelligent file loading + multi-tier caching + plugin management (Python/JS) with a zGuard trust gate | [zLoader_GUIDE](../../Documentation/L1_Foundation/zLoader_GUIDE.md) |

> Boot sequence: `zConfig → zComm → (zParser) → zLoader → …`. `zConfig` and `zComm` come up **before** `zDisplay`, so they print readiness directly. `zLoader` initializes after `zParser` (its path-resolution/parsing dependency, in L2).

> **Root vocabulary:** shared protocol literals (session-dict keys, run modes, file extensions, file-type ids, path symbols, zMachine prefixes) are single-sourced in `core/zVocabulary.py` — a dependency-free leaf re-exported via the `zOS` aggregator. These subsystems draw from it (`from zOS.zVocabulary import …`) rather than re-declaring; historical `*_constants.py` names remain as thin aliases. See [zVocabulary_GUIDE](../../Documentation/L0_Core/zVocabulary_GUIDE.md).

---

## a_zConfig — configuration (`z.config`)

The single source of truth for **where things live and how the app is configured**, resolved hierarchically (machine → environment → session → zSpark overrides).

- **Surface:** `z.config.machine`, `z.config.environment`, `z.config.session`, `z.config.http_server`, `z.config.websocket`, `z.config.raven`, `z.config.resource_limits`
- **Provides:** cross-platform paths, env/secret resolution, the logger instance, and server/WebSocket config consumed by `zComm` and L4 `zServer`.
- **Code:** `a_zConfig/zConfig.py` (facade) + `zConfig_modules/`

## b_zComm — communication (`z.comm`)

Low-level network & service primitives behind one facade (delegates to specialized managers; no `zDisplay` dependency).

- **Surface:** `http_get/post/put/patch/delete`, `start_service/stop_service/restart_service/service_status`, object storage `put/get/exists/get_url/delete`, WebSocket primitives, `check_port`/`is_port_open`, health checks.
- **Provides:** the HTTP/service/storage layer used by `zData`, `zServer`, and friends. Reads its endpoints/ports from `z.config`.
- **Code:** `b_zComm/zComm.py` (facade) + `zComm_modules/` (`comm_http`, `comm_storage`, `comm_websocket*`, `services/`, `comm_utils`)

## c_zLoader — file loading, caching, plugins (`z.loader`)

Loads and parses zVaFiles (UI/config/schema) with automatic format detection and multi-tier caching, and is the SSOT for dynamic module loading.

- **Surface:** `handle()` / `handle_absolute_path()` (load+parse, cached), `load_plugins()` / `get_plugin()` / `load_python_module()`, and `z.loader.cache` (the `CacheOrchestrator`).
- **Caches:** System (UI/config, LRU) · Pinned (aliases, no eviction) · Schema (DB connections + transactions) · PythonModule (Python/JS modules, collision detection, session injection).
- **Security:** plugin execution passes through the `loader_trust` gate — permissive in open-core, sealed by the `zguard` wheel when installed.
- **Code:** `c_zLoader/zLoader.py` (facade) + `loader_modules/` (`cache/`, `loader_io`, `loader_validator`, `loader_trust`, `loader_constants`)
- **Deep dives:** [zLoader_Guides/](../../Documentation/L1_Foundation/zLoader_Guides/)

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to `*_modules/`. Touch the modules, not the facade signature, for behavior changes.
- **Constants are SSOT:** cross-subsystem protocol vocabulary lives in root `core/zVocabulary.py`; subsystem-internal values + the exception hierarchy live in each subsystem's `*_constants.py`. No magic strings.
- **zGuard seam:** proprietary enforcement is optional and isolated behind `try: from zguard… / except ImportError: <permissive fallback>`. Open-core stays fully functional without it.
- **Docs ↔ code parity:** every guide under `Documentation/` is kept 1:1 with the code here; the `zVault-zCode/` graph mirrors both (tags `[logic]`/`[doc]`/`[folder]`, wikilinked).
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported by the loader).

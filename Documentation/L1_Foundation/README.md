# L1 Foundation — Documentation

Technical index for the **Foundation layer** documentation cluster: the three subsystems that boot first and provide configuration, communication, and file-loading for everything above them.

This README is the **technical entry point** to the guides. For a high-level, code-side orientation of the layer, see [`core/L1_Foundation/README.md`](../../core/L1_Foundation/README.md).

| Order | Subsystem | Facade | Main guide | Sub-guides |
|-------|-----------|--------|------------|-----------|
| **a** | `a_zConfig` | `z.config` | [zConfig_GUIDE](zConfig_GUIDE.md) | [zConfig_Guides/](zConfig_Guides/) |
| **b** | `b_zComm` | `z.comm` | [zComm_GUIDE](zComm_GUIDE.md) | [zComm_Guides/](zComm_Guides/) |
| **c** | `c_zLoader` | `z.loader` | [zLoader_GUIDE](zLoader_GUIDE.md) | [zLoader_Guides/](zLoader_Guides/) |

> **Boot order:** `zConfig → zComm → (zParser) → zLoader`. `zConfig` and `zComm` initialize before `zDisplay` (they print readiness directly); `zLoader` initializes after `zParser`, its path-resolution dependency in L2.

> **Root vocabulary:** cross-subsystem protocol literals (session-dict keys, run modes, file extensions, file-type ids, path symbols, zMachine prefixes) are single-sourced in the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) module (`core/zVocabulary.py`). L1 subsystems draw from it instead of re-declaring; their historical constant names remain as thin aliases.

---

## a_zConfig — configuration (`z.config`)

The single source of truth for **where things live and how the app is configured**, resolved hierarchically (machine → environment → session → zSpark overrides).

**Public surface:** `z.config.machine`, `z.config.environment`, `z.config.session`, `z.config.http_server`, `z.config.websocket`, `z.config.raven`, `z.config.resource_limits`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `paths` | Cross-platform path resolution, workspace detection | [paths_GUIDE](zConfig_Guides/paths_GUIDE.md) |
| `machine` | Hardware detection (CPU, GPU, network, tools) | [machine_GUIDE](zConfig_Guides/machine_GUIDE.md) |
| `environment` | Deployment settings, logging, network config | [environment_GUIDE](zConfig_Guides/environment_GUIDE.md) |
| `session` | Runtime state, session identity, zVars | [session_GUIDE](zConfig_Guides/session_GUIDE.md) |
| `loggers` | Three-tier logging (framework, session, app) | [loggers_GUIDE](zConfig_Guides/loggers_GUIDE.md) |
| `network` | WebSocket and HTTP server configuration | [network_GUIDE](zConfig_Guides/network_GUIDE.md) |
| `persistence` | Save/load configuration changes | [persistence_GUIDE](zConfig_Guides/persistence_GUIDE.md) |

**Consumed by:** `zComm` (server/WebSocket endpoints), `zServer`, and every subsystem needing paths/secrets/logger.
**Code:** `core/L1_Foundation/a_zConfig/zConfig.py` (facade) + `zConfig_modules/`.

## b_zComm — communication (`z.comm`)

Low-level network & service primitives behind one facade. **Layer-0 infrastructure** — no `zDisplay` dependency; reads endpoints/ports from `z.config`.

**Public surface:** `http_get/post/put/patch/delete`, `start_service/stop_service/restart_service/service_status`, object storage `put/get/exists/get_url/delete`, WebSocket primitives, `check_port`/`is_port_open`, health checks.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `comm_http` | Synchronous HTTP client | [http_GUIDE](zComm_Guides/http_GUIDE.md) |
| `comm_websocket*` | WebSocket server, auth, events, input | [websocket_GUIDE](zComm_Guides/websocket_GUIDE.md) |
| `comm_ssl` | SSL/TLS certificate handling | [websocket_GUIDE](zComm_Guides/websocket_GUIDE.md) |
| `services/` | Service lifecycle (PostgreSQL, Redis, …) | [services_GUIDE](zComm_Guides/services_GUIDE.md) |
| `comm_storage` | Object storage (local, S3, Azure, GCS) | [storage_GUIDE](zComm_Guides/storage_GUIDE.md) |
| `comm_utils` / `comm_constants` | Port checking, shared constants | [network_GUIDE](zComm_Guides/network_GUIDE.md) |

> **Scope:** zComm provides raw primitives. For HTTP file serving see `zServer`; for WebSocket orchestration (Terminal↔Web bridge with auth/caching) see `zBifrost` — both are higher layers built on these primitives.

**Code:** `core/L1_Foundation/b_zComm/zComm.py` (facade) + `zComm_modules/`.

## c_zLoader — file loading, caching, plugins (`z.loader`)

Loads and parses zVaFiles (UI/config/schema) with automatic format detection and multi-tier caching; the SSOT for dynamic module loading.

**Public surface:** `handle()` / `handle_absolute_path()` (load+parse, cached), `load_plugins()` / `get_plugin()` / `load_python_module()`, and `z.loader.cache` (the `CacheOrchestrator`).

**Cache tiers** — routed by the orchestrator:

| Tier | Cache | Behavior |
|------|-------|----------|
| System | `SystemCache` | UI/config files, LRU + mtime invalidation (schemas are **not** cached here) |
| Pinned | `PinnedCache` | User aliases, no eviction |
| Schema | `SchemaCache` | DB connections + transaction lifecycle |
| Python module | `PythonModuleCache` | Python/JS modules, collision detection, session injection, mtime + LRU |

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `loader_io` | Raw file I/O (`load_file_raw`) | [io_GUIDE](zLoader_Guides/io_GUIDE.md) |
| `cache/cache_system` | System cache | [cache_system_GUIDE](zLoader_Guides/cache_system_GUIDE.md) |
| `cache/cache_pinned` | Pinned cache | [cache_pinned_GUIDE](zLoader_Guides/cache_pinned_GUIDE.md) |
| `cache/cache_schema` | Schema cache | [cache_schema_GUIDE](zLoader_Guides/cache_schema_GUIDE.md) |
| `cache/cache_python_module` | Python module cache | [cache_plugin_GUIDE](zLoader_Guides/cache_plugin_GUIDE.md) |
| `cache/cache_orchestrator` | Unified cache router | [orchestrator_GUIDE](zLoader_Guides/orchestrator_GUIDE.md) |
| `loader_constants` | Constants + exception hierarchy | [constants_GUIDE](zLoader_Guides/constants_GUIDE.md) |
| `loader_validator` | Fail-fast config/path/type validation | [validator_GUIDE](zLoader_Guides/validator_GUIDE.md) |
| `loader_trust` | Plugin-trust gate (zGuard seam) | [trust_GUIDE](zLoader_Guides/trust_GUIDE.md) |
| `cache/cache_utils` | Cache inspection helpers | [utils_GUIDE](zLoader_Guides/utils_GUIDE.md) |
| `cache/cache_pattern` | Wildcard matcher (SSOT for all caches) | [pattern_GUIDE](zLoader_Guides/pattern_GUIDE.md) |

> **Security:** plugin execution passes through `loader_trust.verify_plugin_trust()` before `exec_module`. Open-core falls back to permissive (`try: from zguard… / except ImportError`); installing the `zguard` wheel seals the same seam. A failed policy raises `PluginTrustError` (propagated unwrapped).

**Code:** `core/L1_Foundation/c_zLoader/zLoader.py` (facade) + `loader_modules/`.

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to `*_modules/`. Change behavior in the modules, not the facade signature.
- **Constants are SSOT:** cross-subsystem protocol vocabulary is single-sourced in root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); subsystem-internal values + the exception hierarchy stay in each subsystem's `*_constants.py`. No magic strings.
- **zGuard seam:** proprietary enforcement is optional and isolated behind `try: from zguard… / except ImportError: <permissive fallback>`. Open-core stays fully functional without it.
- **Docs ↔ code parity:** every guide here maps 1:1 to a code module; the `zVault-zCode/` graph mirrors both (`[doc]`/`[logic]`/`[folder]` tags, wikilinked). Vault links mirror the **repo tree** (structure), not domain/logic.
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported by the loader).

**See also:** [Home](../../README.md) · [code-side L1 overview](../../core/L1_Foundation/README.md)

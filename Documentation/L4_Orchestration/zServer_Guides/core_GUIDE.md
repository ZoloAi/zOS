# zServer Core Managers Guide

> **Modules:** `core/L4_Orchestration/q_zServer/zServer_modules/core/`
> (`config_manager.py`, `mount_manager.py`, `route_manager.py`, `schema_manager.py`)
> **Purpose:** Configuration and resource managers — resolve server config (SSOT), map URLs to the filesystem, detect/merge route files, and auto-initialize database schemas.
> *(`cache_manager.py` lives in this folder too but is documented in [caching_GUIDE.md](caching_GUIDE.md).)*

**[← Back to zServer Guide](../zServer_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

The core managers own everything zServer needs *before* it can serve a request: where files live, what the config says, which route files exist, and what database tables to create. They are pure resource managers — no request handling.

| Manager | Responsibility |
|---------|----------------|
| `ConfigManager` | Mirror `HttpServerConfig` (the SSOT) to server components |
| `MountManager` | URL-prefix → filesystem mapping (SSOT for mounts) |
| `RouteManager` | Detect + merge route files; build the `HTTPRouter` |
| `SchemaManager` | Auto-initialize DB schemas from `models/` |

---

## ConfigManager

`ConfigManager` extracts and mirrors values from the injected `HttpServerConfig` instance (resolved in `a_zConfig`, the **single source of truth**), so every server component reads one config object:

| Attribute | Source key | Default | Notes |
|-----------|-----------|---------|-------|
| `enabled` / `host` / `port` | `zServer.*` | — | basic bind config |
| `serve_path` | `zServer.serve_path` | cwd | resolved to absolute |
| `routes_file` | `zServer.routes_file` | auto-detect | optional explicit file |
| `server_type` | `zServer.type` (`ZSERVER_TYPE`) | `dev` | runner: `dev` / `waitress` |
| `max_body_bytes` | `zServer.max_body_bytes` (`ZSERVER_MAX_BODY_BYTES`) | 25 MiB | request-body cap → 413 |
| `cors_origin` | `zServer.cors_origin` (`ZSERVER_CORS_ORIGIN`) | `""` | same-origin only by default |
| `ssl_enabled` / `ssl_cert` / `ssl_key` | `zServer.ssl_*` | off | HTTPS for the dev runner |
| `static_mounts` | `zServer.static_mounts` | `{}` | passed to MountManager |

`get_deployment_mode()` returns the **environment** name (`Development` / `Testing` / `Production`) from `z.config` — this is distinct from `server_type` (which runner binds) and is used by caching to force `no-cache` in development.

> **Why the mirror?** Keeping `max_body_bytes`/`cors_origin`/`server_type` resolved in `HttpServerConfig` and mirrored here means request handlers never re-read env vars or re-derive defaults — one resolution, one object.

---

## MountManager

`MountManager` is the SSOT for URL-prefix → filesystem mapping.

**Default (reserved) mounts**, relative to `serve_path`:

```
/static/     → {serve_path}/static/
/templates/  → {serve_path}/templates/
/UI/         → {serve_path}/UI/
```

These three prefixes are **reserved** (`RESERVED_MOUNTS`): a custom mount that tries to repoint them is refused and logged — defaults cannot be hijacked.

**Custom mounts** come from `zServer.static_mounts`:

```python
z = zOS({"zServer": {"static_mounts": {"/assets/": "/path/to/assets"}}})
```

**Plugin auto-mount** — `auto_mount_plugins()` mounts `/plugins/` from the first of `{serve_path}/plugins`, `zCloud/plugins`, or `{cwd}/plugins` that exists, so `_zScripts` metadata can reference `/plugins/<name>.js`.

**Longest-prefix-wins** — `get_mount_for_path()` sorts mounts by prefix length (descending) before matching, so overlapping prefixes resolve deterministically (no dict-order dependence).

---

## RouteManager

`RouteManager` auto-detects and merges route files (Flask blueprint pattern), then builds the `HTTPRouter`.

**Detection** scans two locations for `zServer.*.{zolo,yaml,json}`:

1. **Root** — primary routes (e.g. `zServer.routes.zolo`)
2. **`routes/` subfolder** — modular blueprints (e.g. `routes/zServer.api.yaml`, `routes/zServer.themes.zolo`)

**Merge** (`load_and_merge_routes`) loads each file via `z.loader` (which delegates to `z.parser` for format detection) and merges into one structure: `meta` dicts are updated, `routes` dicts are merged with **last-wins** on conflicts. A `/` default is ensured if none is declared.

> The resulting router's matching/auto-discovery/RBAC behaviour is documented in [routing_GUIDE → HTTPRouter](routing_GUIDE.md#httprouter--matching).

---

## SchemaManager

`SchemaManager` auto-initializes database schemas on server start. It scans `{serve_path}/models/` for `zSchema.*.{zolo,yaml,json}`, loads each via `z.loader`, and creates tables through `z.data`.

- Convention-driven: drop a `models/zSchema.Users.zolo` and the table is created at boot.
- **Idempotent** — tables are created only if missing; re-running is safe.
- No public API — it runs automatically during initialization.

```
models/
├── zSchema.Users.zolo      → users table
└── zSchema.Products.yaml   → products table
```

---

## Troubleshooting

**Custom mount ignored** — it targeted a reserved prefix (`/static/`, `/templates/`, `/UI/`); use a different prefix.

**Wrong file served for overlapping mounts** — longest-prefix-wins is deterministic; check you don't have a shorter prefix shadowing intent (it won't, but verify the prefixes).

**Schema not initialized** — `[zServer] No zSchema files found in models/`: confirm files match `zSchema.*` and live in `{serve_path}/models/`.

---

## See Also

- [zServer Main Guide](../zServer_GUIDE.md) — facade overview
- [routing_GUIDE.md](routing_GUIDE.md) — how detected routes are matched + dispatched
- [lifecycle_GUIDE.md](lifecycle_GUIDE.md) — how `server_type` selects the runner
- [caching_GUIDE.md](caching_GUIDE.md) — `cache_manager` (also in this folder)

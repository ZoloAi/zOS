# zServer Guide

**[← Back to zWalker Guide](zWalker_GUIDE.md) | [Home](../../README.md) | [L4 Overview](README.md)**

> **Full-Featured HTTP/WSGI Server with Declarative Routing**
> Open-core web server with static files, declarative routes, caching, RBAC, and a safe-by-default web baseline — *trust zServer like Flask*.

---

## What It Does

**zServer** (`z.server`) is the L4 HTTP server subsystem: it serves the same declarative `.zolo` apps over HTTP.

- ✅ **Static file serving** — HTML/CSS/JS/images with smart caching and hardened path containment
- ✅ **Declarative routing** — routes defined in zVaFiles (`.zolo`, `.yaml`, `.json`)
- ✅ **Auto-discovery** — routes from directory structure; schemas from `models/`
- ✅ **HTTP caching** — ETag, Last-Modified, Cache-Control with statistics
- ✅ **RBAC** — role-based access control via `z.auth`
- ✅ **One pipeline, two runners** — `dev` (`http.server`) + `waitress` (in-process WSGI) share the exact same request path; external WSGI hosts via `get_wsgi_app()`
- ✅ **Safe by default** — body-size cap, security headers, same-origin CORS, escaped output
- ✅ **zWalker + template rendering** — server-side zUI rendering and Jinja2

**Status:** ✅ Audited + hardened (manager-based architecture, unified request pipeline, web-safe defaults)

> This is a **facade overview**. For deep dives into each module cluster, see the [`zServer_Guides/`](#architecture-overview) folder linked below.

---

## Architecture Overview

zServer is a manager-based facade (`z.server`) delegating to specialized clusters under `zServer_modules/`. Each cluster has its own guide:

| Cluster | Modules | Responsibility | Guide |
|---------|---------|----------------|-------|
| **routing** | router, route_dispatcher, handler, wsgi_bridge, http_headers, security_checks, zapi_* | Match → access-check → dispatch; the shared request pipeline + web-safety baseline | [routing_GUIDE](zServer_Guides/routing_GUIDE.md) |
| **rendering** | page_renderer, static_file_handler, error_pages, form_utils | Matched route → bytes (zUI→HTML, static files, templates, forms, errors) | [rendering_GUIDE](zServer_Guides/rendering_GUIDE.md) |
| **core** | config_manager, mount_manager, route_manager, schema_manager | Config SSOT, URL→filesystem mounts, route-file detection, schema auto-init | [core_GUIDE](zServer_Guides/core_GUIDE.md) |
| **lifecycle** | lifecycle_manager, dev_server_manager, waitress_manager, wsgi_app | Runner selection (`dev`/`waitress`) + WSGI export | [lifecycle_GUIDE](zServer_Guides/lifecycle_GUIDE.md) |
| **caching** | cache_manager, http_cache_utils | Cache policies + ETag/Last-Modified/304 + stats | [caching_GUIDE](zServer_Guides/caching_GUIDE.md) |
| **ports** | (doctrine, cross-module) | Pinned = fail loud, unpinned = hunt + announce; the full host/port cascade | [ports_GUIDE](zServer_Guides/ports_GUIDE.md) |

```
z.server (facade)
│
├── core ........ ConfigManager · MountManager · RouteManager · SchemaManager · CacheManager
├── lifecycle ... LifecycleManager → DevServerManager | WaitressManager | wsgi_app
├── routing ..... HTTPRouter → RouteDispatcher  (Handler / WSGIBridgeHandler share guards + http_headers)
└── rendering ... PageRenderer · StaticFileHandler · ErrorPages · FormUtils

Integrations: z.auth (RBAC) · z.loader/z.parser (route files) · z.data (schemas) · z.walker (zUI render)
```

**One request pipeline for every transport:** the `dev` handler and the `waitress`/external-WSGI handler run the *same* code (`WSGIBridgeHandler`), so behaviour and security are identical across runners.

---

## Quick Start

### 1. Static server

```python
from zOS import zOS

z = zOS({"zServer": {"enabled": True, "port": 8080, "serve_path": "./public"}})
z.server.start()
print(f"Server: {z.server.get_url()}")
z.server.wait()
```

### 2. Declarative routing

Create `zServer.routes.zolo`:

```yaml
type: server
routes:
  /:
    type: static
    file: index.html
  /dashboard:
    type: zWalker
    zVaFolder: @.UI
    zVaFile: zUI.Dashboard
    zBlock: zDashboard
    auto_discover_blocks: true
```

```python
z = zOS({"zServer": {"enabled": True, "port": 8080, "serve_path": "."}})
z.server.start()
z.server.wait()
```

> Route detection, the full route-type reference, and auto-discovery are in [routing_GUIDE](zServer_Guides/routing_GUIDE.md) and [core_GUIDE](zServer_Guides/core_GUIDE.md).

---

## Public API (facade)

| Method | Description |
|--------|-------------|
| `start()` | Start the server (runner per `config.server_type`; a *pinned* port raises `OSError` if taken, an unpinned one hunts — see zOS #43) |
| `stop()` | Graceful shutdown (any runner) |
| `wait()` | Block until interrupted (Ctrl+C handled) |
| `is_running()` | `bool`, any runner |
| `get_url()` | `"http://host:port"` (`https://` if SSL) |
| `get_wsgi_app()` | WSGI callable for external hosts / `wsgi.py` |
| `health_check()` | `{running, host, port, url, serve_path}` |

```python
z.server.start()
print(z.server.health_check())   # {'running': True, 'host': '127.0.0.1', 'port': 8080, ...}
```

Advanced: managers are reachable via `z.server.config_manager`, `.mount_manager`, `.route_manager`, `.cache_manager`, and `z.server.router` — see the cluster guides.

---

## Configuration

```python
z = zOS({
    "zServer": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 8080,
        "serve_path": "./public",
        "routes_file": "zServer.routes.zolo",   # optional explicit file
        "static_mounts": {"/assets/": "/path/to/assets"},  # optional
        "type": "dev",                            # runner: "dev" | "waitress"
        "max_body_bytes": 26214400,               # request-body cap → 413 (25 MiB)
        "cors_origin": "",                        # "" = same-origin only
        "ssl_enabled": False, "ssl_cert": "...", "ssl_key": "..."
    }
})
```

| Key | Env var | Default | Purpose |
|-----|---------|---------|---------|
| `type` | `ZSERVER_TYPE` | `dev` | Runner: `dev` (http.server) or `waitress` |
| `max_body_bytes` | `ZSERVER_MAX_BODY_BYTES` | 25 MiB | Request-body cap; oversize → **413** |
| `cors_origin` | `ZSERVER_CORS_ORIGIN` | `""` | CORS allow-origin; empty = same-origin, never wildcard |

> The runner is **explicit, not inferred** from the environment name. The legacy `http_server` zSpark key is still accepted for backward compatibility; new apps use `zServer`. Full config SSOT details: [core_GUIDE → ConfigManager](zServer_Guides/core_GUIDE.md#configmanager).

---

## Trust posture — "trust zServer like Flask"

The open-core server ships a **safe-by-default web baseline** comparable to Flask/Werkzeug, applied identically across all runners (one pipeline):

- RBAC enforced via `z.auth` (fails closed); parity on the `/api/route-config` SPA endpoint
- `realpath`+`commonpath` path containment; reserved mounts can't be overridden
- sensitive-path block on **every** verb; body-size cap → 413
- always-on security headers; **same-origin CORS by default** (opt-in, never wildcard)
- CRLF-safe redirects; `html.escape`d render/form output; zAPI auth fails closed

**Production-grade hardening stays at the edge** (TLS termination, rate limiting, WAF/abuse control) — the V3 concern owned by the zGuard-sealed runtime + zCloud / ingress, documented privately. Mechanics and threat coverage: [routing_GUIDE → Response hardening](zServer_Guides/routing_GUIDE.md#response-hardening).

---

## Relationship with zBifrost

**zServer** (HTTP) and **zBifrost** (WebSocket) are independent and composable:

| Aspect | zServer | zBifrost |
|--------|---------|----------|
| Protocol | HTTP/HTTPS | WebSocket |
| Purpose | Pages, APIs, static files | Real-time messaging |
| Library | `http.server` / `waitress` | `websockets` |
| Port | 8080 (preferred; unpinned boots hunt upward) | 8765 (default) |
| Deployment | `dev` + `waitress` runners | single asyncio mode |

Run either standalone or both together (full-stack: HTTP page frame + WebSocket live session).

---

## Best Practices

- **Use declarative routing** in `zServer.routes.zolo`, not code — versionable and testable.
- **Lean on auto-discovery** — directory structure mirrors URLs; only declare explicit routes for special cases.
- **Use `zRBAC`** on protected routes instead of in-code auth.
- **Use `wait()`** for signal handling instead of manual loops.
- **Use the `waitress` runner** (or export `get_wsgi_app()`) for deployment; the `dev` runner is for local work.

---

## Summary

zServer is a manager-based HTTP server: **declarative**, **auto-discovering**, **HTTP-cached**, **RBAC-gated**, and **safe by default** — with one request pipeline behind the `dev` and `waitress` runners plus a WSGI export.

| Go deeper | Guide |
|-----------|-------|
| Matching, dispatch, route types, web-safety | [routing_GUIDE](zServer_Guides/routing_GUIDE.md) |
| zUI/static/template/form rendering | [rendering_GUIDE](zServer_Guides/rendering_GUIDE.md) |
| Config SSOT, mounts, route detection, schemas | [core_GUIDE](zServer_Guides/core_GUIDE.md) |
| Runners + WSGI export | [lifecycle_GUIDE](zServer_Guides/lifecycle_GUIDE.md) |
| HTTP caching | [caching_GUIDE](zServer_Guides/caching_GUIDE.md) |

**Architecture:** manager-based delegation — one request pipeline for every transport
**Status:** ✅ Audited + hardened (open-core baseline, "trust like Flask")

---

**[← Back to zWalker Guide](zWalker_GUIDE.md) | [Home](../../README.md) | [L4 Overview](README.md)**

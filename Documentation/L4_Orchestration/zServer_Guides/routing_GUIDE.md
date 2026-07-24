# zServer Routing Guide

> **Modules:** `core/L4_Orchestration/r_zServer/zServer_modules/routing/`
> (`router.py`, `route_dispatcher.py`, `handler.py`, `wsgi_bridge.py`, `http_headers.py`, `security_checks.py`, `zapi_handler.py`, `zapi_scanner.py`, `nav_html_builder.py`, `utils.py`)
> **Purpose:** Match URLs to declarative routes, enforce RBAC, dispatch to the right handler, and apply the safe-by-default web baseline — through **one request pipeline shared by every transport**.

**[← Back to zServer Guide](../zServer_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

The routing cluster is the heart of zServer: it turns an incoming HTTP request into a matched route, checks access, and dispatches to a type-specific handler. Its defining property is that **the `dev` runner (`http.server`) and the `waitress`/external-WSGI runners run the exact same code path** — so behaviour and security posture are identical regardless of how the server is hosted.

```
request ─► Handler (dev)  ┐
          WSGIBridgeHandler ┘─► shared guards ─► HTTPRouter.match ─► check_access ─► RouteDispatcher ─► handler
                                (path-block,                         (RBAC)          (by route type)
                                 body-cap, headers)
```

---

## The one-pipeline design

| Component | Role |
|-----------|------|
| `LoggingHTTPRequestHandler` (`handler.py`) | The `dev` runner's `BaseHTTPRequestHandler`. Implements `do_GET/POST/PUT/DELETE/PATCH`, the shared request guards, and the response-header SSOT. |
| `WSGIBridgeHandler` (`wsgi_bridge.py`) | Wraps the **same** handler so a WSGI server (Waitress, or any external host via `wsgi.py`) drives the identical pipeline. Reads the request body bounded by `max_body_bytes`. |
| `http_headers.py` | SSOT for response headers + CORS policy (see [Response hardening](#response-hardening)). |
| `security_checks.py` | `SecurityChecker` — sensitive-path blocking + filesystem containment. |
| `HTTPRouter` (`router.py`) | Path matching + auto-discovery + RBAC. |
| `RouteDispatcher` (`route_dispatcher.py`) | Per-type request handling. |

Because both runners inherit the same guards, **a fix lands once and covers all transports** — there is no "dev-only" or "prod-only" security path.

---

## HTTPRouter — matching

`HTTPRouter` resolves a path in priority order:

1. **Exact match** — `path in route_map`
2. **Parametrized match** — `/:param` patterns (e.g. `/users/:user_id/avatar`); captured values land in `route["_route_params"]`
3. **Auto-discovered match** — virtual routes synthesized from the directory structure
4. **Default route** — fallback if declared

```python
router = z.server.router
len(router.route_map)              # explicit routes (from zVaFiles)
len(router.auto_discovered_routes) # virtual routes discovered at startup
```

### RBAC (`check_access`)

Every matched route passes through `router.check_access(route)` before dispatch. Access rules are declared on the route via `zRBAC`:

```yaml
/admin:
  type: static
  file: admin.html
  zRBAC:
    require_auth: true        # must be logged in
    require_role: admin       # must hold the role
    require_permission: edit  # must hold the permission
```

Checks **fail closed** (default deny) and delegate to `z.auth`. The same `check_access` gate runs for full-page renders **and** for the `/api/route-config` SPA endpoint, so single-page navigation cannot leak a route's config (`zBlock`/`zVaFile`/`zVaFolder`/`zMeta`) that a full render would have denied.

---

## Auto-discovery

When a `zWalker` route sets `auto_discover_blocks: true`, the router walks the `zVaFolder` and synthesizes virtual routes that mirror the folder/block structure:

```
UI/
├── zUI.Dashboard.zolo   → /Dashboard
├── zUI.About.zolo       → /About
└── zProducts/
    └── zUI.zCLI.zolo    → /zProducts/zCLI
```

Explicit routes always win over discovered ones (a discovered path is skipped if it already exists in `route_map`). The `error/` prefix is reserved for `UI/error/zUI.<code>` error pages.

> Route **file** detection and blueprint merging live in [core_GUIDE → RouteManager](core_GUIDE.md#routemanager).

---

## Route types reference

The dispatcher routes on each route's `type`:

| Type | Purpose |
|------|---------|
| `static` | Serve a file from the filesystem (path-contained to the mount root) |
| `content` | Return an inline HTML string (Flask `return "<h1>…</h1>"`) |
| `template` | Render a Jinja2 template with context |
| `zWalker` | Server-side render zUI blocks (supports auto-discovery) |
| `dynamic` | Render a single zUI block to HTML (no auto-discovery) |
| `zLoom` | Virtual, data-gated zUI route — a DB read both gates and renders (empty → 404) |
| `zProxy` | Front-door: resolve slug → wake tenant app → 302 redirect |
| `form` | Declarative web form (zDialog pattern for web) |
| `json` | Declarative JSON response |
| `zFunc` | Call a plugin function directly (uploads, custom endpoints) |
| `zAPI` | Execute a registered zData operation, return JSON (auto-discovered) |

> Rendering-oriented types (`static`, `content`, `template`, `zWalker`, `dynamic`, `form`) are detailed in [rendering_GUIDE.md](rendering_GUIDE.md). Data types (`zLoom`, `zProxy`, `zAPI`) are below.

### zLoom — data-gated virtual routes

```yaml
/u/%username:
  type: zLoom
  zVaFolder: @.UI
  zVaFile: zUI.Profile
  zBlock: zProfile
```

The block's own `zMeta.zLoom` read is the gate **and** the render source (SSOT): a row → render through the normal zWalker path; nothing → **404** (never 403, so a private/unknown handle never reveals whether it exists). Visibility policy lives entirely in that read's where-clause.

### zProxy — tenant front door

```yaml
/app/%slug:
  type: zProxy
  zProxy: { table: zApps, key: slug, spark_field: zspark_path }
```

Resolves the slug against a registry table, wakes the tenant app (scale-from-zero), and **302**s to it. Only rows with `status: live` resolve; anything else 404s.

### zAPI — declarative JSON operations

zAPI routes are **auto-discovered from zUI files at startup** by `zapi_scanner.py`; each carries a resolved `zdata_config` + `zapi_config`. `zapi_handler.py` executes the registered `z.data` operation and returns JSON.

**Auth fails closed:** a route that declares `auth` but is missing its `auth_model` returns **500** ("auth misconfigured") rather than granting access — a missing model never produces a fabricated pass.

---

## Response hardening

`http_headers.build_response_headers(cors_origin)` is the single source for response headers on **both** runners:

- **Always-on security headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`
- **CORS same-origin by default:** no `Access-Control-Allow-Origin` is emitted unless `cors_origin` is set; the value is **never** wildcard and never duplicated (zAPI no longer adds its own CORS headers)
- `sanitize_header_value()` strips CR/LF from any header value

### Request guards (every verb, both runners)

- **Sensitive-path block** — `SecurityChecker.is_path_blocked` runs on `do_GET/POST/PUT/DELETE/PATCH` (env/config/manifest paths, dotfiles, …), so a routed write verb can't reach a blocked prefix.
- **Body-size cap** — oversize requests are rejected with **413** before the body is read into memory, bounded by `config.max_body_bytes` (see [core_GUIDE → ConfigManager](core_GUIDE.md#configmanager)).

### Redirects (CRLF / open-redirect safe)

`form` and `zProxy` `Location` headers are passed through `sanitize_header_value()`; error messages embedded in `?error=` query strings are URL-encoded. This blocks header-injection and reflected open-redirects.

---

## Filesystem containment (`SecurityChecker.is_path_safe`)

Static/mount/UI serving never trusts a path by prefix string-match. `is_path_safe(file_path, allowed_root)` canonicalizes both with `os.path.realpath` and verifies `os.path.commonpath([real_file, real_root]) == real_root`. This blocks:

- `../` traversal
- **symlink escape** (a link pointing outside the root)
- **sibling-prefix escape** (`/srv/static` vs `/srv/static_secret/…`)

It is the **single containment door** for all three static serve paths in [rendering_GUIDE → StaticFileHandler](rendering_GUIDE.md#static-file-serving).

---

## Troubleshooting

**Routes not auto-detected** — `[zServer] No zServer route files found`: check the route file matches `zServer.*.{zolo,yaml,json}` in the root or `routes/` folder (see core_GUIDE).

**Auto-discovered routes empty** — `Auto-discovery complete: 0 virtual routes`: set `auto_discover_blocks: true` on the `zWalker` route.

**RBAC not enforcing** — confirm the route carries a `zRBAC` block and `z.auth` is initialized; checks fail closed only when auth context exists.

**413 Payload Too Large** — body exceeded `max_body_bytes`; raise it deliberately (`zServer.max_body_bytes` / `ZSERVER_MAX_BODY_BYTES`).

---

## See Also

- [zServer Main Guide](../zServer_GUIDE.md) — facade overview
- [rendering_GUIDE.md](rendering_GUIDE.md) — turning matched routes into HTML/bytes
- [core_GUIDE.md](core_GUIDE.md) — route file detection, mounts, config SSOT
- [lifecycle_GUIDE.md](lifecycle_GUIDE.md) — the runners that drive this pipeline

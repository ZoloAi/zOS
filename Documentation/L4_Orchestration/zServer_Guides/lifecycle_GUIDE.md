# zServer Lifecycle Guide

> **Modules:** `core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/`
> (`lifecycle_manager.py`, `dev_server_manager.py`, `waitress_manager.py`, `wsgi_app.py`)
> **Purpose:** Select and run the server — one request pipeline behind two in-process runners (`dev` / `waitress`) plus a WSGI export for external hosts.

**[← Back to zServer Guide](../zServer_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

The lifecycle cluster decides **which server binds the socket** and manages its start/stop. The runner is chosen by `config.server_type` — explicitly, **not** inferred from the environment name — and every runner drives the same [request pipeline](routing_GUIDE.md).

| `server_type` | Runner | Module | Use |
|---------------|--------|--------|-----|
| `dev` (default) | `http.server` in a background thread | `dev_server_manager` | local development |
| `waitress` | Waitress WSGI server, in-process | `waitress_manager` | cross-platform production |
| *(n/a)* | external WSGI host imports the app | `wsgi_app` | gunicorn/uwsgi/nginx-unit behind a proxy |

> The legacy Gunicorn subprocess runner has been retired — a single stateful WS bridge does not fit a multi-process prefork model. Production is now Waitress in-process, or the WSGI app exported to a host of your choice.

---

## LifecycleManager

`LifecycleManager` is the runner-aware orchestrator:

- `_resolve_server_type()` → `config.server_type` (default `dev`)
- `start()` routes to `_start_waitress()` for `waitress`, otherwise the dev thread
- Hands the shared WSGI app (`get_wsgi_app()`) to the Waitress runner
- Unified `start` / `stop` / `wait` / `is_running` regardless of runner; cleans up on shutdown

```python
z.server.start()      # binds per server_type
z.server.is_running() # true in any runner
z.server.stop()       # graceful, any runner
z.server.wait()       # block until interrupted (Ctrl+C handled)
```

---

## DevServerManager (`server_type: dev`)

Runs Python's built-in `http.server` in a background thread — ideal for local iteration.

- Creates the SSL context when `ssl_enabled` (local HTTPS)
- Passes `directory=serve_path` to the handler — it does **not** `os.chdir` the process. (Earlier versions changed the process CWD; that was removed so the dev runner matches Waitress's no-side-effect posture.)

```python
z = zOS({"zServer": {"enabled": True, "type": "dev", "port": 8080, "serve_path": "./public"}})
z.server.start()
print(z.server.get_url())   # http://127.0.0.1:8080  (https:// if ssl_enabled)
```

---

## WaitressManager (`server_type: waitress`)

Runs the pure-Python **Waitress** WSGI server in-process — cross-platform, no native build, nothing extra to operate.

- Serves the same `WSGIBridgeHandler` pipeline as the dev runner
- Does not mutate the process CWD
- Graceful start/stop via the unified lifecycle interface

```python
z = zOS({"zServer": {"enabled": True, "type": "waitress", "host": "127.0.0.1", "port": 8080}})
z.server.start()
z.server.wait()
```

Front it with a reverse proxy (nginx/Caddy) for TLS termination, rate limiting, and abuse control — that hardening lives at the **edge**, not in the open-core server (see [routing_GUIDE → Response hardening](routing_GUIDE.md#response-hardening) and the main guide's trust posture).

---

## wsgi_app — external WSGI export

`z.server.get_wsgi_app()` returns the WSGI callable — the **same** pipeline the in-process runners use. Ship a static `wsgi.py` to run under any external WSGI host:

```python
# wsgi.py — consumed by gunicorn/uwsgi/nginx-unit, etc.
from zOS import zOS

z = zOS({"zServer": {"enabled": True, "serve_path": "/var/www/app"}})
application = z.server.get_wsgi_app()
```

This is the route to multi-worker prefork if you need it: export the app to a process manager that forks, rather than asking zServer to manage subprocesses.

---

## Deployment shapes

```text
local dev          internet ──► nginx/Caddy (TLS, rate-limit) ──► zServer (waitress)  [recommended prod]
─────────          ───────────────────────────────────────────────────────────────
dev runner         internet ──► WSGI host (gunicorn/uwsgi) ──► wsgi.py (get_wsgi_app)  [external prefork]
(http.server)
```

> Prefer **edge TLS termination** in production and bind zServer to localhost. The dev runner's `ssl_enabled` is for local HTTPS testing.

---

## Troubleshooting

**`waitress` runner won't start** — `No module named 'waitress'`: `pip install waitress` (only needed for that runner), or use `type: dev`.

**Port already in use** — behavior depends on whether the port is *pinned*
(zOS #43). An explicit port (spark `zServer.port`, `HTTP_PORT` env, or a
hosted driver injection) is a contract: boot fails loud with
`OSError: Port 8080 already in use` — change the pin or stop the conflicting
process. An **unpinned** boot never hits this error: zOS hunts upward from
8080 through a bounded window and announces the port it actually bound on
stdout. If you see the OSError, something pinned the port.

**Server didn't pick the expected runner** — `server_type` is explicit; check `zServer.type` / `ZSERVER_TYPE` (it is *not* derived from the deployment/environment name).

---

## See Also

- [zServer Main Guide](../zServer_GUIDE.md) — facade overview
- [routing_GUIDE.md](routing_GUIDE.md) — the pipeline every runner drives
- [core_GUIDE.md](core_GUIDE.md) — `ConfigManager` resolves `server_type`
- [caching_GUIDE.md](caching_GUIDE.md) — environment affects cache policy

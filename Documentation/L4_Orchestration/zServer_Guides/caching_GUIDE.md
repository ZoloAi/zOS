# zServer Caching Guide

> **Modules:** `zServer_modules/core/cache_manager.py` + `zServer_modules/utils/http_cache_utils.py`
> **Purpose:** HTTP cache validation — per-file-type cache policies, ETag / Last-Modified / 304 handling, and hit/miss statistics.

**[← Back to zServer Guide](../zServer_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

zServer implements standard HTTP caching so browsers can revalidate cheaply (304) and skip re-downloading unchanged assets. Two pieces collaborate:

| Module | Role |
|--------|------|
| `CacheManager` (core) | Cache **policy** per file type + statistics |
| `http_cache_utils` (utils) | Low-level **mechanics**: ETag generation, HTTP-date formatting, 304 decisions |

---

## CacheManager — policies

Default policies (`max_age` in seconds):

| File type | max_age | Visibility | Effect |
|-----------|---------|-----------|--------|
| `static` | 3600 | public | cache 1 hour |
| `api` | 300 | private | cache 5 minutes |
| `ui` | 0 | private | always revalidate |
| `template` | 0 | private | always revalidate |
| `favicon` | 86400 | public | cache 1 day |

`get_cache_policy(file_type)` returns the policy (falling back to `{max_age: 0, public: False}`), and the manager builds the `Cache-Control` header from it:

- `max_age == 0` → `no-cache`
- otherwise → `<public|private>, max-age=<n>, must-revalidate`

**Development forces revalidation.** When `get_deployment_mode()` is `development` / `testing` / `debug`, every response is `no-cache` — so you always see fresh files while iterating. (This is the *environment*, independent of `server_type`; see [core_GUIDE → ConfigManager](core_GUIDE.md#configmanager).)

```python
z.server.cache_manager.get_cache_policy("static")  # {"max_age": 3600, "public": True}
z.server.cache_manager.policies                     # full policy table
```

---

## http_cache_utils — mechanics

| Function | Purpose |
|----------|---------|
| `generate_etag(content=…, mtime=…)` | Strong ETag (`"…"`) for content (byte-for-byte) or **weak** ETag (`W/"…"`) for mtime (semantic) |
| `format_http_date(timestamp)` | RFC-compliant `Last-Modified` / date formatting |
| `should_return_304(headers, etag, last_modified)` | Validate `If-None-Match` / `If-Modified-Since` against current state |
| `send_304_response(...)` | Emit a `304 Not Modified` |

Static-file responses ([rendering_GUIDE → Static file serving](rendering_GUIDE.md#static-file-serving)) attach an ETag + `Last-Modified`; a conditional request that still matches gets a 304 with no body.

---

## Statistics

`get_statistics()` tracks cache effectiveness:

```python
stats = z.server.cache_manager.get_statistics()
# {"hits": 42, "misses": 8, "bytes_saved": 1048576, "by_type": {...}}
hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])
print(f"Cache hit rate: {hit_rate:.1%}")
```

`bytes_saved` accumulates the size of bodies skipped via 304, and `by_type` breaks hits/misses down per file type.

---

## Performance tips

- **Tune `max_age` to your workload** — long for fingerprinted static assets, short for APIs, `0` for always-fresh UI.
- **Serve large static assets from a CDN / the edge** in production; let zServer focus on application logic.
- **Don't expect cache hits in development** — the environment forces `no-cache`; test caching with a production environment.

---

## Troubleshooting

**Cache: 0 hits, all misses** — likely the development environment forcing `no-cache`. Check `get_deployment_mode()` and `cache_manager.policies` (static should show `max_age > 0`).

**Asset never revalidates** — confirm the response carries an ETag/`Last-Modified`; a `max_age: 0` policy is `no-cache` by design.

---

## See Also

- [zServer Main Guide](../zServer_GUIDE.md) — facade overview
- [core_GUIDE.md](core_GUIDE.md) — `cache_manager` is a core manager; environment via `ConfigManager`
- [rendering_GUIDE.md](rendering_GUIDE.md) — where caching is applied to served files

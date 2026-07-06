# zos-plugin Facades Guide

> **Modules:** `core/zos_plugin/facades.py`
> **Purpose:** The declarative connection points a plugin names — each wraps one zOS primitive and is the *single* place that knows its internal path, so when a path moves, plugins don't.

**[← Back to zos-plugin Guide](../zPlugin_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

A plugin author writes pure intent (`def upload(user, files, transfer, data): ...`) and `@zfunc` injects these facades by parameter name (see [contract_GUIDE → DI](contract_GUIDE.md#dependency-injection-contextpy)). No deep `from zOS.L2_Handling...` imports, no manual session traversal, no hand-built result dicts.

---

## Value objects

| Type | What it is |
|------|------------|
| `Row(dict)` | A data row with attribute access (`row.id` as well as `row["id"]`) |
| `Stored` | Result of a storage write (`key`, `url`, `path`) + `cache_busted_url` (`?v=<ts>` so a same-keyed replacement reloads) |
| `UploadedFile` | Transport-agnostic view over one raw upload — `bytes`, `mime`, `filename`, `size`, `ext` (mime→ext via the shared `_IMAGE_EXT` map) |

---

## `user` — the logged-in account (`UserCtx`)

Resolved from the session (SSOT: `session.zAuth.applications`). Truthy when authenticated; `id`/`name`/`email`/`role`/`raw`.

```python
user.require()        # returns self, or raises ZAbort("Not authenticated", 401)
if user: ...          # __bool__ → id is not None
```

`UserCtx.from_session(session, app=...)` picks the named app's account, else the first authenticated app (single-app sessions are the common case).

---

## `files` — uploads for this invocation (`FilesFacade`)

Access blobs declared by the transport (multipart over HTTP, or a CLI path source). `bool(files)`, `field in files`, `files.get(field=None)` (named, or the only/first file).

```python
img = files.image("avatar", max_mb=5, allow=None)
```

`image()` returns a **validated** `UploadedFile`, aborting on policy miss: missing file → 400, type not in the allowlist → **415**, empty → 400, over `max_mb` → **413**. This is the input-validation seam for uploads.

---

## `data` — declarative CRUD over zData (`DataFacade`)

Ergonomic CRUD; values are plain dicts, rows come back as `Row`s. Operations are **structured/parameterized** through `zos.data` — never raw SQL.

| Method | Behaviour |
|--------|-----------|
| `select(table, where, fields)` | list of `Row` |
| `first(table, where)` | first `Row` or `None` |
| `insert(table, values)` | insert; best-effort returns the new row (max-id of the match set) |
| `update(table, values, where)` | update matching rows |
| `upsert(table, where, values)` | update the `where` match (or insert `where+values`); return the row |

> `insert`/`upsert` return is **best-effort** (a probe select picks the max-id match) — fine for the common single-writer flow; don't rely on it under heavy concurrent inserts.

---

## `transfer` — bytes in/out of zOS (`TransferFacade`)

Thin front to the zTransfer engine (local in dev, S3/CDN in prod). The facade is the **one place** that knows the engine's internal import path and caches the engine on `zos.transfer`.

```python
stored = transfer.store(img.bytes, key="users/1/avatar.png", mime="image/png", filename="a.png")
# → Stored(key, url, path); raises ZAbort(500) if the write fails
transfer.run(spec)   # raw zTransfer spec escape hatch
```

---

## `instance` / `proxy` — run & address another app

Both ride the compute driver ([compute_GUIDE](compute_GUIDE.md)); the backend (local process in dev, k8s in prod) is selected by env, so the plugin flow is identical everywhere.

- **`instance`** owns *lifecycle*: `wake(app, timeout=25)` → `Instance` (ensures running+reachable), `sleep(app)` → bool, `status(app)` → `Instance` (never raises).
- **`proxy`** owns *addressing*: `resolve(app, timeout=25)` → `ProxyTarget` (wake-and-hold; `url`/`ws_url`/`ready`). Dev returns the instance's own address (redirect hand-off); prod returns an ingress URL whose reverse-proxy forwards HTTP/WS to the pod.

```python
@zfunc
def launch(app_id, proxy, data):
    row = data.first("zApps", where={"slug": app_id})
    t = proxy.resolve({"app_id": app_id, "folder": row["folder"], "spark": row["spark"]})
    return {"ok": t.ready, "data": {"url": t.url, "state": t.state}}
```

---

## Troubleshooting

**`415 Unsupported image type`** — the upload's mime isn't in the allowlist; pass `allow=[...]` or fix the client.

**`row.x` raises `AttributeError`** — the column isn't in the row; `Row` maps missing attrs to `AttributeError` (use `.get("x")`).

**`instance.wake` returns `state="waking"`** — the app didn't open its port within `timeout`; raise the timeout or check the instance log ([compute_GUIDE](compute_GUIDE.md)).

---

## See Also

- [zos-plugin Guide](../zPlugin_GUIDE.md) · [contract_GUIDE.md](contract_GUIDE.md)
- [compute_GUIDE.md](compute_GUIDE.md) — the driver behind `instance`/`proxy`
- [hosting_GUIDE.md](hosting_GUIDE.md)

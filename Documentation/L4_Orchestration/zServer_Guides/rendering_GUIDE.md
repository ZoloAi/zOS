# zServer Rendering Guide

> **Modules:** `core/L4_Orchestration/q_zServer/zServer_modules/rendering/`
> (`page_renderer.py`, `static_file_handler.py`, `error_pages.py`, `form_utils.py`)
> **Purpose:** Turn a matched route into bytes — server-side zUI rendering, static-file serving, Jinja2 templates, declarative web forms, and error pages — with XSS-safe output by default.

**[← Back to zServer Guide](../zServer_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

Once the [routing pipeline](routing_GUIDE.md) has matched a route and granted access, a rendering module produces the response body. There are four renderers, each owning a family of route types:

| Module | Route types | Output |
|--------|-------------|--------|
| `page_renderer` | `zWalker`, `dynamic` | zUI blocks → HTML |
| `static_file_handler` | `static`, `/static/*`, `/UI/*`, mounts | files from disk |
| `form_utils` | `form` | declarative web forms (zDialog for web) |
| `error_pages` | (any failure) | 403 / 404 / error HTML |

`template` (Jinja2) and `content` (inline HTML) are rendered directly in the dispatcher; both are covered below.

---

## PageRenderer — zUI → HTML

`PageRenderer.render_page(zVaFile, zBlock)` executes a zUI block server-side and emits HTML. It is the bridge between the declarative zUI format and the browser.

**XSS-safe by construction.** All route-/user-derived values interpolated into the HTML are passed through `html.escape` (an internal `_h()` helper). This covers:

- zUI element debug keys/values, link `href`/`label`, `title` attributes
- display-event `content` values and list items
- the page `title` in the template wrapper
- error `message` text

Numeric attributes (e.g. `indent`) are cast to `int()` before use, so a string can't be injected through a size/offset field.

```yaml
/dashboard:
  type: zWalker
  zVaFolder: @.UI
  zVaFile: zUI.Dashboard
  zBlock: zDashboard
  auto_discover_blocks: true
```

`dynamic` is the single-block variant (no auto-discovery): `{ type: dynamic, zVaFile: zUI.Widget, zBlock: zVaF }`.

---

## Static file serving

`StaticFileHandler` serves three path families — `/static/*`, custom mounts, and `/UI/*`. Every one of them resolves the candidate path and then gates it through the **single containment door**, `SecurityChecker.is_path_safe(file_path, root)` (`realpath` + `commonpath`), before opening the file. See [routing_GUIDE → Filesystem containment](routing_GUIDE.md#filesystem-containment-securitycheckeris_path_safe).

- **MIME detection** is centralized in `HandlerUtils.guess_content_type(file_path)` (falls back to `application/octet-stream`) — no duplicated `mimetypes` logic.
- **Caching** (ETag / Last-Modified / 304) is delegated to the [caching cluster](caching_GUIDE.md).
- Mount resolution (which root a URL maps to, longest-prefix-wins) lives in [core_GUIDE → MountManager](core_GUIDE.md#mountmanager).

---

## Template rendering (Jinja2)

```yaml
/profile:
  type: template
  file: profile.html
  context:
    user: "{{ session.user }}"
```

`template` routes render a Jinja2 template with the supplied context. Use templates for traditional server-rendered pages; use `zWalker`/`dynamic` when the page is authored as a declarative zUI block.

`content` routes return an inline HTML string directly (`{ type: content, content: "<h1>…</h1>" }`) — handy for tiny endpoints.

---

## Declarative web forms

`form_utils` implements the zDialog pattern for the web: a form is declared as data and rendered to HTML, and its POST submission is handled by the same module.

```yaml
/contact:
  type: form
  schema: zForm.Contact
```

On submit failure, the error message is **HTML-escaped** before being rendered back into the page, and any error surfaced via redirect is CRLF-stripped + URL-encoded in the `Location`/`?error=` (see [routing_GUIDE → Redirects](routing_GUIDE.md#redirects-crlf--open-redirect-safe)).

---

## Error pages

`error_pages` renders `403` (access denied) and `404` (not found) responses. Custom error UIs can be authored as `UI/error/zUI.<code>.zolo` blocks (the `error/` prefix is reserved during auto-discovery). Error message text is escaped like all other rendered content.

---

## Troubleshooting

**Blank or partial zUI page** — confirm the `zVaFile`/`zBlock` exist and the block renders under zWalker locally; rendering errors surface as an escaped error page, not a 500 stack.

**Static file 404 inside the mount** — the path resolved outside the mount root and was rejected by containment; check for symlinks pointing outside `serve_path`.

**Template not found** — `template` routes resolve `file` relative to the templates mount; verify the `/templates/` mount (core_GUIDE → MountManager).

---

## See Also

- [zServer Main Guide](../zServer_GUIDE.md) — facade overview
- [routing_GUIDE.md](routing_GUIDE.md) — matching, dispatch, containment, response headers
- [core_GUIDE.md](core_GUIDE.md) — mounts (which root a URL serves from)
- [caching_GUIDE.md](caching_GUIDE.md) — ETag / Last-Modified / 304 for served files

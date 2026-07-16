# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/seo_endpoints.py
"""
Built-in /robots.txt + /sitemap.xml (SEO endpoint seam, issue #24 Phase A).

Philosophy (mirrors default_templates.py):
    - "Just Works" — every Bifrost app answers robots/sitemap out of the box
    - Override-able — an app's own explicit route for either path always wins
      (the dispatcher only calls these when the router has NO match), so an
      alpha app can ship a `Disallow: /` robots.txt and shadow the default
    - Projection, not duplication — the sitemap is enumerated from the SAME
      route tables the router serves (route_map + auto_discovered_routes);
      no second list of pages exists anywhere

Sitemap inclusion policy (public outline only):
    - page types only (zWalker / template / zLoom) — never static/zAPI/zProxy
    - parameterized paths (":" segments) and wildcards are skipped — dynamic
      row enumeration is a beta concern (see issue #24 limitations)
    - gated routes are skipped via the SSOT gate engine (zos.zgate) — a route
      with ANY authored gate is not public, so it never leaks into the sitemap
"""

import html

_PAGE_TYPES = {"zWalker", "template", "zLoom"}


def _request_base(handler) -> str:
    """Absolute URL base from the request (proxy-aware), no trailing slash."""
    headers = getattr(handler, 'headers', None)
    host = None
    proto = 'http'
    if headers is not None:
        host = headers.get('X-Forwarded-Host') or headers.get('Host')
        proto = headers.get('X-Forwarded-Proto') or 'http'
    if not host:
        return ''
    return f"{proto}://{host}"


def _send(handler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-type", content_type)
    handler.send_header("Content-length", len(body))
    handler.end_headers()
    handler.wfile.write(body)


def serve_robots(handler) -> None:
    """Default robots.txt: allow pages, keep bots off the API, point at the
    sitemap. An app that wants different policy ships its own /robots.txt
    route — the dispatcher never calls this when a route matches."""
    base = _request_base(handler)
    lines = [
        "User-agent: *",
        "Disallow: /api/",
        "Allow: /",
    ]
    if base:
        lines.append(f"Sitemap: {base}/sitemap.xml")
    body = ("\n".join(lines) + "\n").encode("utf-8")
    _send(handler, body, "text/plain; charset=utf-8")


def _public_page_paths(router, zos, logger=None):
    """Enumerate crawlable page paths from the live route tables (SSOT)."""
    paths = []
    seen = set()
    stats = {'total': 0, 'shape': 0, 'type': 0, 'param': 0, 'status': 0, 'gate': 0}
    for source in (getattr(router, 'route_map', None) or {},
                   getattr(router, 'auto_discovered_routes', None) or {}):
        for path, route in source.items():
            stats['total'] += 1
            if not isinstance(path, str) or not isinstance(route, dict):
                stats['shape'] += 1
                continue
            if path in seen:
                continue
            if route.get("type", "static") not in _PAGE_TYPES:
                stats['type'] += 1
                continue
            # Parameterized (/u/:username) and wildcard routes need row
            # enumeration — beta scope, skipped here (issue #24).
            if ':' in path or '*' in path or '%' in path:
                stats['param'] += 1
                continue
            # Error-page routes render through zWalker but carry a real status.
            if route.get("_status_code"):
                stats['status'] += 1
                continue
            # SSOT gate engine: any authored gate → not a public page.
            try:
                if zos is not None and getattr(zos, 'zgate', None) is not None:
                    if zos.zgate.gate_predicate(route) is not None:
                        stats['gate'] += 1
                        continue
            except Exception as exc:  # pylint: disable=broad-except
                if logger:
                    logger.debug(f'[seo_endpoints] gate check skipped for {path}: {exc}')
                stats['gate'] += 1
                continue
            seen.add(path)
            paths.append(path)
    if logger:
        logger.debug(f'[seo_endpoints] enumeration: {stats} → {len(paths)} public')
    return sorted(paths)


def serve_sitemap(handler, router, zos, logger=None) -> None:
    """sitemap.xml projected from the route tables. Empty host → empty urlset
    (a sitemap of relative URLs is invalid; better honest-empty than broken)."""
    base = _request_base(handler)
    entries = []
    if base:
        for path in _public_page_paths(router, zos, logger=logger):
            loc = html.escape(base + path, quote=True)
            entries.append(f"  <url><loc>{loc}</loc></url>")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + ("\n" if entries else "")
        + "</urlset>\n"
    ).encode("utf-8")
    if logger:
        logger.debug(f'[seo_endpoints] sitemap served ({len(entries)} urls)')
    _send(handler, body, "application/xml; charset=utf-8")

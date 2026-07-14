# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/html_injectors.py
"""
HTML head/body injectors for server-rendered pages (extracted from route_dispatcher).

Pure functions that stamp the CSS cascade (zbase → zCanvas → zBrush), the zui-config
script, the <title>, the navbar HTML, and the zGuard trust watermark into already-
rendered HTML. This is the ONE home for head-injection — shared verbatim by the
template and zWalker render paths (see page_route_handlers).
"""

import html


# Client-URL policy SSOT moved to zSys/bifrost_client_pin.py, shared with the
# sealed zGuard bridge (bridge_connection imports it for bifrost_core_url).
# Everything (bootstrap <script>, zbase.css, core) resolves from ONE git-tag
# pin (zguard_bin/BIFROST_CLIENT_PIN) served via jsdelivr/gh; the npm @1 alias
# is a fail-safe only. BIFROST_CDN_BASE stays re-exported for old importers.
from zSys.bifrost_client_pin import BIFROST_CDN_BASE, bifrost_client_base


def _bifrost_client_base() -> str:
    """Resolve at call time — zEnv loads into os.environ after import."""
    return bifrost_client_base()


def _build_styles_links(zVaFile_meta, logger=None, styles_folder=None, zbase_css_url=None, zcanvas_name=None):
    """
    Build <link rel="stylesheet"> tags for the full CSS cascade.

    Cascade order (Layer 0 → 2):
    0. zbase.css  — bifrost structural baseline (CDN, always injected server-side
                    so CSS is synchronous with page load, no JS async fetch race)
    1. zCanvas — app-wide root CSS, declared via `zCanvas: <name>` in zSpark
                 (resolves to /styles/<name>.css; a dot nests: main.zC_Main →
                 /styles/main/zC_Main.css). Falls back to styles/zCanvas.css
                 when no zCanvas is declared, for backward compatibility.
    2. zBrush: [name] — per-page stylesheets declared in zUI zMeta

    Resolution rules for zBrush entries (zOS convention: non-absolute = relative to /styles/):
    - bare name (pricing)             → /styles/pricing.css
    - dotted name (demo.zVideo_demo)  → /styles/demo/zVideo_demo.css  (dot = sub-dir)
    - &.mount.name (&.brand.zCloud)   → /brand/zCloud.css             (dot = sub-dir, from server root)
    - absolute path (/custom/a.css)   → passed through as-is
    """
    import os as _os
    links = []

    # Layer 0: zbase.css — bifrost structural baseline, always injected by server
    if zbase_css_url:
        links.append(f'<link rel="stylesheet" href="{zbase_css_url}">')
        if logger:
            logger.debug(f'[RouteDispatcher] zbase: {zbase_css_url}')

    # Layer 1: zCanvas — app-wide root CSS from zSpark `zCanvas: <name>`.
    # Honor the declared name first; fall back to legacy styles/zCanvas.css.
    # A dot is a sub-directory separator under /styles/ (main.zC_Main -> styles/main/zC_Main.css).
    canvas_file = f"{zcanvas_name.replace('.', '/')}.css" if zcanvas_name else 'zCanvas.css'
    if styles_folder and _os.path.isfile(_os.path.join(styles_folder, canvas_file)):
        links.append(f'<link rel="stylesheet" href="/styles/{canvas_file}">')
        if logger:
            logger.debug(f'[RouteDispatcher] zCanvas: injected /styles/{canvas_file}')

    # Layer 2: zBrush — per-page CSS declared in zMeta
    z_brush = (zVaFile_meta or {}).get('zBrush', [])
    if isinstance(z_brush, str):
        z_brush = [z_brush]
    for ref in (z_brush or []):
        ref = str(ref).strip()
        if not ref:
            continue
        if ref.startswith('&.'):
            href = '/' + ref[2:].replace('.', '/') + '.css'
        elif ref.startswith('/'):
            href = ref
        else:
            # zOS convention: non-absolute = relative to /styles/; a dot is a
            # sub-directory separator (demo.zVideo_demo -> /styles/demo/zVideo_demo.css).
            href = f"/styles/{ref.replace('.', '/')}.css"
        links.append(f'<link rel="stylesheet" href="{href}">')
        if logger:
            logger.debug(f'[RouteDispatcher] zBrush: {ref} → {href}')

    if not links:
        return ''
    return '\n<!-- zbase + zCanvas + zBrush -->\n' + '\n'.join(links) + '\n'


def _build_nav_html_safe(navbar_items, brand, logger=None, zos=None):
    """3A: Build navbar HTML string from RBAC-filtered items. Returns None on any failure.

    ``zos`` is forwarded to the builder so items carrying an explicit zLink
    override resolve to their canonical URL (zPath → route) instead of a
    structure-by-name href.
    """
    if not navbar_items:
        return None
    try:
        from .nav_html_builder import build_nav_html
        return build_nav_html(navbar_items, brand=brand, zos=zos)
    except Exception as exc:
        if logger:
            logger.debug(f'[RouteDispatcher] nav_html build skipped: {exc}')
        return None


def _inject_zui_head(html_content, zui_config_values, zVaFile_meta, styles_folder, logger=None, zcanvas_name=None):
    """Inject zBrush style <link>s + the zui-config <script> before </head> (SSOT).

    Both the `template` and `zWalker` render paths used to carry an identical pair
    of `</head>` replacements; this is the one place that head-injection lives now.
    The caller owns `zui_config_values` (the zWalker path adds a `websocket` block;
    the template path does not), keeping their only real difference at the call site.
    """
    import json

    # syntaxBase — announce the served zolo-lsp Prism bundle (versioned URL,
    # e.g. "/zsyntax/1.2.0/"). The client's prism_loader prefers it over its
    # own bundled syntax/ dir and treats the value as an OPAQUE base. Absent
    # entirely (not null) when the installed zolo-lsp predates the bundle —
    # zSys.zsyntax_bundle is the same SSOT MountManager mounts from, so the
    # field is only ever announced when the route actually serves.
    from zSys.zsyntax_bundle import zsyntax_base
    _syntax_base = zsyntax_base()
    if _syntax_base and 'syntaxBase' not in zui_config_values:
        zui_config_values = {**zui_config_values, 'syntaxBase': _syntax_base}

    zbase_css_url = f'{_bifrost_client_base()}/zSys/theme/zbase.css'
    styles_html = _build_styles_links(
        zVaFile_meta, logger, styles_folder=styles_folder, zbase_css_url=zbase_css_url,
        zcanvas_name=zcanvas_name
    )
    if styles_html:
        html_content = html_content.replace('</head>', styles_html + '</head>', 1)

    # Only inject the config script when at least one value is present (not all None)
    if any(v is not None for v in zui_config_values.values()):
        zui_config_json = json.dumps(zui_config_values, indent=4)
        zui_config_script = (
            '\n<!-- zUI Config (auto-injected from zSession) -->\n'
            '<script id="zui-config" type="application/json">\n'
            f'{zui_config_json}\n</script>\n</head>'
        )
        html_content = html_content.replace('</head>', zui_config_script, 1)
        if logger:
            logger.info("[RouteDispatcher] Auto-injected <script id='zui-config'> into HTML head")
    return html_content


def _inject_seo_meta(html_content, page_title, app_brand, zVaFile_meta,
                     request_host=None, request_path=None, request_proto=None,
                     logger=None):
    """Stamp crawler-facing meta tags into the shell head (SEO seam, zMeta-driven).

    The rendered shell is a hydration stub (content arrives over the Bifrost WS),
    so plain-GET consumers — search engines, link-preview bots, social cards —
    see only what this head carries. Declarative sources, all optional:

      zMeta.zDescription → <meta name="description"> + og:description
      zMeta.zImage       → og:image (absolutized against the request host)
      page title / brand → og:title / og:site_name
      request host+path  → canonical <link> + og:url (skipped when Host unknown)

    Nothing is invented: pages that declare nothing get title/site_name/canonical
    only. Injection is idempotent per render (runs once, before </head>).
    """
    if '</head>' not in html_content:
        return html_content

    description = (zVaFile_meta or {}).get('zDescription')
    image = (zVaFile_meta or {}).get('zImage')

    base_url = None
    if request_host:
        proto = request_proto or 'http'
        base_url = f"{proto}://{request_host}"

    canonical = None
    if base_url is not None and request_path:
        canonical = base_url + request_path.split('?', 1)[0]

    def _attr(value):
        return html.escape(str(value), quote=True)

    tags = []
    if description:
        tags.append(f'<meta name="description" content="{_attr(description)}">')
    if page_title:
        tags.append(f'<meta property="og:title" content="{_attr(page_title)}">')
    if description:
        tags.append(f'<meta property="og:description" content="{_attr(description)}">')
    if app_brand:
        tags.append(f'<meta property="og:site_name" content="{_attr(app_brand)}">')
    tags.append('<meta property="og:type" content="website">')
    if canonical:
        tags.append(f'<link rel="canonical" href="{_attr(canonical)}">')
        tags.append(f'<meta property="og:url" content="{_attr(canonical)}">')
    if image:
        img = str(image)
        if img.startswith('/') and base_url:
            img = base_url + img
        tags.append(f'<meta property="og:image" content="{_attr(img)}">')
        tags.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        tags.append('<meta name="twitter:card" content="summary">')

    seo_html = '\n<!-- SEO meta (auto-injected from zMeta) -->\n' + '\n'.join(tags) + '\n'
    if logger:
        logger.debug(f'[RouteDispatcher] SEO meta injected ({len(tags)} tags)')
    return html_content.replace('</head>', seo_html + '</head>', 1)


def _inject_title(html_content, page_title, logger=None):
    """Write the computed page title into the rendered ``<title>`` (SSOT).

    The Jinja ``<title>{{ title }}</title>`` is rendered before the per-page
    title is known (title derives from block-first zMeta resolved after render),
    so the tag comes out empty. Both render paths compute ``page_title`` just
    before head-injection — this stamps it into the already-rendered ``<title>``
    so the browser tab matches the injected ``zui-config.title``.
    """
    if not page_title:
        return html_content
    import re
    safe = html.escape(str(page_title), quote=False)
    new_html, n = re.subn(r'<title>.*?</title>', f'<title>{safe}</title>',
                          html_content, count=1, flags=re.DOTALL)
    if n and logger:
        logger.info(f"[RouteDispatcher] Stamped <title>: {page_title!r}")
    return new_html


def _inject_watermark(html_content, zos=None, logger=None):
    """Inject the zGuard trust watermark (zOS License §3.2) before ``</body>``.

    Instance-level mark: ON for an UNREGISTERED instance (no verifiable owner),
    OFF once signed in. Both the ON/OFF verdict and the badge markup come from
    zGuard (sealed) via the zAuth facade — open core only places the returned
    string. No-op when registered, when zGuard is absent, or on any error.
    """
    if not zos or not hasattr(zos, 'auth'):
        return html_content
    try:
        mark = zos.auth.watermark_html()
    except Exception as exc:  # pylint: disable=broad-except
        if logger:
            logger.debug(f'[RouteDispatcher] watermark skipped: {exc}')
        return html_content
    if not mark:
        return html_content
    if '</body>' in html_content:
        return html_content.replace('</body>', mark + '</body>', 1)
    return html_content + mark

# zOS/core/L3_Abstraction/o_zBifrost/zBifrost_modules/nav_html_builder.py

"""
NavHTMLBuilder — server-side navbar HTML generation (Phase 3A).

Python owns the navbar structure. The client receives ready-to-inject HTML with
data-nav-* attributes; a small JS event delegator wires the interactions.

This removes NavigationRenderer.renderNavBar() as the source-of-truth for
the meta navbar and eliminates 150+ lines of client-side construction logic.
"""

import re
import uuid


def build_nav_html(
    items: list,
    brand: str = None,
    theme: str = 'light',
    css_class: str = 'zcli-navbar-meta',
    zos=None,
) -> str:
    """
    Build Bootstrap-compatible navbar HTML from a RBAC-filtered items list.

    Args:
        items:     List of navbar items (strings or dicts with zSub/zRBAC/zLink).
        brand:     Brand text shown as the leftmost link (e.g. "zCloud").
        theme:     zTheme variant — 'light' or 'dark'.
        css_class: Extra CSS class on the <nav> element.
        zos:       zOS instance — required to resolve an item's zLink (zPath →
                   URL route via the SSOT ZLinkResolver). When absent, items fall
                   back to structure-by-name hrefs (``/<itemName>``).

    Returns:
        HTML string ready for innerHTML injection.
    """
    collapse_id = f'navbar-collapse-{uuid.uuid4().hex[:9]}'

    parts = [
        f'<nav class="zNavbar zNavbar-{theme} {css_class}" role="navigation">'
    ]

    if brand:
        parts.append(f'<a href="/" class="zNavbar-brand">{_esc(brand)}</a>')

    parts.append(
        f'<button class="zNavbar-toggler"'
        f' data-nav-action="hamburger"'
        f' data-nav-target="{collapse_id}"'
        f' aria-controls="{collapse_id}"'
        f' aria-expanded="false"'
        f' aria-label="Toggle navigation">'
        f'<i class="bi bi-list" style="font-size:1.5rem;"></i>'
        f'</button>'
    )

    parts.append(f'<div class="zNavbar-collapse" id="{collapse_id}">')
    parts.append('<ul class="zNavbar-nav">')

    for item in items:
        parts.extend(_render_item(item, zos))

    parts.append('</ul>')
    parts.append('</div>')
    parts.append('</nav>')

    return ''.join(parts)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _render_item(item, zos=None) -> list:
    """Render one navbar item (simple string or hierarchical dict)."""
    if isinstance(item, dict):
        # {itemName: {zSub: [...], zLink: ..., ...}} — carries metadata
        item_name = next(iter(item))
        item_data = item[item_name] if isinstance(item[item_name], dict) else {}
        sub_items = item_data.get('zSub', [])
        zlink = item_data.get('zLink')

        if sub_items:
            return _render_dropdown(item_name, sub_items, zos, zlink)

        # Dict without zSub — plain link. An explicit zLink override (zPath)
        # retargets the href away from the structure-by-name default.
        label = _strip(item_name)
        href = _href_for(item_name, zlink, zos)
        return [_simple_li(label, href)]

    if isinstance(item, str):
        label = _strip(item)
        href = _to_href(item)
        return [_simple_li(label, href)]

    return []


def _render_dropdown(parent_name: str, sub_items, zos=None, parent_zlink=None) -> list:
    parent_label = _strip(parent_name)
    parent_href = _href_for(parent_name, parent_zlink, zos)

    parts = ['<li class="zNav-item zDropdown">']
    parts.append(
        f'<a href="{parent_href}" class="zNav-link zDropdown-toggle"'
        f' data-nav-action="dropdown-toggle"'
        f' aria-haspopup="true" aria-expanded="false">'
        f'{_esc(parent_label)}</a>'
    )
    parts.append('<div class="zDropdown-menu">')

    # SSOT: a child's target is resolved ONCE by the navbar authority (the same
    # helper the zCLI menu uses), then mapped to a route via the shared
    # ZLinkResolver — so the dropdown can't drift from the terminal. Children
    # arrive normalized as {child: {zLink?, zRBAC?}}; tolerate a raw list too.
    for child_name, child_meta in _iter_children(sub_items):
        sub_label = _strip(child_name)
        child_zlink = _resolve_child_zlink(parent_name, child_name, child_meta)
        sub_href = _href_for(child_name, child_zlink, zos)
        parts.append(
            f'<a href="{sub_href}" class="zDropdown-item"'
            f' data-nav-action="navigate" data-nav-href="{sub_href}">'
            f'{_esc(sub_label)}</a>'
        )

    parts.append('</div>')
    parts.append('</li>')
    return parts


def _iter_children(sub_items):
    """Yield ``(child_name, child_meta)`` from a normalized dict or raw list."""
    if isinstance(sub_items, dict):
        for name, meta in sub_items.items():
            yield name, (meta if isinstance(meta, dict) else {})
    elif isinstance(sub_items, list):
        for child in sub_items:
            if isinstance(child, str):
                yield child, {}
            elif isinstance(child, dict) and len(child) == 1:
                name = next(iter(child))
                meta = child[name]
                yield name, (meta if isinstance(meta, dict) else {})


def _resolve_child_zlink(parent_name, child_name, child_meta):
    """Resolve a zSub child to its zLink via the single navbar authority."""
    try:
        from zOS.L2_Handling.h_zNavigation.navigation_modules.handlers.handler_navbar import (
            NavbarHandler,
        )
        return NavbarHandler.resolve_zsub_child_zlink(
            parent_name, child_name, child_meta
        )
    except Exception:  # pragma: no cover — never block navbar render
        meta = child_meta if isinstance(child_meta, dict) else {}
        return meta.get('zLink')


def _simple_li(label: str, href: str) -> str:
    return (
        f'<li class="zNav-item">'
        f'<a href="{href}" class="zNav-link"'
        f' data-nav-action="navigate" data-nav-href="{href}">'
        f'{_esc(label)}</a>'
        f'</li>'
    )


def _strip(item: str) -> str:
    """Remove zOS navigation modifiers ($, ^, ~) from the start of a string."""
    return re.sub(r'^[$^~]+', '', item)


def _to_href(item: str) -> str:
    clean = _strip(item)
    return f'/{clean}'


def _href_for(item_name: str, zlink, zos) -> str:
    """Resolve a navbar item's href.

    Default is structure-by-name (``/<itemName>``). When the item declares an
    explicit ``zLink`` (a zPath like ``@.zViews.zUI.zStack.zStack``) we map it to
    its canonical URL through the SSOT ``ZLinkResolver.resolve_href_to_route`` —
    the same authority zDisplay/zNavigation use — so a navbar item can target any
    relocated page (e.g. login moved under ``zAuth/``) without minting a dead
    ``/<itemName>`` route. Falls back to structure-by-name when there is no zLink,
    no zos, or the zPath has no registered route (resolver returns it unchanged).
    """
    if zlink and zos is not None:
        try:
            from zOS.L2_Handling.h_zNavigation.navigation_modules.resolvers.resolver_zlink import (
                ZLinkResolver,
            )
            resolved = ZLinkResolver(None).resolve_href_to_route(zos, zlink)
            if resolved and not resolved.startswith('@'):
                return resolved
        except Exception:  # pragma: no cover — never block navbar render
            pass
    return _to_href(item_name)


def _esc(text: str) -> str:
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
    )

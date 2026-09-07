# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/oauth_endpoints.py
"""
Built-in /zauth/<provider>/<start|callback> doors (PROPOSAL.zOAuth.md).

Philosophy (mirrors seo_endpoints.py):
    - "Just Works" — configure ZOAUTH_<PROVIDER>_CLIENT_ID/SECRET in zEnv and
      the doors are live; no route registration, no app code
    - Override-able — an app's own explicit route for a /zauth/ path shadows
      the built-in (the dispatcher checks before calling here)
    - Thin — this module is TRANSPORT only (parse, redirect, cookie context
      comes free from the per-request session seam); every decision lives in
      f_zAuth.actions.action_oauth

Every answer is a 302: success → the sanitized ``next`` path, refusal →
``/?zauth_error=<coarse code>`` (the real reason is logged server-side; a URL
never carries detail).
"""

from urllib.parse import parse_qs, urlparse

from .seo_endpoints import _request_base

_LOG = "[zOAuth-door]"


def handle_oauth_request(handler, router, clean_path, logger=None):
    """Dispatch a /zauth/… request. Always answers (302); returns None."""
    from zOS.L2_Handling.f_zAuth.zAuth_modules.actions import (  # pylint: disable=import-outside-toplevel
        action_oauth,
    )

    zos = getattr(router, 'zos', None)
    parts = [p for p in clean_path.split('/') if p]  # ['zauth', provider, hop]
    if len(parts) != 3 or zos is None:
        return _redirect(handler, '/?zauth_error=bad_path')
    _, provider, hop = parts

    base = _request_base(handler)
    redirect_uri = f"{base}/zauth/{provider}/callback" if base else ""
    query = {k: v[0] for k, v in parse_qs(urlparse(handler.path).query).items()}

    if hop == 'start':
        url = action_oauth.begin(zos, provider, redirect_uri,
                                 next_path=query.get('next', '/'))
        if not url:
            return _redirect(handler, '/?zauth_error=provider_unavailable')
        return _redirect(handler, url)

    if hop == 'callback':
        ok, dest_or_code = action_oauth.complete(zos, provider, query, redirect_uri)
        if ok:
            return _redirect(handler, dest_or_code or '/')
        return _redirect(handler, f'/?zauth_error={dest_or_code}')

    if logger:
        logger.warning(f"{_LOG} unknown hop '{hop}' on {clean_path}")
    return _redirect(handler, '/?zauth_error=bad_path')


def _redirect(handler, location):
    """302 with no-store — auth hops must never be cached."""
    handler.send_response(302)
    handler.send_header('Location', location)
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', '0')
    handler.end_headers()
    return None

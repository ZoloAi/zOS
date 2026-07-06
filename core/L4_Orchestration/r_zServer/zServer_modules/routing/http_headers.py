# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/http_headers.py

"""
HTTP response-header SSOT — one policy, every transport.

Both the dev http.server handler and the WSGI bridge emit their per-response
headers through here, so security headers and CORS are defined ONCE instead of
copy-pasted into each ``end_headers``. "Trust zServer like Flask" means a single,
auditable header policy that is identical on dev and prod.

Policy:
  - Security headers are ALWAYS applied (defense-in-depth; no opt-out needed).
  - CORS is OFF by default (same-origin only). It is emitted only when an operator
    sets a non-empty ``cors_origin`` (zSpark.zServer.cors_origin / ZSERVER_CORS_ORIGIN).
    We never ship a wildcard ``*`` by default.
  - A ``Content-Security-Policy: frame-src`` backstop is ALWAYS applied — the
    browser-enforced mirror of the zEmbed allow-list (``ZEMBED_MODE``) plus any
    operator-enabled SDK-widget origins (``ZEMBED_SDK``, e.g. PayPal/Stripe). It
    is a *frame-src-only* CSP: with no ``default-src``, every other resource type
    (the CDN-loaded client + theme, inline bootstrap) stays unrestricted, so the
    shell is untouched. It governs only what the page may put in an ``<iframe>``,
    so even a forged client payload can't frame an off-list origin.
"""

# Security response headers applied to EVERY zServer response (dev + WSGI, all
# routes, static, and error pages). CSP is intentionally omitted: the zApp shell
# loads the bifrost client + theme CSS from a CDN and uses inline bootstrap, so a
# strict default CSP would break working apps. Apps that want CSP set it per-route.
SECURITY_RESPONSE_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "SAMEORIGIN"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
)

# Advertised when CORS is enabled. Mirrors the verbs the router actually accepts
# (zAPI does POST/PUT/DELETE/PATCH), so preflight matches dispatch — no per-layer drift.
CORS_ALLOW_METHODS = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
CORS_ALLOW_HEADERS = "Content-Type, Authorization, X-API-Key"


def sanitize_header_value(value) -> str:
    """Strip CR/LF so request-derived values can't inject headers (response splitting)."""
    return str(value).replace("\r", "").replace("\n", "")


def _embed_csp_header() -> tuple:
    """Build the ``Content-Security-Policy: frame-src`` backstop header.

    Reads ``ZEMBED_MODE`` (the zEmbed event lane) and ``ZEMBED_SDK`` (the opt-in
    SDK-widget lane — PayPal/Stripe frame their own origin from a JS SDK) from the
    environment, same as CORS above. The zEmbed policy SSOT unions both into one
    ``frame-src`` value, so the browser enforces the exact allow-list the server
    emits — no drift. ``ZEMBED_SDK`` may be a JSON list (zEnv nested) or a CSV;
    format parsing stays in the config layer (``loads_env_value``). Falls back to
    the safe default if a policy/config module is somehow unavailable.
    """
    import os
    try:
        from zOS.L2_Handling.e_zDisplay.zDisplay_modules.embed.embed_policy import (
            embed_frame_src, ZEMBED_MODE_KEY, ZEMBED_SDK_KEY,
        )
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.environment.config_zenv import (
            loads_env_value,
        )
        sdk = loads_env_value(os.getenv(ZEMBED_SDK_KEY))
        value = embed_frame_src(os.getenv(ZEMBED_MODE_KEY), sdk_providers=sdk)
    except Exception:
        value = "'self' https://open.spotify.com https://player.vimeo.com https://www.youtube.com"
    return ("Content-Security-Policy", f"frame-src {value}")


def build_response_headers(cors_origin: str = "") -> list:
    """Return the (name, value) header pairs to add to every response.

    Args:
        cors_origin: trusted origin to allow, or "" / None for same-origin only.

    Returns:
        list[tuple[str, str]] of security headers (+ CORS headers when enabled).
    """
    headers = list(SECURITY_RESPONSE_HEADERS)
    headers.append(_embed_csp_header())
    origin = (cors_origin or "").strip()
    if origin:
        headers.append(("Access-Control-Allow-Origin", origin))
        headers.append(("Access-Control-Allow-Methods", CORS_ALLOW_METHODS))
        headers.append(("Access-Control-Allow-Headers", CORS_ALLOW_HEADERS))
        # A specific (non-wildcard) origin is content-negotiated → advertise Vary.
        if origin != "*":
            headers.append(("Vary", "Origin"))
    return headers


__all__ = [
    "SECURITY_RESPONSE_HEADERS",
    "CORS_ALLOW_METHODS",
    "CORS_ALLOW_HEADERS",
    "sanitize_header_value",
    "build_response_headers",
    "_embed_csp_header",
]

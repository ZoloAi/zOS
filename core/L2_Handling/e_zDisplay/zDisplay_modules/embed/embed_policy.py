# zOS/core/L2_Handling/e_zDisplay/zDisplay_modules/embed/embed_policy.py

"""
zEmbed Policy — provider normalization + trust allow-list (SSOT)
================================================================

The SERVER-side trust boundary for the ``zEmbed`` event. Bifrost embeds render
foreign documents (an ``<iframe>``) in the visitor's browser, so the decision of
*what may embed* and *with which capabilities* must be made here — never in the
public bifrost-client, which is inspectable and replaceable and therefore can
never be a security boundary.

Two jobs, one module (so they can never drift):

1. **Normalization** — turn a human URL into its embeddable form
   (``youtube.com/watch?v=ID`` → ``youtube.com/embed/ID``). This is what lets a
   single ``zEmbed`` event cover every provider without per-provider grammar.

2. **Trust** — an allow-list of known-good providers, each carrying the exact
   ``sandbox`` / ``allow`` token set its embed needs. Unknown URLs are denied
   under the safe default (fail-closed); the caller degrades them to a plain
   link instead of an iframe.

Mode tiers (operator control via zEnv ``ZEMBED_MODE`` is wired in Phase 2):
- ``off``   — no embedding at all (deny everything).
- ``safe``  — allow-listed providers only (the fail-closed default).
- ``trust`` — any URL embeds, under a conservative generic sandbox (author's
  call, e.g. a closed internal app).

``resolve_embed`` returns a flat decision dict the event hands straight to the
renderer. The proprietary attestation layer lives in ``embed_trust`` (zGuard).
"""

import re
from urllib.parse import urlparse, parse_qs

# ── Mode vocabulary (mirrors zTerminal's ZTERMINAL_MODE tiers) ───────────────
ZEMBED_MODE_KEY = "ZEMBED_MODE"
EMBED_MODE_OFF = "off"
EMBED_MODE_SAFE = "safe"
EMBED_MODE_TRUST = "trust"
EMBED_MODE_DEFAULT = EMBED_MODE_SAFE
_VALID_MODES = (EMBED_MODE_OFF, EMBED_MODE_SAFE, EMBED_MODE_TRUST)

# ── SDK-widget lane opt-in (separate from the zEmbed event lane above) ────────
# Providers like PayPal/Stripe REFUSE to be iframed, so they can never be a
# zEmbed. Instead they ship a JS SDK (loaded via zScripts) that draws its OWN
# <iframe> into a page slot. That SDK frame origin is not a zEmbed provider, so
# ZEMBED_MODE never covers it — an operator opts specific providers in via zEnv
# ``ZEMBED_SDK`` (list / CSV of names from SDK_WIDGET_PROVIDERS below). Default
# unset → no SDK origins in the CSP (fail-closed; existing apps unchanged). This
# only widens the browser-enforced ``frame-src`` backstop; it does NOT touch the
# zEmbed event decision (resolve_embed) or its zGuard attestation seam.
ZEMBED_SDK_KEY = "ZEMBED_SDK"


def normalize_mode(value) -> str:
    """Normalize a raw zEnv value into a valid tier.

    Fail-closed: anything unset / empty / unknown collapses to the safe default
    (allow-listed providers only). Only an explicit ``off`` or ``trust`` moves
    off that default — an operator must opt in to either widening or disabling.
    """
    mode = str(value).strip().lower() if value else ""
    return mode if mode in _VALID_MODES else EMBED_MODE_DEFAULT

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_ASPECT = "16:9"
# Conservative envelope for generic (trust-mode) embeds: scripts may run, the
# frame keeps its origin (needed by most providers), but it cannot navigate the
# top window or auto-trigger downloads.
GENERIC_SANDBOX = "allow-scripts allow-same-origin allow-popups allow-forms"
GENERIC_ALLOW = ""


def _youtube(url: str):
    """youtube.com/watch?v=ID | youtu.be/ID | /embed/ID | /shorts/ID → embed."""
    p = urlparse(url)
    host = p.netloc.lower()
    vid = None
    if "youtu.be" in host:
        vid = p.path.lstrip("/").split("/")[0]
    else:
        if p.path.startswith(("/embed/", "/shorts/")):
            vid = p.path.split("/")[2] if len(p.path.split("/")) > 2 else None
        else:
            vid = (parse_qs(p.query).get("v") or [None])[0]
    if not vid:
        return None
    return f"https://www.youtube.com/embed/{vid}"


def _vimeo(url: str):
    """vimeo.com/ID | player.vimeo.com/video/ID → player embed."""
    p = urlparse(url)
    m = re.search(r"/(?:video/)?(\d+)", p.path)
    if not m:
        return None
    return f"https://player.vimeo.com/video/{m.group(1)}"


def _spotify(url: str):
    """open.spotify.com/<type>/<id> → open.spotify.com/embed/<type>/<id>."""
    p = urlparse(url)
    if p.path.startswith("/embed/"):
        return f"https://open.spotify.com{p.path}"
    m = re.match(r"^/(track|album|playlist|artist|episode|show)/([A-Za-z0-9]+)", p.path)
    if not m:
        return None
    return f"https://open.spotify.com/embed/{m.group(1)}/{m.group(2)}"


def _gmaps(url: str):
    """Google Maps → its iframe-embed form.

    Accepts the share/place link or the classic query link and produces the
    embeddable URL. ``/maps/embed`` and ``output=embed`` links pass through; a
    ``q=`` query or ``/maps/place/<name>`` is rewritten to the no-key embed form
    (``maps.google.com/maps?q=…&output=embed``). Non-maps google.com URLs return
    None → denied (the matcher is host-wide, so normalize is the real gate).
    """
    from urllib.parse import quote
    p = urlparse(url)
    if "/maps/embed" in p.path:
        return url
    qs = parse_qs(p.query)
    if qs.get("output") == ["embed"]:
        return url
    # Only a maps URL qualifies — never hijack /search or other google.com paths.
    if "/maps" not in p.path:
        return None
    q = (qs.get("q") or [None])[0]
    if not q:
        m = re.search(r"/maps/place/([^/@]+)", p.path)
        q = m.group(1) if m else None
    if not q:
        return None
    return f"https://maps.google.com/maps?q={quote(q)}&output=embed"


# ── Provider allow-list (SSOT) ───────────────────────────────────────────────
# Each entry: host matcher + normalizer + the exact sandbox/allow envelope that
# provider's embed requires. Add a provider here, not a new event.
EMBED_PROVIDERS = {
    "youtube": {
        "match": re.compile(r"(?:^|\.)(?:youtube\.com|youtu\.be)$", re.I),
        "normalize": _youtube,
        "frame_origin": "https://www.youtube.com",
        "sandbox": "allow-scripts allow-same-origin allow-presentation allow-popups",
        "allow": "accelerometer; autoplay; clipboard-write; encrypted-media; "
                 "gyroscope; picture-in-picture; web-share; fullscreen",
    },
    "vimeo": {
        "match": re.compile(r"(?:^|\.)vimeo\.com$", re.I),
        "normalize": _vimeo,
        "frame_origin": "https://player.vimeo.com",
        "sandbox": "allow-scripts allow-same-origin allow-popups",
        "allow": "autoplay; fullscreen; picture-in-picture",
    },
    "spotify": {
        "match": re.compile(r"(?:^|\.)spotify\.com$", re.I),
        "normalize": _spotify,
        "frame_origin": "https://open.spotify.com",
        "sandbox": "allow-scripts allow-same-origin allow-popups",
        "allow": "autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture",
    },
    "maps": {
        # Host-wide match; _gmaps is the real gate (non-maps google URLs → None).
        # The classic embed redirects maps.google.com → www.google.com, so both
        # origins are allow-listed for the CSP frame-src backstop.
        "match": re.compile(r"(?:^|\.)google\.com$", re.I),
        "normalize": _gmaps,
        "frame_origin": ["https://www.google.com", "https://maps.google.com"],
        "sandbox": "allow-scripts allow-same-origin allow-popups",
        "allow": "fullscreen",
    },
}


# ── SDK-widget provider allow-list (SSOT for the ZEMBED_SDK lane) ─────────────
# Known third parties whose JS SDK renders its OWN <iframe> from a fixed origin
# and thus needs a CSP ``frame-src`` entry (their <script> already loads freely —
# the zServer CSP is frame-src only, no script-src directive). Generic zOS data:
# an operator enables the ones their app uses via zEnv ``ZEMBED_SDK``. Add a
# provider here (with its documented frame origins), never a per-app hardcode.
SDK_WIDGET_PROVIDERS = {
    "paypal": {
        # Smart Payment Buttons / Checkout open an iframe on www.paypal.com and,
        # in sandbox, www.sandbox.paypal.com — the subdomain wildcard covers both.
        "frame_src": ["https://*.paypal.com"],
    },
    "stripe": {
        # Stripe.js Elements/Checkout mount from js.stripe.com; the 3-D Secure /
        # redirect step frames hooks.stripe.com (Stripe's documented CSP set).
        "frame_src": ["https://js.stripe.com", "https://hooks.stripe.com"],
    },
}


def sdk_widget_frame_origins(providers) -> set:
    """Frame origins for the operator-enabled SDK-widget providers.

    ``providers`` is the ``ZEMBED_SDK`` value: a list (parsed JSON from zEnv), a
    comma/space string, or a single name. Fail-closed — only names present in
    ``SDK_WIDGET_PROVIDERS`` contribute origins; anything unknown is dropped, so
    the CSP never widens to a provider we don't ship a vetted origin set for.
    Format parsing of a JSON-encoded zEnv value stays in the config layer
    (``loads_env_value``); here we only normalize names, so this module never
    imports json (file-agnosticism).
    """
    if not providers:
        return set()
    if isinstance(providers, str):
        names = re.split(r"[,\s]+", providers.strip())
    elif isinstance(providers, (list, tuple, set)):
        names = list(providers)
    else:
        return set()
    origins = set()
    for name in names:
        spec = SDK_WIDGET_PROVIDERS.get(str(name).strip().lower())
        if spec:
            origins.update(spec.get("frame_src", ()))
    return origins


def embed_frame_src(mode=EMBED_MODE_DEFAULT, sdk_providers=None) -> str:
    """Build the CSP ``frame-src`` directive value for the active tier.

    The browser-enforced mirror of ``resolve_embed``: same allow-list, expressed
    as origins the page may frame. ``off`` blocks all framing; ``safe`` permits
    only the allow-listed provider origins (+ ``'self'``); ``trust`` widens to any
    https iframe (the author's deliberate opt-in).

    ``sdk_providers`` (the ``ZEMBED_SDK`` opt-in) is the SEPARATE SDK-widget lane:
    those providers ship a JS SDK that frames its own origin, so their frame
    origins are unioned in regardless of ``ZEMBED_MODE`` — that mode governs the
    zEmbed *event* lane only. ``trust`` already allows any https (SDK covered);
    ``off`` with SDK providers enabled degrades from ``'none'`` to just the SDK
    origins (the zEmbed lane stays closed).
    """
    mode = normalize_mode(mode)
    sdk_origins = sdk_widget_frame_origins(sdk_providers)
    if mode == EMBED_MODE_TRUST:
        return "'self' https:"
    origin_set = set(sdk_origins)
    if mode != EMBED_MODE_OFF:
        for spec in EMBED_PROVIDERS.values():
            fo = spec["frame_origin"]
            if isinstance(fo, (list, tuple)):
                origin_set.update(fo)
            else:
                origin_set.add(fo)
    if not origin_set:
        return "'none'"
    origins = " ".join(sorted(origin_set))
    return f"'self' {origins}".strip()


def _match_provider(url: str):
    """Return (name, spec) for the first provider whose host matches, else None."""
    host = (urlparse(url).netloc or "").lower()
    if not host:
        return None
    for name, spec in EMBED_PROVIDERS.items():
        if spec["match"].search(host):
            return name, spec
    return None


def _deny(reason: str) -> dict:
    return {"allowed": False, "provider": None, "src": None,
            "sandbox": None, "allow": None, "aspect": DEFAULT_ASPECT, "reason": reason}


def resolve_embed(url: str, mode: str = EMBED_MODE_DEFAULT) -> dict:
    """Resolve a raw embed URL into a vetted render decision.

    Args:
        url: The author-supplied embed URL.
        mode: ``off`` | ``safe`` | ``trust`` (default ``safe``).

    Returns:
        dict with keys:
          allowed (bool), provider (str|None), src (normalized URL|None),
          sandbox (str|None), allow (str|None), aspect (str), reason (str)

    Fail-closed: an unknown provider under ``safe`` is denied; the caller
    degrades a denied embed to a plain link rather than rendering an iframe.
    """
    if not url or not isinstance(url, str):
        return _deny("empty or non-string url")

    url = url.strip()
    if mode == EMBED_MODE_OFF:
        return _deny("embedding disabled (ZEMBED_MODE: off)")

    scheme = (urlparse(url).scheme or "").lower()
    if scheme not in ("http", "https"):
        return _deny(f"unsupported scheme: {scheme or 'none'}")

    matched = _match_provider(url)
    if matched:
        name, spec = matched
        normalized = spec["normalize"](url)
        if not normalized:
            return _deny(f"could not normalize {name} url")
        return {
            "allowed": True,
            "provider": name,
            "src": normalized,
            "sandbox": spec["sandbox"],
            "allow": spec["allow"],
            "aspect": DEFAULT_ASPECT,
            "reason": "allow-listed provider",
        }

    # Unknown provider.
    if mode == EMBED_MODE_TRUST:
        return {
            "allowed": True,
            "provider": "generic",
            "src": url,
            "sandbox": GENERIC_SANDBOX,
            "allow": GENERIC_ALLOW,
            "aspect": DEFAULT_ASPECT,
            "reason": "generic embed (ZEMBED_MODE: trust)",
        }
    return _deny("provider not in allow-list (ZEMBED_MODE: safe)")


__all__ = [
    "resolve_embed",
    "normalize_mode",
    "embed_frame_src",
    "sdk_widget_frame_origins",
    "EMBED_PROVIDERS",
    "SDK_WIDGET_PROVIDERS",
    "ZEMBED_MODE_KEY",
    "ZEMBED_SDK_KEY",
    "EMBED_MODE_OFF",
    "EMBED_MODE_SAFE",
    "EMBED_MODE_TRUST",
    "EMBED_MODE_DEFAULT",
    "DEFAULT_ASPECT",
]

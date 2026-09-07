# zOS/core/L2_Handling/f_zAuth/zAuth_modules/actions/action_oauth.py
"""
zOAuth — provider sign-in (Google / Facebook) for the credential lane.

See PROPOSAL.zOAuth.md (repo root). The short version: this module is the
ENGINE half of the two built-in `/zauth/<provider>/<start|callback>` doors
(r_zServer routing/oauth_endpoints.py is the HTTP half). It deliberately
invents NO new mechanics:

- identity stamping reuses ``action_login._apply_zvisitor`` — the one SSOT
  that writes ``session["zVisitor"]``, refreshes RBAC caches, and
  write-throughs the identity under the caller's durable ``_zsid``;
- the ledger is the app's own ``ZAUTH_USER_MODEL`` table, discovered exactly
  like zLogin discovers it;
- transport durability is the existing per-request session + zsid cookie —
  nothing here touches cookies.

What IS new: the provider handshake (authorize URL, code→token exchange,
userinfo fetch) and the find-or-create linking rule on
``(oauth_provider, oauth_subject)``.

Security posture (proposal §security): state is unguessable/single-use/
TTL'd/zsid-bound; PKCE S256 where the provider supports it; provider tokens
are used once and dropped; email is display data, never a linking key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from urllib import parse as _uparse
from urllib import request as _ureq

import bcrypt

from .action_login import (
    _apply_zvisitor,
    _default_auth_model,
    _extract_table_name,
)

_LOG = "[zOAuth]"

# ── provider registry ────────────────────────────────────────────────────────
# Endpoint URLs carry env overrides (ZOAUTH_<PROVIDER>_AUTH_URL / _TOKEN_URL /
# _USERINFO_URL): that is the pytest seam (point them at a fake) and the
# escape hatch for future providers — the handshake below is plain OAuth2
# authorization-code, nothing Google-shaped.
_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "pkce": True,
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/v19.0/me?fields=id,name,email",
        "scope": "public_profile email",
        "pkce": False,
    },
}

# The two ledger columns the linking rule REQUIRES (proposal §link).
_LEDGER_PROVIDER_COL = "oauth_provider"
_LEDGER_SUBJECT_COL = "oauth_subject"

# ── state registry (CSRF) ────────────────────────────────────────────────────
# In-process on purpose: zServer is a single process, and the start→callback
# round-trip lands on it within minutes. Keyed by the unguessable state token;
# single-use (popped on first sight); pruned on every touch.
_STATE_TTL_SECONDS = 600
_states: Dict[str, Dict[str, Any]] = {}


def _prune_states(now: Optional[float] = None) -> None:
    now = now or time.time()
    for key in [k for k, v in _states.items()
                if now - v.get("ts", 0) > _STATE_TTL_SECONDS]:
        _states.pop(key, None)


# ── config resolution ────────────────────────────────────────────────────────

def provider_config(name: str) -> Optional[Dict[str, Any]]:
    """Resolve a provider's endpoints (env overrides win) — None if unknown."""
    base = _PROVIDERS.get(name)
    if not base:
        return None
    upper = name.upper()
    cfg = dict(base)
    for key, env_suffix in (
        ("auth_url", "AUTH_URL"),
        ("token_url", "TOKEN_URL"),
        ("userinfo_url", "USERINFO_URL"),
    ):
        override = os.getenv(f"ZOAUTH_{upper}_{env_suffix}")
        if override:
            cfg[key] = override
    return cfg


def client_credentials(name: str) -> Tuple[str, str]:
    """(client_id, client_secret) from zEnv — empty strings when absent."""
    upper = name.upper()
    return (
        os.getenv(f"ZOAUTH_{upper}_CLIENT_ID", ""),
        os.getenv(f"ZOAUTH_{upper}_SECRET", ""),
    )


def is_configured(name: str) -> bool:
    """A provider is live iff it exists AND both credential halves are set."""
    if name not in _PROVIDERS:
        return False
    cid, secret = client_credentials(name)
    return bool(cid and secret)


# ── the two hops ─────────────────────────────────────────────────────────────

def begin(zos: Any, provider: str, redirect_uri: str,
          next_path: str = "/") -> Optional[str]:
    """START hop: mint state (+PKCE), stash, return the authorize URL.

    None = provider unknown/unconfigured (the door answers with a coarse
    error redirect; the reason is logged here).
    """
    logger = getattr(zos, "logger", None)
    cfg = provider_config(provider)
    if cfg is None or not is_configured(provider):
        if logger:
            logger.warning(
                f"{_LOG} start refused: provider '{provider}' "
                f"{'unknown' if cfg is None else 'not configured (missing client id/secret)'}"
            )
        return None

    _prune_states()
    state = secrets.token_urlsafe(24)
    entry: Dict[str, Any] = {
        "provider": provider,
        "next": _sanitize_next(next_path),
        "zsid": _current_zsid(zos),
        "ts": time.time(),
    }

    cid, _secret = client_credentials(provider)
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    if cfg.get("pkce"):
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        entry["verifier"] = verifier
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    _states[state] = entry
    if logger:
        logger.info(f"{_LOG} start → {provider} (state minted, next={entry['next']})")
    return f"{cfg['auth_url']}?{_uparse.urlencode(params)}"


def complete(zos: Any, provider: str, params: Dict[str, str],
             redirect_uri: str) -> Tuple[bool, str]:
    """CALLBACK hop: state → exchange → userinfo → link → stamp.

    Returns ``(True, next_path)`` on success, ``(False, error_code)`` on any
    refusal — the code is coarse ON PURPOSE (it lands in a URL); the real
    reason is logged server-side.
    """
    logger = getattr(zos, "logger", None)

    entry = _take_state(params.get("state"), provider, zos)
    if entry is None:
        if logger:
            logger.warning(f"{_LOG} callback refused: bad/expired/foreign state "
                           f"(provider={provider})")
        return False, "state"

    if params.get("error") or not params.get("code"):
        # The provider bounced us (user cancelled, consent denied, …).
        if logger:
            logger.info(f"{_LOG} provider declined: {params.get('error', 'no code')}")
        return False, "declined"

    cfg = provider_config(provider)
    if cfg is None or not is_configured(provider):
        return False, "provider_unavailable"

    token = _exchange_code(provider, cfg, params["code"], redirect_uri,
                           entry.get("verifier"), logger)
    if not token:
        return False, "exchange"

    info = _fetch_identity(provider, cfg, token, logger)
    if not info:
        return False, "identity"

    user, refusal = _find_or_create_user(zos, provider, info, logger)
    if user is None:
        return False, refusal or "ledger"

    username, role = _apply_zvisitor(user, "username", zos, logger)
    if logger:
        logger.info(f"{_LOG} signed in via {provider}: {username} (role={role})")
    return True, entry.get("next") or "/"


# ── helpers: state ───────────────────────────────────────────────────────────

def _current_zsid(zos: Any) -> str:
    try:
        session = getattr(zos, "session", None)
        return session.get("_zsid", "") if isinstance(session, dict) else ""
    except Exception:  # pylint: disable=broad-except
        return ""


def _take_state(state: Optional[str], provider: str, zos: Any) -> Optional[Dict[str, Any]]:
    """Pop-and-verify a state entry: single-use, fresh, same provider, same zsid."""
    _prune_states()
    if not state:
        return None
    entry = _states.pop(state, None)
    if entry is None or entry.get("provider") != provider:
        return None
    # zsid binding: the browser that finishes must be the one that started.
    # Empty-on-both is allowed (cookieless caller stays consistent).
    if entry.get("zsid", "") != _current_zsid(zos):
        return None
    return entry


def _sanitize_next(next_path: Any) -> str:
    """Same-origin path only: a single leading '/', no scheme/host smuggling."""
    if not isinstance(next_path, str) or not next_path.startswith("/"):
        return "/"
    if next_path.startswith("//") or ":" in next_path.split("?", 1)[0]:
        return "/"
    return next_path


# ── helpers: provider round-trips (module attrs = the pytest seam) ───────────

def _http_json(url: str, data: Optional[Dict[str, str]] = None,
               headers: Optional[Dict[str, str]] = None,
               timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """POST (form) when ``data`` is given, else GET; parse JSON; None on any error.

    stdlib urllib on purpose — no new dependency for two small TLS calls.
    """
    try:
        body = _uparse.urlencode(data).encode("ascii") if data is not None else None
        req = _ureq.Request(url, data=body, headers=headers or {})
        with _ureq.urlopen(req, timeout=timeout) as resp:  # nosec: fixed provider URLs
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # pylint: disable=broad-except
        return None


def _exchange_code(provider: str, cfg: Dict[str, Any], code: str,
                   redirect_uri: str, verifier: Optional[str],
                   logger: Any) -> Optional[str]:
    """code → access_token (server-side, secret never leaves this hop)."""
    cid, secret = client_credentials(provider)
    form = {
        "client_id": cid,
        "client_secret": secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if verifier:
        form["code_verifier"] = verifier
    payload = _http_json(cfg["token_url"], data=form)
    token = (payload or {}).get("access_token")
    if not token and logger:
        logger.warning(f"{_LOG} token exchange failed for {provider} "
                       f"(provider answered {'nothing' if payload is None else list(payload.keys())})")
    return token


def _fetch_identity(provider: str, cfg: Dict[str, Any], token: str,
                    logger: Any) -> Optional[Dict[str, Any]]:
    """userinfo → normalized {sub, name, email} — the identity truth source.

    The token is used for THIS call and dropped (never stored, never in the
    session). Google identities with an unverified email are refused: the
    ledger's username derives from that email.
    """
    url = cfg["userinfo_url"]
    headers = {"Authorization": f"Bearer {token}"}
    if provider == "facebook":
        # Graph API also accepts the token as a query param; the header works
        # too — keep the header form (never logs the token via URL).
        pass
    payload = _http_json(url, headers=headers)
    if not payload:
        if logger:
            logger.warning(f"{_LOG} userinfo fetch failed for {provider}")
        return None

    sub = payload.get("sub") or payload.get("id")
    if not sub:
        if logger:
            logger.warning(f"{_LOG} userinfo for {provider} carries no subject id")
        return None
    if provider == "google" and payload.get("email") \
            and payload.get("email_verified") is False:
        if logger:
            logger.warning(f"{_LOG} refused google identity with unverified email")
        return None
    return {
        "sub": str(sub),
        "name": payload.get("name") or "",
        "email": payload.get("email") or "",
    }


# ── helpers: ledger linking ──────────────────────────────────────────────────

def _find_or_create_user(zos: Any, provider: str, info: Dict[str, Any],
                         logger: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Link the provider identity to the app's OWN ledger.

    Match on ``(oauth_provider, oauth_subject)`` — the only linking key.
    First sign-in creates the row: username from the email local-part
    (uniquified), role left to the SCHEMA DEFAULT (least privilege), password
    LOCKED (random bcrypt) when the schema requires one. Returns
    ``(row, None)`` or ``(None, refusal_code)``.
    """
    model = _default_auth_model()
    table = _extract_table_name(model)
    try:
        schema = zos.loader.handle(model)
        zos.data.load_schema(schema)
    except Exception as exc:  # pylint: disable=broad-except
        if logger:
            logger.error(f"{_LOG} ledger schema load failed ({model}): {exc}")
        return None, "ledger"

    columns = _table_columns(schema, table)
    if not {_LEDGER_PROVIDER_COL, _LEDGER_SUBJECT_COL} <= columns:
        if logger:
            logger.error(
                f"{_LOG} ledger '{table}' lacks {_LEDGER_PROVIDER_COL}/"
                f"{_LEDGER_SUBJECT_COL} — declare both columns to enable zOAuth "
                f"(see PROPOSAL.zOAuth.md §link)")
        return None, "ledger"

    where = {_LEDGER_PROVIDER_COL: provider, _LEDGER_SUBJECT_COL: info["sub"]}
    try:
        rows = zos.data.select(table, where=where)
        if rows and rows != "error" and len(rows) > 0:
            return rows[0], None
    except Exception as exc:  # pylint: disable=broad-except
        if logger:
            logger.error(f"{_LOG} ledger lookup failed: {exc}")
        return None, "ledger"

    row: Dict[str, Any] = {
        "username": _unique_username(zos, table, info, provider, logger),
        _LEDGER_PROVIDER_COL: provider,
        _LEDGER_SUBJECT_COL: info["sub"],
    }
    if "email" in columns and info.get("email"):
        row["email"] = info["email"]
    if "person" in columns and info.get("name"):
        row["person"] = info["name"]
    if "password" in columns:
        # LOCKED lane: an OAuth-born user has no local password. A random
        # 32-byte secret is hashed and immediately forgotten — nothing can
        # ever present it. (Pre-hashed values pass the zHash write-prep
        # untouched — the documented seeding lane.)
        row["password"] = bcrypt.hashpw(
            secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    try:
        zos.data.insert(table, row)
        rows = zos.data.select(table, where=where)
        if rows and rows != "error" and len(rows) > 0:
            if logger:
                logger.info(f"{_LOG} first {provider} sign-in — created ledger row "
                            f"'{row['username']}' (role = schema default)")
            return rows[0], None
    except Exception as exc:  # pylint: disable=broad-except
        if logger:
            logger.error(f"{_LOG} ledger create failed: {exc}")
    return None, "ledger"


def _table_columns(schema: Any, table: str) -> set:
    """Column names of ``table`` in a loaded schema file dict (empty on doubt)."""
    if isinstance(schema, dict):
        spec = schema.get(table)
        if isinstance(spec, dict):
            return set(spec.keys())
    return set()


def _unique_username(zos: Any, table: str, info: Dict[str, Any],
                     provider: str, logger: Any) -> str:
    """Speakable username: email local-part → name → provider-sub; uniquified."""
    email = info.get("email") or ""
    base = (email.split("@", 1)[0] if "@" in email else "") \
        or (info.get("name") or "").strip().lower().replace(" ", ".") \
        or f"{provider}.{info['sub'][:8]}"
    candidate = base
    for suffix in range(0, 50):
        if suffix:
            candidate = f"{base}.{suffix}"
        try:
            rows = zos.data.select(table, where={"username": candidate})
            if not rows or rows == "error" or len(rows) == 0:
                return candidate
        except Exception:  # pylint: disable=broad-except
            return candidate
    # Pathological collision space — fall back to an unguessable tail.
    return f"{base}.{secrets.token_hex(4)}"

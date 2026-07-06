# zSys/cli/login_command.py
"""
`z login` — zOwnership sign-in (the zOS/zMachine instance OWNER).

zOwnership is a FIRST-CLASS pattern, SEPARATE from the runtime ("flask-like")
session: this git-/gh-style command verifies the instance owner against the
external registrar authority and records it to the zMachine (zConfig.identity.zolo)
via the zownership_store. It NEVER writes a runtime session — any zOwnership
symbol leaking into session code is a red flag by design. The CLI verb stays
`login`; everything it does is zOwnership.

Modes:
    z login                       # prompt for email/username + password
    z login info@zolo.media       # prompt password only
    z login --token <PAT>         # non-interactive (CI / hosted instances)
    z login --status              # show the current owner, no changes
    z login --logout              # clear the persisted zOwnership
"""

import getpass
import json
import time
import urllib.request
import urllib.error


# ── Registrar source (TEMP) ────────────────────────────────────────────────
# `z login` verifies the zOS instance OWNER (zOwnership) against an external
# registrar authority over HTTP — never a local data model and never a session.
# This is the single, hardcoded verify endpoint that authority exposes; in -> the
# credential, out -> a verdict + the owner identity. Until the real endpoint is
# settled inside zCloud, this points at the standalone registrar server in
# Tests/mock_registrar_server.py (run it before `z login`). Do not couple this to
# zSchemas, ledgers, or the runtime ("flask-like") session.
REGISTRAR_VERIFY_URL = "http://127.0.0.1:7332/api/zlogin"
# zOwnership-via-api-key counterpart: the instance replays a stored PAT and the
# authority vouches for the same owner identity. Same source, different door.
REGISTRAR_TOKEN_URL = "http://127.0.0.1:7332/api/ztoken"


def _save_zownership(zos, owner: dict, api_key: str = None):
    """Persist the registrar-vouched owner to the zOwnership file (git-like).

    ``owner`` is the identity the registrar returned ({id, username, email,
    api_key, ...}). ``api_key`` is the REPLAYABLE credential to store: the
    password flow passes the registrar's minted key; the token flow passes the
    plaintext PAT the caller replayed (so the stored value stays replayable).
    The registrar is roleless — no role is invented here. Returns (saved, name).
    """
    name = owner.get("username") or owner.get("email") or "your account"
    try:
        saved = zos.auth.save_zownership({
            "username": owner.get("username") or owner.get("email"),
            "user_id": owner.get("id"),
            "role": owner.get("role"),
            "api_key": api_key if api_key is not None else owner.get("api_key"),
        })
    except Exception as err:  # pylint: disable=broad-except
        zos.logger.debug(f"[z.login] zOwnership persist failed: {err}")
        saved = False
    return saved, name


def _show_zownership(zos) -> int:
    """Print the instance owner — read from zMachine, never the runtime session.

    zOwnership is decoupled from the runtime session: it lives only in the
    zMachine file (zConfig.identity.zolo), so status reads it there.
    """
    ident = zos.auth.load_zownership() or {}
    if ident.get("username"):
        zos.display.success(f"[OK] Signed in as {ident.get('username')}")
    else:
        zos.display.text("Not signed in. Run: z login", indent=0, pause=False)
    return 0


def _clear_zownership(zos) -> int:
    """Clear the persisted zOwnership file (sign the owner out)."""
    removed = zos.auth.clear_zownership()
    if removed:
        zos.display.success("[OK] Signed out")
    else:
        zos.display.text("Not signed in.", indent=0, pause=False)
    return 0


def _zownership_signin_token(zos, token: str) -> int:
    """Non-interactive zOwnership sign-in via a Personal Access Token.

    Login-via-api-key: the token is verified by the registrar authority (same
    source as the password flow, different door — REGISTRAR_TOKEN_URL), never a
    local ledger. On a positive verdict the vouched owner is persisted with the
    replayed plaintext token as its api_key (so the stored credential is itself
    replayable).
    """
    status, body = _api_post(REGISTRAR_TOKEN_URL, "", {"api_key": token})

    if status == 0:
        zos.display.error(
            f"[FAIL] Could not reach registrar at {REGISTRAR_TOKEN_URL} "
            f"({body.get('error', 'connection failed')})"
        )
        return 1
    if status != 200 or not body.get("ok"):
        zos.display.error("[FAIL] Invalid or unknown API key")
        return 1

    owner = body.get("user", {}) if isinstance(body, dict) else {}
    saved, name = _save_zownership(zos, owner, api_key=token)
    if saved:
        zos.display.success(f"[OK] Signed in as {name}")
        return 0
    zos.display.text("    (verified; not persisted)", indent=0, pause=False)
    return 1


def _default_server() -> str:
    """Configured auth server for the device flow (falls back to the zAuth default)."""
    try:
        from zOS.L2_Handling.f_zAuth.zAuth_modules.auth_constants import (  # pylint: disable=import-outside-toplevel
            DEFAULT_SERVER_URL,
        )
        return DEFAULT_SERVER_URL
    except Exception:  # pylint: disable=broad-except
        return "http://localhost:5000"


def _api_post(base: str, path: str, payload: dict, timeout: int = 10):
    """Minimal JSON POST to the auth server. Returns (status_code, dict)."""
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except Exception:  # pylint: disable=broad-except
            return err.code, {}
    except Exception as err:  # pylint: disable=broad-except
        return 0, {"error": str(err)}


def _save_zownership_device(zos, result: dict) -> int:
    """Store the server-vouched PAT + identity (zOwnership) from the device flow.

    The server already authenticated the human and minted the token, so the CLI does
    NOT re-verify against a local ledger (it may have none — that's the point of the
    remote/browser flow). It just persists the plaintext token + identity, exactly like
    `--token` does after a successful verify."""
    token = result.get("token")
    ok = zos.auth.save_zownership({
        "username": result.get("username"),
        "user_id": result.get("user_id"),
        "role": result.get("role") or "user",
        "api_key": token,
    })
    name = result.get("username") or "your account"
    role = result.get("role") or "user"
    if ok:
        zos.display.success(f"[OK] Signed in as {name} ({role})")
        return 0
    zos.display.text("    (received token; not persisted)", indent=0, pause=False)
    return 1


def _zownership_signin_device(zos, base: str, verbose: bool) -> int:  # pylint: disable=unused-argument
    """Browser device-flow zOwnership sign-in (gh/gcloud style): start → approve → poll.

    The rendezvous lives on the server (zSchema.device_codes); this CLI never binds a
    local port and never handles the password — it opens the sign-in page (zOpen) and
    polls for the minted PAT, then persists it via the same path as `--token`.
    """
    base = (base or _default_server()).rstrip("/")

    status, start = _api_post(base, "/api/zAuth/device/start", {})
    if status != 200 or not start.get("ok"):
        zos.display.error(f"[FAIL] Could not start device login against {base} ({status})")
        return 1

    data = start.get("data", {})
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    interval = int(data.get("interval", 5) or 5)
    expires_in = int(data.get("expires_in", 600) or 600)
    verify = data.get("verification_uri_complete") or data.get("verification_uri") or "/"
    url = verify if verify.startswith("http") else base + verify

    zos.display.text(f"To sign in, open: {url}", indent=0, pause=False)
    zos.display.text(f"Verification code: {user_code}", indent=0, pause=False)
    try:
        zos.open.handle(f"zOpen({url})")
    except Exception as err:  # pylint: disable=broad-except
        zos.logger.debug(f"[zolo.login] zOpen browser launch skipped: {err}")

    zos.display.text("Waiting for approval in the browser…", indent=0, pause=False)
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        status, res = _api_post(base, "/api/zAuth/device/poll", {"device_code": device_code})
        result = res.get("data", {}) if isinstance(res, dict) else {}
        state = result.get("status")
        if status == 200 and state == "approved" and result.get("token"):
            return _save_zownership_device(zos, result)
        if state == "denied":
            zos.display.error("[FAIL] Device login was denied")
            return 1
        if status == 410 or state == "expired":
            zos.display.error("[FAIL] Device code expired — run `zolo login --device` again")
            return 1
        # pending → keep polling

    zos.display.error("[FAIL] Device login timed out")
    return 1


def _zownership_signin_password(zos, identity, verbose) -> int:  # pylint: disable=unused-argument
    """Interactive (or arg-seeded) zOwnership sign-in via the registrar.

    Verify the zOS instance owner: the credential is sent to the external
    registrar authority (REGISTRAR_VERIFY_URL) which vouches for the owner
    identity; the CLI never touches a local ledger and never writes a session.
    On success it persists the vouched zOwnership (same path as `--token` and the
    device flow) so the owner survives this one-shot process.
    """
    try:
        if not identity:
            identity = input("Email or username: ").strip()
        if not identity:
            zos.display.error("[FAIL] Identity is required")
            return 1
        password = getpass.getpass("Password: ")
    except (EOFError, KeyboardInterrupt):
        zos.display.text("", indent=0, pause=False)
        return 1

    if not password:
        zos.display.error("[FAIL] Password is required")
        return 1

    # email vs username — the registrar accepts either key.
    field = "email" if "@" in identity else "username"
    status, body = _api_post(REGISTRAR_VERIFY_URL, "", {field: identity, "password": password})

    if status == 0:
        zos.display.error(
            f"[FAIL] Could not reach registrar at {REGISTRAR_VERIFY_URL} "
            f"({body.get('error', 'connection failed')})"
        )
        return 1
    if status != 200 or not body.get("ok"):
        zos.display.error("[FAIL] Authentication failed: invalid credentials")
        return 1

    # Registrar-vouched owner identity (roleless — registrar is watermark only).
    owner = body.get("user", {}) if isinstance(body, dict) else {}
    saved, name = _save_zownership(zos, owner)
    if saved:
        zos.display.success(f"[OK] Signed in as {name}")
        return 0
    zos.display.text("    (verified; not persisted)", indent=0, pause=False)
    return 1


def handle_login_command(boot_logger, args, verbose: bool = False) -> int:
    """
    Handle the `login` command — boot a default zOS and establish zOwnership.

    The CLI verb stays `login`; the operation is zOwnership (instance owner),
    SEPARATE from the runtime session.

    Args:
        boot_logger: BootstrapLogger instance
        args: Parsed CLI args (identity, token, status, logout)
        verbose: Show bootstrap logs and initialization output
    """
    from zOS import zOS  # pylint: disable=import-outside-toplevel

    zos = zOS(verbose=verbose)
    boot_logger.flush_to_framework(zos.logger, verbose=verbose)

    if getattr(args, "status", False):
        return _show_zownership(zos)
    if getattr(args, "logout", False):
        return _clear_zownership(zos)

    token = getattr(args, "token", None)
    if token:
        return _zownership_signin_token(zos, token)

    if getattr(args, "device", False):
        return _zownership_signin_device(zos, getattr(args, "server", None), verbose)

    return _zownership_signin_password(zos, getattr(args, "identity", None), verbose)

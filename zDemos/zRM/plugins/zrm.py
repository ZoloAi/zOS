"""zrm — profile-avatar upload, same file-move + zData pairing as
zGallery's plugins/gallery.py add_photo (06_inputs.md files + zGallery's
plugin pairing), applied to Users.avatar instead of a new Photos row.

Two surfaces, two source shapes for the SAME `avatar` zConv value:
  zCLI     — `type: file` already validated the picked zPath and handed back
             an EXISTING absolute OS path.
  zBifrost — a real browser upload has no local disk source, only bytes,
             carried as a base64 envelope dict.
"""

from datetime import datetime, timedelta
from pathlib import Path
import base64
import secrets
import shutil

from zos_plugin import zfunc, ZAbort
from zos_plugin.bundle_store import get_bundle_store

_TABLE = "Users"
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "avatars"
_COVERS_DIR = Path(__file__).resolve().parent.parent / "static" / "covers"

_TOKEN_TTL_HOURS = 24
_DT_FMT = "%Y-%m-%d %H:%M:%S"


#> shared by update_avatar (Users.avatar) and add_site (Sites.cover_image) —
#  same two source shapes either way (06_inputs.md files + zGallery's
#  plugins/gallery.py pairing): zCLI's `type: file` hands back an EXISTING
#  absolute OS path; a real browser upload has no local disk source, only
#  bytes, carried as a base64 envelope dict <#
def _save_upload(file_value, dest_dir: Path, static_prefix: str) -> str:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(file_value, dict):
        dest_name = _unique_name(dest_dir, file_value.get("filename") or "upload")
        if "data_b64" in file_value:
            raw_bytes = base64.b64decode(file_value["data_b64"])
        else:
            raw_bytes = file_value.get("data") or b""  # already-decoded (files facade shape)
        (dest_dir / dest_name).write_bytes(raw_bytes)
    else:
        src = Path(file_value)
        dest_name = _unique_name(dest_dir, src.name)
        shutil.copy(src, dest_dir / dest_name)
    return f"@.static.{static_prefix}.{dest_name}"


#> SAME dual-shape contract as _save_upload, minus the "move to a static
#  zPath" step — a bundle isn't a servable static file, it's raw tar.gz
#  bytes handed straight to BundleStore.unpack (22_hosting.md "front
#  door.push") <#
def _read_upload_bytes(file_value) -> bytes:
    if isinstance(file_value, dict):
        if "data_b64" in file_value:
            return base64.b64decode(file_value["data_b64"])
        return file_value.get("data") or b""
    return Path(file_value).read_bytes()


@zfunc
def update_avatar(user_id, avatar, data):
    zpath = _save_upload(avatar, _STATIC_DIR, "avatars")
    data.update(_TABLE, {"avatar": zpath}, where={"id": user_id})
    return "Avatar updated"


#> stub the "sent email" (zShop's own precedent for a would-normally-be-
#  emailed step) — the real payload is the token+expiry pair; Register
#  never touches them directly, keeping name/email/password insert-shaped
#  identical to zBlog's original bare zData insert.
#  gap found the hard way: schema-level `zHash: bcrypt` only fires inside
#  the DECLARATIVE `zData: {action: insert}` block compiler — the
#  zos_plugin `data.insert()` facade used HERE does not re-run it, so a
#  plugin-driven insert on a zHash field must hash explicitly via the
#  SAME `zos.auth.hash_password` crud_insert.py itself calls, or the row
#  silently lands with a plaintext password zLogin can never verify <#
@zfunc
def register_user(name, email, password, data, zos):
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)).strftime(_DT_FMT)
    data.insert(_TABLE, {
        "name":                name,
        "email":               email,
        "password":            zos.auth.hash_password(password),
        "email_verified":      False,
        "verification_token":  token,
        "token_expires_at":    expires_at,
    })
    return "Account created — verify your email from your profile to finish setup."


#> a fresh token OVERWRITES the old one — the old link's zLoom lookup
#  (`where: verification_token = %route.token`) stops matching anything the
#  instant this runs, so an unclicked stale link dies quietly on its own <#
@zfunc
def resend_verification(user_id, data):
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)).strftime(_DT_FMT)
    data.update(_TABLE, {
        "verification_token": token,
        "token_expires_at":   expires_at,
    }, where={"id": user_id})
    return "New verification link ready below."


#> called from the /Verify/%token zLoom page — that route's OWN spool
#  already 404'd on a token matching zero rows, so getting here means the
#  row exists; only remaining question is whether it's still fresh <#
@zfunc
def confirm_email(token, data):
    row = data.first(_TABLE, where={"verification_token": token})
    if not row:
        raise ZAbort("This verification link is no longer valid.", status=404)

    expires_at = datetime.strptime(row["token_expires_at"], _DT_FMT)
    if datetime.utcnow() > expires_at:
        raise ZAbort("This verification link has expired — request a new one from your profile.", status=410)

    data.update(_TABLE, {
        "email_verified":     True,
        "verification_token": "",
    }, where={"id": row["id"]})
    return "Email verified — you can sign in now."


#> forgot-password step 1 — SAME stub-the-email shape as register_user/
#  resend_verification (the "sent email" is stubbed, the token+expiry pair is
#  the real payload). Looked up by email (not %session.zVisitor.id) because
#  the caller is, by definition, signed OUT on the public /ForgotPassword
#  page — reuses the identical plugin from the signed-IN Account panel too
#  (Security.ResetPasswordBtn passes its own already-resolved email) so both
#  entry points share one code path <#
@zfunc
def request_password_reset(email, data):
    row = data.first(_TABLE, where={"email": email})
    if not row:
        # never reveal whether an email is registered — same message either way
        return "If that email is on file, a reset link is on its way."

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.utcnow() + timedelta(hours=_TOKEN_TTL_HOURS)).strftime(_DT_FMT)
    data.update(_TABLE, {
        "reset_token":            token,
        "reset_token_expires_at": expires_at,
    }, where={"id": row["id"]})
    return "If that email is on file, a reset link is on its way."


#> forgot-password step 2 — called from the /ResetPassword/%token page's
#  onSubmit. zHash: bcrypt on the schema only fires inside a declarative
#  `zData: {action: insert}` block (register_user's own docstring gap) — a
#  plugin-driven update on a zHash field needs the SAME explicit
#  zos.auth.hash_password call. Single-use by construction, same as
#  confirm_email: reset_token clears to "" on success so a replayed link's
#  zLoom lookup matches zero rows the second time <#
@zfunc
def reset_password(token, password, data, zos):
    row = data.first(_TABLE, where={"reset_token": token})
    if not row:
        raise ZAbort("This reset link is no longer valid.", status=404)

    expires_at = datetime.strptime(row["reset_token_expires_at"], _DT_FMT)
    if datetime.utcnow() > expires_at:
        raise ZAbort("This reset link has expired — request a new one.", status=410)

    data.update(_TABLE, {
        "password":               zos.auth.hash_password(password),
        "reset_token":            "",
        "reset_token_expires_at": None,
    }, where={"id": row["id"]})
    return "Password updated — you can sign in now."


#> a bare %item-scoped zFunc call, no zModal/zDialog wrapper — a standalone
#  (New Site) AND an %item-scoped (Edit/Delete) zModal's onSubmit both fail
#  to bind ("Form configuration error: No onSubmit action specified") when
#  the firing button lives inside a lazy-loaded zDash panel specifically;
#  this direct-call shape sidesteps the whole zDialog/zModal submit path.
#  owner_id passed in (not read off session inside the plugin) — same
#  %session.zVisitor.id-as-zolo-arg shape resend_verification already uses <#
@zfunc
def delete_site(site_id, owner_id, data):
    data.delete("Sites", where={"id": site_id, "owner_id": owner_id})
    return "Site deleted"


#> New Site gains an OPTIONAL cover upload — plugin-driven insert (same
#  register_user shape) only because a file field can't ride a plain
#  declarative `zData: {action: insert}` block.
#  gap found the hard way, SAME class as register_user's own zHash note:
#  a schema `default:` (status/created_at here) only auto-fires inside the
#  DECLARATIVE `zData: {action: insert}` compiler — a plugin-driven
#  data.insert() leaves an omitted column NULL, which then renders as a
#  raw unresolved `%item.status` token in the feed/MySites list AND sorts
#  wrong (created_at DESC treats NULL oddly) — so both are stamped
#  explicitly here, same as register_user already does for email_verified/
#  verification_token/token_expires_at. cover_image is the ONE field left
#  to the schema default when skipped — that default (a real servable
#  path) renders fine either way, unlike status/created_at above <#
#> Stage 2 of the hosting phase adds hosting_mode/app_bundle — same
#  plugin-driven-insert-skips-schema-defaults gap noted above, so
#  hosting_mode is stamped explicitly too (empty/None -> "internal").
#  app_bundle is a tar.gz (BundleStore's own contract, core/zos_plugin/
#  bundle_store.py — an app/ prefix slice + optional attachments/), NOT a
#  free-text filesystem path: unpack it via the SAME LocalBundleStore the
#  (currently uncalled) `zolo push` pipeline already ships, and store the
#  resulting relative zspark_path — the REAL front_door.push shape
#  (22_hosting.md), not a dev-machine absolute-path shortcut <#
@zfunc
def add_site(title, slug, tagline, owner_id, cover, body, hosting_mode, app_bundle, data, zos):
    #> an empty string round-trips through the CSV backend as a missing
    #  value (read back as None), which then renders as a literal
    #  unresolved %item.Sites.body token instead of blank — same class of
    #  gap as Users.avatar's own schema-default reasoning above. An
    #  app-mode site has no real body page of its own, so a short fixed
    #  placeholder sidesteps the gap entirely rather than chasing it here <#
    body = body or ("Hosted app, served at its own /app front door." if hosting_mode == "app" else "")
    spark_path = ""
    if hosting_mode == "app" and app_bundle:
        bundle = get_bundle_store(zos=zos).unpack(slug, _read_upload_bytes(app_bundle))
        spark_path = bundle.zspark_path
    site_row = {
        "title":        title,
        "slug":         slug,
        "tagline":      tagline,
        "body":         body,
        "owner_id":     owner_id,
        "status":       "draft",
        "hosting_mode": hosting_mode or "internal",
        "spark_path":   spark_path,
        "created_at":   datetime.utcnow().strftime(_DT_FMT),
    }
    if cover:
        site_row["cover_image"] = _save_upload(cover, _COVERS_DIR, "covers")
    data.insert("Sites", site_row)
    return "Site created"


def _unique_name(dest_dir: Path, name: str) -> str:
    """Never clobber an existing static file sharing the same name."""
    if not (dest_dir / name).exists():
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while (dest_dir / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"

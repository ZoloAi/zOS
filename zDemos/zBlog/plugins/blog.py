"""blog — profile-avatar upload, same file-move + zData pairing as
zGallery's plugins/gallery.py add_photo (06_inputs.md files + zGallery's
plugin pairing), applied to Users.avatar instead of a new Photos row.

Two surfaces, two source shapes for the SAME `avatar` zConv value:
  zCLI     — `type: file` already validated the picked zPath and handed back
             an EXISTING absolute OS path.
  zBifrost — a real browser upload has no local disk source, only bytes,
             carried as a base64 envelope dict.
"""

from pathlib import Path
import base64
import shutil

from zos_plugin import zfunc

_TABLE = "Users"
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "avatars"


@zfunc
def update_avatar(user_id, avatar, data):
    if isinstance(avatar, dict):
        dest_name = _unique_name(avatar.get("filename") or "avatar")
        _STATIC_DIR.mkdir(parents=True, exist_ok=True)
        if "data_b64" in avatar:
            raw_bytes = base64.b64decode(avatar["data_b64"])
        else:
            raw_bytes = avatar.get("data") or b""  # already-decoded (files facade shape)
        (_STATIC_DIR / dest_name).write_bytes(raw_bytes)
    else:
        src = Path(avatar)
        dest_name = _unique_name(src.name)
        _STATIC_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, _STATIC_DIR / dest_name)

    data.update(_TABLE, {"avatar": f"@.static.avatars.{dest_name}"}, where={"id": user_id})
    return "Avatar updated"


def _unique_name(name: str) -> str:
    """Never clobber an existing static file sharing the same name."""
    if not (_STATIC_DIR / name).exists():
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while (_STATIC_DIR / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"

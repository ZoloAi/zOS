"""gallery — turn a picked/uploaded photo into a servable static file + row.

Two surfaces, two source shapes for the SAME `photo` zConv value:
  zCLI     — `type: file` already validated the picked zPath and handed back
             an EXISTING absolute OS path (see zAgents/src/06_inputs.md).
  zBifrost — a real browser upload has no local disk source, only bytes. The
             onSubmit call (`zConv.photo` inline in the `&.` invocation string)
             carries the client's base64 envelope through as a plain JSON
             object — see dialog_context.inject_placeholders + plugin_args.
             parse_argument_value for the two parser fixes that let a dict
             argument survive that string round-trip at all.

Either way the row lands with a @.static.photos.<file> zPath — a raw
filesystem path never resolves as media, only a zPath does (the gotcha noted
on zSchema.Photos' `image` field).
"""

from pathlib import Path
import base64
import shutil

from zos_plugin import zfunc

_TABLE = "Photos"
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "photos"


@zfunc
def add_photo(title, caption, photo, data):
    if isinstance(photo, dict):
        dest_name = _unique_name(photo.get("filename") or "upload")
        _STATIC_DIR.mkdir(parents=True, exist_ok=True)
        if "data_b64" in photo:
            raw_bytes = base64.b64decode(photo["data_b64"])
        else:
            raw_bytes = photo.get("data") or b""  # already-decoded (files facade shape)
        (_STATIC_DIR / dest_name).write_bytes(raw_bytes)
    else:
        src = Path(photo)
        dest_name = _unique_name(src.name)
        _STATIC_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, _STATIC_DIR / dest_name)

    data.insert(_TABLE, {
        "title": title,
        "caption": caption or "",
        "image": f"@.static.photos.{dest_name}",
    })
    return f"Added {title}"


@zfunc
def update_photo(photo_id, title, caption, data):
    """Edit details (zModal + zDialog, 03_navigation.md) — a plain field
    update, no file involved, so a straight zData.update is enough."""
    data.update(_TABLE, {"title": title, "caption": caption or ""}, where={"id": photo_id})
    return f"Updated {title}"


@zfunc
def delete_photo(photo_id, data):
    """Per-row delete (08_data_crud.md `per_row`) — a bare zBtn.action CALL,
    not a full zData block, so the row's own static file is cleaned up first.
    """
    row = data.first(_TABLE, where={"id": photo_id})
    if row is None:
        return "error"

    image_path = row.get("image") or ""
    prefix = "@.static.photos."
    if image_path.startswith(prefix):
        stray = _STATIC_DIR / image_path[len(prefix):]
        stray.unlink(missing_ok=True)

    data.delete(_TABLE, where={"id": photo_id})
    return f"Deleted {row.get('title')}"


def _unique_name(name: str) -> str:
    """Never clobber an existing static file sharing the same name."""
    if not (_STATIC_DIR / name).exists():
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while (_STATIC_DIR / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"

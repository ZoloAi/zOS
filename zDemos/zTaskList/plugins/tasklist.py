"""tasklist — toggle a row's done flag by id, no dialog, no typed id.

Genuinely needs Python: flipping a boolean based on its OWN current value
has no computed-set equivalent (18_data_advanced.md "computed" is
arithmetic-only — $inc/$dec/$mul/$div/zExpr, no boolean NOT), so this is a
real read-then-write, the documented zos_plugin lane for exactly that:
@zfunc + the injected `data` facade (08_data_crud.md `per_row`).

Delete used to live here too, but a plain pass-through remove has no real
Python-required behavior — it's now a zModal + zDialog(fields: []) onSubmit
holding a real zData block directly in zUI.zTaskList.zolo (08_data_crud.md
per_row "preferred"), no plugin.
"""

from zos_plugin import zfunc

_TABLE = "Tasks"


@zfunc
def toggle_task(id, data):
    row = data.first(_TABLE, where={"id": int(id)})
    if not row:
        return False
    data.update(_TABLE, {"done": not row.get("done")}, where={"id": int(id)})
    return True

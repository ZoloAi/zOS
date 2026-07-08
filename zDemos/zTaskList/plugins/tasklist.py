"""tasklist — per-row actions for the task list (toggle/remove by id).

Unlike a pure args->result plugin, these need zData access (checking off /
removing ONE row on a click, no dialog, no typed id) — the documented
zos_plugin lane for exactly that: @zfunc + the injected `data` facade.
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


@zfunc
def delete_task(id, data):
    data.delete(_TABLE, where={"id": int(id)})
    return True

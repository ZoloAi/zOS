"""contacts — per-row delete actions (id baked in per-row by zList, no dialog).

Same documented lane as zTaskList's toggle/delete: @zfunc + the injected
`data` facade for a one-click remove with no typed id. The company-name
lookup per contact row is handled declaratively (a per-row _data sibling in
zUI.zcontacts.zolo), not here — a plugin is for behavior, not a display value
zLoom already knows how to fetch.
"""

from zos_plugin import zfunc

_CONTACTS = "Contacts"
_COMPANIES = "Companies"


@zfunc
def delete_contact(id, data):
    data.delete(_CONTACTS, where={"id": int(id)})
    return True


@zfunc
def delete_company(id, data):
    data.delete(_COMPANIES, where={"id": int(id)})
    return True

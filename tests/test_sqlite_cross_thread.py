# tests/test_sqlite_cross_thread.py
"""SQLite adapter must survive cross-thread use (Bifrost form_submit reality).

In Bifrost the connection is opened lazily on whichever thread touches the
schema first (boot / migration / drift check), but form_submit onSubmit
plugins execute in a worker thread. With sqlite3's default
check_same_thread=True every browser-driven insert died with
"SQLite objects created in a thread can only be used in that same thread"
(zCloud Register: plugins/register.py data.insert). The C library is compiled
SERIALIZED (sqlite3.threadsafety == 3) on every supported build, so sharing
the connection is safe — the adapter now drops the Python-side guard.

Regression suite for the fix in SQLiteAdapter._open.
"""

import importlib.util
import sqlite3
import sys
import threading
from pathlib import Path

_CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(_CORE))  # zSys

if "zOS" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zOS", _CORE / "__init__.py", submodule_search_locations=[str(_CORE)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["zOS"] = _module
    _spec.loader.exec_module(_module)

from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends import adapter_registry  # noqa: E402,F401
from zOS.L3_Abstraction.m_zData.zData_modules.shared.backends.adapter_factory import AdapterFactory  # noqa: E402


def _registrar_adapter(tmp_path):
    """zCloud Register in miniature: opened on the main thread."""
    adapter = AdapterFactory.create_adapter(
        "sqlite", {"path": str(tmp_path), "label": "app", "meta": {}}
    )
    adapter.connect()
    adapter.create_table("zRegistrar_verification", {
        "id": {"type": "int", "pk": True},
        "name": {"type": "str"},
        "email": {"type": "str"},
    })
    # Force the physical open (lazy) to happen HERE, on the main thread —
    # exactly like boot-time migration/drift did in the crashing server.
    adapter.select("zRegistrar_verification")
    return adapter


def test_insert_from_worker_thread(tmp_path):
    """The exact register.begin shape: open on main, insert on worker."""
    adapter = _registrar_adapter(tmp_path)
    errors = []

    def _submit():
        try:
            adapter.insert(
                "zRegistrar_verification",
                ["name", "email"],
                ["Buggy", "gal.video.prod@gmail.com"],
            )
        except Exception as e:  # pragma: no cover - the failure being regressed
            errors.append(e)

    t = threading.Thread(target=_submit)
    t.start()
    t.join()

    assert not errors, f"cross-thread insert raised: {errors}"
    rows = adapter.select("zRegistrar_verification")
    assert len(rows) == 1
    assert rows[0]["email"] == "gal.video.prod@gmail.com"


def test_reads_from_multiple_threads(tmp_path):
    adapter = _registrar_adapter(tmp_path)
    adapter.insert("zRegistrar_verification", ["name", "email"], ["a", "a@z.m"])
    errors = []

    def _read():
        try:
            rows = adapter.select("zRegistrar_verification")
            assert rows[0]["name"] == "a"
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=_read) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"cross-thread reads raised: {errors}"


def test_disconnect_invalidates_all_threads_then_reopens(tmp_path):
    """Per-ws cleanup closes ALL thread connections; next use reopens clean."""
    adapter = _registrar_adapter(tmp_path)
    adapter.insert("zRegistrar_verification", ["name", "email"], ["a", "a@z.m"])

    opened_on_worker = []

    def _touch():
        adapter.select("zRegistrar_verification")
        opened_on_worker.append(adapter.connection)

    t = threading.Thread(target=_touch)
    t.start()
    t.join()
    assert opened_on_worker[0] is not None

    adapter.disconnect()
    assert adapter.connection is None  # this thread's handle invalidated too

    # Lazy reopen on next use — from any thread — must succeed.
    rows = adapter.select("zRegistrar_verification")
    assert rows[0]["name"] == "a"


def test_serialized_build_assumption():
    """The fix's precondition on this interpreter — loudly flag exotic builds."""
    assert sqlite3.threadsafety == 3, (
        "sqlite3 not compiled SERIALIZED — the adapter falls back to "
        "check_same_thread=True on this build (single-thread use only)"
    )

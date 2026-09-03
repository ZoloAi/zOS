"""zOS#2 — LocalProcessDriver orphan sweep.

A host restart forgets the in-process instance table while children (own
session groups) keep running. Every spawn drops a pidfile; a fresh driver's
``_sweep_orphans`` must reap anything still alive from a previous host life —
and ONLY things that are provably ours (command-line markers), confirming
each kill (TERM → wait → KILL) instead of fire-and-forget.

POSIX-only behavior (Windows clears files, leaves processes) — tests skip
there.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ZOS_ROOT = Path(__file__).resolve().parents[1]
if str(ZOS_ROOT) not in sys.path:
    sys.path.insert(0, str(ZOS_ROOT))

from zOS.zos_plugin.drivers import LocalProcessDriver  # noqa: E402

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX sweep semantics")


def _spawn_detached_marked(marker_arg: str) -> int:
    """Spawn a long sleeper whose argv carries a zolo child marker, detached
    from this test process (own session; parent shell exits immediately) so a
    kill leaves no zombie under us — exactly the orphan shape a host restart
    leaves behind. Returns the sleeper's pid."""
    # Own session (start_new_session, like the real driver spawn) is CRITICAL:
    # the sweep kills by PROCESS GROUP, and a plain `bash … &` child inherits
    # the test runner's group — the sweep would TERM pytest itself. The
    # intermediate python exits at once, reparenting the sleeper to init so a
    # kill leaves no zombie under this test process (macOS has no setsid CLI).
    out = subprocess.run(
        [sys.executable, "-c",
         "import subprocess, sys; "
         "p = subprocess.Popen("
         "[sys.executable, '-c', 'import time; time.sleep(120)', sys.argv[1]], "
         "start_new_session=True, stdout=subprocess.DEVNULL, "
         "stderr=subprocess.DEVNULL); "
         "print(p.pid)",
         marker_arg],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    pid = int(out)
    # Give ps a beat to see the child.
    time.sleep(0.3)
    return pid


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _write_pidfile(runtime: Path, app_id: str, pid: int) -> Path:
    d = runtime / app_id
    d.mkdir(parents=True, exist_ok=True)
    f = d / "instance_9999.pid"
    f.write_text(str(pid))
    return f


@posix_only
def test_sweep_reaps_marked_orphan(tmp_path):
    pid = _spawn_detached_marked("zSpark.fakeapp.zolo")
    pidfile = _write_pidfile(tmp_path, "fakeapp", pid)
    assert _alive(pid)

    LocalProcessDriver(runtime_dir=str(tmp_path))

    # Confirmed-kill contract: the orphan is gone and its pidfile cleared.
    deadline = time.time() + 3
    while _alive(pid) and time.time() < deadline:
        time.sleep(0.1)
    assert not _alive(pid), "marked orphan must be reaped on driver boot"
    assert not pidfile.exists(), "reaped orphan's pidfile must be cleared"


@posix_only
def test_sweep_spares_innocent_pid(tmp_path):
    # A live process with NO zolo marker in its argv (pid recycling shape).
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        pidfile = _write_pidfile(tmp_path, "recycled", proc.pid)
        time.sleep(0.3)

        LocalProcessDriver(runtime_dir=str(tmp_path))

        assert proc.poll() is None, (
            "a pid whose command line is not a zolo child must NEVER be signaled"
        )
        assert not pidfile.exists(), "stale pidfile is still cleared"
    finally:
        proc.kill()
        proc.wait()


@posix_only
def test_sweep_clears_dead_pidfile(tmp_path):
    # A pid that no longer exists (normal case after machine reboot).
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    pidfile = _write_pidfile(tmp_path, "gone", dead.pid)

    LocalProcessDriver(runtime_dir=str(tmp_path))

    assert not pidfile.exists()


@posix_only
def test_sweep_clears_garbage_pidfile(tmp_path):
    d = tmp_path / "junk"
    d.mkdir(parents=True)
    pidfile = d / "instance_1234.pid"
    pidfile.write_text("not-a-pid")

    LocalProcessDriver(runtime_dir=str(tmp_path))

    assert not pidfile.exists()


@posix_only
def test_fresh_runtime_dir_is_noop(tmp_path):
    LocalProcessDriver(runtime_dir=str(tmp_path / "never-created"))

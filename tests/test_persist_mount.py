"""
zPersist mounts (zOS#114) — unit tests for zos_plugin.persist and the
symlink-safety of LocalBundleStore.list_app_files.

The contract under test:
  • spark_wants_persist: tolerant line-scan, truthy values opt in, falsy/absent don't
  • relocate_data_root: seeds the mount ONCE (previous live Data preferred over
    the bundle seed), replaces the build's Data/ with a symlink, is idempotent,
    and never merges into an existing mount
  • list_app_files never follows the Data symlink — the #63 guard must see no
    Data/ files on a persist build (a push can't delete mount data)
"""

import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1] / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from zos_plugin.bundle_store import LocalBundleStore  # noqa: E402
from zos_plugin.persist import (  # noqa: E402
    data_is_relocated, relocate_data_root, resolve_persist_root,
    spark_wants_persist,
)


# ── spark_wants_persist ──────────────────────────────────────────────────────

def _spark(tmp_path, body: str) -> Path:
    f = tmp_path / "zSpark.app.zolo"
    f.write_text(body, encoding="utf-8")
    return f


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("True", True), ("yes", True), ("1", True),
    ("/some/path", True),          # path value = opt-in, location NOT honoured
    ("false", False), ("no", False), ("0", False), ("off", False),
    ("none", False), ("", False),
])
def test_spark_wants_persist_values(tmp_path, value, expected):
    spark = _spark(tmp_path, f"zSpark:\n    title: App\n    zPersist: {value}\n")
    assert spark_wants_persist(spark) is expected


def test_spark_without_key_or_file(tmp_path):
    assert spark_wants_persist(_spark(tmp_path, "zSpark:\n    title: App\n")) is False
    assert spark_wants_persist(tmp_path / "missing.zolo") is False


def test_commented_key_does_not_count(tmp_path):
    spark = _spark(tmp_path, "zSpark:\n    title: App\n    # zPersist: true\n")
    assert spark_wants_persist(spark) is False


# ── relocate_data_root ───────────────────────────────────────────────────────

def _build(tmp_path, name="b1", rows="a,b\n1,2\n") -> Path:
    build = tmp_path / name
    (build / "Data").mkdir(parents=True)
    (build / "Data" / "t.csv").write_text(rows, encoding="utf-8")
    return build


def test_first_push_seeds_from_bundle(tmp_path):
    build = _build(tmp_path)
    mount = tmp_path / "_persist" / "u" / "app" / "Data"
    summary = relocate_data_root(build, mount)
    assert (mount / "t.csv").read_text() == "a,b\n1,2\n"
    assert (build / "Data").is_symlink()
    assert (build / "Data").resolve() == mount.resolve()
    assert data_is_relocated(build)
    assert summary["seeded_from"] and summary["seeded_files"] == 1


def test_seed_prefers_previous_live_build(tmp_path):
    prev = _build(tmp_path, "prev", rows="a,b\n1,2\n99,100\n")   # production truth
    new = _build(tmp_path, "new", rows="a,b\n1,2\n")             # stale seed
    mount = tmp_path / "_persist" / "u" / "app" / "Data"
    relocate_data_root(new, mount, seed_from=prev / "Data")
    assert (mount / "t.csv").read_text() == "a,b\n1,2\n99,100\n"


def test_second_push_never_touches_mount(tmp_path):
    mount = tmp_path / "_persist" / "u" / "app" / "Data"
    relocate_data_root(_build(tmp_path, "b1"), mount)
    (mount / "t.csv").write_text("a,b\nLIVE,DATA\n", encoding="utf-8")  # users wrote
    b2 = _build(tmp_path, "b2", rows="a,b\nfresh,seed\n")
    summary = relocate_data_root(b2, mount)
    assert (mount / "t.csv").read_text() == "a,b\nLIVE,DATA\n"
    assert (b2 / "Data").is_symlink()
    assert summary["seeded_from"] is None


def test_relocate_is_idempotent(tmp_path):
    build = _build(tmp_path)
    mount = tmp_path / "_persist" / "u" / "app" / "Data"
    relocate_data_root(build, mount)
    relocate_data_root(build, mount)  # re-run on an already-linked build
    assert (build / "Data").resolve() == mount.resolve()


def test_build_without_data_dir_gets_empty_mount(tmp_path):
    build = tmp_path / "b1"
    build.mkdir()
    mount = tmp_path / "_persist" / "u" / "app" / "Data"
    summary = relocate_data_root(build, mount)
    assert mount.is_dir() and not any(mount.iterdir())
    assert (build / "Data").is_symlink()
    assert summary["seeded_from"] is None


# ── resolve_persist_root ─────────────────────────────────────────────────────

def test_persist_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHOST_PERSIST_ROOT", str(tmp_path / "vault"))
    assert resolve_persist_root() == (tmp_path / "vault").resolve()


def test_persist_root_relative_env_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHOST_PERSIST_ROOT", "relative/vault")
    monkeypatch.delenv("STORAGE_LOCAL_ROOT", raising=False)
    monkeypatch.setenv("ZHOST_HOSTED_ROOT", str(tmp_path))
    # relative override is refused → falls to <hosted>/storage/_persist
    assert resolve_persist_root() == (tmp_path / "storage" / "_persist").resolve()


def test_persist_root_under_storage_local_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ZHOST_PERSIST_ROOT", raising=False)
    monkeypatch.setenv("ZHOST_HOSTED_ROOT", str(tmp_path))
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", "storage/")
    assert resolve_persist_root() == (tmp_path / "storage" / "_persist").resolve()


# ── list_app_files must not follow the Data symlink (#63 guard stays quiet) ──

def test_list_app_files_skips_symlinked_data(tmp_path):
    store = LocalBundleStore(str(tmp_path))
    build = tmp_path / "_hosted" / "u/app" / "builds" / "7"
    (build / "zViews").mkdir(parents=True)
    (build / "zViews" / "zUI.app.zolo").write_text("x", encoding="utf-8")
    mount = tmp_path / "storage" / "_persist" / "u" / "app" / "Data"
    mount.mkdir(parents=True)
    (mount / "t.csv").write_text("a\n1\n", encoding="utf-8")
    (build / "Data").symlink_to(mount, target_is_directory=True)

    files = store.list_app_files("u/app", 7)
    assert files == ["zViews/zUI.app.zolo"]
    assert store.list_app_files("u/app", 7, prefix="Data/") == []


def test_list_app_files_still_sees_regular_data(tmp_path):
    store = LocalBundleStore(str(tmp_path))
    build = tmp_path / "_hosted" / "u/app" / "builds" / "7"
    (build / "Data").mkdir(parents=True)
    (build / "Data" / "t.csv").write_text("a\n1\n", encoding="utf-8")
    assert store.list_app_files("u/app", 7, prefix="Data/") == ["Data/t.csv"]


def test_build_dir_accessor(tmp_path):
    store = LocalBundleStore(str(tmp_path))
    build = tmp_path / "_hosted" / "u/app" / "builds" / "3"
    build.mkdir(parents=True)
    assert store.build_dir("u/app", 3) == build
    assert store.build_dir("u/app", 99) is None

# zOS/tests/test_bundle_store_root.py
"""Regression tests for hosted-tree root resolution (zOS#3).

cwd is not a location an operator chose: a receiver launched from an app folder
grew its own ``_hosted/`` there, so the same push landed under two roots
depending only on how the process started. A DECLARED root pins it — and the
store exposes that root so whoever LOCATES a build resolves against the same
answer the writer used.
"""
# pylint: disable=protected-access

import os
import unittest
from pathlib import Path
from unittest import mock

from zos_plugin.bundle_store import (
    HOSTED_DIRNAME,
    get_bundle_store,
    resolve_hosted_root,
)


class _Env:
    def __init__(self, values=None, env_vars=None):
        self._values = values or {}
        self._env_vars = env_vars or {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_env_var(self, key, default=None):
        return self._env_vars.get(key, default)


class _Config:
    def __init__(self, environment=None):
        self.environment = environment


class _Zos:
    def __init__(self, environment=None, workspace_dir=None):
        self.config = _Config(environment)
        if workspace_dir is not None:
            self.workspace_dir = workspace_dir


def _clean_env():
    patched = mock.patch.dict(os.environ, {}, clear=False)
    patched.start()
    os.environ.pop("ZHOST_HOSTED_ROOT", None)
    return patched


class TestResolveHostedRoot(unittest.TestCase):

    def setUp(self):
        self._patched = _clean_env()
        self.addCleanup(self._patched.stop)

    def test_explicit_arg_wins(self):
        zos = _Zos(_Env({"hosted_root": "/declared"}), workspace_dir="/ws")
        self.assertEqual(resolve_hosted_root(zos, "/explicit"), Path("/explicit"))

    def test_env_declared_root_beats_workspace(self):
        os.environ["ZHOST_HOSTED_ROOT"] = "/mnt/hosted"
        self.assertEqual(
            resolve_hosted_root(_Zos(_Env(), workspace_dir="/ws")),
            Path("/mnt/hosted"),
        )

    def test_zenv_declared_root_beats_workspace(self):
        zos = _Zos(_Env({"hosted_root": "/srv/apps"}), workspace_dir="/ws")
        self.assertEqual(resolve_hosted_root(zos), Path("/srv/apps"))

    def test_relative_declared_root_is_ignored(self):
        # A relative value is media-shaped, never a host-wide app tree.
        zos = _Zos(_Env({"hosted_root": "apps/"}), workspace_dir="/ws")
        self.assertEqual(resolve_hosted_root(zos), Path("/ws"))

    def test_storage_local_root_is_NOT_the_hosted_root(self):
        # The media bucket must not relocate the app tree — that would orphan
        # every registry zspark_path already recorded against the workspace.
        zos = _Zos(
            _Env({"storage_local_root": "/Users/someone/zCloud-bucket"}),
            workspace_dir="/ws",
        )
        self.assertEqual(resolve_hosted_root(zos), Path("/ws"))

    def test_workspace_used_when_nothing_declared(self):
        self.assertEqual(resolve_hosted_root(_Zos(_Env(), workspace_dir="/ws")), Path("/ws"))

    def test_cwd_is_the_last_resort(self):
        self.assertEqual(resolve_hosted_root(_Zos()), Path(os.getcwd()).resolve())

    def test_tilde_expands(self):
        os.environ["ZHOST_HOSTED_ROOT"] = "~/hosted-apps"
        self.assertEqual(
            resolve_hosted_root(_Zos()),
            Path("~/hosted-apps").expanduser().resolve(),
        )


class TestStoreRootIsReadable(unittest.TestCase):
    """The reader's half: a locator can ask the store, not re-derive a root."""

    def setUp(self):
        self._patched = _clean_env()
        self.addCleanup(self._patched.stop)

    def test_store_base_follows_declared_root(self):
        os.environ["ZHOST_HOSTED_ROOT"] = "/mnt/hosted"
        store = get_bundle_store(_Zos(_Env(), workspace_dir="/ws"))
        self.assertEqual(store._base, Path("/mnt/hosted") / HOSTED_DIRNAME)

    def test_store_root_matches_resolution(self):
        os.environ["ZHOST_HOSTED_ROOT"] = "/mnt/hosted"
        zos = _Zos(_Env(), workspace_dir="/ws")
        self.assertEqual(get_bundle_store(zos).root, resolve_hosted_root(zos))

    def test_store_root_defaults_to_workspace(self):
        zos = _Zos(_Env(), workspace_dir="/ws")
        self.assertEqual(get_bundle_store(zos).root, Path("/ws"))


if __name__ == "__main__":
    unittest.main()

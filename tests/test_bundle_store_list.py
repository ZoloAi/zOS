"""LocalBundleStore.list_app_files — powers the push data-loss guard (zOS#63)."""
import io
import tarfile
import tempfile
import unittest

from zos_plugin.bundle_store import LocalBundleStore  # pylint: disable=import-error


def _tar(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, payload in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


class TestListAppFiles(unittest.TestCase):
    def test_lists_build_files_with_prefix_filter(self):
        bundle = _tar({
            "app/zSpark.app.zolo": b"zMode: zBifrost",
            "app/Data/Members.csv": b"id\n1",
            "app/Data/Settings.csv": b"k,v",
            "app/styles/main.css": b"body{}",
            "attachments/notes.txt": b"dormant",
        })
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalBundleStore(tmp)
            store.unpack("owner/app", bundle, build_id=7)

            all_files = store.list_app_files("owner/app", build_id=7)
            self.assertIn("Data/Members.csv", all_files)
            self.assertIn("styles/main.css", all_files)
            # dormant attachments are not the app tree
            self.assertFalse(any(f.startswith("_attachments/") for f in all_files))

            data_only = store.list_app_files("owner/app", build_id=7, prefix="Data/")
            self.assertEqual(data_only, ["Data/Members.csv", "Data/Settings.csv"])

    def test_missing_build_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalBundleStore(tmp)
            self.assertEqual(store.list_app_files("owner/app", build_id=99), [])

    def test_base_class_default_is_empty(self):
        from zos_plugin.bundle_store import BundleStore  # pylint: disable=import-error,import-outside-toplevel
        self.assertEqual(BundleStore.list_app_files(None, "x", 1), [])
        self.assertFalse(BundleStore.remove_build(None, "x", 1))


class TestRemoveBuild(unittest.TestCase):
    def test_removes_one_build_leaves_sibling(self):
        bundle = _tar({"app/zSpark.a.zolo": b"x", "app/Data/D.csv": b"d"})
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalBundleStore(tmp)
            store.unpack("owner/app", bundle, build_id=1)
            store.unpack("owner/app", bundle, build_id=2)

            self.assertTrue(store.remove_build("owner/app", 1))
            self.assertEqual(store.list_app_files("owner/app", build_id=1), [])
            # sibling (live) build untouched
            self.assertIn("Data/D.csv", store.list_app_files("owner/app", build_id=2))
            # idempotent: second removal reports nothing removed
            self.assertFalse(store.remove_build("owner/app", 1))

    def test_never_removes_flat_tree(self):
        bundle = _tar({"app/zSpark.a.zolo": b"x"})
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalBundleStore(tmp)
            store.unpack("owner/app", bundle)  # flat, no build_id
            self.assertFalse(store.remove_build("owner/app", None))
            self.assertIn("zSpark.a.zolo", store.list_app_files("owner/app"))


if __name__ == "__main__":
    unittest.main()

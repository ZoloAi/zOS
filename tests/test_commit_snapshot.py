"""
z raven --commit full-tree snapshots (zOS#99).

Old behaviour: _SHARED_GLOBS covered four .zolo folders — plugins/, styles/,
templates/, public/ were never archived, so a "restore point" silently missed
the app's plugin logic and its stylesheet. The contract under test now:
snapshot = the WHOLE app tree minus _SNAPSHOT_EXCLUDES (exclude-based, like
zolo push), stated in the commit's own manifest.json.
"""

import json
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import pytest  # noqa: E402

from L4_Orchestration.s_zRaven.zRaven_modules.utils.commit_manager import (  # noqa: E402
    CommitBlockedError,
    _excluded,
    create_commit,
)


def _make_app(root: Path) -> Path:
    """A miniature app exercising every folder class from the field report."""
    files = {
        "zSpark.probe.zolo":            "zSpark:\n    zMode: zCLI\n",
        "zRaven/zRaven.probe.zolo":     "Tests:\n    Done:\n        zMarker: done\n",
        "zRaven/zRaven.other.zolo":     "Tests:\n    Done:\n        zMarker: done\n",
        "zViews/zUI.probe.zolo":        "Main:\n    zH1: probe\n",
        "models/zSchema.users.zolo":    "users:\n    name:\n        type: str\n",
        "plugins/logic.py":             "def fn():\n    return 1\n",
        "styles/zCanvas.css":           ".x { color: red }\n",
        "templates/zVaF.html":          "<html></html>\n",
        "public/upload.txt":            "payload\n",
        "routes/zServer.routes.zolo":   "/: {}\n",
        # noise — must NOT be captured
        "Data/users.csv":               "name\nalice\n",
        "logs/probe.log":               "boot\n",
        "zRaven/output/runs.csv":       "raven_file,steps_total,steps_passed,steps_failed\n",
        "zVersions/tests/old.zolo":     "stale\n",
        "plugins/__pycache__/l.pyc":    "bytecode",
        "zProject.probe.receipt.zolo":  "app_id: 123\n",
    }
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    # a green run row so the commit gate passes
    (root / "zRaven" / "output" / "runs.csv").write_text(
        "raven_file,steps_total,steps_passed,steps_failed\n"
        "zRaven.probe.zolo,3,3,0\n",
        encoding="utf-8",
    )
    return root


def _commit(root: Path, **kw) -> dict:
    return create_commit(
        root, root / "zSpark.probe.zolo", "probe",
        {"title": "probe"}, **kw,
    )


def test_full_tree_captured_including_code_and_styles(tmp_path):
    result = _commit(_make_app(tmp_path))
    snap = result["path"] / "snapshot"
    # the #99 casualties — plugin logic, stylesheet, template, upload page
    for rel in ("plugins/logic.py", "styles/zCanvas.css",
                "templates/zVaF.html", "public/upload.txt",
                "models/zSchema.users.zolo", "routes/zServer.routes.zolo",
                "zRaven/zRaven.other.zolo"):
        assert (snap / rel).exists(), f"missing from snapshot: {rel}"
    # flow-owned still flagged separately, and not duplicated in shared
    assert "zSpark.probe.zolo" in result["flow_owned"]
    assert "zRaven/zRaven.probe.zolo" in result["flow_owned"]
    assert not set(result["flow_owned"]) & set(result["shared"])


def test_noise_excluded(tmp_path):
    result = _commit(_make_app(tmp_path))
    snap = result["path"] / "snapshot"
    for rel in ("Data/users.csv", "logs/probe.log", "zRaven/output/runs.csv",
                "zVersions/tests/old.zolo", "plugins/__pycache__/l.pyc",
                "zProject.probe.receipt.zolo"):
        assert not (snap / rel).exists(), f"noise leaked into snapshot: {rel}"


def test_manifest_states_the_contract(tmp_path):
    result = _commit(_make_app(tmp_path))
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    assert manifest["contract"] == "full-tree"
    assert "Data" in manifest["excluded"]
    assert "plugins/logic.py" in manifest["shared"]


def test_diff_covers_plugin_edits(tmp_path):
    root = _make_app(tmp_path)
    _commit(root)
    (root / "plugins" / "logic.py").write_text("def fn():\n    return 2\n")
    result = _commit(root)
    diff = (result["path"] / "diff.txt").read_text()
    assert "plugins/logic.py" in diff
    assert "-    return 1" in diff and "+    return 2" in diff


def test_binary_change_noted_not_dumped(tmp_path):
    root = _make_app(tmp_path)
    cover = root / "public" / "cover.png"
    cover.write_bytes(b"\x89PNG\0\0fake")
    _commit(root)
    cover.write_bytes(b"\x89PNG\0\0fake2")
    result = _commit(root)
    diff = (result["path"] / "diff.txt").read_text()
    assert "=== binary changed: public/cover.png ===" in diff
    assert "fake2" not in diff


def test_commits_do_not_recurse_into_prior_commits(tmp_path):
    root = _make_app(tmp_path)
    _commit(root)
    result = _commit(root, label="second")
    snap = result["path"] / "snapshot"
    rels = [p.relative_to(snap) for p in snap.rglob("*") if p.is_file()]
    assert rels  # c2 captured the tree...
    assert not any("zVersions" in r.parts for r in rels)  # ...but not c1


def test_gate_still_blocks_red_flow(tmp_path):
    root = _make_app(tmp_path)
    (root / "zRaven" / "output" / "runs.csv").write_text(
        "raven_file,steps_total,steps_passed,steps_failed\n"
        "zRaven.probe.zolo,3,2,1\n",
        encoding="utf-8",
    )
    with pytest.raises(CommitBlockedError):
        _commit(root)
    _commit(root, force=True)  # override still honored


def test_excluded_matcher_semantics():
    assert _excluded("Data/users.csv")
    assert _excluded("zRaven/output/runs.csv")
    assert _excluded("zRaven/zShots/probe/mobile/x.png")
    assert _excluded("deep/nested/__pycache__/x.pyc")
    assert _excluded("zProject.myapp.receipt.zolo")
    assert not _excluded("zRaven/zRaven.probe.zolo")
    assert not _excluded("plugins/logic.py")
    assert not _excluded("styles/zCanvas.css")

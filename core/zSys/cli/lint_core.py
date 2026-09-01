# zSys/cli/lint_core.py
"""
Static fault detection over an app's .zolo files (zOS#84 — z lint / strict boot).

One walk, five fault classes — everything here is statically checkable at load
time without running the app:

  parse           zlsp tokenize diagnostics (Error/Warning). This is the SSOT for
                  everything the parser itself refuses or warns about: comment-
                  pairing anomalies (unterminated ``#>``, ``#>`` inside an open
                  span — zOS#80), duplicate sibling blocks (a fatal ZoloParseError,
                  surfaced as an Error diagnostic since zLSP 1.2.2), bad indent.
                  Repeated shorthand zEvents (zText, zH2, …) are SUPPORTED grammar
                  (auto-suffixed ``__dup2`` by the zVaF parser) and never fault.
  shuttle         a zShuttle naming a reel absent from every zSpool declaration
                  in the file, or a zPattern absent from zLoom/patterns/
  pattern         a bare ``%name:`` invocation with no registered pattern
  zclass-token    a ``%token`` inside ``_zClass:`` — render tokens never resolve
                  in class position, the literal ships to the DOM
  onsuccess       an ``onSuccess:`` verb outside the dispatch subsystem set

The same fault list drives both surfaces: the ``strict:`` boot gate in
zspark_command (refuse to boot, default ON, opt-out ``strict: false``) and the
standalone ``z lint`` command.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Dirs that are not the app's own authored surface. ``_hosted`` matters most:
# a host (zCloud) must never refuse ITS boot over a fault in a guest's bundle.
# ``zVersions`` holds frozen raven-commit snapshots — history, not the app.
_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", "_hosted", "Data", "output",
    ".venv", "venv", "zVersions",
})

# Mirrors CommandLauncher._launch_dict subsystem_keys + zDelegate routing
# (core/L2_Handling/g_zDispatch/dispatch_modules/dispatch_launcher.py). Kept as
# a literal so ``z lint`` stays import-light; the unit test pins it to the SSOT.
_ONSUCCESS_VERBS = frozenset({
    "zDisplay", "zFunc", "zDialog", "zDash", "zFlat", "zLink", "zDelta",
    "zModal", "zMenu", "zWizard", "zRead", "zData", "zExport", "zImport",
    "zTransfer", "zVar", "zList", "zLogin", "zLogout", "zDelegate",
})

# _zClass tokens that never resolve: render-time namespaces and bare slots.
# %item.* / %index DO resolve — the loop pass textually bakes them per row —
# so they are deliberately NOT matched here.
_DEAD_CLASS_TOKEN_RE = re.compile(r"%(?:data|session|zVisitor)\.|%[A-Za-z_]\w*(?![\w.])")
_VERB_CALL_RE = re.compile(r"^([A-Za-z_]\w*)\s*\(")


@dataclass
class Fault:
    """One statically-detected fault, positioned for the author."""
    file: str          # path relative to the app dir
    line: int          # 1-based; 0 when the fault is file-scoped
    code: str          # fault class (parse | dup-key | shuttle | ...)
    message: str

    def render(self) -> str:
        pos = f":{self.line}" if self.line else ""
        return f"{self.file}{pos}  [{self.code}]  {self.message}"


def lint_app(app_dir: Path) -> List[Fault]:
    """Walk every authored .zolo file under ``app_dir`` and collect faults."""
    app_dir = Path(app_dir).resolve()
    registry = _load_pattern_registry(app_dir)
    faults: List[Fault] = []

    for path in sorted(_iter_zolo_files(app_dir)):
        rel = str(path.relative_to(app_dir))
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            faults.append(Fault(rel, 0, "read", f"unreadable as UTF-8 text: {exc}"))
            continue
        faults.extend(_lint_file(rel, content, registry, app_dir, path))

    return faults


def _iter_zolo_files(app_dir: Path):
    for path in app_dir.rglob("*.zolo"):
        parts = path.relative_to(app_dir).parts
        if any(p in _SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        # dot-files are never authored surface — macOS tar extraction drops
        # binary AppleDouble companions ("._zSpark.<app>.zolo") next to real files
        if parts[-1].startswith("."):
            continue
        yield path


def _lint_file(
    rel: str,
    content: str,
    registry: Set[str],
    app_dir: Path,
    path: Path,
) -> List[Fault]:
    from zlsp.parser import tokenize  # pylint: disable=import-outside-toplevel

    faults: List[Fault] = []
    result = tokenize(content, str(path))

    for diag in result.diagnostics or []:
        if diag.severity in (1, 2):  # Error, Warning
            faults.append(Fault(
                rel, diag.range.start.line + 1, "parse", diag.message,
            ))

    data = result.data if isinstance(result.data, dict) else None
    if data is not None:
        in_patterns_dir = "zLoom" in Path(rel).parts and "patterns" in Path(rel).parts
        declared_spools = _collect_spool_names(data)
        _walk_tree(
            rel, data, faults,
            registry=registry,
            declared_spools=declared_spools,
            check_pattern_keys=not in_patterns_dir,
        )
    return faults


# ---------------------------------------------------------------------------
# pattern registry (parse zLoom/patterns/ directly — no framework boot needed)
# ---------------------------------------------------------------------------

def _load_pattern_registry(app_dir: Path) -> Set[str]:
    """Top-level keys of zLoom/patterns/* — the names a ``%name:`` may invoke.

    Mirrors component_expand.load_component_registry without needing a booted
    zOS: same dir, same "each top-level key IS a name, zMeta skipped" rule.
    """
    names: Set[str] = set()
    patterns_dir = app_dir / "zLoom" / "patterns"
    if not patterns_dir.is_dir():
        return names
    from zlsp.parser import loads  # pylint: disable=import-outside-toplevel
    for fpath in sorted(patterns_dir.iterdir()):
        ext = fpath.suffix.lower()
        try:
            if ext == ".zolo":
                data = loads(fpath.read_text(encoding="utf-8"), filename=str(fpath))
            elif ext == ".json":
                data = json.loads(fpath.read_text(encoding="utf-8"))
            else:
                continue
        except Exception:  # pylint: disable=broad-except
            continue  # unparseable pattern file surfaces via its own parse faults
        if isinstance(data, dict):
            names.update(k for k in data if k != "zMeta")
    return names


# ---------------------------------------------------------------------------
# parsed-tree walks
# ---------------------------------------------------------------------------
#
# NOTE on duplicates: sibling duplicate detection is deliberately NOT
# reimplemented here. The parser is the SSOT — repeatable shorthand zEvents
# (zlsp.token_registry.UI_ELEMENT_SHORTHAND_KEYS / ZRAVEN_REPEATABLE_KEYS)
# parse to auto-suffixed ``__dup2`` keys, and any OTHER duplicate is a fatal
# ZoloParseError that tokenize surfaces as an Error diagnostic (zLSP >= 1.2.2),
# which the "parse" fault class above already reports.

def _collect_spool_names(node: Any, found: Optional[Set[str]] = None) -> Set[str]:
    """Union of every ``zSpool: [...]`` list in the file (root zMeta + panel meta)."""
    if found is None:
        found = set()
    if isinstance(node, dict):
        spool = node.get("zSpool")
        if isinstance(spool, list):
            found.update(s for s in spool if isinstance(s, str))
        elif isinstance(spool, str) and not isinstance(node.get("zPattern"), str):
            # a bare-string declaration (not a zShuttle's reel reference)
            found.add(spool)
        for val in node.values():
            _collect_spool_names(val, found)
    elif isinstance(node, list):
        for item in node:
            _collect_spool_names(item, found)
    return found


def _walk_tree(
    rel: str,
    node: Any,
    faults: List[Fault],
    registry: Set[str],
    declared_spools: Set[str],
    check_pattern_keys: bool,
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_tree(rel, item, faults, registry, declared_spools, check_pattern_keys)
        return
    if not isinstance(node, dict):
        return

    for key, val in node.items():
        if key == "zShuttle" and isinstance(val, dict):
            _check_shuttle(rel, val, faults, registry, declared_spools)
        elif key == "_zClass":
            # inside zLoom/patterns/, bare %slots are filled at expansion —
            # only dotted render-time tokens are dead there
            _check_zclass(rel, val, faults, allow_bare_slots=not check_pattern_keys)
        elif key == "onSuccess":
            _check_onsuccess(rel, val, faults)
        elif (
            check_pattern_keys
            and isinstance(key, str)
            and key.startswith("%")
            and "." not in key          # dotted %-keys are zGate IR, not invocations
            and key[1:] not in registry
        ):
            faults.append(Fault(
                rel, 0, "pattern",
                f"'%{key[1:]}:' invokes a pattern not defined in zLoom/patterns/ — "
                f"it will ship to the page as-is",
            ))
        _walk_tree(rel, val, faults, registry, declared_spools, check_pattern_keys)


def _check_shuttle(
    rel: str, cfg: Dict[str, Any], faults: List[Fault],
    registry: Set[str], declared_spools: Set[str],
) -> None:
    spool = cfg.get("zSpool")
    pattern = cfg.get("zPattern")
    if not isinstance(spool, str) or not isinstance(pattern, str):
        faults.append(Fault(
            rel, 0, "shuttle",
            f"zShuttle needs 'zSpool: <reel>' and 'zPattern: <name>' "
            f"(got zSpool={spool!r}, zPattern={pattern!r})",
        ))
        return
    if pattern not in registry:
        faults.append(Fault(
            rel, 0, "shuttle",
            f"zShuttle weaves pattern '%{pattern}' but zLoom/patterns/ has no such "
            f"definition — every slot would surface literal",
        ))
    reel = spool[len("%data."):] if spool.startswith("%data.") else spool
    if reel not in declared_spools:
        faults.append(Fault(
            rel, 0, "shuttle",
            f"zShuttle names reel '{reel}' but no zSpool declaration in this file "
            f"provides it — the list resolves empty",
        ))


def _check_zclass(
    rel: str, val: Any, faults: List[Fault], allow_bare_slots: bool = False,
) -> None:
    dead_re = (
        re.compile(r"%(?:data|session|zVisitor)\.") if allow_bare_slots
        else _DEAD_CLASS_TOKEN_RE
    )
    values = val if isinstance(val, list) else [val]
    for item in values:
        if isinstance(item, str) and dead_re.search(item):
            faults.append(Fault(
                rel, 0, "zclass-token",
                f"_zClass value {item!r} carries a %token that never resolves in "
                f"class position — the literal lands in the DOM "
                f"(only loop-baked %item.* resolves here)",
            ))


def _check_onsuccess(rel: str, val: Any, faults: List[Fault]) -> None:
    if isinstance(val, dict):
        for verb in val:
            if verb not in _ONSUCCESS_VERBS:
                faults.append(Fault(
                    rel, 0, "onsuccess",
                    f"onSuccess verb '{verb}' is not a dispatch subsystem — "
                    f"supported: {', '.join(sorted(_ONSUCCESS_VERBS))}",
                ))
        return
    if isinstance(val, str):
        text = val.strip()
        if text.startswith("&"):
            return  # plugin call — dispatch owns validation at run time
        m = _VERB_CALL_RE.match(text)
        verb = m.group(1) if m else text
        if verb not in _ONSUCCESS_VERBS:
            faults.append(Fault(
                rel, 0, "onsuccess",
                f"onSuccess '{text}' does not name a dispatch subsystem — "
                f"supported: {', '.join(sorted(_ONSUCCESS_VERBS))}",
            ))

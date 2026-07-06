#!/usr/bin/env python3
"""
audit_gen.py — zOS Documentation Vault Generator

Mirrors the exact zOS + zGuard folder structure into an Obsidian vault.
Each file becomes a note with: semantic type tag, LOC, dependency wikilinks.
Anomalies surface through Obsidian's graph gravity — not through audit noise.

Tag taxonomy (7 types, each gets a distinct graph color):
  facade    — module entry point (zFoo.py at module root)
  constants — pure data: constants, config, schemas, no behaviour
  event     — dispatch/handler/event layer
  logic     — business logic, processors, resolvers, builders
  backend   — data storage, adapters, SQL, persistence
  bridge    — cross-boundary connectors (zBifrost, zGuard bifrost, auth)
  leaf      — small utility/helper, typically no importers

Usage:
    python scripts/audit_gen.py [--zos PATH] [--zguard PATH] [--vault PATH]
"""

import ast
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path


# ─── Tag taxonomy ─────────────────────────────────────────────────────────────

# Hex colors → Obsidian graph uses decimal RGB
TAG_COLORS = {
    "facade":    "#7C5CBF",   # violet
    "constants": "#E6A817",   # amber
    "event":     "#2E9BDA",   # sky blue
    "logic":     "#E05A5A",   # coral
    "backend":   "#E87A30",   # orange
    "bridge":    "#D65FAF",   # pink
    "leaf":      "#4CAF82",   # emerald
}


def _hex_to_rgb_int(h: str) -> int:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r << 16) | (g << 8) | b


def classify_file(rel_path: str, loc: int, functions: list, classes: list, imports: list) -> str:
    """Return one of the 7 tag types based on file characteristics."""
    stem = Path(rel_path).stem
    parts = [p.lower() for p in Path(rel_path).parts]
    stem_l = stem.lower()

    # bridge — bifrost, auth boundary, zGuard connectors
    if any(k in stem_l for k in ("bifrost", "bridge", "watermark", "boot_identity")):
        return "bridge"
    if "zguard" in parts and any(k in stem_l for k in ("auth", "push", "session")):
        return "bridge"

    # backend — data storage, sql, adapters, persistence
    if any(k in stem_l for k in ("adapter", "backend", "sql", "sqlite", "postgresql",
                                  "migration", "ddl", "crud", "persist", "store")):
        return "backend"
    if any(k in parts for k in ("backends", "persistence", "m_zdata")):
        return "backend"

    # constants — pure data files
    if any(k in stem_l for k in ("constants", "config", "schema", "settings", "defaults")):
        # confirm: few/no functions that do work
        if len(functions) <= 3:
            return "constants"

    # event — handlers, dispatchers, event processors
    if any(k in stem_l for k in ("handler", "dispatch", "event", "listener", "trigger", "signal")):
        return "event"
    if "handlers" in parts or "dispatch" in parts:
        return "event"

    # facade — module entry point: named z*.py at shallow depth in its module dir
    if stem.startswith("z") and stem[1:2].isupper():
        depth_in_module = sum(1 for p in Path(rel_path).parts if "_modules" not in p)
        if depth_in_module <= 5:
            return "facade"

    # backend continued — operations, queries
    if any(k in stem_l for k in ("operation", "query", "read", "write", "insert", "delete", "parser_")):
        if any(k in parts for k in ("operations", "parsers", "m_zdata")):
            return "backend"

    # leaf — small utility, no real structure
    if loc < 120 and len(functions) <= 4 and not classes:
        return "leaf"

    # logic — everything else with substance
    return "logic"


# ─── Scanner ─────────────────────────────────────────────────────────────────

def _count_loc(source: str) -> int:
    return sum(1 for l in source.splitlines() if l.strip() and not l.strip().startswith("#"))


def _extract_imports(tree: ast.Module) -> list[str]:
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _extract_top_level(tree: ast.Module):
    funcs, classes = [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
    return funcs, classes


class FileInfo:
    __slots__ = ("abs_path", "rel_path", "repo", "loc", "tag",
                 "imports_raw", "functions", "classes")

    def __init__(self, abs_path, rel_path, repo, loc, tag, imports_raw, functions, classes):
        self.abs_path = abs_path
        self.rel_path = rel_path
        self.repo = repo
        self.loc = loc
        self.tag = tag
        self.imports_raw = imports_raw
        self.functions = functions
        self.classes = classes


def scan_repo(root: Path, repo_name: str) -> list:
    skip_dirs = {"__pycache__", "_deprecated", ".venv", "venv", "build", "dist", ".git"}
    files = []

    for py_file in sorted(root.rglob("*.py")):
        if any(d in py_file.parts for d in skip_dirs):
            continue

        rel = py_file.relative_to(root).as_posix()

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        loc = _count_loc(source)

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            tree = ast.Module(body=[], type_ignores=[])

        imports_raw = _extract_imports(tree)
        funcs, classes = _extract_top_level(tree)
        tag = classify_file(rel, loc, funcs, classes, imports_raw)

        files.append(FileInfo(py_file, rel, repo_name, loc, tag, imports_raw, funcs, classes))

    return files


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph(all_files: list) -> dict:
    """Resolve import strings to known rel_paths."""
    lookup: dict[str, str] = {}
    for fi in all_files:
        dotted = fi.rel_path.replace("/", ".").replace(".py", "")
        lookup[dotted] = fi.rel_path
        stem = Path(fi.rel_path).stem
        if stem not in lookup:
            lookup[stem] = fi.rel_path

    graph = {fi.rel_path: {"imports": [], "imported_by": []} for fi in all_files}

    for fi in all_files:
        for imp in fi.imports_raw:
            resolved = lookup.get(imp)
            if resolved and resolved != fi.rel_path:
                graph[fi.rel_path]["imports"].append(resolved)
                graph[resolved]["imported_by"].append(fi.rel_path)

    return graph


# ─── Note writers ─────────────────────────────────────────────────────────────

LOC_LIMIT = 600


def note_path(vault: Path, fi: FileInfo) -> Path:
    """Mirror the source tree exactly: vault/<repo>/<rel_path>.md"""
    return vault / fi.repo / (fi.rel_path.replace(".py", ".md"))


def write_file_note(vault: Path, fi: FileInfo, graph: dict) -> None:
    path = note_path(vault, fi)
    path.parent.mkdir(parents=True, exist_ok=True)

    imports_resolved = sorted(set(graph[fi.rel_path]["imports"]))
    imported_by = sorted(set(graph[fi.rel_path]["imported_by"]))
    loc_flag = " ⚠️" if fi.loc > LOC_LIMIT else ""

    lines = [
        "---",
        f"type: {fi.tag}",
        f"repo: {fi.repo}",
        f"loc: {fi.loc}",
        f"tags: [{fi.tag}]",
        "---",
        "",
        f"# {Path(fi.rel_path).stem}",
        f"`{fi.rel_path}`",
        "",
        f"**LOC:** {fi.loc}{loc_flag}  ",
        f"**Type:** `{fi.tag}`",
        "",
    ]

    if fi.functions or fi.classes:
        lines.append("## Exports")
        lines.append("")
        for c in fi.classes:
            lines.append(f"- class `{c}`")
        for f in fi.functions[:30]:
            lines.append(f"- `{f}()`")
        lines.append("")

    if imports_resolved:
        lines.append("## Imports")
        lines.append("")
        for dep in imports_resolved:
            stem = Path(dep).stem
            lines.append(f"- [[{dep.replace('.py','')}|{stem}]]")
        lines.append("")

    if imported_by:
        lines.append("## Imported By")
        lines.append("")
        for src in imported_by:
            stem = Path(src).stem
            lines.append(f"- [[{src.replace('.py','')}|{stem}]]")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_folder_index(vault: Path, folder: Path, files_in_folder: list, graph: dict) -> None:
    """_index.md for each folder — sorts first, gives folder-level overview."""
    index_path = folder / "_index.md"
    total_loc = sum(fi.loc for fi in files_in_folder)
    by_tag = defaultdict(list)
    for fi in files_in_folder:
        by_tag[fi.tag].append(fi)

    lines = [
        f"# {folder.name}",
        "",
        f"**Files:** {len(files_in_folder)}  ",
        f"**LOC:** {total_loc:,}",
        "",
        "## By Type",
        "",
    ]
    for tag in sorted(by_tag):
        lines.append(f"**{tag}** ({len(by_tag[tag])})")
        for fi in sorted(by_tag[tag], key=lambda x: x.rel_path):
            stem = Path(fi.rel_path).stem
            rel = fi.rel_path.replace(".py", "")
            loc_flag = " ⚠️" if fi.loc > LOC_LIMIT else ""
            lines.append(f"- [[{fi.repo}/{rel}|{stem}]] ({fi.loc}{loc_flag})")
        lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")


# ─── Obsidian config ──────────────────────────────────────────────────────────

def write_obsidian_config(vault: Path) -> None:
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    # Graph color groups — one per tag
    color_groups = []
    for tag, hex_color in TAG_COLORS.items():
        color_groups.append({
            "query": f"tag:#{tag}",
            "color": {"a": 1, "rgb": _hex_to_rgb_int(hex_color)}
        })

    graph_config = {
        "colorGroups": color_groups,
        "showTags": True,
        "showAttachments": False,
        "hideUnresolved": True,
        "showOrphans": True,
        "collapse-filter": False,
        "collapse-color-groups": False,
        "collapse-display": False,
        "collapse-forces": True,
        "repelStrength": 10,
        "linkStrength": 1,
        "linkDistance": 30,
        "scale": 1,
        "close": False
    }
    (obsidian_dir / "graph.json").write_text(
        json.dumps(graph_config, indent=2), encoding="utf-8"
    )

    # app.json — minimal
    app_config = {
        "defaultViewMode": "preview",
        "newFileLocation": "current"
    }
    (obsidian_dir / "app.json").write_text(
        json.dumps(app_config, indent=2), encoding="utf-8"
    )


# ─── Home note ────────────────────────────────────────────────────────────────

def write_home(vault: Path, stats: dict) -> None:
    lines = [
        "# zOS Vault",
        "",
        "> Documentation mirror of zOS + zGuard source trees.",
        f"> Last generated: run `python scripts/audit_gen.py` to refresh.",
        "",
        "## Stats",
        "",
        f"| | |",
        f"|---|---|",
        f"| Files | {stats['files']} |",
        f"| Total LOC | {stats['total_loc']:,} |",
        f"| LOC > 600 | {stats['loc_violations']} |",
        "",
        "## Tag Legend",
        "",
    ]
    for tag, color in TAG_COLORS.items():
        lines.append(f"- `{tag}` — {color}")
    lines += [
        "",
        "## Structure",
        "",
        "- [[zOS/_index|zOS]] — core framework",
        "- [[zGuard/_index|zGuard]] — trust / bifrost layer",
        "",
        "## Quick Finds",
        "",
        "- All facades: search `tag:#facade`",
        "- LOC violations: search `loc > 600` or look for ⚠️ in index notes",
        "- Cross-boundary: search `tag:#bridge`",
    ]
    (vault / "Home.md").write_text("\n".join(lines), encoding="utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zos", default=str(Path(__file__).parent.parent))
    parser.add_argument("--zguard", default=str(Path.home() / "Projects" / "zGuard"))
    parser.add_argument("--vault", default=str(Path(__file__).parent.parent / "vault"))
    args = parser.parse_args()

    zos_root = Path(args.zos)
    zguard_root = Path(args.zguard)
    vault = Path(args.vault)
    vault.mkdir(exist_ok=True)

    print(f"[audit_gen] zOS:    {zos_root}")
    print(f"[audit_gen] zGuard: {zguard_root}")
    print(f"[audit_gen] Vault:  {vault}")

    zos_files = scan_repo(zos_root, "zOS")
    zguard_files = scan_repo(zguard_root, "zGuard") if zguard_root.exists() else []
    all_files = zos_files + zguard_files
    print(f"[audit_gen] Files: {len(all_files)} ({len(zos_files)} zOS + {len(zguard_files)} zGuard)")

    print("[audit_gen] Building graph...")
    graph = build_graph(all_files)

    print("[audit_gen] Writing notes...")
    # Track which vault folders have files for index generation
    folder_files: dict[Path, list] = defaultdict(list)

    for fi in all_files:
        write_file_note(vault, fi, graph)
        folder = note_path(vault, fi).parent
        folder_files[folder].append(fi)

    print("[audit_gen] Writing folder indices...")
    for folder, files in folder_files.items():
        write_folder_index(vault, folder, files, graph)

    print("[audit_gen] Writing Obsidian config...")
    write_obsidian_config(vault)

    total_loc = sum(fi.loc for fi in all_files)
    loc_violations = sum(1 for fi in all_files if fi.loc > 600)

    stats = {"files": len(all_files), "total_loc": total_loc, "loc_violations": loc_violations}
    write_home(vault, stats)

    print()
    print("─" * 50)
    for tag in TAG_COLORS:
        count = sum(1 for fi in all_files if fi.tag == tag)
        print(f"  {tag:<12} {count:>4} files")
    print(f"  {'---':<12} {'----'}")
    print(f"  {'total':<12} {len(all_files):>4} files  {total_loc:,} LOC")
    print(f"  LOC > 600:   {loc_violations}")
    print("─" * 50)
    print("[audit_gen] Done.")


if __name__ == "__main__":
    main()

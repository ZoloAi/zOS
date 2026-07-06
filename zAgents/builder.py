#!/usr/bin/env python3
"""
zAgents builder — reads src/*.md, outputs generated/ for all IDE targets.

Targets:
  generated/cursor/        → topic-split .mdc files with frontmatter (Cursor)
                             loaded lazily by glob — zero token cost until file opened
  generated/claude/        → Claude Code mirror:
    CLAUDE.md              → lean index (workflow + topic_refs) → ~/.claude/CLAUDE.md
    zolo/<topic>.md        → topic files → ~/.claude/zolo/<topic>.md
                             Claude reads on demand via topic_refs instructions
  generated/AGENTS.md      → flat concat, (see zolo-*.mdc) stripped — Codex/Aider/generic
                             written to workspace root only for non-Cursor workspaces

Cursor frontmatter is embedded in each src/ file as an HTML comment on line 1:
  <!-- cursor: description="..." alwaysApply=true -->
  <!-- cursor: description="..." globs="**/zUI.*.zolo" alwaysApply=false -->

Run:
  python -m zOS.zAgents.builder
  # or from zOS root:
  python zAgents/builder.py
"""

import json
import re
import sys
from pathlib import Path

# Strips Cursor-specific cross-references from flat builds.
# Catches both:
#   "(see zolo-raven.mdc)"          — parenthetical inline
#   "see zolo-data.mdc for ..."     — standalone sentence on its own line
_SEE_MDC_RE = re.compile(
    r'(\s*\(see zolo-[\w-]+\.mdc\)'           # parenthetical form
    r'|^see zolo-[\w-]+\.mdc[^\n]*$)',         # standalone line form
    re.IGNORECASE | re.MULTILINE
)

SRC_DIR = Path(__file__).parent / "src"
GEN_DIR = Path(__file__).parent / "generated"

CURSOR_HEADER_RE = re.compile(
    r'^<!--\s*cursor:\s*(.*?)\s*-->',
    re.IGNORECASE
)

ATTR_RE = re.compile(r'(\w+)=(?:"([^"]*?)"|(\S+))')


def _parse_cursor_header(line: str) -> dict | None:
    m = CURSOR_HEADER_RE.match(line.strip())
    if not m:
        return None
    attrs = {}
    for key, val_quoted, val_bare in ATTR_RE.findall(m.group(1)):
        attrs[key] = val_quoted if val_quoted else val_bare
    return attrs


def _strip_cursor_comment(content: str) -> str:
    lines = content.splitlines(keepends=True)
    if lines and CURSOR_HEADER_RE.match(lines[0].strip()):
        return "".join(lines[1:]).lstrip("\n")
    return content


def _build_mdc_frontmatter(attrs: dict) -> str:
    description = attrs.get("description", "zolo rules")
    always = attrs.get("alwaysApply", "true").lower() == "true"
    globs = attrs.get("globs", "")

    lines = ["---", f'description: {description}']
    if globs:
        if ',' in globs:
            glob_list = [g.strip() for g in globs.split(',')]
            lines.append(f'globs: {json.dumps(glob_list)}')
        else:
            lines.append(f'globs: {globs}')
    lines.append(f'alwaysApply: {"true" if always else "false"}')
    lines.append("---\n")
    return "\n".join(lines)


def _src_files() -> list[Path]:
    return sorted(SRC_DIR.glob("*.md"))


def build_cursor():
    """Generate topic-split .mdc files into generated/cursor/.

    The output dir is wiped first so renamed/removed src topics never leave
    orphan .mdc zombies that keep getting injected into every workspace.
    """
    out_dir = GEN_DIR / "cursor"
    if out_dir.exists():
        for stale in out_dir.glob("*.mdc"):
            stale.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    for src in _src_files():
        content = src.read_text(encoding="utf-8")
        first_line = content.splitlines()[0] if content.splitlines() else ""
        attrs = _parse_cursor_header(first_line)

        body = _strip_cursor_comment(content)
        stem = src.stem  # e.g. "01_zspark"
        # Preserve the src numeric prefix in the filename so the curated
        # ordering (00→NN) carries into .cursor/rules/ instead of going alpha.
        m = re.match(r'^(\d+)_(.+)$', stem)
        mdc_name = f"zolo-{m.group(1)}-{m.group(2)}.mdc" if m else f"zolo-{stem}.mdc"

        if attrs:
            frontmatter = _build_mdc_frontmatter(attrs)
        else:
            frontmatter = "---\nalwaysApply: false\n---\n\n"

        out_path = out_dir / mdc_name
        out_path.write_text(frontmatter + body, encoding="utf-8")
        print(f"  [cursor] {out_path.relative_to(GEN_DIR.parent)}")


def _is_cursor_only(content: str) -> bool:
    """Return True if the src file is marked cursorOnly=true (excluded from flat builds)."""
    first_line = content.splitlines()[0] if content.splitlines() else ""
    attrs = _parse_cursor_header(first_line)
    if not attrs:
        return False
    return attrs.get("cursorOnly", "false").lower() == "true"


def build_flat(filename: str):
    """Generate a single flat markdown file from all src/ files (skips cursorOnly=true)."""
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GEN_DIR / filename

    parts = []
    for src in _src_files():
        content = src.read_text(encoding="utf-8")
        if _is_cursor_only(content):
            continue
        body = _strip_cursor_comment(content).strip()
        parts.append(body)

    combined = "\n\n---\n\n".join(parts)
    combined = _SEE_MDC_RE.sub('', combined)
    out_path.write_text(combined + "\n", encoding="utf-8")
    print(f"  [flat]   {out_path.relative_to(GEN_DIR.parent)}")


# The src file used as the CLAUDE.md index body (workflow). Excluded from the
# per-topic files since its full content is the index itself.
_CLAUDE_INDEX_SRC = "00_workflow.md"


def build_claude():
    """Generate Claude Code mirror output into generated/claude/.

    Produces:
      generated/claude/CLAUDE.md        → lean index: workflow + topic_refs
      generated/claude/zolo/<topic>.md  → one file per src topic, no frontmatter

    Install target: ~/.claude/CLAUDE.md + ~/.claude/zolo/<topic>.md
    Claude reads topic files on demand via explicit topic_refs instructions.

    Dynamic (parity with build_cursor): every src/*.md becomes a topic file, and
    each file's cursor `description` header supplies the "when to read" hint. No
    hardcoded stem map — renaming/renumbering src files can never silently break
    the Claude build or leave orphan topics (the dir is wiped first).
    """
    out_dir = GEN_DIR / "claude"
    topics_dir = out_dir / "zolo"
    if topics_dir.exists():
        for stale in topics_dir.glob("*.md"):
            stale.unlink()
    topics_dir.mkdir(parents=True, exist_ok=True)

    # --- topic files (all src except the index source) ---
    topic_ref_lines = []
    for src in _src_files():
        if src.name == _CLAUDE_INDEX_SRC:
            continue
        stem = src.stem
        topic_slug = re.sub(r'^\d+_', '', stem)   # "03_navigation" → "navigation"
        content = src.read_text(encoding="utf-8")
        first_line = content.splitlines()[0] if content.splitlines() else ""
        attrs = _parse_cursor_header(first_line) or {}
        when_desc = attrs.get("description", topic_slug)
        body = _strip_cursor_comment(content).strip()
        body = _SEE_MDC_RE.sub('', body)
        out_path = topics_dir / f"{topic_slug}.md"
        out_path.write_text(body + "\n", encoding="utf-8")
        print(f"  [claude] {out_path.relative_to(GEN_DIR.parent)}")
        topic_ref_lines.append(
            f"    {when_desc} → read ~/.claude/zolo/{topic_slug}.md"
        )

    # --- index (CLAUDE.md) = workflow + topic_refs ---
    workflow = SRC_DIR / _CLAUDE_INDEX_SRC
    if not workflow.exists():
        print(f"  [claude] WARNING: {_CLAUDE_INDEX_SRC} not found — skipping CLAUDE.md")
        return
    index_body = _strip_cursor_comment(workflow.read_text(encoding="utf-8")).strip()
    index_body = _SEE_MDC_RE.sub('', index_body)

    topic_refs_block = (
        "\ntopic_refs:\n"
        "    syntax references live in ~/.claude/zolo/ — read the relevant file on demand:\n"
        + "\n".join(topic_ref_lines)
    )
    index_out = out_dir / "CLAUDE.md"
    index_out.write_text(index_body + topic_refs_block + "\n", encoding="utf-8")
    print(f"  [claude] {index_out.relative_to(GEN_DIR.parent)}")


def build_all():
    print("\n[zAgents] Building agent instruction files...\n")
    build_cursor()                # Cursor: topic-split .mdc, glob lazy-loaded
    build_claude()                # Claude Code: lean index + ~/.claude/zolo/ topic files
    build_flat("AGENTS.md")       # Codex/Aider/generic: full concat, no dead refs
    print("\n[zAgents] Build complete.\n")


if __name__ == "__main__":
    build_all()

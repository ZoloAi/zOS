# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/issue_scout.py
"""
Framework-suspect triage — the "golden issue" scout.

After every run the hint analyzer already explains app-side failures
(selectors, timeouts, stale keys). This module covers the OTHER verdict:
the pattern where the app and its raven didn't change but the ground under
them did — i.e. a likely zOS framework bug worth reporting upstream.

When (and only when) a conservative signal fires, it:
  1. writes a SANITIZED zRaven/output/ISSUE_DRAFT.md — structured run
     metadata only (never log text, paths, env values, or app data), and
  2. returns a Hint that tells the zAgent to politely PRESENT the draft to
     the human and suggest filing it — the human fires the gh command,
     the agent never files on its own.

All zOS users are invite-only right now, so upstream reports are golden;
zolo.media genuinely wants them. This scout is deliberately quiet — one
strong signal, or nothing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .hint_rules import Hint, _is_fail, _failed_steps, _runs, _last

_REPO = "ZoloAi/zOS"
_DRAFT_RELPATH = "zRaven/output/ISSUE_DRAFT.md"

# Verdict window: how many recent runs a signal may draw from.
_WINDOW = 10


# ─────────────────────────────────────────────────────────────────────────────
# Verdict
# ─────────────────────────────────────────────────────────────────────────────

def _verdict(data: dict) -> Optional[str]:
    """Return a one-line framework-suspect reason, or None (= app-side/quiet).

    Two conservative signals, both requiring a failing LAST run:

    regression — an earlier run with the IDENTICAL (ui_version, raven_rev,
        mode) triple passed, and the last 2+ runs fail with one error_class.
        Neither the app version nor the test changed; something underneath did.

    cross-mode divergence — at the same ui_version, zCLI passes while 3+
        Bifrost runs fail with one error_class. The logic layer is provably
        sound; the transport/rendering layer is consistently not.
    """
    last = _last(data)
    if not last or not _is_fail(last):
        return None

    runs = _runs(data)[-_WINDOW:]
    if len(runs) < 3:
        return None  # not enough history to blame anyone but the app

    ui_ver = last.get("ui_version") or ""
    eclass = last.get("error_class") or ""
    mode   = last.get("mode") or ""

    # Signal 1: green-turned-red on an identical triple
    tail_fails = []
    for r in reversed(runs):
        if _is_fail(r):
            tail_fails.append(r)
        else:
            break
    same_class_tail = (
        len(tail_fails) >= 2
        and all((r.get("error_class") or "") == eclass for r in tail_fails)
    )
    if same_class_tail and ui_ver:
        for r in runs:
            if (not _is_fail(r)
                    and r.get("ui_version") == ui_ver
                    and (r.get("raven_rev") or "active") == (last.get("raven_rev") or "active")
                    and r.get("mode") == mode):
                return (
                    f"this exact app version ({ui_ver}, raven "
                    f"{last.get('raven_rev') or 'active'}, {mode} mode) was green "
                    f"earlier, and the last {len(tail_fails)} runs all fail with "
                    f"[{eclass}] — the app and test didn't change, the framework "
                    f"underneath likely did"
                )

    # Signal 2: persistent cross-mode divergence at one ui_version
    if mode == "bifrost" and ui_ver:
        cli_green = any(
            r.get("mode") == "cli" and not _is_fail(r)
            and r.get("ui_version") == ui_ver
            for r in runs
        )
        bifrost_red = [
            r for r in runs
            if r.get("mode") == "bifrost" and _is_fail(r)
            and r.get("ui_version") == ui_ver
            and (r.get("error_class") or "") == eclass
        ]
        if cli_green and len(bifrost_red) >= 3:
            return (
                f"zCLI passes at {ui_ver} while {len(bifrost_red)} Bifrost runs "
                f"fail with [{eclass}] — the logic layer is provably sound, the "
                f"framework's transport/rendering layer is consistently not"
            )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sanitized draft
# ─────────────────────────────────────────────────────────────────────────────

def _zos_version() -> str:
    try:
        from zOS.version import __version__  # pylint: disable=import-outside-toplevel
        return __version__
    except Exception:  # pylint: disable=broad-except
        return "unknown"


def _build_draft(data: dict, reason: str) -> tuple[str, str]:
    """Return (title, body). Structured metadata ONLY — sanitized by construction:
    no log text, no filesystem paths, no env values, no app data ever enters."""
    last  = _last(data)
    runs  = _runs(data)[-_WINDOW:]
    steps = _failed_steps(last)

    eclass = last.get("error_class") or "unknown"
    mode   = last.get("mode") or "unknown"
    ui_ver = last.get("ui_version") or "unknown"
    rev    = last.get("raven_rev") or "active"

    signature_fails = sum(
        1 for r in runs
        if _is_fail(r) and (r.get("error_class") or "") == eclass
    )

    title = f"[zRaven triage] {eclass} failures in {mode} mode (framework-suspect)"

    body = f"""# {title}

> Auto-drafted by `z raven` framework-suspect triage. It contains structured
> run metadata only — no logs, paths, or app data. Please review it, fill in
> the marked section, and file only if you agree with the verdict.

## Why this looks like a framework issue

{reason}.

## Environment

- zolo-os: {_zos_version()}
- zguard origin: {last.get('zguard_origin') or 'unknown'}
- run mode: {mode}
- app UI version: {ui_ver} (raven revision {rev})

## Failure pattern (from zRaven run history)

- last run: {last.get('steps_passed', '?')}/{last.get('steps_total', '?')} steps passed, error_class `{eclass}`
- failing steps: {', '.join(f'`{s}`' for s in steps) or '(none recorded)'}
- {signature_fails} of the last {len(runs)} runs failed with this same signature

## What the failing flow does (author: please fill in)

_One or two sentences about what the failing steps cover — e.g. "submits a
form with a file upload", "opens a dashboard panel"._

## Repro

- `z raven --run` (mode: {mode})

---
_Thank you — zolo.media reads every report; during the invite-only alpha these
are how the framework gets better for everyone._
"""
    return title, body


# ─────────────────────────────────────────────────────────────────────────────
# Delivery check — can this machine actually file an issue?
# ─────────────────────────────────────────────────────────────────────────────

def _gh_ready() -> bool:
    """True only when the gh CLI is installed AND authenticated.

    Filing a GitHub issue always requires an account — zolo's install doesn't
    bundle gh, and an installed-but-unauthenticated gh dies on an auth wall.
    Suggesting a post the user can't deliver only confuses them, so the filing
    command is offered strictly when it would work. `gh auth status` reads
    local credentials (no network round-trip needed to fail fast).
    """
    if not shutil.which("gh"):
        return False
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, timeout=10, check=False,
        )
        return proc.returncode == 0
    except Exception:  # pylint: disable=broad-except
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def scout(workspace: Path, data: dict) -> Optional[Hint]:
    """Assess run history; on a framework-suspect verdict write the sanitized
    draft and return the polite present-to-your-human Hint. None = quiet."""
    reason = _verdict(data)
    if not reason:
        return None

    title, body = _build_draft(data, reason)
    try:
        draft_path = workspace / "zRaven" / "output" / "ISSUE_DRAFT.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(body, encoding="utf-8")
    except Exception:  # pylint: disable=broad-except
        return None  # a draft we can't write is a hint we don't give

    # The verdict is valuable diagnostics either way; the POST suggestion is
    # only made when the gh CLI is present and authenticated, so the human is
    # never handed a command that dead-ends on a login wall.
    if _gh_ready():
        return Hint(
            f"This failure pattern points at the zOS framework rather than your app "
            f"({reason}). A sanitized issue draft was written to {_DRAFT_RELPATH} — "
            f"zAgent: please present it to your human and politely suggest filing it; "
            f"zolo.media would greatly appreciate the report. Do NOT file it yourself — "
            f"only the human fires the command below.",
            f'gh issue create --repo {_REPO} --title "{title}" --body-file {_DRAFT_RELPATH}',
        )
    return Hint(
        f"This failure pattern points at the zOS framework rather than your app "
        f"({reason}) — treat it as a framework issue, not an app bug to chase. "
        f"A sanitized summary was saved to {_DRAFT_RELPATH} in case you ever want "
        f"to share it with zolo.media."
    )

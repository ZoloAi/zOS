# zShell Security Module Guide

> **Module:** `zOS/core/L3_Abstraction/p_zShell/shell_modules/shell_policy.py` (+ the safeguards it backs in `shell_cmd_shortcut.py`, `shell_cmd_auth.py`, `shell_cmd_comm.py`)  
> **Purpose:** The open-core, fail-closed safety layer for the shell — the single source of truth for what is sealed in a remote (Bifrost) session and how credentials are kept off the wire and out of history.

---

## Overview

zShell is fully open-core but is also a surface a **remote Bifrost client** can
reach. `shell_policy.py` is the SSOT that the router and the help system both
consume so the shell behaves safely by default. The *enforcement of the remote
boundary itself* (the Bifrost runtime, three-tier identity, and `ZTERMINAL_MODE`
execution policy) is **zGuard-sealed** — see the
[zBifrost Guide](../zBifrost_GUIDE.md). zShell consumes that boundary; it does not
define it.

> Trust model note: per the zOS docs-split rule, open-core documents the
> fail-closed *behavior*; the network-boundary *mechanism* lives in zGuard.

---

## 1. Bifrost seal-policy

`SEALED_IN_BIFROST` maps command types to the actions that are refused in a Bifrost
session:

| Command | Sealed actions |
|---------|----------------|
| `data` | `delete`, `drop`, `migrate` |
| `config` | `set`, `reset` |

`enforce_bifrost_seal(zos, parsed)` runs in the router **before dispatch**. If the
session is Bifrost and the `(type, action)` pair is sealed, it returns an error
dict instead of executing. The seal is **unconditional** in Bifrost (Bifrost is
always sandboxed — there is no operator override here). Read-only counterparts
(`data read/head/describe/status`, `config check/show/get`) stay available; local
zCLI sessions are unaffected.

`sealed_actions_for(zos, command_type)` exposes the same SSOT to the help layer so
the UX never advertises a sealed capability (see [help_GUIDE.md](help_GUIDE.md)).

---

## 2. Credential redaction

`redact_sensitive_command(command)` returns a history-safe, masked copy of a line
that carries inline secrets, or `None` when nothing is sensitive:

| Input | Stored in history |
|-------|-------------------|
| `auth login alice s3cret` | `auth login alice ***` |
| `auth apikey verify tok_…` | `auth apikey verify ***` |
| `auth apikey issue/revoke …` | unchanged (identity, not a secret) |

The REPL calls this from `_redact_history()` after each read
(see [runner_GUIDE.md](runner_GUIDE.md)). Complementing it,
`shell_cmd_auth._handle_login` **never** accepts a password on argv — it is always
collected via hidden `getpass`; an argv password is warned and ignored.

---

## 3. Shortcut path containment

`shell_cmd_shortcut.py` constrains `shortcut --save`/`--load`: a custom filename
resolves to a `.json` **inside the shortcuts directory**; absolute paths and `..`
traversal are refused (`path_not_allowed`). Loaded files are merged only as
validated `name → command` **string pairs** — malformed entries are dropped with a
warning, so an untrusted file cannot inject arbitrary session state.

---

## 4. Operator-gated host install

`shell_cmd_comm.py`'s `comm install --auto` shells out to a host package manager
only when `_operator_can_run_subprocess()` passes: a **local zCLI** session that has
explicitly opted in via `ZTERMINAL_MODE: trusted`. It is blocked in Bifrost and when
the mode is unset/sandboxed/disabled. Post-install service start delegates to
`zos.comm.start_service` (no direct subprocess), and the PostgreSQL service name is
sourced from zComm's `PostgreSQLService` (SSOT).

---

## API summary

| Symbol | Role |
|--------|------|
| `SEALED_IN_BIFROST` | SSOT map of sealed `(type → actions)` |
| `enforce_bifrost_seal(zos, parsed)` | Router pre-dispatch seal (→ error dict or `None`) |
| `sealed_actions_for(zos, type)` | Sealed actions for the current session (help filter) |
| `redact_sensitive_command(command)` | History-safe masked line, or `None` |

---

## See Also

- [executor_GUIDE.md](executor_GUIDE.md) — where the seal is enforced
- [runner_GUIDE.md](runner_GUIDE.md) — where history is redacted
- [help_GUIDE.md](help_GUIDE.md) — how sealed surfaces are hidden from the UX
- [zBifrost Guide](../zBifrost_GUIDE.md) — the zGuard-sealed network boundary

---

**[← Back to zShell Guide](../zShell_GUIDE.md)**

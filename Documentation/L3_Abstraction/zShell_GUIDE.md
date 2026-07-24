**[← Back to zBifrost Guide](zBifrost_GUIDE.md) | [Home](../../README.md) | [Next: zWalker Guide →](../L4_Orchestration/zWalker_GUIDE.md)**

---

# zShell

**zShell** is the **interactive command center (REPL)** of **zOS** (Layer 3 — Abstraction).
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

In one sentence: a text-based control panel where you drive *every* zOS subsystem —
data, auth, config, functions, files, workflows — through one consistent command
line, using the same `@.` zPath syntax you use everywhere else in zOS.

You don't wire commands to subsystems yourself. You type *what you want*; zShell
parses it, routes it to the right executor, and renders the result through
`zDisplay` — so the same command behaves correctly in the terminal **and** over a
live web (Bifrost) session.

---

## What zShell is in charge of

- **Reading and routing commands** — one parser + an O(1) command router send each
  line to the right subsystem executor.
- **Navigating the workspace** — `cd`/`pwd`/`ls`/`where` move around using zPaths,
  mirrored into the zSession working directory.
- **Driving subsystems** — `data`, `auth`, `config`, `func`, `load`, `open`,
  `comm`, `session`, `walker` are thin adapters onto the real subsystems.
- **Building multi-step workflows** — the **wizard canvas** lets you stage steps
  and run them together (see below).
- **Convenience** — persistent command history, user-defined `shortcut`s, and a
  built-in `help` system.

---

## The behavior to expect

zShell adapts to *where* it runs, from the same command set:

- **In the terminal (zCLI):** a normal blocking REPL. The full command surface is
  available, including host-affecting and destructive operations (you are the
  local operator).
- **Over the web (Bifrost):** the bridge renders the shell to a browser. zShell is
  **always sandboxed** here — destructive and host-mutating commands are sealed
  (see [Safety](#safety-what-is-sealed-in-a-remote-session)), and the help surface
  only advertises what the remote client may actually run.

Start it from your project:

```bash
z shell            # launch the interactive REPL
# or, from the zOS menu:
zolo               # → "Enter zShell"
```

```text
zOS> where                 # show workspace + zPath
zOS> ls @.zTestSuite.demos # list a path
zOS> help data             # detailed help for a command
zOS> exit                  # leave (also: quit, q)
```

---

## Commands at a glance

| Group | Commands | What they do |
|-------|----------|--------------|
| **Navigation** | `where`, `cd`, `pwd`/`cwd`, `ls` (`list`/`dir`) | Move around the workspace with zPaths |
| **Resources** | `load`, `data` | Load schemas/UI; run CRUD/DDL/migrations via zData |
| **Identity** | `auth` | `login` (hidden prompt), `logout`, `status`, `apikey issue/verify/revoke` |
| **Config** | `config` | `check`, `show`, `get`, `set`, `reset` |
| **Execution** | `func`, `open`, `comm`, `session`, `walker` | Call functions, open files/URLs, manage services, inspect session, enter UI mode |
| **Workflow** | `wizard` | Wizard canvas: `--start`, `--show`, `--run`, `--clear`, `--stop` |
| **Convenience** | `shortcut`, `help`, `echo` | User shortcuts, help, print |
| **Special** | `exit`/`quit`/`q`, `clear`/`cls`, `tips`, `#` | Session control; `#` lines and blank input are ignored |

Type `help` for the list, or `help <command>` for usage and examples. The exact set
is derived from the command registry — `help` is always the source of truth.

---

## Wizard canvas

The wizard canvas stages multiple commands and runs them as one unit, so related
operations don't half-complete:

```text
zOS> wizard --start
zOS> data insert users --model $db --fields name --values "Alice"
zOS> data insert posts --model $db --fields author --values "Alice"
zOS> wizard --show      # review staged steps
zOS> wizard --run       # execute together
zOS> wizard --stop      # leave canvas mode
```

Execution is delegated to **zWizard**; zShell only provides the canvas UX and the
per-step command bridge.

---

## Safety: what is sealed in a remote session

zShell is fully open-core, but it is also a surface a **remote Bifrost client** can
reach. The open-core behavior you can rely on, with zGuard absent or present:

- **Destructive/mutating ops are sealed over Bifrost.** In a Bifrost session
  `data delete` / `data drop` / `data migrate` and `config set` / `config reset`
  are refused before dispatch — read-only counterparts stay available. A remote
  client cannot destroy or reconfigure the host through the shell.
- **Credentials never travel on argv or into history.** `auth login` always
  collects the password at a hidden prompt; a password typed positionally is
  ignored, and credential lines are redacted from the readline history file.
- **`shortcut --save/--load` is path-contained.** Custom filenames resolve to a
  `.json` *inside* the shortcuts directory; absolute paths and `..` traversal are
  refused, and loaded files are accepted only as `name → command` string pairs.
- **Host package installs are operator-gated.** `comm install --auto` runs a host
  package manager only on a **local zCLI** session that has explicitly opted in via
  `ZTERMINAL_MODE: trusted`; it is blocked in Bifrost and when unset.

These are open-core **fail-closed defaults**. The *enforcement of the remote
boundary itself* — the Bifrost runtime, the three-tier identity, and the
`ZTERMINAL_MODE` execution policy — is the **zGuard-sealed** network layer (see the
[zBifrost Guide](zBifrost_GUIDE.md)); the shell consumes that
boundary rather than defining it.

> App-author's own risk (same class as a Flask app shipping `DEBUG=True`): an
> operator who sets `ZTERMINAL_MODE: trusted` and then exposes the shell to
> untrusted input has opened that door themselves.

---

## Under the hood

zShell is a **facade** (`zShell.run_shell()` / `execute_command()` / `show_help()`)
over a small set of open-core modules: a REPL runner, a command router, one thin
executor per command, the wizard canvas, the help system, and shared
helpers/constants.

```python
from zOS.L3_Abstraction.p_zShell import zShell

shell = zShell(z)              # z = your zOS instance
shell.run_shell()              # interactive REPL
shell.execute_command("data read users --model @.zSchema.users")
shell.show_help()
```

Source: `zOS-OpenCore/core/L3_Abstraction/p_zShell/`.

---

## Module map

This guide is a **facade overview**. For deep dives into a specific module, see the
guides in `zShell_Guides/`:

| Group | Module | What it does | Deep dive |
|-------|--------|--------------|-----------|
| **Core** | `shell_runner` | REPL loop, prompts, history, redaction, special commands | [runner_GUIDE.md](zShell_Guides/runner_GUIDE.md) |
| | `shell_executor` | Parse, route (O(1) map), enforce the Bifrost seal | [executor_GUIDE.md](zShell_Guides/executor_GUIDE.md) |
| **Commands** | `commands/` | One thin executor per command (UI-adapter pattern) | [commands_GUIDE.md](zShell_Guides/commands_GUIDE.md) |
| **Workflow** | `wizard_canvas` | Stage steps and run them together via zWizard | [wizard_canvas_GUIDE.md](zShell_Guides/wizard_canvas_GUIDE.md) |
| **Help** | `shell_help` (+ `shell_cmd_help`) | Welcome/tips/help, mode-aware filtering | [help_GUIDE.md](zShell_Guides/help_GUIDE.md) |
| **Safety** | `shell_policy` (+ shortcut/auth/comm) | Bifrost seal, credential redaction, path/subprocess gates | [security_GUIDE.md](zShell_Guides/security_GUIDE.md) |
| **Shared** | `shell_paths`, `command_helpers`, `executor_constants`, `zshell_constants` | zPath SSOT, arg helpers, canonical keys/colors | [internals_GUIDE.md](zShell_Guides/internals_GUIDE.md) |

---

## Try it

```bash
z shell
zOS> help          # see the live command set
zOS> where         # confirm your workspace
zOS> ls            # explore
```

> Building on zShell: data operations are documented in the
> [zData Guide](zData_GUIDE.md); the web bridge it renders through is
> the [zBifrost Guide](zBifrost_GUIDE.md); multi-step workflows are in
> the [zWizard Guide](zWizard_GUIDE.md).

---

**[← Back to zBifrost Guide](zBifrost_GUIDE.md) | [Home](../../README.md) | [Next: zWalker Guide →](../L4_Orchestration/zWalker_GUIDE.md)**

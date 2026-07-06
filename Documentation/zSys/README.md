# zSys — Documentation

Technical index for the **Layer-0 system utilities** — the grab-bag of crucial, *pre-boot* helpers that live at `core/zSys/` and are shared by the entire runtime before (and beneath) the layered subsystems L1–L4 exist.

Unlike the layer clusters (L1 Foundation, L2 Handling, …), `zSys` is **not a runtime boot stage** and **not a single subsystem**. It is the **floor** every layer stands on: logging, the CLI entrypoints, install/shutdown lifecycle, error rendering, formatting, and accessibility. Documenting it separately keeps these cross-cutting utilities from being mistaken for any single layer's concern.

> **Layer-0 contract:** `zSys/*` runs **pre-boot** (before the `zOS` instance / `a_zConfig` exist) and in standalone contexts (WSGI workers). The core utilities therefore **never import `zOS.*` at module top-level** — only the lazy, post-boot `cli/` commands do (`import-outside-toplevel`). When a token must be shared between a `zSys` util (L0) and a foundation subsystem (L1+), the **SSOT lives at the lowest consumer (here, in `zSys`)** and **L1 imports DOWN** — never the reverse. `zVocabulary` is only viable for tokens whose lowest consumer is L1+.

| Member | Code | What it is | Guide |
|--------|------|------------|-------|
| **Logger** | `core/zSys/logger/` | Pre-boot + standalone logging: one canonical format, a buffering bootstrap logger, log-level + deployment-mode parsing, custom `SESSION` level | [logger_GUIDE](logger_GUIDE.md) |
| **Shutdown** | `core/zSys/shutdown/` | Graceful teardown: reverse-order subsystem cleanup (fail-safe + idempotent) + SIGINT/SIGTERM handlers (runner-aware exit) | [shutdown_GUIDE](shutdown_GUIDE.md) |
| **Errors** | `core/zSys/errors/` | Hinted exceptions + auto-registration, the interactive `zTraceback` UI, `ExceptionContext`, and an init-order validation guard | [errors_GUIDE](errors_GUIDE.md) |
| **Formatting** | `core/zSys/formatting/` | `Colors` ANSI SSOT, the pre-zDisplay `print_ready_message` banner, and the zTheme-class → ANSI bridge | [formatting_GUIDE](formatting_GUIDE.md) |
| **Accessibility** | `core/zSys/accessibility/` | Emoji → human/screen-reader text, mode-aware Bootstrap-Icons rendering, and the allowlist sanitizers closing the web XSS seam | [accessibility_GUIDE](accessibility_GUIDE.md) |
| _cli_ | `core/zSys/cli/` | `z` command surface (scaffold/install/push/migrate/raven/…) | _forthcoming_ |
| _install_ | `core/zSys/install/` | Install-type detection + setup | _forthcoming_ |

---

## logger — pre-boot & standalone logging (`from zSys.logger import …`)

The first thing `main.py` touches and the only logger available before the framework exists. It defines **one canonical log line** (`format_log_message`) reused by Bootstrap, Framework, App, and standalone loggers, buffers pre-boot messages until the framework logger is ready, and parses log-level + deployment-mode out of zSpark. It is a **pure sink** — message strings flow in, formatted text flows out; it executes nothing.

**Public surface (selected):** `BootstrapLogger`, `ConsoleLogger`, `UnifiedFormatter`, `format_log_message`, `format_bootstrap_verbose`, `get_log_level_from_zspark`, `resolve_deployment_from_zspark` / `is_production_from_zspark` / `is_testing_from_zspark`, `ensure_session_level`, plus the `DEPLOYMENT_*` and `LOG_LEVEL_*` vocabulary.

**Guide split:** the [logger_GUIDE](logger_GUIDE.md) is a facade overview; per-cluster deep dives live in [`logger_Guides/`](logger_Guides/) — [formats](logger_Guides/formats_GUIDE.md), [bootstrap](logger_Guides/bootstrap_GUIDE.md), [config](logger_Guides/config_GUIDE.md), [runtime](logger_Guides/runtime_GUIDE.md).

> **Trust:** fully open-core, **CLEAN — no zGuard seam**. No `eval`/`exec`/`compile`/`subprocess`/`pickle`/`os.system`/network/bind. The only file write is `bootstrap.emergency_dump` → a **fixed-name** `.zos-bootstrap-error.log` in `Path.cwd()`, wrapped in try/except (fail-safe), with **no user-controlled path**. Foreign content reaches the logger only as **message strings** (never executed). Residual **LOW / accepted** info-disclosure: the bootstrap buffer / emergency dump / `--verbose` print pre-boot content verbatim — redaction is the *caller's* responsibility, already hardened at the higher layers (`o_zShell`, `r_zRaven`, `j_zDialog`).

**Code:** `core/zSys/logger/` (`formats`, `constants`, `levels`, `bootstrap`, `console`, `config`, `execution_context`).

---

## shutdown — graceful teardown (`from zSys.shutdown import …`)

Two functions the engine wires at boot. `perform_shutdown(zos)` closes subsystems in **reverse init order** (WebSocket → HTTP → Database → Logger), each step wrapped in an `ExceptionContext` so a failure never halts the rest, and **idempotent** via `zos._shutdown_in_progress`. `register_signal_handlers(zos)` maps `SIGINT`/`SIGTERM` to that teardown — on the **main thread only** — and exits the process cleanly, except when `ZRAVEN_RUNNER=1` (so the test runner's post-run work isn't bypassed). Every status glyph, console line, and log/error string is single-sourced in `shutdown_constants.py`.

**Public surface (selected):** `perform_shutdown(zos)` → `Dict[str, bool] | None`; `register_signal_handlers(zos)`; the `SIGNAL_*` / `SHUTDOWN_*` / `LOG_*` / `ERROR_*` vocabulary.

**Guide split:** the [shutdown_GUIDE](shutdown_GUIDE.md) is a facade overview; per-cluster deep dives live in [`shutdown_Guides/`](shutdown_Guides/) — [cleanup](shutdown_Guides/cleanup_GUIDE.md), [signals](shutdown_Guides/signals_GUIDE.md).

> **Trust:** fully open-core, **CLEAN — no zGuard seam**. No `eval`/`exec`/`subprocess`/`pickle`/network/bind/file-write. Process termination (`sys.exit`) is **OS-signal-driven, not network-reachable** (SIGINT/SIGTERM, main thread, suppressed under `ZRAVEN_RUNNER`) — mirrors the `p_zWalker` local-only-exit posture. Fail-safe + foreign-content-free (operates only on the live `zos` instance).

**Code:** `core/zSys/shutdown/` (`cleanup`, `signals`, `shutdown_constants`).

---

## errors — exceptions + diagnostics (`from zSys.errors import …`)

A family of hinted exceptions (`zCLIException` + 13 subclasses) that each carry a `message`, an actionable `hint`, and a debug `context`, and **auto-register** with the current `zos.zTraceback` on raise (thread-local `get_current_zos()`, **failing silently** if no context). `zTraceback` is the handler: it installs a custom excepthook, logs with full traceback, and — when `session[zTraceback]` is enabled — launches the interactive **Walker traceback UI** (inheriting the parent's deployment mode + log level); every "no logger / no zos / UI failed" path degrades to one `_emergency_print` to stderr. `ExceptionContext` wraps a risky operation (log + suppress/reraise), and `validate_zos_instance` is a tiny init-order guard. Traceback UI labels/colors/prompts + the fallback strings are single-sourced in `errors_constants.py`.

**Public surface (selected):** `zCLIException` (+ `SchemaNotFoundError`, `ValidationError`, `AuthenticationRequiredError`, …); `zTraceback`; `ExceptionContext`; `display_error_summary` / `display_full_traceback` / `display_formatted_traceback`; `validate_zos_instance` / `validate_zcli_instance`.

**Guide split:** the [errors_GUIDE](errors_GUIDE.md) is a facade overview; per-cluster deep dives live in [`errors_Guides/`](errors_Guides/) — [exceptions](errors_Guides/exceptions_GUIDE.md), [traceback](errors_Guides/traceback_GUIDE.md), [validation](errors_Guides/validation_GUIDE.md).

> **Trust:** fully open-core, **CLEAN — no zGuard seam**. No `eval`/`exec`/`subprocess`/`pickle`/network/bind/file-write — only `sys.excepthook = …` and an in-method `import zCLI` to launch the UI. The interactive excepthook is **gated + local-CLI-only** (off unless `session[zTraceback]`), not network-reachable. Auto-registration is `try/except: pass` so it never breaks a raise. **Secret-safe (E5):** `ValidationError` stores a redacted `<type len=N>` descriptor, never the raw rejected value, so secrets can't reach logs/UI. Layer-0 discipline: canonical session keys (`zOS.zVocabulary`) + `DEPLOYMENT_DEFAULT` (`zSys.logger`) are lazy-imported inside post-boot methods (E2).

**Code:** `core/zSys/errors/` (`exceptions`, `traceback`, `validation`, `errors_constants`).

---

## formatting — terminal color + banner SSOT (`from zSys.formatting import …`)

The terminal-style floor. `Colors` is the **one place** ANSI escapes are defined (every other module references `Colors.*`, never raw `\033[…]`). `print_ready_message` prints a width-safe "Ready" banner **before zDisplay exists** — detecting terminal width (`COLUMNS` → `get_terminal_size` → `tput cols`), clamping to `[60,120]`, ASCII separators only — and **self-suppresses in Production/Testing** by resolving the deployment mode from the live zSpark via the logger SSOT (explicit flags override for `--verbose`). `ztheme_to_ansi` bridges web styling to the terminal: it maps zTheme CSS classes (`zText-*`, `zLink-*`, `zFont-*`, `zBg-*`) to ANSI for the zDisplay markdown renderer, and — because unknown classes return `''` — doubles as an **escape-injection allowlist**.

**Public surface (selected):** `Colors`; `print_ready_message(label, color=…, is_production=None, is_testing=None)`; `map_ztheme_class_to_ansi` / `map_ztheme_classes_to_ansi` / `get_reset_code` / `colorize_with_class`.

**Guide split:** the [formatting_GUIDE](formatting_GUIDE.md) is a facade overview; per-cluster deep dives live in [`formatting_Guides/`](formatting_Guides/) — [colors](formatting_Guides/colors_GUIDE.md), [terminal](formatting_Guides/terminal_GUIDE.md), [ztheme_to_ansi](formatting_Guides/ztheme_to_ansi_GUIDE.md).

> **Trust:** fully open-core, **CLEAN — no zGuard seam**. No `eval`/`exec`/`pickle`/network/bind/file-write. The one `subprocess.run(["tput","cols"])` is argv-safe (`shell=False`, no input, `.isdigit()`-validated). The zTheme mapper is its own **ANSI-injection allowlist** (unknown class → `''`). Layer-0 discipline: the deployment-resolution reaches (`get_current_zos`, `zSys.logger.config`) are lazy, in-function, and try/except-guarded so they never break init.

**Code:** `core/zSys/formatting/` (`colors`, `terminal`, `ztheme_to_ansi`).

---

## accessibility — accessible output + icon rendering (`from zSys.accessibility import …`)

The accessible-output floor. `emoji_descriptions` turns emoji into human-readable text (Unicode CLDR) for screen readers and `[bracketed]` zCLI fallbacks. `icon_mapper.render_for_mode` renders Bootstrap Icons per output mode — `<i class="bi bi-…">` HTML in **zBifrost**, curated emoji → Unicode → `[text]` in **zCLI** — defaulting the mode to the canonical `zVocabulary.ZMODE_ZBIFROST`. Both data files live **co-located** at `core/zSys/accessibility/data/` (`emoji-a11y.en.json`, `bootstrap-icons.json`) — folded in from the former standalone `zSys/data/` since this package is their only consumer — and ship in the wheel via `setup.py` `package_data={"zSys.accessibility": ["data/*.json"]}`. They load **once, lazily**, through one shared `_data.load_data_json` resolver (no file access at import; graceful `{}` on error). Because the web branch emits raw markup from `.zolo`-authored `name`/`size`/`color`/`_zClass`, `sanitize.py` is the **SSOT allowlist** — icon names `^[a-z0-9-]+$`, class tokens `^[A-Za-z0-9_-]+$`, **fail-closed** — applied at both the mapper and the `e_zDisplay` `icon_renderer` `_zClass` seam.

**Public surface (selected):** `get_emoji_descriptions()` / `EmojiDescriptions`; `get_icon_mapper()` / `IconMapper`; `safe_icon_name` / `safe_class_attr`.

**Guide split:** the [accessibility_GUIDE](accessibility_GUIDE.md) is a facade overview; per-cluster deep dives live in [`accessibility_Guides/`](accessibility_Guides/) — [emoji_descriptions](accessibility_Guides/emoji_descriptions_GUIDE.md), [icon_mapper](accessibility_Guides/icon_mapper_GUIDE.md), [sanitize](accessibility_Guides/sanitize_GUIDE.md).

> **Trust:** open-core, but the **first zSys util with a real V3 seam** — the zBifrost path emits HTML from foreign `.zolo` content. **A4 stored-XSS is closed** by allowlist sanitizers at both emission seams (mapper + `icon_renderer` `_zClass`), fail-closed (invalid name → inert HTML-escaped `[text]`, not an `<i>` tag). The terminal path is inert (text/emoji), so it needs no guard. No `eval`/`exec`/`subprocess`/`pickle`/network/bind; data loads read-only via one fixed resolver. Layer-0 discipline: stdlib + siblings at top, `ZMODE_ZBIFROST` lazy-imported inside `render_for_mode` (A3). Test moved out of the shipped wheel (A5).

**Code:** `core/zSys/accessibility/` (`emoji_descriptions`, `icon_mapper`, `sanitize`, `_data`).

---

## Conventions (for agents)

- **Pre-boot safe:** core `zSys` utilities import stdlib + sibling `zSys.*` only — never `zOS.*` at top-level (lazy imports inside post-boot `cli/` commands are the sole exception).
- **SSOT lives at the lowest consumer:** a value shared by L0 and L1 is owned in `zSys` and imported *down* by L1 (e.g. `from zSys.logger import DEPLOYMENT_KEYS`). Promote to root `zVocabulary` only when L1+ is the lowest consumer.
- **One format truth:** all logging output flows through `format_log_message`; colors come from the `Colors` SSOT (`zSys.formatting`) — no raw ANSI escapes in logic.
- **Sinks don't redact:** the logger formats and emits; secret redaction is owned by the *calling* subsystem.
- **Vault parity:** the `zVault-zCode/` graph mirrors these files; links follow the **repo tree** (structure), not domain/logic.

**See also:** [L0 Core docs](../L0_Core/README.md) · [L1 Foundation docs](../L1_Foundation/README.md) · code-side: `core/zSys/`

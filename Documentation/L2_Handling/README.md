# L2 Handling — Documentation

Technical index for the **Handling layer** documentation cluster: the subsystems that sit on top of the Foundation layer (L1) and turn raw input, files, and declarations into resolved paths, parsed structures, rendered output, dispatched calls, and authorized actions.

This README is the **technical entry point** to the L2 guides. For a high-level, code-side orientation of the layer, see [`core/L2_Handling/README.md`](../../core/L2_Handling/README.md). For the Foundation layer beneath it, see [L1 Foundation docs](../L1_Foundation/README.md).

| Order | Subsystem | Facade | Main guide | Status |
|-------|-----------|--------|------------|--------|
| **d** | `d_zParser` | `z.parser` | [zParser_GUIDE](zParser_GUIDE.md) · [zParser_Guides/](zParser_Guides/) | **Migrated + refreshed** |
| **e** | `e_zDisplay` | `z.display` | [zDisplay_GUIDE](zDisplay_GUIDE.md) · [zDisplay_Guides/](zDisplay_Guides/) | **Migrated + refreshed** |
| **f** | `f_zAuth` | `z.auth` | [zAuth_GUIDE](zAuth_GUIDE.md) · [zAuth_Guides/](zAuth_Guides/) | **Migrated + refreshed** |
| **g** | `g_zDispatch` | `z.dispatch` | [zDispatch_GUIDE](zDispatch_GUIDE.md) · [zDispatch_Guides/](zDispatch_Guides/) | **Migrated + refreshed** |
| **h** | `h_zNavigation` | `z.navigation` | [zNavigation_GUIDE](zNavigation_GUIDE.md) · [zNavigation_Guides/](zNavigation_Guides/) | **Migrated + refreshed** |
| **i** | `i_zFunc` | `z.func` | [zFunc_GUIDE](zFunc_GUIDE.md) · [zFunc_Guides/](zFunc_Guides/) | **Migrated + refreshed** |
| **j** | `j_zDialog` | `z.dialog` | [zDialog_GUIDE](zDialog_GUIDE.md) · [zDialog_Guides/](zDialog_Guides/) | **Migrated + refreshed** |
| **k** | `k_zOpen` | `z.open` | [zOpen_GUIDE](zOpen_GUIDE.md) · [zOpen_Guides/](zOpen_Guides/) | **Migrated + refreshed** |

> **Migration status:** the Handling layer is being reorganized one subsystem at a time (same pattern as L1 Foundation). Only the subsystem audited and updated for the current pass moves into this cluster; the rest keep their guides in the `Documentation/` root until their turn. **`d_zParser`, `e_zDisplay`, `f_zAuth`, `g_zDispatch`, `h_zNavigation`, `i_zFunc`, `j_zDialog`, and `k_zOpen` are migrated.**

> **Root vocabulary:** cross-subsystem protocol literals (session-dict keys, file-type ids, path symbols, zMachine prefixes, file extensions) are single-sourced in the root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) module (`core/zVocabulary.py`). L2 subsystems draw from it instead of re-declaring; their historical constant names remain as thin aliases.

---

## d_zParser — parsing & path resolution (`z.parser`)

The unified parsing interface for zOS: path resolution, command parsing, file content parsing, plugin-syntax parsing, expression evaluation, and declarative zVaFile parsing — behind one facade.

**Public surface (selected):** `zPath_decoder`, `identify_zFile`, `parse_file_content` / `parse_yaml` / `parse_json`, `parse_command`, `is_plugin_invocation` / `parse_plugin_invocation`, `zExpr_eval`, `parse_ui_file` / `parse_schema_file` / `parse_config_file`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `path/` | zPath / zMachine / symbol resolution, file identification | [path_GUIDE](zParser_Guides/path_GUIDE.md) |
| `file/` | YAML/JSON parsing, format detection, RBAC transformation | [file_GUIDE](zParser_Guides/file_GUIDE.md) |
| `commands/` | Command router + 20+ type-specific parsers | [commands_GUIDE](zParser_Guides/commands_GUIDE.md) |
| `plugin/` | Plugin-invocation detection & syntax parsing (primitives) | [plugin_GUIDE](zParser_Guides/plugin_GUIDE.md) |
| `vafile/` | zVaFile parsing (UI / Schema / Config / Generic + validation) | [vafile_GUIDE](zParser_Guides/vafile_GUIDE.md) |
| `parser_utils` / `parser_functions` | Expression eval, dotted paths, function-path parsing | [utils_GUIDE](zParser_Guides/utils_GUIDE.md) |
| `parser_trust` | Path-trust gate (zGuard seam) | *(in main guide → Security & trust)* |
| `shared/` | Argument splitting + constants (vocab from root `zVocabulary`) | *(built-in)* |

> **Security:** content is parsed with `yaml.safe_load` / stdlib `json` only (no `eval`/`exec`). Resolved paths that get read pass through `parser_trust.verify_path_trust()` before file access. Open-core falls back to permissive (`try: from zguard.parser.path_trust… / except ImportError`); installing `zguard` seals the same seam. A denied path raises `PathTrustError` (propagated unwrapped).

> **Scope:** zParser provides parsing **primitives only**. Plugin loading/caching/execution belongs to `zFunc`; command execution belongs to `zShell`. zParser detects and parses syntax; upper layers act on it.

**Code:** `core/L2_Handling/d_zParser/zParser.py` (facade) + `parser_modules/`.

---

## e_zDisplay — rendering & input (`z.display`)

Professional terminal output and input behind one unified, event-driven facade: text, headers, tables, progress bars, spinners, menus, selections, links, media, and system UI (`zDeclare`/`zSession`/`zMenu`/`zDialog`). Dual-mode: zCLI (terminal) and zBifrost (browser/WebSocket).

**Public surface (selected):** `text`, `header`, `code`, `selection`, `button`, `zURL`, `list`/`dl`/`json`/`zTable`, `progress_bar`/`spinner`/`swiper`, `zDeclare`/`zSession`/`zMenu`/`zDialog`, plus the unified `handle(event_dict)` router.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `io/` | Terminal I/O primitives (raw, line, block, input) | [io_GUIDE](zDisplay_Guides/io_GUIDE.md) |
| `basic/` | Core event logic (outputs, inputs, signals) | [basic_GUIDE](zDisplay_Guides/basic_GUIDE.md) |
| `compounds/` | Interactive widgets (selection, buttons, links) | [compounds_GUIDE](zDisplay_Guides/compounds_GUIDE.md) |
| `advanced/` | Markdown, progress bars, spinners, tables | [advanced_GUIDE](zDisplay_Guides/advanced_GUIDE.md) |
| `system/` | System UI (zDeclare, zMenu, zDialog, zSession) | [system_GUIDE](zDisplay_Guides/system_GUIDE.md) |
| `api/` | Convenience methods (backward compatibility) | [api_GUIDE](zDisplay_Guides/api_GUIDE.md) |
| `utils/` | Pure utilities, **mode detection SSOT** (`mode_helper`) | [utils_GUIDE](zDisplay_Guides/utils_GUIDE.md) |
| `sandbox/` | zTerminal local exec + `display_trust` (zGuard seam) | *(in main guide → zTerminal & trust)* |

> **zTerminal security (fail-closed):** `zTerminal` runs code on the operator's **local machine** (zCLI mode) — it is **not** a secure sandbox. Local execution is OFF unless the operator explicitly declares `ZTERMINAL_MODE: sandboxed` (Python only) or `trusted` in zEnv; absent/`disabled`/unknown ⇒ no execution. This removes the silent-auto-run risk on checked-out repos containing foreign `zTerminal` content. Bifrost mode short-circuits here and is enforced by the sealed WebSocket handler. `sandbox/display_trust.verify_terminal_exec()` is a seam on top of the config gate: **open-core ships only the permissive fallback** (no-op without zGuard); installing zGuard seals it (denial → `TerminalTrustError`). The sealed policy and its fork-resistance are **proprietary — see the private zGuard docs** (contact admin / `z patch`).

> **SSOT:** mode protocol values (`zCLI`/`zBifrost`) alias root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) `ZMODE_*`; `mode_helper` is the single source for mode detection (`is_bifrost_mode`/`is_terminal_mode`/`get_mode` + `TERMINAL_MODES`). `Walker`/empty modes are zDisplay-local. Optional `zlsp` escape-decoding is guarded (renders degrade, never crash, when `zlsp` is absent).

**Code:** `core/L2_Handling/e_zDisplay/zDisplay.py` (facade) + `zDisplay_modules/`.

---

## f_zAuth — authentication & authorization (`z.auth`)

Three-tier authentication (zSession / Application / Dual) with bcrypt password
security, git-like persistent machine identity, and context-aware RBAC. **The
first subsystem split open / closed by design:** local/standard auth is open-core;
zCloud ecosystem auth is sealed in zGuard (Type A2).

**Public surface (selected):** `login`/`logout`/`status`/`is_authenticated`/`get_credentials`, `authenticate_app_user`/`switch_app`/`get_app_user`, `set_active_context`/`get_active_user`, `has_role`/`has_permission`/`grant_permission`/`revoke_permission`, `hash_password`/`verify_password`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `security/` | bcrypt hashing + timing-safe verify (12 rounds, 72-byte) | [security_GUIDE](zAuth_Guides/security_GUIDE.md) |
| `persistence/` | machine identity at rest (`zConfig.identity.zolo`) — **sealed seam** | [persistence_GUIDE](zAuth_Guides/persistence_GUIDE.md) |
| `logic/authentication/` | three-tier logic, contexts, multi-app | [authentication_GUIDE](zAuth_Guides/authentication_GUIDE.md) |
| `logic/rbac/` | context-aware roles & permissions (SQLite) | [rbac_GUIDE](zAuth_Guides/rbac_GUIDE.md) |
| `actions/` | declarative `zLogin`/`zLogout` handlers | [actions_GUIDE](zAuth_Guides/actions_GUIDE.md) |
| `api/` (delegates) | public facade composition (16 methods) | [delegates_GUIDE](zAuth_Guides/delegates_GUIDE.md) |
| `logic/authentication/{api_key_auth,remote_authentication,boot_identity}`, `persistence/identity_store` | **zGuard seams** (PAT / zCloud / boot / identity-at-rest) | *(in main guide → Trust Model & zGuard Seams)* |

> **Open/closed split (Type A2 — fail-closed):** unlike the permissive parser/display
> seams, the zAuth ecosystem seams **fail closed** — `api_key_auth`,
> `remote_authentication`, `boot_identity` raise "z patch" without zGuard;
> `identity_store` degrades to no-op (boots anonymous). They never fabricate an
> identity. **zGuard binary ≠ login:** with the binary present, anonymous users
> still get the full runtime. The sealed mechanisms (PAT `sha256` ledger model,
> zCloud handshake, keychain-at-rest, boot cascade) are **proprietary — see the
> private zGuard auth docs** (`zGuard/Documentation/auth/`; contact admin / `z patch`).

> **SSOT:** auth session keys (`SESSION_KEY_ZAUTH`, `ZAUTH_KEY_*`) are sourced from
> `a_zConfig`; the protocol mode literal aliases root `zVocabulary` `ZMODE_ZCLI`.
> bcrypt cost/limits live in `auth_constants`.

> **Persistence note:** Tier-1 identity is the `zConfig.identity.zolo` file (read
> once at boot) — **not** a SQLite session DB (the old `SessionPersistence` path is
> retired). RBAC *permissions* still use SQLite (`"auth"` label).

**Code:** `core/L2_Handling/f_zAuth/zAuth.py` (facade) + `zAuth_modules/`.

---

## g_zDispatch — command routing (`z.dispatch`)

The universal command router: parses command keys (with modifiers), detects the
command type, and routes to the owning subsystem. **Pure routing layer** — no
business logic, no UI rendering, no data operations; it delegates everything and
focuses on flow control. Dual-mode (zCLI / zBifrost).

**Public surface (selected):** `handle(zKey, zHorizontal, context, walker)` (facade) and the standalone `handle_zDispatch(...)`; component access via `z.dispatch.modifiers` / `z.dispatch.launcher`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `dispatch_launcher` / `dispatch_helpers` | command routing + mode helpers | [launcher_GUIDE](zDispatch_Guides/launcher_GUIDE.md) |
| `dispatch_modifiers` + `modifiers/` | `^ ~ * !` detection (bounce, menu, required) | [modifiers_GUIDE](zDispatch_Guides/modifiers_GUIDE.md) |
| `handlers/` | subsystem integration (auth, CRUD, data, navigation, routing, subsystems, export, import) | [handlers_GUIDE](zDispatch_Guides/handlers_GUIDE.md) |
| `commands/` | string command parsing (`zFunc(...)`, wizard detection) | [commands_GUIDE](zDispatch_Guides/commands_GUIDE.md) |
| `expansion/` | shorthand + plural + organizational expansion | [expansion_GUIDE](zDispatch_Guides/expansion_GUIDE.md) |
| `resolvers/` | data + UI block resolution | [resolvers_GUIDE](zDispatch_Guides/resolvers_GUIDE.md) |
| `transfer/` | **zTransfer/zExport/zImport** — backend-agnostic data movement | [transfer_GUIDE](zDispatch_Guides/transfer_GUIDE.md) |
| `dispatch_constants` | shared constants (SSOT vocab from root `zVocabulary`) | [constants_GUIDE](zDispatch_Guides/constants_GUIDE.md) |

> **Trust:** zDispatch has **no code-exec surface** (no `eval`/`exec`/`pickle`/`subprocess`); the transfer codec is csv/json only. It is a pure router — auth delegates to `f_zAuth` (inherits fail-closed Tier-2), and plugin/`zFunc` routing delegates to the zFunc/zLoader trust gate (no bypass). `EVENT_BINDING_KEYS` are inert during render. **Nothing to seal in zGuard** — it is generic routing infra.

> **SSOT:** `MODE_BIFROST`/`MODE_ZCLI` alias root `zVocabulary` `ZMODE_*`; `KEY_ZVAFILE`/`KEY_ZBLOCK` alias `SESSION_KEY_*`. `MODE_WALKER` is dispatch-internal. The `PLURAL_REGISTRY` / `EVENT_BINDING_KEYS` are dispatch-owned SSOT (consumed by other subsystems, not redefined). *(zData command-contract keys — `action`/`model`/`table`/… — overlap `m_zData`; SSOT home deferred to the zData pass.)*

**Code:** `core/L2_Handling/g_zDispatch/zDispatch.py` (facade) + `dispatch_modules/`.

---

## h_zNavigation — navigation infrastructure (`z.navigation`)

Interactive menus, breadcrumb trails, navigation-state tracking, and inter-file
linking (zLink) behind one facade. **UI-flow layer** — it loads/routes blocks and
manages navigation state; it owns no business logic, no data, no secrets. Dual-mode
(zCLI / zBifrost / Web).

**Public surface (selected):** `create`/`select` (menus), `handle_zCrumbs`/`handle_zBack` (breadcrumbs), `navigate_to`/`get_current_location`/`get_navigation_history` (state), `handle_zLink` (inter-file linking).

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `menu/` | menu creation, rendering, interaction, search | [menu_system_GUIDE](zNavigation_Guides/menu_system_GUIDE.md) |
| `navigation_breadcrumbs` + `handlers/` | trail management, "Back", navbar/panels/history/zback ops | [breadcrumbs_GUIDE](zNavigation_Guides/breadcrumbs_GUIDE.md) · [handlers_GUIDE](zNavigation_Guides/handlers_GUIDE.md) |
| `navigation_state` | location tracking + FIFO history | [navigation_state_GUIDE](zNavigation_Guides/navigation_state_GUIDE.md) |
| `navigation_linking` | zLink flow (parse → gate → load → execute) | [linking_GUIDE](zNavigation_Guides/linking_GUIDE.md) |
| `resolvers/resolver_zlink` | zLink parse + RBAC check + **`classify_href` SSOT** | [resolvers_GUIDE](zNavigation_Guides/resolvers_GUIDE.md) |
| `navigation_constants` | shared constants (vocab from root `zVocabulary`) | *(built-in)* |

> **Trust — zLink RBAC is *presentational*, not the boundary.** The zLink permission
> check (`{"role":"admin"}` read from `session[zAuth]`, exact-match) decides **which
> block renders** — UX/defense-in-depth, not enforcement. Authoritative authorization
> for privileged **actions/data** lives in `f_zAuth` (`has_role`/`has_permission`) and
> sealed zGuard `wizard_rbac`. No code-exec surface (zLink perm dicts parsed via
> `zParser.zExpr_eval` — JSON, not `eval`). **Nothing to seal in zGuard.**

> **SSOT:** session keys (`zVaFolder`/`zVaFile`/`zBlock`/`zCrumbs`/`zAuth`/`zMode`) draw
> from `a_zConfig` → root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); mode literals
> alias `ZMODE_ZCLI`/`ZMODE_ZBIFROST`/`ZMODE_WEB` (Web mode lifted to vocabulary this
> pass). `ZLinkResolver.classify_href` is the Python SSOT for href classification,
> imported by `e_zDisplay`. Navigation-internal keys (`current_location`,
> `navigation_history`) stay local.

**Code:** `core/L2_Handling/h_zNavigation/zNavigation.py` (facade) + `navigation_modules/`.

---

## i_zFunc — function & plugin execution (`z.func`)

Dynamic loading and execution of **Python** functions, **JavaScript** functions
(Node.js), and **plugin** modules behind one facade — with auto-injection
(`zos`/`session`/`context`), transparent async handling, and zCLI argument types
(`zContext`/`zHat`/`zConv`/`this.key`). **This is the highest-value code-exec
surface after zTerminal**, so every load path goes through one trust gate.

**Public surface (selected):** `handle("@script.py > fn(...)")` (Python/JS),
`execute_plugin("&plugin.fn(...)")`, `load_plugin(name)`, `zNow(...)`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `executors/` | `ExecutionMixin` + `PythonExecutor` (inject + async) | [execution_GUIDE](zFunc_Guides/execution_GUIDE.md) |
| `arg_processing/` | argument parsing + special context types | [arguments_GUIDE](zFunc_Guides/arguments_GUIDE.md) |
| `func_resolver` | dynamic Python/JS resolution — **routed through the zLoader gate** | [resolution_GUIDE](zFunc_Guides/resolution_GUIDE.md) |
| `plugin_resolver` / `plugin_loader` / `plugin_executor` | plugin invocation, gated load, execution | [plugins_GUIDE](zFunc_Guides/plugins_GUIDE.md) |
| `func_js_executor` | Node.js execution — gated + injection-safe | [javascript_GUIDE](zFunc_Guides/javascript_GUIDE.md) |
| `builtin_functions` | built-ins (`zNow`) | [builtins_GUIDE](zFunc_Guides/builtins_GUIDE.md) |
| `func_constants` | shared constants (vocab from root `zVocabulary`) | *(built-in)* |

> **Trust — one gate, every path (Type B).** zFunc loads/executes arbitrary code,
> so **all** loading routes through c_zLoader's `verify_plugin_trust` seam:
> `handle("@.py")` and `execute_plugin("&…")` both go via
> `zos.loader.load_python_module`; `handle("@.js")` gates inside `func_js_executor`
> before spawning Node. Open-core is permissive (loads any path); installing
> zGuard seals the seam (allowed dirs / signatures) and denies with
> `PluginTrustError` **before code runs** (fail-closed) — sealed policy is
> **proprietary (private zGuard docs)**. JS invocation is **injection-safe**
> (payload via env var, never interpolated). Nothing zFunc-specific is concealed;
> it just must never load *around* the gate.

> **SSOT:** file extensions (`FILE_EXT_PY`/`FILE_EXT_JS`) alias root
> [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); messages / timeouts / param
> names / plugin search paths are single-sourced in `func_constants`; the module
> cache is owned by zLoader (`zFunc.module_cache` is a deprecated shim).

**Code:** `core/L2_Handling/i_zFunc/zFunc.py` (facade) + `zFunc_modules/`.

---

## j_zDialog — interactive forms (`z.dialog`)

Declarative form engine: define a form once (`model`/`fields`/`onSubmit`), auto-validate
against zSchema, and render mode-agnostically (zCLI terminal / zBifrost WebSocket).
Adds **confirm mode** (`fields: []` → y/n prompt or confirm button), **enum
enrichment** (schema `enum` → pick-list/`<select>`), placeholder injection
(`zConv.*`, `%session.*`, model), and a **server-side onSubmit registry** so the
client can't tamper with the submission.

**Public surface (selected):** `zDialog.handle(zHorizontal, context)` (facade) and the legacy `handle_zDialog(...)`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `dialog_context` | context creation + 5-type placeholder injection (`zConv`) | [dialog_context_GUIDE](zDialog_Guides/dialog_context_GUIDE.md) |
| `dialog_submit` | dict submission via zDispatch (model/session inject, masking) | [dialog_submit_GUIDE](zDialog_Guides/dialog_submit_GUIDE.md) |
| `dialog_constants` | shared keys/colors/messages (zBifrost mode from root `zVocabulary`) | [dialog_constants_GUIDE](zDialog_Guides/dialog_constants_GUIDE.md) |

> **Trust:** zDialog is a **declarative orchestration layer** — no code-exec surface
> (no `eval`/`exec`/`subprocess`), so **nothing to seal in zGuard**. Submission goes
> through `g_zDispatch` → owning subsystem (plugin/`zFunc` routing inherits the
> `c_zLoader` trust gate); the `onSubmit` handler is registered server-side by
> `_dialogId` (anti-tamper); `zConv`/payloads are **password-masked** before logging.
> *Latent SQLi (tracked → m_zData):* `inject_placeholders` smart-quotes `zConv.*` into
> onSubmit strings — only a risk if executed as a **raw** query; modern zData ops are
> structured/parameterized. Prefer `data:`/`where:` dicts over raw `query:` strings.

> **SSOT:** the zBifrost protocol-mode value aliases root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md) `ZMODE_ZBIFROST`; the mode **key** (`SESSION_KEY_ZMODE`) is sourced from `a_zConfig`. *(Tracked overlaps, not fixed here: the `"zConv"` literal and command-contract keys — `KEY_MODEL`/`KEY_TABLE`/`KEY_DATA`/`KEY_ZDATA`/`KEY_ZCRUD` — overlap zDispatch/zData; the password-masking + `%session.*` helpers duplicate zFunc / zDispatch `dispatch_launcher`.)*

**Code:** `core/L2_Handling/j_zDialog/zDialog.py` (facade) + `dialog_modules/`.

---

## k_zOpen — file & URL opening (`z.open`)

Unified opener: detects content type, resolves zPath notation (`@`/`~`), and routes to
the right app — URLs/HTML → browser, text → IDE, plus dedicated media methods. **Local-first
and trust-gated:** every public entry fails closed outside zCLI, and resolved paths pass a
path-trust seam before any read or launch.

**Public surface (selected):** `handle("zOpen(...)")` (file/URL/zPath + `onSuccess`/`onFail` hooks), `open_image`/`open_video`/`open_audio`.

| Module | Responsibility | Sub-guide |
|--------|----------------|-----------|
| `open_paths` | zPath (`@`/`~`) resolution → absolute path string | [open_paths_GUIDE](zOpen_Guides/open_paths_GUIDE.md) |
| `open_urls` | URL opening (detector-resolved browser + default fallback) | [open_urls_GUIDE](zOpen_Guides/open_urls_GUIDE.md) |
| `open_files` | extension routing (HTML→browser, text→IDE) + content fallback | [open_files_GUIDE](zOpen_Guides/open_files_GUIDE.md) |
| `open_constants` | shared constants (vocab from root `zVocabulary`) | [open_constants_GUIDE](zOpen_Guides/open_constants_GUIDE.md) |
| `open_trust` | path-trust gate (zGuard seam) | *(in main guide → Security & Trust)* |

> **Trust (Type B, fail-closed off zCLI).** zOpen performs **local-machine** actions
> (read/disclose files, launch browsers/IDEs/players), so it is gated twice: a **mode gate**
> (`_local_mode_allowed`) blocks every public entry unless `session[zMode] == zCLI` — fail-closed
> in zBifrost/Web so a remote client can't drive the operator's machine; and a **path-trust seam**
> (`open_trust.verify_path_trust`) reuses zParser's sealed `zguard.parser.path_trust` policy before
> any read/launch (open-core permissive; zGuard seals it → `PathTrustError`, propagated unwrapped).
> **V2 hardening:** IDE/browser launches use only **detector-resolved, `which()`-validated** commands
> (`get_ide_launch_command`/`get_browser_launch_command`); an unresolved editor degrades to safe
> content display rather than exec'ing a raw binary name.

> **SSOT:** zPath symbols (`@`/`~`), session machine keys (`ide`/`browser`), file-extension atoms,
> and control-flow returns (`zBack`/`stop`) alias root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md);
> the mode literal aliases `ZMODE_ZCLI`. The zPath **resolution algorithm** and URL/zPath/file
> **classification** stay local to zOpen by design (their contracts differ from `zParser.zPath_decoder`
> / `ZLinkResolver.classify_href`) — only the atoms are shared.

**Code:** `core/L2_Handling/k_zOpen/zOpen.py` (facade) + `open_modules/`.

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to its `*_modules/`. Change behavior in the modules, not the facade signature.
- **Constants are SSOT:** cross-subsystem protocol vocabulary is single-sourced in root [`zVocabulary`](../L0_Core/zVocabulary_GUIDE.md); subsystem-internal values stay in each subsystem's `*_constants.py` / package. No magic strings.
- **zGuard seam:** proprietary enforcement is optional and isolated behind `try: from zguard… / except ImportError: <fallback>`. Fallback posture depends on category: **permissive** for Type-B safety seams (parser/display), **fail-closed/unavailable** for Type-A2 ecosystem auth (zAuth PAT/remote/boot/identity). Open-core stays usable without zGuard; sealed capabilities just say "z patch".
- **Docs ↔ code parity:** every guide here maps 1:1 to a code module; the `zVault-zCode/` graph mirrors both (`[doc]`/`[logic]`/`[folder]` tags, wikilinked). Vault links mirror the **repo tree** (structure), not domain/logic.
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported).

**See also:** [Home](../../README.md) · [code-side L2 overview](../../core/L2_Handling/README.md) · [L1 Foundation docs](../L1_Foundation/README.md) · [L0 Core docs](../L0_Core/README.md)

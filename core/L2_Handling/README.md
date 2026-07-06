# L2 — Handling Layer

The **handling tier** of zOS. These subsystems sit on top of the Foundation layer (L1) and turn raw input, files, and declarations into resolved paths, parsed structures, rendered output, dispatched calls, authorized actions, navigation, forms, and opened resources. Everything above (L3 Abstraction, L4 Orchestration) builds on them.

They initialize in **alphabetical order** during `zOS()` boot, each reachable as a facade on the live instance:

| Order | Subsystem | Facade | In one line | Guide |
|------|-----------|--------|-------------|-------|
| **d** | `d_zParser` | `z.parser` | Path/command/file/plugin/expression parsing + zVaFile parsing — behind one facade, with a path-trust read gate | [zParser_GUIDE](../../Documentation/L2_Handling/zParser_GUIDE.md) |
| **e** | `e_zDisplay` | `z.display` | Event-driven terminal + WebSocket I/O: text, tables, widgets, menus, system UI; dual-mode (zCLI / zBifrost) | [zDisplay_GUIDE](../../Documentation/L2_Handling/zDisplay_GUIDE.md) |
| **f** | `f_zAuth` | `z.auth` | Three-tier auth (session/app/dual) + bcrypt + machine identity + context-aware RBAC; open/closed split | [zAuth_GUIDE](../../Documentation/L2_Handling/zAuth_GUIDE.md) |
| **g** | `g_zDispatch` | `z.dispatch` | Universal command router — parses keys/modifiers, detects type, routes to the owning subsystem | [zDispatch_GUIDE](../../Documentation/L2_Handling/zDispatch_GUIDE.md) |
| **h** | `h_zNavigation` | `z.navigation` | Menus, breadcrumb trails, navigation state, and inter-file linking (zLink) | [zNavigation_GUIDE](../../Documentation/L2_Handling/zNavigation_GUIDE.md) |
| **i** | `i_zFunc` | `z.func` | Dynamic Python/JS/plugin execution with auto-injection, async handling — through one trust gate | [zFunc_GUIDE](../../Documentation/L2_Handling/zFunc_GUIDE.md) |
| **j** | `j_zDialog` | `z.dialog` | Declarative, auto-validated forms with server-side onSubmit; dual-mode rendering | [zDialog_GUIDE](../../Documentation/L2_Handling/zDialog_GUIDE.md) |
| **k** | `k_zOpen` | `z.open` | Universal opener (URLs/files/zPaths + media) — local-first, fail-closed off zCLI, path-trust gated | [zOpen_GUIDE](../../Documentation/L2_Handling/zOpen_GUIDE.md) |

> `zParser` initializes early (it is `zLoader`'s path-resolution dependency, bridging L1↔L2); the rest come up in order on top of the Foundation facades (`z.config`/`z.comm`/`z.loader`) and `z.display`.

> **Root vocabulary:** shared protocol literals (session-dict keys, run modes, file extensions, file-type ids, path symbols, zMachine prefixes, control-flow returns) are single-sourced in `core/zVocabulary.py` — a dependency-free leaf re-exported via the `zOS` aggregator. These subsystems draw from it (`from zOS.zVocabulary import …`) rather than re-declaring; historical `*_constants.py` names remain as thin aliases. See [zVocabulary_GUIDE](../../Documentation/L0_Core/zVocabulary_GUIDE.md).

---

## d_zParser — parsing & path resolution (`z.parser`)

The unified parsing interface: path resolution, command parsing, file-content parsing, plugin-syntax parsing, expression evaluation, and declarative zVaFile parsing — behind one facade. Parsing **primitives only**; upper layers act on what it detects.

- **Surface:** `zPath_decoder`, `identify_zFile`, `parse_file_content`/`parse_yaml`/`parse_json`, `parse_command`, `is_plugin_invocation`/`parse_plugin_invocation`, `zExpr_eval`, `parse_ui_file`/`parse_schema_file`/`parse_config_file`.
- **Security:** content parsed with `yaml.safe_load`/stdlib `json` (no `eval`/`exec`); read paths pass through the `parser_trust` gate (permissive in open-core, sealed by zGuard).
- **Code:** `d_zParser/zParser.py` (facade) + `parser_modules/`

## e_zDisplay — rendering & input (`z.display`)

Professional terminal output and input behind one event-driven facade — dual-mode: zCLI (terminal) and zBifrost (browser/WebSocket).

- **Surface:** `text`, `header`, `code`, `selection`, `button`, `zURL`, `list`/`dl`/`json`/`zTable`, `progress_bar`/`spinner`/`swiper`, `zDeclare`/`zSession`/`zMenu`/`zDialog`, plus the unified `handle(event_dict)` router.
- **Security:** `zTerminal` local exec is **fail-closed** (OFF unless explicitly declared); `mode_helper` is the mode-detection SSOT; `display_trust` is a zGuard seam.
- **Code:** `e_zDisplay/zDisplay.py` (facade) + `zDisplay_modules/`

## f_zAuth — authentication & authorization (`z.auth`)

Three-tier authentication (session / application / dual) with bcrypt, git-like persistent machine identity, and context-aware RBAC. The first subsystem **split open/closed by design** — local auth is open-core; zCloud ecosystem auth is sealed in zGuard.

- **Surface:** `login`/`logout`/`status`/`is_authenticated`/`get_credentials`, `authenticate_app_user`/`switch_app`, `set_active_context`/`get_active_user`, `has_role`/`has_permission`/`grant_permission`/`revoke_permission`, `hash_password`/`verify_password`.
- **Security (Type A2, fail-closed):** ecosystem seams (`api_key_auth`, `remote_authentication`, `boot_identity`, `identity_store`) raise "z patch" / degrade without zGuard — they never fabricate an identity.
- **Code:** `f_zAuth/zAuth.py` (facade) + `zAuth_modules/`

## g_zDispatch — command routing (`z.dispatch`)

The universal command router: parses command keys (with `^ ~ * !` modifiers), detects the command type, and routes to the owning subsystem. **Pure routing** — no business logic, no UI, no data ops.

- **Surface:** `handle(zKey, zHorizontal, context, walker)` (facade) + standalone `handle_zDispatch(...)`; components via `z.dispatch.modifiers` / `z.dispatch.launcher`.
- **Security:** no code-exec surface (no `eval`/`exec`/`pickle`/`subprocess`); auth/plugin routing inherit the `f_zAuth` / `c_zLoader` gates. Nothing to seal.
- **Code:** `g_zDispatch/zDispatch.py` (facade) + `dispatch_modules/`

## h_zNavigation — navigation infrastructure (`z.navigation`)

Interactive menus, breadcrumb trails, navigation-state tracking, and inter-file linking (zLink) behind one facade. **UI-flow layer** — owns no business logic, data, or secrets.

- **Surface:** `create`/`select` (menus), `handle_zCrumbs`/`handle_zBack` (breadcrumbs), `navigate_to`/`get_current_location`/`get_navigation_history` (state), `handle_zLink`.
- **Security:** zLink RBAC is *presentational* (which block renders); authoritative authorization lives in `f_zAuth` + sealed zGuard. `ZLinkResolver.classify_href` is the href-classification SSOT.
- **Code:** `h_zNavigation/zNavigation.py` (facade) + `navigation_modules/`

## i_zFunc — function & plugin execution (`z.func`)

Dynamic loading and execution of Python functions, JavaScript (Node.js), and plugin modules behind one facade — with auto-injection (`zos`/`session`/`context`), transparent async, and zCLI arg types. **The highest-value code-exec surface after zTerminal.**

- **Surface:** `handle("@script.py > fn(...)")` (Python/JS), `execute_plugin("&plugin.fn(...)")`, `load_plugin(name)`, `zNow(...)`.
- **Security (Type B):** every load path routes through `c_zLoader`'s `verify_plugin_trust` seam (fail-closed with zGuard, `PluginTrustError` before code runs); JS invocation is injection-safe (payload via env var).
- **Code:** `i_zFunc/zFunc.py` (facade) + `zFunc_modules/`

## j_zDialog — interactive forms (`z.dialog`)

Declarative form engine: define a form once (`model`/`fields`/`onSubmit`), auto-validate against zSchema, render mode-agnostically (zCLI / zBifrost). Adds confirm mode, enum enrichment, placeholder injection, and a **server-side onSubmit registry** so the client can't tamper.

- **Surface:** `zDialog.handle(zHorizontal, context)` (facade) + legacy `handle_zDialog(...)`.
- **Security:** declarative orchestration — no code-exec surface; submission routes through `g_zDispatch` (inherits the loader/zFunc gate); `zConv`/payloads are password-masked before logging. Nothing to seal.
- **Code:** `j_zDialog/zDialog.py` (facade) + `dialog_modules/`

## k_zOpen — file & URL opening (`z.open`)

Unified opener: detects content type, resolves zPath (`@`/`~`), and routes — URLs/HTML → browser, text → IDE, plus dedicated media methods. **Local-first and trust-gated.**

- **Surface:** `handle("zOpen(...)")` (file/URL/zPath + `onSuccess`/`onFail` hooks), `open_image`/`open_video`/`open_audio`.
- **Security (Type B, fail-closed off zCLI):** a **mode gate** (`_local_mode_allowed`) blocks every public entry outside zCLI; a **path-trust seam** (`open_trust`, reusing zParser's sealed policy) gates reads/launches; IDE/browser launches run only **detector-resolved, `which()`-validated** commands.
- **Code:** `k_zOpen/zOpen.py` (facade) + `open_modules/`
- **Deep dives:** [zOpen_Guides/](../../Documentation/L2_Handling/zOpen_Guides/)

---

## Conventions (for agents)

- **Facade pattern:** each subsystem is a thin public class delegating to `*_modules/`. Touch the modules, not the facade signature, for behavior changes.
- **Constants are SSOT:** cross-subsystem protocol vocabulary lives in root `core/zVocabulary.py`; subsystem-internal values + exception hierarchies live in each subsystem's `*_constants.py`. No magic strings.
- **zGuard seam:** proprietary enforcement is optional and isolated behind `try: from zguard… / except ImportError: <fallback>`. Fallback posture is **permissive** for Type-B safety seams (parser/display/loader/open) and **fail-closed** for Type-A2 ecosystem auth. Open-core stays fully functional without it.
- **Docs ↔ code parity:** every guide under `Documentation/L2_Handling/` is kept 1:1 with the code here; the `zVault-zCode/` graph mirrors both (tags `[logic]`/`[doc]`/`[folder]`, wikilinked).
- **`.zolo` first:** examples prefer the native `.zolo` format (`.yaml`/`.json` are also supported).

**See also:** [Home](../../README.md) · [L1 Foundation overview](../L1_Foundation/README.md) · [L2 Handling docs](../../Documentation/L2_Handling/README.md)

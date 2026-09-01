<!-- cursor: description="zSpark — app boot config (entry-point keys; deep config seek-as-need)" globs="**/zSpark.*.zolo" alwaysApply=false -->
zSpark: app boot config | one per app | string-first .zolo — !quotes !YAML | zOS speaks back on boot, read console

core: the keys that boot the app
    title:     My App         — display name AND machine identity (slugged → scopes auth/RBAC, API, storage); the one key never omit
    zSpace:    @.             — workspace root every @. resolves from (default: cwd)
    zMode:     zCLI | zBifrost — where it runs: terminal | web GUI; zBifrost = WS bridge to the client, !a server (that's zServer)

address: which screen opens first — read like a street address; target is ALWAYS a zUI.*.zolo
    zVaFolder: @.zViews        — folder (zPath, !trailing-slash)
    zVaFile:   zUI.myApp       — view file (!extension; always zUI.*)
    zBlock:    MyBlock         — entry block inside zVaFile

env: optional, sensible defaults
    zEnv:      development     — loads zEnv.<name>.zolo over zEnv.base.zolo
    zLog:      INFO            — DEBUG | INFO | WARNING | ERROR; z-prefix (zINFO…) adds engine trace
    zLogPath:  @.logs          — zPath

strict: boot-time static fault gate — ON by default (no key needed)
    checks   — every authored .zolo statically, before anything runs: parse/comment anomalies
               (unterminated `#>`, duplicate NAMED sibling blocks — repeated shorthand zEvents like
               zText/zH2 are supported grammar and never fault), zShuttle reels/patterns that don't
               exist, %tokens in `_zClass:` that can never resolve there (only loop-baked %item.*
               resolves in class position), `onSuccess:` verbs outside the dispatch set
    refuses  — faults print with file:line and the app does NOT boot (zRaven inherits the same gate)
    opt_out  — `strict: false` in zSpark downgrades the refusal to a printed warning list (boots anyway);
               explicit, per-app, for migrating older apps — fix the faults, then drop the key
    standalone — `z lint <app dir | zSpark file>` runs the identical checks without booting

zRequirements: declared INSIDE zEnv.base.zolo (!zSpark key) — app-specific Python deps for plugins
    zRequirements: [Pillow>=10.0, requests]  — flat pip-spec list, same grammar as any zEnv value
    gate     — identical shape to zMigration: boot NEVER installs, only verifies; refuses to launch + prints the fix if anything's missing (zRaven inherits the same refusal)
    install  — `z requirements <zspark file>` — the one explicit write path (`--dry-run` preview · `--auto-approve` skip prompt)
    matched_by — distribution name (importlib.metadata), !import name — "Pillow" satisfies even though it imports as `PIL`
    plugin_use — a plugin does a normal `from PIL import Image`; !sandboxing, !separate venv — runs in-process with the full interpreter (golden: zDemos/zDarkroom)

seek_as_need: !boot-critical — pull the reference when you reach the key
    zServer   — HTTP leg: host/port/routes/static (zBifrost only) -> zServer ref
    zSocket   — WebSocket leg the Bifrost bridge rides (legacy alias: websocket) -> zBifrost ref
    zCanvas   — app-wide canvas applied across pages -> zUI ref
    zPersist  — create Apps/{title}/ user-data dir -> Config ref
    zRaven*   — bind a test suite (zRaven, zRavenTimeout, zRavenPort…); !add during dev (noisy auto-run) -> 13_testing
    plugins   — list of .py loaded at boot -> plugins ref

retired: dropped keys — printed as a deprecation warning if still set
    zSwap     — was user-data persistence -> renamed zPersist (unrelated to the `z swap` CLI zero-downtime command)

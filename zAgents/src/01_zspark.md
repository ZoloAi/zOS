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

seek_as_need: !boot-critical — pull the reference when you reach the key
    zServer   — HTTP leg: host/port/routes/static (zBifrost only) -> zServer ref
    zSocket   — WebSocket leg the Bifrost bridge rides (legacy alias: websocket) -> zBifrost ref
    zCanvas   — app-wide canvas applied across pages -> zUI ref
    zPersist  — create Apps/{title}/ user-data dir -> Config ref
    zRaven*   — bind a test suite (zRaven, zRavenTimeout, zRavenPort…); !add during dev (noisy auto-run) -> 04_raven
    plugins   — list of .py loaded at boot -> plugins ref

retired: dropped keys — printed as a deprecation warning if still set
    zSwap     — was user-data persistence -> renamed zPersist (unrelated to the `z swap` CLI zero-downtime command)

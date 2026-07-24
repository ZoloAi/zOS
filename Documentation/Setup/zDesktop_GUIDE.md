# zDesktop — native windows & the Zolo.app launcher

**Code:** `desktop/macos/` (Swift launcher) · engine seam in `core/engine.py`
**Extra:** `pip install "zolo-os[webview]"` (pywebview — the native window)
**Since:** 1.7.0 (zOS #33)

zOS apps are web-served by default. **zDesktop** is the native-window mode:
the same app, in its own OS window instead of a browser tab.

## Two doors, one seam

| Door | Who sets it | Effect |
|---|---|---|
| `zSpark.zDesktop: true` | The app author | This app always opens in a native window |
| `ZOS_DESKTOP=1` env | A launcher (e.g. Zolo.app) | *Adds* the window when the spark didn't declare one |

The spark keeps the final say when present; the env var only **adds** the
window. That separation is the whole design — product logic stays in the
engine, launchers stay thin.

## Zolo.app (macOS)

A thin Swift launcher (`desktop/macos/ZoloLauncher.swift`) that makes a Mac
feel like zOS is installed as an app, not a toolchain:

1. **No engine?** Bootstraps the runtime into `~/.zolo/venv` and runs `z patch`.
2. **Machine not signed in?** Opens the user's zRM and bridges the web sign-in
   to `z login --token` — signing into your zRM signs your Mac in. One act.
3. **Double-clicked `.zolo` file?** Hands it to `z` with `ZOS_DESKTOP=1` — the
   app opens natively even if its spark never declared `zDesktop`.
4. **Everything in place?** Opens the zRM in a native window — the control room.

The `.zolo` filetype is registered via a UTI (`media.zolo.source`,
`desktop/macos/Info.plist`), so Finder shows zolo files with canonical icons
and double-click just works.

### Building it

```bash
cd desktop/macos
./build.sh              # unsigned build (local testing)
./build.sh --sign       # Developer ID signed
./build.sh --notarize   # signed + notarized + stapled
# Output: dist/Zolo.app (+ dist/Zolo.dmg when signing)
```

## The window itself

The native window is pywebview (the `[webview]` extra). If the extra is
missing, the engine says so and falls back to browser serving — the app still
runs. Install hint: `pip install "zolo-os[webview]"` (there is **no**
`zolo-desktop` package; see the install guide's naming warning).

## See Also

- [zInstall_GUIDE.md](zInstall_GUIDE.md) — extras, package naming
- [../L4_Orchestration/zServer_Guides/ports_GUIDE.md](../L4_Orchestration/zServer_Guides/ports_GUIDE.md)
  — launchers should parse the stdout port announcement, never assume 8080

#!/usr/bin/env bash
# Build Zolo.app — the thin macOS launcher (zOS #33).
#
#   ./build.sh              unsigned build (local testing)
#   ./build.sh --sign       Developer ID signed
#   ./build.sh --notarize   signed + notarized + stapled (requires a stored
#                           notarytool keychain profile named "zolo-notary":
#                           xcrun notarytool store-credentials zolo-notary \
#                               --apple-id <id> --team-id 86P2GB83LY \
#                               --password <app-specific-password>)
#
# Output: dist/Zolo.app (+ dist/Zolo.dmg when signing)

set -euo pipefail
cd "$(dirname "$0")"

IDENTITY="Developer ID Application: Gal Nachshon (86P2GB83LY)"
APP=dist/Zolo.app
ICON_SRC="../../../zLSP/zlsp/editors/vscode/marketplace-package/icons/zolo_filetype.png"

say() { printf '\033[1m→ %s\033[0m\n' "$*"; }

# ── 1. compile ────────────────────────────────────────────────────────────────
say "compiling ZoloLauncher.swift"
rm -rf dist && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -o "$APP/Contents/MacOS/ZoloLauncher" ZoloLauncher.swift \
    -framework Cocoa -framework WebKit
cp Info.plist "$APP/Contents/Info.plist"

# ── 2. icons — app icon + document icon from the canonical filetype art ──────
make_icns() {  # $1 src.png  $2 dest-name (no ext)
    local src="$1" name="$2" iconset="dist/$2.iconset"
    mkdir -p "$iconset"
    for sz in 16 32 128 256 512; do
        sips -z $sz $sz       "$src" --out "$iconset/icon_${sz}x${sz}.png"      >/dev/null
        sips -z $((sz*2)) $((sz*2)) "$src" --out "$iconset/icon_${sz}x${sz}@2x.png" >/dev/null
    done
    iconutil -c icns "$iconset" -o "$APP/Contents/Resources/$name.icns"
    rm -rf "$iconset"
}
say "building icons from $ICON_SRC"
make_icns "$ICON_SRC" Zolo
make_icns "$ICON_SRC" ZoloFile

# ── 3. sign / notarize ────────────────────────────────────────────────────────
if [[ "${1:-}" == "--sign" || "${1:-}" == "--notarize" ]]; then
    say "signing with: $IDENTITY"
    codesign --force --deep --options runtime --sign "$IDENTITY" "$APP"
    codesign --verify --strict "$APP" && say "signature verified"

    say "packing Zolo.dmg"
    hdiutil create -volname Zolo -srcfolder "$APP" -ov -format UDZO dist/Zolo.dmg >/dev/null

    if [[ "${1:-}" == "--notarize" ]]; then
        say "notarizing (this takes a few minutes)"
        xcrun notarytool submit dist/Zolo.dmg --keychain-profile zolo-notary --wait
        xcrun stapler staple dist/Zolo.dmg
        xcrun stapler staple "$APP"
        say "notarized + stapled"
    fi
fi

say "done: $APP"

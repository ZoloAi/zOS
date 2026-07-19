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

# ── 1. compile — UNIVERSAL (this is a public download; half the Mac installed
#      base is still Intel, and an arm64-only slice greets them with
#      "you can't open the application") ──────────────────────────────────────
say "compiling ZoloLauncher.swift (arm64 + x86_64 → universal)"
rm -rf dist && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
for arch in arm64 x86_64; do
    swiftc -O -target "${arch}-apple-macos12.0" -o "dist/ZoloLauncher-${arch}" \
        ZoloLauncher.swift -framework Cocoa -framework WebKit
done
lipo -create dist/ZoloLauncher-arm64 dist/ZoloLauncher-x86_64 \
    -output "$APP/Contents/MacOS/ZoloLauncher"
rm -f dist/ZoloLauncher-arm64 dist/ZoloLauncher-x86_64
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

    say "packing Zolo.dmg (styled: background + /Applications drag target)"
    STAGE=dist/dmg-stage
    rm -rf "$STAGE" && mkdir -p "$STAGE/.background"
    cp -R "$APP" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"
    cp assets/dmg_background.png "$STAGE/.background/background.png"

    # RW image first so Finder can persist the layout (.DS_Store), then compress.
    hdiutil create -volname Zolo -srcfolder "$STAGE" -ov -format UDRW dist/Zolo-rw.dmg >/dev/null
    MOUNT=$(hdiutil attach dist/Zolo-rw.dmg -readwrite -noverify -noautoopen | awk -F'\t' '/\/Volumes\//{print $3}')
    osascript <<OSA
tell application "Finder"
    tell disk "Zolo"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 860, 520}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 110
        set background picture of viewOptions to file ".background:background.png"
        set position of item "Zolo.app" of container window to {165, 235}
        set position of item "Applications" of container window to {495, 235}
        close
        open
        update without registering applications
        delay 1
        close
    end tell
end tell
OSA
    sync
    hdiutil detach "$MOUNT" >/dev/null
    hdiutil convert dist/Zolo-rw.dmg -format UDZO -o dist/Zolo.dmg -ov >/dev/null
    rm -f dist/Zolo-rw.dmg && rm -rf "$STAGE"
    # The dmg needs its OWN signature — notarization staples it either way, but
    # Gatekeeper's install check (spctl -t install) rejects an unsigned container.
    codesign --force --sign "$IDENTITY" dist/Zolo.dmg

    if [[ "${1:-}" == "--notarize" ]]; then
        say "notarizing (this takes a few minutes)"
        xcrun notarytool submit dist/Zolo.dmg --keychain-profile zolo-notary --wait
        xcrun stapler staple dist/Zolo.dmg
        xcrun stapler staple "$APP"
        say "notarized + stapled"
    fi
fi

say "done: $APP"

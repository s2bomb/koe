#!/bin/zsh
# Build mac/koe.app — koe's signed launcher bundle (owns the TCC identity).
#
# Ad-hoc signature by default: TCC tracks it by code-directory hash, grants
# persist across launches. A rebuild changes the hash, so after rebuilding you
# may need to re-run --register (and re-toggle Accessibility). For a rebuild-
# stable identity, create a self-signed signing cert and pass it:
#   KOE_CODESIGN_IDENTITY="koe Codesign" ./build.sh
set -eu
DIR="${0:A:h}"
APP="$DIR/koe.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -o "$APP/Contents/MacOS/koe-launcher" "$DIR/launcher/main.swift"
cp "$DIR/launcher/Info.plist" "$APP/Contents/Info.plist"
codesign --force --deep --identifier com.s2bomb.koe \
         --sign "${KOE_CODESIGN_IDENTITY:--}" "$APP"
codesign --verify --deep --strict "$APP"
print -- "built: $APP"

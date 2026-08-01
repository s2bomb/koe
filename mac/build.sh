#!/bin/zsh
# Build mac/koe.app — koe's signed launcher bundle (owns the TCC identity).
#
# Signs with the stable self-signed cert by default ("rigd Codesign", the same
# local identity the rig daemon uses) so TCC grants SURVIVE rebuilds. Ad-hoc
# signing was tried and bit immediately: each rebuild changes the code hash,
# TCC keeps reporting "authorized" by bundle id but silently hides audio
# devices at enforcement (observed 2026-08-01). Override on machines without
# the cert:  KOE_CODESIGN_IDENTITY=- ./build.sh
set -eu
DIR="${0:A:h}"
APP="$DIR/koe.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -o "$APP/Contents/MacOS/koe-launcher" "$DIR/launcher/main.swift"
cp "$DIR/launcher/Info.plist" "$APP/Contents/Info.plist"
codesign --force --deep --identifier com.s2bomb.koe \
         --sign "${KOE_CODESIGN_IDENTITY:-rigd Codesign}" "$APP"
codesign --verify --deep --strict "$APP"
print -- "built: $APP"

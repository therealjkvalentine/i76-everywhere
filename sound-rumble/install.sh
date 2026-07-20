#!/bin/sh
# Install/revert the sound-rumble dsound.dll proxy in the Mac wrapper game dir.
# EXPERIMENTAL backup path — mutually exclusive with ../ffb-shim (both rumble).
set -e
cd "$(dirname "$0")"
GAME=$(ls -d "$HOME/Applications/Sikarugir/"*"/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76" 2>/dev/null | head -1)
[ -n "$GAME" ] || { echo "game dir not found"; exit 1; }
echo "game dir: $GAME"

if [ "$1" = "--revert" ]; then
    rm -f "$GAME/dsound.dll"
    echo "removed dsound.dll proxy (Wine falls back to builtin dsound)"
    exit 0
fi

[ -f dsound.dll ] || { echo "run ./build.sh first"; exit 1; }
if [ -f "$GAME/i7_sfrce.dll" ] && [ -f "$GAME/i7_sfrce_org.dll" ]; then
    echo "WARNING: the ffb-shim looks installed (i7_sfrce.dll is our shim)."
    echo "         Both drive the pad and will FIGHT. Revert it first:"
    echo "         ../ffb-shim/install.sh --revert"
fi
cp -f dsound.dll "$GAME/dsound.dll"
REPO=$(cd .. && pwd)
python3 "$REPO/tools/gpw-envelopes.py"    "$GAME" --out "$GAME/rumble-envelopes.ini"    2>/dev/null || echo "WARN: envelopes not generated"
python3 "$REPO/tools/gpw-fingerprints.py" "$GAME" --out "$GAME/rumble-fingerprints.ini" 2>/dev/null || echo "WARN: fingerprints not generated"
echo "installed. Wine may prefer builtin dsound — if no rumble, set in the launch env:"
echo "  WINEDLLOVERRIDES=\"dsound=n,b\""
echo "revert: $0 --revert"

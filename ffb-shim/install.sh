#!/bin/sh
# Install/revert the FFB shim in the Mac wrapper's game dir.
set -e
cd "$(dirname "$0")"
GAME=$(ls -d "$HOME/Applications/Sikarugir/"*"/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76" 2>/dev/null | head -1)
[ -n "$GAME" ] || { echo "game dir not found under ~/Applications/Sikarugir"; exit 1; }
echo "game dir: $GAME"

if [ "$1" = "--revert" ]; then
    [ -f "$GAME/i7_sfrce_org.dll" ] || { echo "no backup to revert to"; exit 1; }
    mv -f "$GAME/i7_sfrce_org.dll" "$GAME/i7_sfrce.dll"
    echo "reverted to the original i7_sfrce.dll"
    exit 0
fi

[ -f I7_SFRCE.DLL ] || { echo "run ./build.sh first"; exit 1; }
if [ -f "$GAME/i7_sfrce.dll" ] && [ ! -f "$GAME/i7_sfrce_org.dll" ]; then
    cp -p "$GAME/i7_sfrce.dll" "$GAME/i7_sfrce_org.dll"
    echo "original backed up as i7_sfrce_org.dll"
fi
cp -f I7_SFRCE.DLL "$GAME/i7_sfrce.dll"
echo "shim installed. Telemetry: C:\\AutoHotkey\\ffb-state.txt / ffb-events.txt"
echo "revert anytime: $0 --revert"

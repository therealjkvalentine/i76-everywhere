#!/bin/sh
# Double-click to launch the I'76 memory trainer overlay on the running game.
# Start Interstate '76 FIRST, get into a mission, THEN run this.
set -e
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
PFX="$APP/Contents/SharedSupport/prefix"
AHKDIR="$PFX/drive_c/AutoHotkey"
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! pgrep -f 'i76\.exe|nitro\.exe' >/dev/null; then
  echo "The game isn't running. Launch Interstate '76, enter a mission, then run this again."
  echo "(Press any key to close.)"; read _; exit 0
fi

cp "$HERE/tools/i76-trainer.ahk" "$AHKDIR/i76-trainer.ahk"

export WINEPREFIX="$PFX" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"
echo "Launching trainer overlay... (F8 hide/show, F7 head-look test, F9/F10/F11 scanner)"
"$APP/Contents/SharedSupport/wine/bin/wine" 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\i76-trainer.ahk' >/dev/null 2>&1 &
echo "Trainer started. This window can be closed."
sleep 1

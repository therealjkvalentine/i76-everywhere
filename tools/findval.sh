#!/bin/sh
# Find one or more exact int32 values in the running game and report them as
# entity-relative offsets.  Usage: tools/findval.sh 1995 3986
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
AHK="$APP/Contents/SharedSupport/prefix/drive_c/AutoHotkey"
export WINEPREFIX="$APP/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"
cp "$(dirname "$0")/i76-findval.ahk" "$AHK/i76-findval.ahk"
printf '%s' "$*" > "$AHK/fv.cmd"; rm -f "$AHK/fv.out"
timeout 180 "$APP/Contents/SharedSupport/wine/bin/wine" 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\i76-findval.ahk' 2>/dev/null
sleep 0.5; cat "$AHK/fv.out" 2>/dev/null; echo

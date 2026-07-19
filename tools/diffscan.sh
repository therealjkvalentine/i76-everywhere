#!/bin/sh
# usage: diffscan.sh "first int 3721"  |  diffscan.sh "next dec"
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
AHK="$APP/Contents/SharedSupport/prefix/drive_c/AutoHotkey"
export WINEPREFIX="$APP/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"
printf '%s' "$1" > "$AHK/diff.cmd"
rm -f "$AHK/diff.out"
timeout 180 "$APP/Contents/SharedSupport/wine/bin/wine" 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\i76-diffscan.ahk' 2>/dev/null
sleep 0.5
cat "$AHK/diff.out" 2>/dev/null; echo

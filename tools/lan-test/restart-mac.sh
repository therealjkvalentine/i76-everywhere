#!/bin/bash
# restart-mac.sh APP : stop the game in APP's prefix (wineserver -k, only that prefix), start APP with open, Esc to the main menu
A="$1"; P="$A/Contents/SharedSupport/prefix"
DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$P" "$A/Contents/SharedSupport/wine/bin/wineserver" -k 2>/dev/null
for i in $(seq 1 30); do sleep 1; pgrep -f 'i76\.exe' >/dev/null || break; done; sleep 3
open "$A"; for i in $(seq 1 60); do sleep 1; pgrep -f 'i76\.exe' >/dev/null && break; done; echo "started after $i s"; sleep 30
for k in 1 2 3 4 5; do /tmp/i76mp/probe3.sh "$A" key 1B >/dev/null; sleep 4; /tmp/i76mp/macnav.sh "$A" st | grep -q "^0x10025a50 0x00000000 13 2 0 17" && { echo "main menu ($k Esc)"; exit 0; }; done
echo "main menu NOT reached: $(/tmp/i76mp/macnav.sh "$A" st)"; exit 1

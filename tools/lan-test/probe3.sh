#!/bin/bash
# probe3.sh APP args... : run i76probe3.exe (tools/wine-probe) inside APP's Wine session (the game's own wine + prefix)
A="$1"; shift
export DYLD_FALLBACK_LIBRARY_PATH="$A/Contents/Frameworks:$A/Contents/SharedSupport/wine/lib" WINEPREFIX="$A/Contents/SharedSupport/prefix" WINEDEBUG=-all WINEESYNC=1 WINEMSYNC=1
cd /tmp/i76mp && "$A/Contents/SharedSupport/wine/bin/wine" /tmp/i76mp/i76probe3.exe "$@" 2>&1 | tr -d '\r' | grep -v msync

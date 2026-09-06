#!/bin/sh
# Launch the I'76 debug menu (tools/i76-debugmenu.ahk) inside the game's Wine
# prefix, or fetch the logs a field run left behind.
#
#   tools/debugmenu.sh            copy the current script in + launch the menu
#                                 (game should be running, in a mission)
#   tools/debugmenu.sh --fetch    print debugmenu.out (latest snapshot) and
#                                 debugmenu.log (every value change) from the run
#   tools/debugmenu.sh --clear    delete the in-prefix logs before a fresh run
#
# Same launch conventions as chaindiff.sh / setup-input-remapper.sh: the script
# runs as a Windows process in the prefix so ReadProcessMemory reaches the game.
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
AHK="$APP/Contents/SharedSupport/prefix/drive_c/AutoHotkey"
export WINEPREFIX="$APP/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"

case "$1" in
--fetch)
    echo "=== debugmenu.out (latest snapshot) ==="
    cat "$AHK/debugmenu.out" 2>/dev/null || echo "(none)"
    echo "=== debugmenu.log (value changes) ==="
    cat "$AHK/debugmenu.log" 2>/dev/null || echo "(none)"
    ;;
--clear)
    rm -f "$AHK/debugmenu.out" "$AHK/debugmenu.log"
    echo "cleared"
    ;;
*)
    [ -f "$AHK/AutoHotkeyU32.exe" ] || { echo "AutoHotkey not installed in the prefix - run setup-input-remapper.sh once first"; exit 1; }
    cp "$(dirname "$0")/i76-debugmenu.ahk" "$AHK/i76-debugmenu.ahk"
    echo "launching debug menu (window appears top-left; F8 hides it)..."
    "$APP/Contents/SharedSupport/wine/bin/wine" 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\i76-debugmenu.ahk' >/dev/null 2>&1 &
    echo "started (pid $!). Afterwards: tools/debugmenu.sh --fetch"
    ;;
esac

#!/bin/sh
# Interstate '76 - universal in-container input remapper (AutoHotkey v1.1).
#
# The engine knows exactly three mouse buttons; buttons 4/5 and the wheel only
# exist at the Windows layer. Instead of a per-OS remapper (Karabiner on Mac,
# Steam Input on Deck, ...), run ONE Windows-native remapper INSIDE the same
# Wine/Proton prefix on every platform: AutoHotkey v1.1.37.02 (portable exe,
# runs cleanly under Wine 10; config = i76-remap.ahk, checked into this repo).
#
#   setup-input-remapper.sh            install/refresh into every Mac wrapper
#   setup-input-remapper.sh --test     syntax-check + hook smoke test under Wine
#   setup-input-remapper.sh --revert   remove (the launcher then skips it)
#
# The Mac launcher stub (i76-launch-stub.swift) auto-starts
# C:\AutoHotkey\AutoHotkeyU32.exe C:\AutoHotkey\i76-remap.ahk when installed.
# Deck / native Windows: docs/INPUT-REMAPPER.md (+ i76-with-remap.bat).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
AHK_URL="https://github.com/AutoHotkey/AutoHotkey/releases/download/v1.1.37.02/AutoHotkey_1.1.37.02.zip"
AHK_SHA256="6f3663f7cdd25063c8c8728f5d9b07813ced8780522fd1f124ba539e2854215f"

find_games() {
    for base in "$HOME/Applications/Sikarugir" "$HOME/Applications" "/Applications"; do
        [ -d "$base" ] || continue
        find "$base" -maxdepth 8 -type d -path '*drive_c/GOG Games/Interstate 76' 2>/dev/null
    done | sort -u
}
GAMES=$(find_games)
[ -n "$GAMES" ] || { echo "no I76 wrapper found under ~/Applications"; exit 1; }

# game dir .../prefix/drive_c/GOG Games/Interstate 76 -> drive_c, prefix, .app root
drive_c_of() { dirname "$(dirname "$1")"; }
app_of()     { echo "${1%%/Contents/SharedSupport/*}"; }

if [ "$1" = "--revert" ]; then
    echo "$GAMES" | while read -r g; do
        D="$(drive_c_of "$g")/AutoHotkey"
        [ -d "$D" ] && { rm -rf "$D"; echo "removed: $D"; } || echo "not installed: $D"
    done
    exit 0
fi

ZIP=""
fetch_ahk() {  # download once, verify pinned sha256
    [ -n "$ZIP" ] && return 0
    ZIP="$(mktemp -d)/ahk.zip"
    echo "downloading AutoHotkey v1.1.37.02 (official GitHub release)..."
    curl -sL -o "$ZIP" "$AHK_URL"
    got=$(shasum -a 256 "$ZIP" | cut -d' ' -f1)
    [ "$got" = "$AHK_SHA256" ] || { echo "sha256 mismatch ($got) - aborting"; exit 1; }
}

echo "$GAMES" | while read -r g; do
    D="$(drive_c_of "$g")/AutoHotkey"
    mkdir -p "$D"
    if [ ! -f "$D/AutoHotkeyU32.exe" ]; then
        fetch_ahk
        unzip -o -q -j "$ZIP" AutoHotkeyU32.exe license.txt -d "$D"
    fi
    cp -f "$HERE/i76-remap.ahk" "$D/i76-remap.ahk"
    echo "installed -> $D (config: i76-remap.ahk)"
done

[ "$1" = "--test" ] || { echo "Done. Launcher picks it up next run (rebuild via build-launchers.sh if the stub predates 2026-07-14)."; exit 0; }

# --- --test: per wrapper, (1) load-time syntax check via /iLib (no run),
# (2) hook smoke test: SendLevel-1 SendEvent must trigger level-0 hotkeys,
# proving keyboard AND mouse hooks install and see injected events in the
# prefix. Skips the wineserver shutdown if the game is running.
echo "$GAMES" | while read -r g; do
    APP="$(app_of "$g")"
    D="$(drive_c_of "$g")/AutoHotkey"
    export WINEPREFIX="$APP/Contents/SharedSupport/prefix"
    export WINEESYNC=1 WINEMSYNC=1 WINEDEBUG=-all
    export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/SharedSupport/wine/lib"
    WINE="$APP/Contents/SharedSupport/wine/bin/wine"

    echo "== $APP"
    ERR=$("$WINE" 'C:\AutoHotkey\AutoHotkeyU32.exe' /ErrorStdOut /iLib NUL 'C:\AutoHotkey\i76-remap.ahk' 2>/dev/null || true)
    [ -z "$ERR" ] && echo "  syntax check: PASS" || { echo "  syntax check: FAIL"; echo "$ERR"; exit 1; }

    cat > "$D/smoke-test.ahk" <<'EOF'
#NoTrayIcon
#Persistent
#InstallKeybdHook
#InstallMouseHook
SendLevel, 1
FileAppend, alive %A_AhkVersion% ptr%A_PtrSize%`n, C:\AutoHotkey\smoke.txt
SetTimer, RunTest, -300
return
$F13::FileAppend, kbd-hook-fired`n, C:\AutoHotkey\smoke.txt
XButton2::FileAppend, mouse-hook-fired`n, C:\AutoHotkey\smoke.txt
RunTest:
SendEvent {F13}
Sleep, 800
SendEvent {Click X2}
Sleep, 800
FileAppend, test-done`n, C:\AutoHotkey\smoke.txt
ExitApp
EOF
    rm -f "$D/smoke.txt"
    "$WINE" 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\smoke-test.ahk' >/dev/null 2>&1
    sleep 1
    if grep -q kbd-hook-fired "$D/smoke.txt" 2>/dev/null && grep -q mouse-hook-fired "$D/smoke.txt"; then
        echo "  hook smoke test: PASS (keyboard + mouse hooks see injected events)"
    else
        echo "  hook smoke test: FAIL"; cat "$D/smoke.txt" 2>/dev/null; exit 1
    fi
    rm -f "$D/smoke.txt" "$D/smoke-test.ahk"
    if pgrep -f "i76\.exe" >/dev/null 2>&1; then
        echo "  (game running - leaving wineserver up)"
    else
        "$APP/Contents/SharedSupport/wine/bin/wineserver" -k 2>/dev/null || true
    fi
done
echo "All tests passed."

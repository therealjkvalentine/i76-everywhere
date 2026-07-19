#!/bin/sh
# Find-what-writes / breakpoint driver for i76.exe using winedbg on macOS Wine.
#
# WHY launch-mode (not attach): macOS denies debugger-attach to the running game
# ("error 5"). But LAUNCHING i76.exe under winedbg gives full 32-bit debug
# control (breakpoints, registers, watchpoints) - verified 2026-07-18. So this
# creates a fresh debug instance rather than attaching to the user's game.
#
# Usage:
#   i76-findwrites.sh watch 0x<addr>     # break when <addr> is written, dump regs+bt
#   i76-findwrites.sh break 0x<addr>     # break at code <addr>, dump regs+bt
#   i76-findwrites.sh cmds '<winedbg cmds; newline-separated>'
#
# NOTE: the debug instance renders via its own DirectDraw (no DxWnd), so it
# competes with the user's game for the display. Run when the user's session is
# paused, or point WINEPREFIX at a cloned prefix (I76_DEBUG_PREFIX env).
set -e
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
PFX="${I76_DEBUG_PREFIX:-$APP/Contents/SharedSupport/prefix}"
WINE="$APP/Contents/SharedSupport/wine/bin/wine"
GAME='C:\GOG Games\Interstate 76\i76.exe'
export WINEPREFIX="$PFX" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"

MODE="$1"; ADDR="$2"
case "$MODE" in
  watch)  SCRIPT="watch *$ADDR
cont
info reg
bt
detach
quit
y";;
  break)  SCRIPT="break *$ADDR
cont
info reg
bt
detach
quit
y";;
  cmds)   SCRIPT="$2";;
  *) echo "usage: $0 watch|break 0x<addr>  |  cmds '<winedbg cmds>'"; exit 1;;
esac

printf '%s\n' "$SCRIPT" | timeout "${I76_DBG_TIMEOUT:-60}" "$WINE" winedbg "$GAME" 2>&1 \
  | grep -viE 'fixme|preloader|err:environ'

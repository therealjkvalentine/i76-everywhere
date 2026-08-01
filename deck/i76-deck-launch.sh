#!/bin/bash
# Interstate '76 - Steam launch wrapper for the Deck BASELINE tier.
#
# Put this in the shortcut's LAUNCH OPTIONS (Steam > Interstate 76 > Properties):
#
#     "/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide
#
# Steam expands %command% to the whole reaper/runtime/proton invocation, so this
# script receives the real launch line as "$@" and can reuse it verbatim.
#
# WHAT IT DOES: starts AutoHotkey (i76-remap.ahk - the pad layer + rumble mixer
# shared with Mac/Windows) INSIDE THE SAME Proton prefix as the game, then runs
# the game, then tears AHK down. Without this the remapper would land in its own
# prefix and see nothing.
#
# WHY THE PREFIX IS DISCOVERED AT RUNTIME: Steam runs non-Steam shortcuts in
# ~/.steam/steam/steamapps/compatdata/<appid>/pfx - NOT the prefix deck-install.sh
# built. Rather than guess the appid, we read $STEAM_COMPAT_DATA_PATH, which Steam
# exports into this wrapper's environment, and sync the AHK payload in from the
# staging dir on every launch. That also survives a prefix rebuild.
#
# Degrades gracefully: if the payload or Proton can't be found, the game still
# launches (just without the pad layer). It must never block play.
set -u

STAGE="${I76_AHK_STAGE:-$HOME/Games/Interstate76/ahk}"
LOG="${I76_LAUNCH_LOG:-$HOME/Games/Interstate76/deck-launch.log}"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
: > "$LOG" 2>/dev/null || LOG=/dev/null
log() { echo "[i76-launch] $*" >> "$LOG"; }

log "argv: $*"
log "STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-<unset>}"

# --- locate Proton in the expanded %command% -------------------------------
PROTON=""
for a in "$@"; do
    case "$a" in
        */proton) if [ -x "$a" ]; then PROTON="$a"; break; fi ;;
    esac
done
[ -n "$PROTON" ] && log "proton: $PROTON" || log "proton: NOT FOUND in argv"

# --- is there a payload to inject? ------------------------------------------
# NOTE: the actual copy happens AFTER the warm-up sleep below, not here. On a
# first-ever launch the prefix doesn't exist yet, so drive_c only appears once
# Proton has built it - staging up front would silently no-op on exactly the
# run where a new user is watching.
DRIVE_C="${STEAM_COMPAT_DATA_PATH:-}/pfx/drive_c"
HAVE_PAYLOAD=""
if [ -n "${STEAM_COMPAT_DATA_PATH:-}" ] \
   && [ -f "$STAGE/AutoHotkeyU32.exe" ] && [ -f "$STAGE/i76-remap.ahk" ]; then
    HAVE_PAYLOAD=1
else
    log "no payload (stage=$STAGE, compat=${STEAM_COMPAT_DATA_PATH:-<unset>}) - launching bare"
fi

# --- run the game ------------------------------------------------------------
# Backgrounded (not exec'd) so we still own the process and can clean up after.
"$@" &
GAME_PID=$!
log "game pid $GAME_PID"

AHK_PID=""
cleanup() {
    if [ -n "$AHK_PID" ]; then
        kill "$AHK_PID" 2>/dev/null || true
    fi
    # Belt-and-braces: a live AutoHotkeyU32.exe would keep Proton's wineserver up
    # and leave Steam showing the game as still running.
    pkill -f 'AutoHotkeyU32\.exe' 2>/dev/null || true
    log "cleanup done"
}
trap cleanup EXIT INT TERM

# Give Proton time to build/boot the prefix before injecting a second process;
# starting AHK first on a cold prefix races the game's own prefix creation.
if [ -n "$PROTON" ] && [ -n "$HAVE_PAYLOAD" ]; then
    (
        # 15s is an ASSUMPTION, not a measurement - it's "long enough for Proton
        # to build/boot a cold prefix" on a Deck. If the log shows AHK starting
        # before the game is up (or too late to catch the first mission), retune:
        #   I76_AHK_DELAY=25 in the launch options, ahead of the wrapper path.
        sleep "${I76_AHK_DELAY:-15}"
        # Bail if the game already died during warm-up.
        kill -0 "$GAME_PID" 2>/dev/null || exit 0
        if [ ! -d "$DRIVE_C" ]; then
            log "drive_c still absent after warm-up - skipping AHK this run"
            exit 0
        fi
        mkdir -p "$DRIVE_C/AutoHotkey"
        cp -f "$STAGE/AutoHotkeyU32.exe" "$DRIVE_C/AutoHotkey/" 2>/dev/null || true
        cp -f "$STAGE/i76-remap.ahk"     "$DRIVE_C/AutoHotkey/" 2>/dev/null || true
        if [ -f "$STAGE/license.txt" ]; then
            cp -f "$STAGE/license.txt" "$DRIVE_C/AutoHotkey/" 2>/dev/null || true
        fi
        log "payload staged -> $DRIVE_C/AutoHotkey; starting AHK"
        "$PROTON" run 'C:\AutoHotkey\AutoHotkeyU32.exe' 'C:\AutoHotkey\i76-remap.ahk' >>"$LOG" 2>&1
    ) &
    AHK_PID=$!
    log "ahk launcher pid $AHK_PID (stages + starts in ${I76_AHK_DELAY:-15}s)"
fi

wait "$GAME_PID"
RC=$?
log "game exited rc=$RC"
exit $RC

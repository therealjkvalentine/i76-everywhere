#!/bin/bash
# Interstate '76 - Steam launch wrapper for the Deck: loads the engine switches
# (i76-env.sh, written by setup-deck-wide.sh) and the BASELINE tier's AHK pad layer.
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

# --- engine switches (deck/setup-deck-wide.sh) -------------------------------
# The Strlkup.dll proxy reads I76_* from the environment, and Wine passes the Unix
# environment through to i76.exe. No file = stock behaviour.
ENVF="${I76_ENV_FILE:-$HOME/Games/Interstate76/i76-env.sh}"
if [ -f "$ENVF" ]; then
    # shellcheck disable=SC1090
    . "$ENVF"
    log "switches from $ENVF: $(env | grep -E '^I76' | sort | tr '\n' ' ')"
else
    log "no $ENVF - no engine switches"
fi

# --- display profile: handheld panel or TV (2026-10-13) -----------------------
# Owner, docked to a TV: "the screen renders in a non 16:9 aspect ratio" and "looks a little darker".
# The picture's shape is the size of the X screen the game is given, not the TV: in Game Mode
# gamescope runs the game in its own Xwayland whose size is Steam's per-game "Game Resolution"
# (Default = 1280x800 for this shortcut even when docked; gamescope then scales that 16:10 picture
# onto the TV with bars). So the size is read from the game's own X display ($DISPLAY) and becomes
# I76_ASPECT (Hor+ camera, HUD squeeze) and dgVoodoo's [Glide] Resolution; the profile picks the
# brightness. Values (i76-env.sh, all optional):
#   I76_DECK_DISPLAY = auto (default) | handheld | tv | off (off = leave I76_ASPECT and dgVoodoo.conf alone)
#   I76_HANDHELD_GAMMA (1.3)  I76_HANDHELD_BRIGHTNESS (100)  I76_HANDHELD_SS (2 = render at 2x, averaged down)
#   I76_TV_GAMMA (1.45)       I76_TV_BRIGHTNESS (100)        I76_TV_SS (1)     I76_TV_REFRESH (60)
#   I76_TV_CONTRAST / I76_TV_COLOR, I76_HANDHELD_CONTRAST / I76_HANDHELD_COLOR (100 = dgVoodoo neutral)
#   I76_DECK_MAXPIX (2073600 = 1920x1080): the render size is halved while it is above this (4K TVs)
# Gamma lifts the 3D mission picture only (glide2x gamma ramp; higher = brighter mid-tones, no clipping);
# dgVoodoo Brightness / Contrast / Color are linear and also reach the menus and movies.
DISP_PROFILE="${I76_DECK_DISPLAY:-auto}"
GAMEDIR_D="${I76_GAMEDIR:-$HOME/Games/Interstate76/game}"
screen_size() {    # WxH of the X screen the game will run on, or nothing
    local s=""
    if command -v xrandr >/dev/null 2>&1; then
        # a primary output's own size first (desktop mode with two screens), else the whole screen
        s=$(xrandr --current 2>/dev/null | sed -n 's/^[^ ]* connected primary \([0-9]*x[0-9]*\)+.*/\1/p' | head -1)
        [ -n "$s" ] || s=$(xrandr --current 2>/dev/null | sed -n 's/^Screen 0:.*current \([0-9]*\) x \([0-9]*\),.*/\1x\2/p' | head -1)
    fi
    if [ -z "$s" ] && command -v xdpyinfo >/dev/null 2>&1; then
        s=$(xdpyinfo 2>/dev/null | sed -n 's/^ *dimensions: *\([0-9]*x[0-9]*\) pixels.*/\1/p' | head -1)
    fi
    if [ -z "$s" ] && command -v python3 >/dev/null 2>&1; then
        s=$(python3 - 2>/dev/null <<'PY'
import ctypes
x = ctypes.CDLL("libX11.so.6"); x.XOpenDisplay.restype = ctypes.c_void_p
d = x.XOpenDisplay(None)
if d:
    d = ctypes.c_void_p(d); print("%dx%d" % (x.XDisplayWidth(d, 0), x.XDisplayHeight(d, 0)))
PY
)
    fi
    echo "$s"
}
external_display() {   # "<connector> <preferred mode>" of a connected HDMI / DP output, or nothing
    local st c m
    for st in ${I76_DRM_GLOB:-/sys/class/drm/card*-*/status}; do
        [ -f "$st" ] || continue
        c=$(basename "$(dirname "$st")")
        case "$c" in *eDP*|*LVDS*|*DSI*|*Writeback*) continue ;; esac
        [ "$(cat "$st" 2>/dev/null)" = connected ] || continue
        m=$(head -1 "$(dirname "$st")/modes" 2>/dev/null)
        echo "${c#card*-} ${m:-unknown}"; return 0
    done
}
for f in "$GAMEDIR_D"/*; do    # which proxy / shell / exe this launch runs (any case: GOG writes some upper case)
    case "$(basename "$f" | tr 'A-Z' 'a-z')" in strlkup.dll|i76shell.dll|i76.exe) log "md5 $(md5sum "$f" 2>/dev/null)" ;; esac
done
if [ "$DISP_PROFILE" != off ]; then
    SCR="$(screen_size)"; EXT="$(external_display)"
    log "display: DISPLAY=${DISPLAY:-<unset>} screen=${SCR:-<unknown>} external=${EXT:-none} gamescope=$(env | grep -E '^(GAMESCOPE|STEAM_GAMESCOPE|SteamDeck|STEAM_DISPLAY)' | tr '\n' ' ')"
    if [ "$DISP_PROFILE" = auto ]; then
        if [ -n "$EXT" ]; then DISP_PROFILE=tv; else DISP_PROFILE=handheld; fi
    fi
    SW="${SCR%x*}"; SH="${SCR#*x}"
    case "$SW$SH" in ''|*[!0-9]*) SW=""; SH="" ;; esac
    if [ -z "$SW" ]; then
        SW=1280; SH=800; log "display: screen size unreadable - assuming the panel's 1280x800"
    fi
    if [ "$DISP_PROFILE" = tv ]; then
        GAMMA="${I76_TV_GAMMA:-1.45}"; BRIGHT="${I76_TV_BRIGHTNESS:-100}"; SS="${I76_TV_SS:-1}"
        CONTR="${I76_TV_CONTRAST:-100}"; COLR="${I76_TV_COLOR:-100}"
        export I76_GLIDE_REFRESH="${I76_TV_REFRESH:-60}"
        if [ "$SW" -eq 1280 ] && [ "$SH" -eq 800 ] && [ -n "$EXT" ]; then
            log "display: WARNING - docked (${EXT}) but the game gets 1280x800, so the TV shows a 16:10 picture with bars."
            log "display:   Fix: Game Mode > Interstate 76 > gear > Properties > General > Game Resolution = Native (or 1920x1080)."
        fi
    else
        GAMMA="${I76_HANDHELD_GAMMA:-1.3}"; BRIGHT="${I76_HANDHELD_BRIGHTNESS:-100}"; SS="${I76_HANDHELD_SS:-2}"
        CONTR="${I76_HANDHELD_CONTRAST:-100}"; COLR="${I76_HANDHELD_COLOR:-100}"
    fi
    RW=$((SW * SS)); RH=$((SH * SS)); MAXPIX="${I76_DECK_MAXPIX:-2073600}"
    while [ $((RW * RH)) -gt "$MAXPIX" ] && [ "$SS" -gt 1 ]; do SS=$((SS - 1)); RW=$((SW * SS)); RH=$((SH * SS)); done
    while [ $((RW * RH)) -gt "$MAXPIX" ] && [ "$RW" -gt 1280 ]; do RW=$((RW / 2)); RH=$((RH / 2)); done
    # the handheld 2x (2560x1600) is above MAXPIX on purpose: measured 60.0 fps on the LCD (2026-10-07)
    if [ "$DISP_PROFILE" = handheld ] && [ "$SW" -eq 1280 ] && [ "$SH" -eq 800 ]; then
        SS="${I76_HANDHELD_SS:-2}"; RW=$((SW * SS)); RH=$((SH * SS))
    fi
    export I76_ASPECT="${SW}x${SH}" I76_GLIDE_GAMMA="$GAMMA"
    log "display: profile $DISP_PROFILE - I76_ASPECT=$I76_ASPECT, render ${RW}x${RH}, gamma $GAMMA, brightness $BRIGHT, contrast $CONTR, color $COLR, refresh ${I76_GLIDE_REFRESH:-?}"
    CONF="$GAMEDIR_D/dgVoodoo.conf"
    if [ -f "$CONF" ] && command -v python3 >/dev/null 2>&1; then
        # values only, never keys (dgVoodoo rejects a conf over one line it does not know); a key that is
        # not there exactly once in its section is left alone and logged
        python3 - "$CONF" "${RW}x${RH}" "$BRIGHT" "$CONTR" "$COLR" >>"$LOG" 2>&1 <<'PY' || log "display: dgVoodoo.conf not changed (python error)"
import re, sys, os
p, res, bri, con, col = sys.argv[1:6]
t = open(p, encoding="latin-1").read()
out = []
for sec, key, val in [("Glide", "Resolution", res), ("General", "Brightness", bri),
                      ("General", "Contrast", con), ("General", "Color", col)]:
    hs = list(re.finditer(r'(?m)^\[([^\]]+)\][ \t]*$', t))
    idx = [i for i, m in enumerate(hs) if m.group(1) == sec]
    if len(idx) != 1:
        out.append("[%s] x%d - left alone" % (sec, len(idx))); continue
    i = idx[0]; a = hs[i].end(); b = hs[i + 1].start() if i + 1 < len(hs) else len(t)
    body = t[a:b]
    pat = re.compile(r'(?m)^(%s[ \t]*=[ \t]*)([^;\n]*?)([ \t]*(?:;[^\n]*)?)$' % re.escape(key))
    hits = pat.findall(body)
    if len(hits) != 1:
        out.append("[%s] %s x%d - left alone" % (sec, key, len(hits))); continue
    old = hits[0][1].strip()
    if old == val:
        out.append("%s=%s" % (key, val)); continue
    t = t[:a] + pat.sub(lambda m: m.group(1) + val + m.group(3), body, count=1) + t[b:]
    out.append("%s %s->%s" % (key, old, val))
tmp = p + ".tmp"
open(tmp, "w", encoding="latin-1", newline="").write(t)
os.replace(tmp, p)
print("[i76-launch] display: dgVoodoo.conf " + ", ".join(out))
PY
    else
        log "display: no $CONF or no python3 - dgVoodoo.conf not changed"
    fi
fi

# --- control profile (deck/setup-deck-pad.sh) ---------------------------------
# One layout since 2026-10-08 (owner: the Deck plays exactly the gamepad layout): Steam layout
# controller_neptune_i76_pad.vdf presents a plain pad, the shared i76-remap.ahk (the Windows/Mac
# pad layer) turns it into keys, so the shared controls/input.map is the live map. input.map is
# the only file the engine reads, so it is copied into place on every launch. I76_PROFILE=deck
# (launch options) brings back the old key layout's map for a v8.1 controller layout.
GAMEDIR_W="${I76_GAMEDIR:-$HOME/Games/Interstate76/game}"
if [ "${I76_PROFILE:-pad}" = "pad" ]; then
    export I76_DECK_AHK=1
    MAPSRC="$GAMEDIR_W/input.map.profile-pad"
else
    MAPSRC="$GAMEDIR_W/input.map.profile-deck"
fi
if [ -f "$MAPSRC" ]; then
    cp -f "$MAPSRC" "$GAMEDIR_W/input.map" && log "profile ${I76_PROFILE:-pad}: input.map <- $(basename "$MAPSRC")"
else
    log "profile ${I76_PROFILE:-pad}: $MAPSRC missing - input.map left as it is"
fi

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
if [ "${I76_DECK_AHK:-1}" = "0" ]; then
    log "I76_DECK_AHK=0 - pad layer off (Steam Input layout drives the game)"
elif [ -n "${STEAM_COMPAT_DATA_PATH:-}" ] \
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

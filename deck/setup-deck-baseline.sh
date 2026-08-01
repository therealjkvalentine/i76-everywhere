#!/bin/bash
# Interstate '76 - switch the Deck to the BASELINE control tier. RUNS ON THE DECK.
#
# Brings the Deck to parity with the Mac/Windows controller work: the shared
# AutoHotkey layer (i76-remap.ahk) supplies the LB shift layer, independent
# triggers, look-back rear gun, camera cycle and the RUMBLE MIXER, while the
# game's own winmm joystick1 bindings carry analog steer/throttle.
#
# Trade-off you are opting into (docs/DECK-BASELINE.md): the Steam Input v4
# config's trackpad radial menu and L4/L5/R4/R5 grip bindings go away. They are
# convenience-tier only - every critical action is covered by this tier
# (docs/CONTROL-DOCTRINE.md).
#
#   ./setup-deck-baseline.sh              install
#   ./setup-deck-baseline.sh --revert     restore input.map + remove the payload
#
# AFTER RUNNING, two manual Steam steps (see the summary this prints):
#   1. Launch options   -> the wrapper line
#   2. Controller layout -> Valve's "Gamepad" template
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
INSTALL="${I76_INSTALL:-$HOME/Games/Interstate76}"
GAMEDIR="${I76_GAMEDIR:-$INSTALL/game}"
STAGE="$INSTALL/ahk"
MAPF="$GAMEDIR/input.map"
MARK="# --- BASELINE gamepad tier (deck/setup-deck-baseline.sh) ---"

AHK_URL="https://github.com/AutoHotkey/AutoHotkey/releases/download/v1.1.37.02/AutoHotkey_1.1.37.02.zip"
AHK_SHA256="6f3663f7cdd25063c8c8728f5d9b07813ced8780522fd1f124ba539e2854215f"

say() { echo "  $*"; }

# ---------------------------------------------------------------- revert ----
if [ "${1:-}" = "--revert" ]; then
    echo "== reverting =="
    if [ -f "$MAPF.pre-baseline" ]; then
        mv -f "$MAPF.pre-baseline" "$MAPF"; say "input.map restored from .pre-baseline"
    else
        say "no .pre-baseline backup found - input.map left alone"
    fi
    rm -rf "$STAGE" "$INSTALL/i76-deck-launch.sh"
    say "payload + wrapper removed"
    echo
    echo "Also undo in Steam: clear the launch options back to just  -glide"
    echo "and re-select the 'Interstate 76 - Option 1 v4' controller template."
    exit 0
fi

[ -d "$GAMEDIR" ] || { echo "game dir not found: $GAMEDIR (set I76_GAMEDIR)"; exit 1; }

# ------------------------------------------------------------ 1. payload ----
echo "== 1. AutoHotkey payload =="
mkdir -p "$STAGE"
if [ ! -f "$STAGE/AutoHotkeyU32.exe" ]; then
    TMP="$(mktemp -d)"; ZIP="$TMP/ahk.zip"
    say "downloading AutoHotkey v1.1.37.02 (official GitHub release)..."
    curl -fsSL -o "$ZIP" "$AHK_URL"
    # sha256sum on Linux, shasum on macOS - this script may be run from either
    if command -v sha256sum >/dev/null 2>&1; then got=$(sha256sum "$ZIP" | cut -d' ' -f1)
    else got=$(shasum -a 256 "$ZIP" | cut -d' ' -f1); fi
    [ "$got" = "$AHK_SHA256" ] || { echo "sha256 mismatch ($got) - aborting"; rm -rf "$TMP"; exit 1; }
    # python3 rather than unzip: guaranteed present on SteamOS, unzip is not
    python3 - "$ZIP" "$STAGE" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for n in ("AutoHotkeyU32.exe", "license.txt"):
    try:
        with z.open(n) as s, open(sys.argv[2] + "/" + n, "wb") as d:
            d.write(s.read())
    except KeyError:
        pass
PY
    rm -rf "$TMP"
    say "AutoHotkeyU32.exe staged"
else
    say "AutoHotkeyU32.exe already staged"
fi

# Lint carried over from setup-input-remapper.sh: a bare wheel remap sticks the
# destination key down forever (AHK gives the wheel no release event). This bit
# us once already - never ship a config that has one.
if grep -qE '^[[:space:]]*[*~$]*Wheel(Up|Down|Left|Right)::[^[:space:]]+[[:space:]]*$' "$REPO/i76-remap.ahk"; then
    echo "FATAL: i76-remap.ahk contains a bare wheel remap (WheelUp::key) - the key would stick."
    exit 1
fi
cp -f "$REPO/i76-remap.ahk" "$STAGE/i76-remap.ahk"
say "i76-remap.ahk staged (shared with Mac/Windows - one source of truth)"

# ------------------------------------------------------------ 2. wrapper ----
echo "== 2. launch wrapper =="
cp -f "$HERE/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh"
chmod +x "$INSTALL/i76-deck-launch.sh"
say "installed -> $INSTALL/i76-deck-launch.sh"

# ----------------------------------------------------------- 3. input.map ---
echo "== 3. input.map baseline bindings =="
if [ ! -f "$MAPF" ]; then
    say "input.map not found at $MAPF - launch the game once, then re-run"
elif grep -qF "$MARK" "$MAPF"; then
    say "baseline block already present (idempotent - nothing to do)"
else
    [ -f "$MAPF.pre-baseline" ] || cp "$MAPF" "$MAPF.pre-baseline"
    # The analog sinks are REPLACED (steer/throttle can only have one live
    # source pair); the button/hat blocks are APPENDED as alternatives. Tokens
    # are verbatim from the game's own JOYSTICK.MAP - see the long note in
    # docs/input.map.reference about `Down/Up` and `-` polarity.
    python3 - "$MAPF" <<'PY'
import re, sys
p = sys.argv[1]
# latin-1 round-trips arbitrary bytes; this is a 1997 file of unknown encoding.
t = open(p, encoding="latin-1").read()
for sink, body in (("steer", "   - joystick1  Left/Right"),
                   ("throttle", "   - joystick1  Down/Up")):
    block = "%s {\n%s\n}" % (sink, body)
    # `steer {` cannot match `steer_left {` - the space+brace is required.
    t, n = re.subn(r'%s \{[^}]*\}' % sink, block, t, count=1)
    if not n:                       # sink absent entirely - append it
        t = t.rstrip() + "\n\n" + block + "\n"
        print("  (%s block was missing - appended)" % sink)
open(p, "w", encoding="latin-1").write(t)
PY
    cat >> "$MAPF" <<EOF

$MARK
# Parity with Mac/Windows. Analog steer/throttle above now read joystick1 only.
# Face buttons + hat below are ALTERNATIVES (separate blocks, never chords -
# see the alternatives rule in docs/CONTROL-DOCTRINE.md).
# Rollback: deck/setup-deck-baseline.sh --revert
weapon_fire {
   + joystick1  Button1
}
special1 {
   + joystick1  Button2
}
weapon_cycle {
   + joystick1  Button3
}
e_brake {
   + joystick1  Button4
}
pilot_glance_up {
   + joystick1  HatUp
}
pilot_glance_down {
   + joystick1  HatDown
}
pilot_glance_left {
   + joystick1  HatLeft
}
pilot_glance_right {
   + joystick1  HatRight
}
EOF
    say "baseline block appended (backup: input.map.pre-baseline)"
fi

# -------------------------------------------------------------- summary ----
cat <<EOF

================================================================
Deployed. TWO MANUAL STEAM STEPS REMAIN - neither can be scripted
safely while Steam is running.

1. LAUNCH OPTIONS
   Steam > Interstate 76 > Properties > Launch Options, replace with:

     "$INSTALL/i76-deck-launch.sh" %command% -glide

2. CONTROLLER LAYOUT
   Steam > Interstate 76 > controller icon > Browse Configs >
   Templates > "Gamepad".

   NOT "disable Steam Input" - on a Deck that drops you into lizard
   mode (keyboard/mouse emulation), which is the opposite of what
   this tier wants. The Gamepad template keeps Steam Input on but
   makes it present a plain XInput pad: raw buttons reach the AHK
   layer, sticks reach joystick1, and rumble has a path back to the
   haptics.

Then: connect nothing, just launch (the Deck's own pad enumerates at
startup). Work through the decode sheet in docs/DECK-BASELINE.md and
report back - the button numbering and the rumble path are ASSUMED on
Deck hardware until you confirm them.

Launch log (for when something looks wrong):
  $INSTALL/deck-launch.log
================================================================
EOF

#!/bin/bash
# Interstate '76 - the second Deck control profile: the shared pad layer. RUNS ON THE DECK.
#
# Adds a library entry "Interstate 76 (pad layer)" beside the normal one. It plays the same game
# folder with the controls Windows and Mac use (docs/CONTROL-DOCTRINE.md, "Direction for the Steam
# Deck"): Steam Input layout v9 presents a plain gamepad (+ the Deck extras: grips, trackpad menu,
# trackpad mouse), the shared i76-remap.ahk runs inside the Proton prefix and turns the pad into keys
# (analog driving, Y view cycle, LB shift layer for hardpoints / gears / horn / binoculars), and the
# shared controls/input.map is the live map while it runs. The normal entry keeps layout v8.1 and the
# Deck's own map; i76-deck-launch.sh copies the right map into place on every launch.
#
#   ./setup-deck-pad.sh            install or update (re-runnable)
#   ./setup-deck-pad.sh --revert   remove the profile files (the library entry stays; delete it in Steam)
#
# STATUS 2026-10-07: built from the Mac; the shared pad layer has never run on Deck hardware.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="${I76_PAYLOAD:-$HERE/..}"
INSTALL="${I76_INSTALL:-$HOME/Games/Interstate76}"
GAME="${I76_GAMEDIR:-$INSTALL/game}"
STAGE="$INSTALL/ahk"
TEMPLATES="$HOME/.steam/steam/controller_base/templates"
AHK_URL="https://github.com/AutoHotkey/AutoHotkey/releases/download/v1.1.37.02/AutoHotkey_1.1.37.02.zip"
AHK_SHA256="6f3663f7cdd25063c8c8728f5d9b07813ced8780522fd1f124ba539e2854215f"
say() { echo "  $*"; }
die() { echo "FATAL: $*"; exit 1; }

if [ "${1:-}" = "--revert" ]; then
    [ -f "$GAME/input.map.profile-deck" ] && cp -f "$GAME/input.map.profile-deck" "$GAME/input.map" && say "input.map <- input.map.profile-deck"
    rm -f "$GAME/input.map.profile-pad" "$TEMPLATES/controller_neptune_i76_pad.vdf"
    say "profile files removed; delete the 'Interstate 76 (pad layer)' entry in Steam (Manage > Remove)"
    exit 0
fi

[ -f "$GAME/i76.exe" ] || die "no i76.exe in $GAME"
for f in controls/input.map i76-remap.ahk deck/controller_neptune_i76_pad.vdf deck/i76-deck-launch.sh deck/add-pad-shortcut.py; do
    [ -f "$PAYLOAD/$f" ] || die "payload missing: $f"
done
if pgrep -x i76.exe >/dev/null 2>&1; then die "the game is running - quit it first"; fi

echo "== 1. maps =="
if [ ! -f "$GAME/input.map.profile-deck" ]; then
    cp "$GAME/input.map" "$GAME/input.map.profile-deck"; say "the Deck's map kept as input.map.profile-deck"
else
    say "input.map.profile-deck already kept"
fi
cp -f "$PAYLOAD/controls/input.map" "$GAME/input.map.profile-pad"
say "input.map.profile-pad <- controls/input.map (md5 $(md5sum "$GAME/input.map.profile-pad" | cut -c1-8))"
if [ -f "$PAYLOAD/tools/lint-input-map.py" ]; then
    T="$(mktemp -d)"; cp "$GAME/input.map.profile-pad" "$T/input.map"; cp "$GAME/i76.exe" "$T/"
    python3 "$PAYLOAD/tools/lint-input-map.py" "$T" | tail -1 | sed 's/^/  lint: /'; rm -rf "$T"
fi

echo "== 2. pad layer (AutoHotkey inside the prefix) =="
mkdir -p "$STAGE"
if [ ! -f "$STAGE/AutoHotkeyU32.exe" ]; then
    T="$(mktemp -d)"; curl -fsSL -o "$T/ahk.zip" "$AHK_URL"
    [ "$(sha256sum "$T/ahk.zip" | cut -d' ' -f1)" = "$AHK_SHA256" ] || die "AutoHotkey download: sha256 mismatch"
    python3 - "$T/ahk.zip" "$STAGE" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for n in ("AutoHotkeyU32.exe", "license.txt"):
    try:
        open(sys.argv[2] + "/" + n, "wb").write(z.read(n))
    except KeyError:
        pass
PY
    rm -rf "$T"; say "AutoHotkey 1.1.37.02 staged"
else
    say "AutoHotkey already staged"
fi
if grep -qE '^[[:space:]]*[*~$]*Wheel(Up|Down|Left|Right)::[^[:space:]]+[[:space:]]*$' "$PAYLOAD/i76-remap.ahk"; then
    die "i76-remap.ahk has a bare wheel remap (the key would stick)"
fi
cp -f "$PAYLOAD/i76-remap.ahk" "$STAGE/i76-remap.ahk"; say "i76-remap.ahk staged (md5 $(md5sum "$STAGE/i76-remap.ahk" | cut -c1-8))"

echo "== 3. Steam layout v9 + launch wrapper =="
mkdir -p "$TEMPLATES"
cp -f "$PAYLOAD/deck/controller_neptune_i76_pad.vdf" "$TEMPLATES/"; say "template installed"
cp -f "$PAYLOAD/deck/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh"; chmod +x "$INSTALL/i76-deck-launch.sh"; say "wrapper installed"

echo "== 4. library entry =="
if pgrep -x steam >/dev/null 2>&1; then
    say "Steam is running: close it and run   python3 $PAYLOAD/deck/add-pad-shortcut.py"
else
    python3 "$PAYLOAD/deck/add-pad-shortcut.py"
fi
cat <<EOF

Done. In the library: "Interstate 76" = layout v8.1 (as before), "Interstate 76 (pad layer)" = the
shared pad layer. The first launch of the new entry builds its own Proton prefix (a minute).
Launch log: $INSTALL/deck-launch.log (look for 'profile pad' and 'starting AHK').
EOF

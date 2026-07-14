#!/bin/bash
# Interstate '76 - Steam Deck installer. RUN ON THE DECK in Desktop Mode.
# Installs the game + dgVoodoo + configs into a self-contained Wine/Proton prefix,
# adds it to Steam as a non-Steam game with our controller config + artwork, and
# sets the -glide launch. No GOG login needed (game files are bundled).
#
# Usage (from the unpacked bundle dir):  ./install-on-deck.sh
set -e
BUNDLE="$(cd "$(dirname "$0")" && pwd)"
INSTALL="$HOME/Games/Interstate76"
PREFIX="$INSTALL/prefix"
GAMEDIR="$INSTALL/game"
echo "== Interstate '76 -> Steam Deck =="

# 1. Lay down the game
mkdir -p "$GAMEDIR"
echo "Copying game files..."
cp -a "$BUNDLE/game/." "$GAMEDIR/"

# 1b. Deck-tune dgVoodoo.conf: FULLSCREEN + fill the 16:10 panel (the shipped conf is
#     the Mac windowed one). Gamescope shows the fullscreen swapchain edge-to-edge.
python3 - "$GAMEDIR/dgVoodoo.conf" <<'PY' 2>/dev/null || true
import re,sys
f=sys.argv[1]; t=open(f).read()
t=re.sub(r'FullScreenMode\s*=\s*\w+.*','FullScreenMode                       = true', t)
t=re.sub(r'ScalingMode\s*=\s*[\w]+.*','ScalingMode                          = stretched   ; fill 16:10 (halfway 4:3<->16:9)', t)
t=re.sub(r'Resolution\s*=\s*\S+.*','Resolution                           = 1280x800     ; Deck native', t)
open(f,'w').write(t)
PY
echo "dgVoodoo.conf tuned for the Deck (fullscreen 16:10)"

# 2. Find a Proton / Wine to build the prefix. Prefer Proton GE, then any Proton,
#    then system wine. We only need it to (a) create the prefix and (b) do the FFB
#    registry rename; Steam will run the game with its own Proton at launch.
find_proton() {
  for p in "$HOME"/.steam/steam/compatibilitytools.d/*/proton \
           "$HOME"/.local/share/Steam/compatibilitytools.d/*/proton \
           "$HOME"/.steam/steam/steamapps/common/Proton*/proton; do
    [ -x "$p" ] && { echo "$p"; return; }
  done
}
PROTON="$(find_proton || true)"
export STEAM_COMPAT_DATA_PATH="$PREFIX"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.steam/steam"
mkdir -p "$PREFIX"

runwine() { # run a wine command through Proton if we have it, else system wine
  if [ -n "$PROTON" ]; then "$PROTON" run "$@"; else WINEPREFIX="$PREFIX/pfx" wine "$@"; fi
}

# 3. Force feedback (docked wheel) - registry rename. Harmless if no wheel.
echo "Enabling force feedback registry key (for a docked wheel)..."
runwine reg copy "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate'76FRC" \
                 "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate '76" /s /f 2>/dev/null || \
runwine reg add  "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate '76" /v EXE /t REG_SZ /d i76.exe /f 2>/dev/null || \
  echo "  (FFB key step skipped - do it later via protontricks if you dock a wheel)"

# 4. Add to Steam as a non-Steam game + artwork + controller config, if the helper
#    is present and Steam is installed.
if [ -f "$BUNDLE/config/add-to-steam.py" ]; then
  echo "Registering with Steam (shortcut + artwork + controller config)..."
  python3 "$BUNDLE/config/add-to-steam.py" \
    --name "Interstate '76" \
    --exe "$GAMEDIR/i76.exe" \
    --args "-glide" \
    --startdir "$GAMEDIR" \
    --artwork "$BUNDLE/artwork" \
    --controller "$BUNDLE/config/i76_deck_controller.vdf" \
    || echo "  (Steam registration needs Steam closed OR do the manual steps in STEAMDECK-README.txt)"
fi

cat <<EOF

Done. Game at: $GAMEDIR
Next (in Steam / Game Mode):
  1. If it wasn't auto-added: Steam > Games > Add a Non-Steam Game > Browse >
     $GAMEDIR/i76.exe ; set launch options to:  -glide
  2. In the game's Properties > Compatibility, force Proton (GE-Proton if you have it).
  3. Controller: apply the "Interstate 76 (driving)" config - see STEAMDECK-README.txt.
  4. Cap to 20 FPS (QAM > Performance > Framerate Limit = 20) - physics safety.
First launch takes a bit (shader precompile); after that it's warm. Have fun.
EOF

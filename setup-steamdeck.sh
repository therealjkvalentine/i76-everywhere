#!/bin/bash
# Interstate '76 - Steam Deck / Linux setup helper. Run in Desktop Mode AFTER installing
# the GOG game via Heroic. Drops our validated graphics config, applies the mouse/pad
# input.map, does the force-feedback registry rename, and checks the Glide wrapper.
# Guides rather than downloads (no game/binary redistribution). See docs/STEAMDECK.md.
#
# Usage:  ./setup-steamdeck.sh "/path/to/Interstate 76 game dir" [/path/to/wineprefix]
#   e.g.  ./setup-steamdeck.sh ~/Games/Heroic/"Interstate 76" ~/Games/Heroic/Prefixes/default/"Interstate 76"
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
GAME="${1:?usage: setup-steamdeck.sh <game-dir> [wineprefix]}"
PREFIX="${2:-}"
[ -d "$GAME" ] || { echo "game dir not found: $GAME"; exit 1; }
[ -f "$GAME/i76.exe" ] || echo "WARNING: i76.exe not in $GAME - is this the right dir?"

echo "== 1. Glide wrapper check =="
if [ -f "$GAME/Glide2x.dll" ]; then
  # dgVoodoo Glide2x is ~200KB; GOG OpenGLide differs. Just report presence.
  sz=$(stat -c%s "$GAME/Glide2x.dll" 2>/dev/null || stat -f%z "$GAME/Glide2x.dll")
  echo "   Glide2x.dll present ($sz bytes). If the 3D screen is black, swap in dgVoodoo"
  echo "   2.78.2 (or 2.8.2) MS/x86/Glide2x.dll and delete GOG's OpenGLide first."
else
  echo "   NO Glide2x.dll found. Drop dgVoodoo2 MS/x86/Glide2x.dll here (see docs/STEAMDECK.md)."
fi

echo "== 2. Graphics config =="
cp "$HERE/dgVoodoo.conf" "$GAME/dgVoodoo.conf"
echo "   dgVoodoo.conf installed (gamma + MSAA 4x + 32-bit; edit Resolution to 'max' for 1280x800)."

echo "== 3. Input map (mouse + gamepad, joystick1) =="
if [ -f "$GAME/input.map" ]; then
  [ -f "$GAME/input.map.pre-steamdeck" ] || cp "$GAME/input.map" "$GAME/input.map.pre-steamdeck"
  # reuse the Mac script's logic if the file looks stock; otherwise just remind
  echo "   input.map exists. To (re)apply mouse+pad bindings, run setup-mouse-and-pad.sh"
  echo "   pointed at this dir, or verify it binds joystick1 (NOT joystick5). See docs."
else
  echo "   input.map not found yet - launch the game once to generate it, then re-run."
fi

echo "== 4. Force feedback (docked wheel) - registry rename =="
if [ -n "$PREFIX" ] && command -v wine >/dev/null 2>&1; then
  WINEPREFIX="$PREFIX" wine reg copy \
    "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate'76FRC" \
    "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate '76" /s /f 2>/dev/null \
    && echo "   FFB enabled (WOW6432Node)." \
    || WINEPREFIX="$PREFIX" wine reg copy \
        "HKLM\\SOFTWARE\\ACTIVISION\\Interstate'76FRC" \
        "HKLM\\SOFTWARE\\ACTIVISION\\Interstate '76" /s /f 2>/dev/null \
        && echo "   FFB enabled." || echo "   FFB rename skipped (run enable-force-feedback.bat in-prefix)."
else
  echo "   Pass the wineprefix as arg 2, or run enable-force-feedback.bat via Heroic/protontricks."
fi

echo "== 5. 20 FPS cap =="
echo "   dgVoodoo.conf sets FPSLimit=20; the exe's I76PATCH.DLL also caps; optionally add the"
echo "   Deck QAM framerate limit = 20. Verify physics in Instant Melee (no car flips on bumps)."

echo ""
echo "Done. Launch flag must be:  i76.exe -glide   (Heroic: launch arguments)."
echo "Add the game to Steam as a Non-Steam Game for Steam Input (driving template)."
echo "Full recipe + open items (music, dgVoodoo version): docs/STEAMDECK.md"

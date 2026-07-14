#!/bin/bash
# Interstate '76 on the Deck - apply the prefix tweaks the Mac port needed, IN CASE
# the first launch crashes/black-screens. Run AFTER launching the game once (that
# creates the Proton prefix). Idempotent. Applies: Windows version = win98,
# a Wine virtual desktop, and the force-feedback registry rename (docked wheel).
#
# Usage on the Deck (Desktop Mode Konsole):  ./first-launch-fix.sh
set -e
STEAM=~/.steam/steam
# find our non-Steam appid's compatdata prefix (created on first launch)
APPID=2731345568                      # I76 shortcut appid (see add-to-steam.py)
CD="$STEAM/steamapps/compatdata/$APPID"
[ -d "$CD/pfx" ] || CD=$(ls -d "$STEAM"/steamapps/compatdata/*/pfx 2>/dev/null | \
  xargs -n1 dirname 2>/dev/null | while read d; do \
    grep -qs Interstate "$d/pfx/drive_c/users"/*/* 2>/dev/null && echo "$d"; done | head -1)
if [ ! -d "$CD/pfx" ]; then
  echo "No prefix yet - LAUNCH THE GAME ONCE first (it builds the prefix), then re-run."
  exit 1
fi
PFX="$CD/pfx"
echo "prefix: $PFX"
GE=$(ls -d "$STEAM"/compatibilitytools.d/GE-Proton*/files/bin/wine 2>/dev/null | sort -V | tail -1)
export WINEPREFIX="$PFX"
export WINEDEBUG=-all
wine() { "$GE" "$@"; }

echo "== win98 app default + virtual desktop =="
wine reg add 'HKCU\Software\Wine\AppDefaults\i76.exe' /v Version /d win98 /f 2>/dev/null || true
wine reg add 'HKCU\Software\Wine\AppDefaults\i76.exe\Explorer' /v Desktop /d i76 /f 2>/dev/null || true
wine reg add 'HKCU\Software\Wine\Explorer\Desktops' /v i76 /d 1280x960 /f 2>/dev/null || true

echo "== force feedback (docked wheel) =="
wine reg copy "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate'76FRC" \
              "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate '76" /s /f 2>/dev/null || \
wine reg add  "HKLM\\SOFTWARE\\WOW6432Node\\ACTIVISION\\Interstate '76" /v EXE /t REG_SZ /d i76.exe /f 2>/dev/null || true

echo "Done. Relaunch the game. If it still won't render, try Proton 9.0 instead of GE-Proton"
echo "in the game's Properties > Compatibility, or ping to debug the prefix remotely."

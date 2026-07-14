#!/bin/sh
# Double-click to open the dgVoodoo 2.78.2 Control Panel for Interstate '76 (the
# "Voodoo" / Glide path). Edit the Glide tab (MSAA, gamma ramp, resolution) or the
# General tab (Output API, brightness), then OK. Changes apply next time you launch
# Interstate 76 - Glide-dgVoodoo-DXVK-Metal.app - they're written to dgVoodoo.conf in the game folder.
#
# LEAVE Output API = Direct3D 11 (FL 10.1) and VideoCard = Voodoo Graphics / TMU 2048
# (higher TMU triggers I76's texture panic). See docs/VISUAL-QUALITY-MAC.md.
#
# One-time: the CPL binary isn't in the repo (it's dgVoodoo's, and the repo ships no
# binaries) - run setup-dgvoodoo-cpl.sh once to fetch dgVoodooCpl.exe into the game dir.
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
GAME="$APP/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"
if [ ! -f "$GAME/dgVoodooCpl.exe" ]; then
  echo "dgVoodooCpl.exe not found. Run setup-dgvoodoo-cpl.sh first." ; sleep 4 ; exit 1
fi
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/SharedSupport/wine/lib"
export WINEPREFIX="$APP/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1
cd "$GAME"
exec "$APP/Contents/SharedSupport/wine/bin/wine" "C:\\GOG Games\\Interstate 76\\dgVoodooCpl.exe"

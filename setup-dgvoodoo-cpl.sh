#!/bin/sh
# Fetch the dgVoodoo 2.78.2 Control Panel (dgVoodooCpl.exe) into the game folder so
# open-dgvoodoo-settings.command can launch it. The CPL is dgVoodoo's own GUI for
# editing dgVoodoo.conf (Glide/DirectX tabs). We ship no binaries in the repo, so this
# grabs the 32-bit CPL from the archived 2.78.2 package (matches our Glide2x.dll).
set -e
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
GAME="$APP/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"
[ -d "$GAME" ] || { echo "game dir not found: $GAME"; exit 1; }
TMP="$(mktemp -d)"
URL="https://archive.org/download/dgvoodoo2_78_2_202205/dgVoodoo2_78_2.zip"
echo "Downloading dgVoodoo 2.78.2 package (~5 MB) for the CPL..."
curl -L --fail --max-time 180 -o "$TMP/dgv.zip" "$URL"
# extract the 32-bit CPL (root dgVoodooCpl.exe in the package = x86)
unzip -o -j "$TMP/dgv.zip" 'dgVoodooCpl.exe' -d "$TMP" >/dev/null
[ -f "$TMP/dgVoodooCpl.exe" ] || { echo "extract failed"; exit 1; }
# sanity: 32-bit PE
file "$TMP/dgVoodooCpl.exe" | grep -qi '80386' || echo "WARNING: CPL is not 32-bit x86"
cp "$TMP/dgVoodooCpl.exe" "$GAME/dgVoodooCpl.exe"
rm -rf "$TMP"
echo "Installed: $GAME/dgVoodooCpl.exe"
echo "Now double-click open-dgvoodoo-settings.command to tweak the Voodoo graphics."

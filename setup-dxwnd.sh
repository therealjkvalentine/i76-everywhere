#!/bin/sh
# Interstate '76 - install DxWnd into the wrapper and freeze it as the launch default.
# DxWnd (GPLv3, https://sourceforge.net/projects/dxwnd/) wraps the game's DirectDraw so
# the software renderer runs in a big, scalable, title-barred window - the "fill the
# screen" answer. This installs DxWnd + our tuned profile (interstate-76.dxw) into the
# wrapper's prefix and points the app's launch stub at it.
#
# One-time, needs network (downloads DxWnd ~5MB). Idempotent.
set -e
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
PFX="$APP/Contents/SharedSupport/prefix"
DIR=$(cd "$(dirname "$0")" && pwd)
DXDIR="$PFX/drive_c/dxwnd"

if [ ! -f "$DXDIR/dxwnd.exe" ]; then
  echo "Downloading DxWnd..."
  TMP=$(mktemp -d)
  curl -sL -o "$TMP/dxwnd.rar" "https://sourceforge.net/projects/dxwnd/files/latest/download"
  mkdir -p "$DXDIR"
  unar -q -f -o "$TMP/x" "$TMP/dxwnd.rar"
  # the archive nests a dxwnd/ dir; copy its contents flat into drive_c/dxwnd
  cp -R "$TMP/x/dxwnd/"* "$DXDIR/" 2>/dev/null || cp -R "$TMP/x/"* "$DXDIR/"
  rm -rf "$TMP"
fi

# install our tuned profile as dxwnd.ini (the [window] header + the frozen target)
{
  printf '[window]\nposx=1077\nposy=523\nsizx=640\nsizy=480\nshowhelp=NO\nexpert=1\n'
  cat "$DIR/interstate-76.dxw"
} > "$DXDIR/dxwnd.ini"

echo "DxWnd installed. Launch the game with: open \"$APP\""
echo "(The app opens DxWnd; double-click the 'Interstate 76' row to play.)"

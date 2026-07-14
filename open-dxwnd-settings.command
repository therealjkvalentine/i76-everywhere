#!/bin/sh
# Double-click to open the DxWnd settings GUI for Interstate '76.
# Right-click the "Interstate 76" row -> Modify to change settings, then OK.
# (The app icon itself launches straight into the game via /R:1; use THIS to tune.)
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/SharedSupport/wine/lib"
export WINEPREFIX="$APP/Contents/SharedSupport/prefix" WINEESYNC=1 WINEMSYNC=1
cd "$APP/Contents/SharedSupport/prefix/drive_c/dxwnd"
exec "$APP/Contents/SharedSupport/wine/bin/wine" 'C:\dxwnd\dxwnd.exe'

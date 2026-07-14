#!/bin/sh
# Interstate '76 - one-time setup for the Voodoo mode (Interstate 76 - Glide-dgVoodoo-DXVK-Metal.app).
# Wires the dgVoodoo Glide chain: dgVoodoo 2.78.2 Glide2x.dll + our known-good
# dgVoodoo.conf/dxvk.conf + the float-when-inactive registry key. The engine-side
# DXVK d3d11 swap is checked (not performed) - see docs/DXGI-DGVOODOO-RESEARCH.md.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
GAME="$APP/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"
[ -d "$GAME" ] || { echo "game dir not found: $GAME"; exit 1; }

# 1. dgVoodoo Glide2x.dll (2.78.2 - NOT 2.81+, Wine-fatal enumeration regression)
GLIDE_MD5_DGVOODOO_2782="30cd5243db07b13c40bc19cadded24dc"
have="$(md5 -q "$GAME/Glide2x.dll" 2>/dev/null || echo none)"
if [ "$have" = "$GLIDE_MD5_DGVOODOO_2782" ]; then
    echo "Glide2x.dll: dgVoodoo 2.78.2 already in place"
else
    echo "Glide2x.dll is not dgVoodoo 2.78.2 (md5 $have)."
    echo "  Download dgVoodoo 2.78.2 (dege's site or archive.org), take 3Dfx/x86/Glide2x.dll,"
    echo "  back up the current one (OpenGLide) and drop it in:"
    echo "    $GAME/"
    exit 1
fi

# 2. known-good configs (windowed, FPSLimit=20, Resolution=2x, async pipelines)
cp "$HERE/dgVoodoo.conf" "$GAME/dgVoodoo.conf"
cp "$HERE/dxvk.conf" "$GAME/dxvk.conf"
echo "dgVoodoo.conf + dxvk.conf installed"

# 3. float-when-inactive (per-app): the -glide shell is exclusive-fullscreen-ish;
#    without this the window minimizes on every focus loss (Wine hardcoded).
export WINEPREFIX="$APP/Contents/SharedSupport/prefix"
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/SharedSupport/wine/lib"
export WINEESYNC=1 WINEMSYNC=1
"$APP/Contents/SharedSupport/wine/bin/wine" reg add \
    'HKCU\Software\Wine\AppDefaults\i76.exe\Mac Driver' \
    /v WindowsFloatWhenInactive /d all /f >/dev/null 2>&1
"$APP/Contents/SharedSupport/wine/bin/wineserver" -k >/dev/null 2>&1 || true
echo "registry: WindowsFloatWhenInactive=all (per-app)"

# 4. engine DXVK check (dgVoodoo needs FL10.1; wined3d refuses it on GL and Vulkan)
D3D11="$APP/Contents/SharedSupport/wine/lib/wine/i386-windows/d3d11.dll"
if strings "$D3D11" 2>/dev/null | grep -qi dxvk; then
    echo "engine d3d11: DXVK - good"
else
    echo "WARNING: engine d3d11.dll does not look like DXVK - the Voodoo mode will fail."
    echo "  See docs/DXGI-DGVOODOO-RESEARCH.md for the swap recipe."
fi
echo "Done. Launch with: Interstate 76 - Glide-dgVoodoo-DXVK-Metal.app (build-launchers.sh installs it)"

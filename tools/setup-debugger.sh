#!/bin/sh
# Install x32dbg (x64dbg's 32-bit build) into the Interstate '76 Wine prefix.
#
# WHY x32dbg and not Cheat Engine: CE's Windows binary is only distributed
# through a third-party "download manager" stub (cheatengine.org states the free
# installer carries "extra software recommendation"; the clean installer is
# Patreon-gated). x32dbg is open source, distributed as a plain zip from its
# own GitHub releases, and gives us the ONE capability our AHK tooling cannot:
# hardware breakpoints -> "find what writes this address". The debug menu's
# F10 successive-scan already covers CE's scanning workflow.
#
# It installs INSIDE the prefix so it runs as a Windows process alongside the
# game: Wine then mediates the debug API through wineserver instead of macOS
# ptrace (which is what blocks native debuggers from attaching on macOS).
#
#   tools/setup-debugger.sh            download (pinned), verify, install
#   tools/setup-debugger.sh --launch   start x32dbg in the prefix
#   tools/setup-debugger.sh --remove   delete it from the prefix
#
# Downloads nothing on --launch/--remove. Ships no binaries in this repo.

set -e
APP="$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app"
PREFIX="$APP/Contents/SharedSupport/prefix"
DEST="$PREFIX/drive_c/x64dbg"
URL="https://github.com/x64dbg/x64dbg/releases/download/2026.05.27/snapshot_2026-05-27_12-11.zip"
SHA="d41966dfc5b435a372798245300ca0ab7bb8e48bdbf48512c6fb20fcca427697"
TMP="${TMPDIR:-/tmp}/x64dbg-i76"

export WINEPREFIX="$PREFIX" WINEESYNC=1 WINEMSYNC=1
export DYLD_FALLBACK_LIBRARY_PATH="$APP/Contents/Frameworks:$APP/Contents/Frameworks/GStreamer.framework/Versions/1.0/lib:$APP/Contents/SharedSupport/wine/lib"

case "$1" in
--launch)
    [ -f "$DEST/x32/x32dbg.exe" ] || { echo "not installed - run tools/setup-debugger.sh first"; exit 1; }
    echo "launching x32dbg inside the prefix..."
    "$APP/Contents/SharedSupport/wine/bin/wine" 'C:\x64dbg\x32\x32dbg.exe' >/dev/null 2>&1 &
    echo "started (pid $!).  See docs/FIND-WHAT-WRITES.md for the workflow."
    ;;
--remove)
    rm -rf "$DEST" && echo "removed $DEST"
    ;;
*)
    [ -d "$PREFIX" ] || { echo "game prefix not found: $PREFIX"; exit 1; }
    mkdir -p "$TMP"
    if [ ! -f "$TMP/x32dbg.zip" ]; then
        echo "downloading x64dbg snapshot (~30 MB) from github.com/x64dbg/x64dbg ..."
        curl -fL# -o "$TMP/x32dbg.zip" "$URL"
    fi
    echo "verifying sha256..."
    GOT=$(shasum -a 256 "$TMP/x32dbg.zip" | awk '{print $1}')
    if [ "$GOT" != "$SHA" ]; then
        echo "CHECKSUM MISMATCH - refusing to install"
        echo "  expected $SHA"
        echo "  got      $GOT"
        exit 1
    fi
    echo "ok. extracting..."
    rm -rf "$TMP/x" && mkdir -p "$TMP/x"
    unzip -q -o "$TMP/x32dbg.zip" -d "$TMP/x"
    mkdir -p "$DEST"
    cp -R "$TMP/x/release/." "$DEST/"
    echo "installed to $DEST"
    echo "next: tools/setup-debugger.sh --launch   (see docs/FIND-WHAT-WRITES.md)"
    ;;
esac

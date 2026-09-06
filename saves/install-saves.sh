#!/bin/sh
# install-saves.sh - copy the repo's bookmark saves into the Mac wrapper's game folder.
#
# The whole set moves together: savegame.dir indexes the .cmp files by slot, so a partial
# copy leaves the index describing saves that are not there.
#
#   ./saves/install-saves.sh [path-to-game-folder]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=${1:-"$HOME/Applications/Sikarugir/Interstate 76 - Software (DxWnd).app/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76"}
[ -f "$GAME/i76.exe" ] || { echo "no i76.exe in: $GAME" >&2; exit 1; }
pgrep -f 'i76.exe' >/dev/null 2>&1 && { echo "close the game first - it rewrites savegame.dir on exit" >&2; exit 1; }

# refuse to install a short index rather than ship the truncation bug onward
python3 - "$HERE/savegame.dir" <<'PY'
import struct, sys, os
p = sys.argv[1]
d = open(p, 'rb').read()
n = struct.unpack_from('<I', d, 0)[0]
want = 0x28 + n * 60
if len(d) < want:
    sys.exit("savegame.dir is truncated (%d bytes, need %d for %d records) - repair it first" % (len(d), want, n))
PY

BACKUP="$GAME/save-backup-$(date +%Y%m%d-%H%M%S)"
if ls "$GAME"/save*.cmp >/dev/null 2>&1 || [ -f "$GAME/savegame.dir" ]; then
    mkdir -p "$BACKUP"
    cp "$GAME"/save*.cmp "$GAME/savegame.dir" "$BACKUP"/ 2>/dev/null || true
    echo "backed up existing saves -> $BACKUP"
    rm -f "$GAME"/save*.cmp "$GAME/savegame.dir"
fi
cp "$HERE"/save*.cmp "$HERE/savegame.dir" "$GAME"/
echo "installed bookmarks into: $GAME"

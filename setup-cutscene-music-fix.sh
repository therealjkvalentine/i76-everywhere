#!/bin/sh
# Interstate '76 - fix wrong music over FMV cutscenes (the SMACKW32 proxy).
#
# The game never stops CD music when a movie starts - on a real 1997 CD-ROM the
# drive couldn't stream data + redbook at once, so movies silenced the music as a
# hardware side effect. With file-based music (GOG / DxWnd virtual CD) the last
# track keeps playing over each cutscene's own baked-in score. This installs a
# proxy SMACKW32.DLL that broadcasts MCI_STOP at SmackOpen (= movie start) and
# forwards all 39 exports (ordinal-exact) to the renamed original smackorg.dll.
# Mission music is untouched - the game starts each track itself after movies.
#
#   setup-cutscene-music-fix.sh            install into every Mac wrapper
#   setup-cutscene-music-fix.sh --revert   restore the original DLL
#
# Windows/Deck: copy smack-music-fix/SMACKW32.DLL into the game folder after
# renaming the original SMACKW32.DLL to smackorg.dll (same two steps).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PROXY="$HERE/smack-music-fix/SMACKW32.DLL"
# md5 of the original 71680-byte RAD Smacker 3.5 DLL that GOG ships
REAL_MD5="b6bb89a764922f036cef0b53f5e839e2"

find_games() {
    for base in "$HOME/Applications/Sikarugir" "$HOME/Applications" "/Applications"; do
        [ -d "$base" ] || continue
        find "$base" -maxdepth 8 -type d -path '*drive_c/GOG Games/Interstate 76' 2>/dev/null
    done | sort -u
}
GAMES=$(find_games)
[ -n "$GAMES" ] || { echo "no I76 wrapper found under ~/Applications"; exit 1; }

if [ "$1" = "--revert" ]; then
    echo "$GAMES" | while read -r g; do
        [ -f "$g/smackorg.dll" ] || { echo "no smackorg.dll in $g (nothing to revert)"; continue; }
        mv -f "$g/smackorg.dll" "$g/SMACKW32.DLL"
        echo "reverted: $g"
    done
    exit 0
fi

[ -f "$PROXY" ] || { echo "proxy not built - run smack-music-fix/build.sh first"; exit 1; }
echo "$GAMES" | while read -r g; do
    cur_md5=$(md5 -q "$g/SMACKW32.DLL" 2>/dev/null || echo none)
    if [ -f "$g/smackorg.dll" ]; then
        : # original already preserved; just refresh the proxy
    elif [ "$cur_md5" = "$REAL_MD5" ]; then
        mv "$g/SMACKW32.DLL" "$g/smackorg.dll"
    else
        echo "SKIP $g - SMACKW32.DLL is not the known original (md5 $cur_md5) and no smackorg.dll backup exists"
        continue
    fi
    cp -f "$PROXY" "$g/SMACKW32.DLL"
    echo "installed -> $g (original kept as smackorg.dll)"
done
echo "Done. Relaunch; cutscenes now silence the leftover CD track (their own audio plays)."
echo "Undo anytime: $0 --revert"

#!/bin/sh
# Interstate '76 - sync your campaign saves across platforms via the repo.
# The committed saves/ folder holds save000-004.cmp + savegame.dir (I76's 5 save
# slots + index) - your own progress, so on any machine you clone/pull this repo you
# can restore your saves and continue / replay any mission you've reached.
#
#   setup-saves.sh              install repo saves/ INTO the game (restore)
#   setup-saves.sh --backup     copy the game's CURRENT saves back INTO repo saves/
#                               (run this, then commit, to share new progress)
#
# I76 saves live next to i76.exe. This finds every Mac wrapper; on Windows/Deck copy
# saves/* into the game folder (Heroic: .../Interstate 76/, or the Proton prefix).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SAVES="$HERE/saves"
mkdir -p "$SAVES"

find_games() {
    for base in "$HOME/Applications/Sikarugir" "$HOME/Applications" "/Applications"; do
        [ -d "$base" ] || continue
        find "$base" -maxdepth 8 -type d -path '*drive_c/GOG Games/Interstate 76' 2>/dev/null
    done | sort -u
}
GAMES=$(find_games)
[ -n "$GAMES" ] || { echo "No I76 wrapper found under ~/Applications (Mac). On Windows/Deck, copy saves/* into the game folder by hand."; exit 1; }

if [ "$1" = "--backup" ]; then
    g=$(echo "$GAMES" | head -1)
    cp "$g"/save00*.cmp "$g/savegame.dir" "$SAVES/" 2>/dev/null
    echo "Backed up $g saves -> repo saves/ . Commit + push to share."
    exit 0
fi

# restore: install repo saves into every wrapper (back up existing first, once)
echo "$GAMES" | while read -r g; do
    [ -d "$g" ] || continue
    [ -f "$g/save000.cmp" ] && [ ! -f "$g/save000.cmp.pre-sync" ] && \
        for f in "$g"/save00*.cmp "$g/savegame.dir"; do [ -f "$f" ] && cp "$f" "$f.pre-sync"; done
    cp "$SAVES"/save00*.cmp "$SAVES/savegame.dir" "$g/" 2>/dev/null && echo "restored saves -> $g"
done
echo "Launch the game; your saved missions are in LOAD. (Undo: the *.pre-sync backups next to each save.)"

#!/bin/bash
# Interstate '76 - put the Deck's game/ADDON back to stock textures (2026-10-14). RUNS ON THE DECK.
#
# Owner: "the night mission on the steam deck is messed up, the textures seem wrong". Cause: the Deck's
# game/ADDON still carries the July HD texture pack (3,300+ files written 2026-07-10, retired project-wide
# on 2026-07-27, never on the Windows daily driver, whose ADDON is the GOG stock set). Its palette-indexed
# .map tiles (cockpit gauges and reticles z*.map, roads r4r*, terrain i2*, lights *_1lt_*, clouds nk_*)
# were re-quantized against ONE day palette (t01). I76 does night by keeping the indices and swapping
# the level palette, so the pack's new indices come out as wrong colours at night only
# (docs/research/HD-TEXTURES-RESEARCH.md, "Why it was retired"; docs/guides/STEAMDECK.md, night missions).
#
# This moves every ADDON file that is not GOG stock (DUMMY.TXT fullres.lst i2ayj_13.map loadgame.pcx
# loadscr.pcx) or a vehicle/armour file (*.vcf *.vsf, kept) into backups/hd-pack-<date>/ADDON, installs
# the launcher with the ADDON audit line, and writes a NOTE.txt. Nothing is deleted.
#
#   ./setup-deck-stock-textures.sh            move the pack aside (re-runnable; a re-run with nothing to move does nothing)
#   ./setup-deck-stock-textures.sh --revert   move the pack back and restore the previous launcher
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL="${I76_INSTALL:-$HOME/Games/Interstate76}"
GAME="${I76_GAMEDIR:-$INSTALL/game}"
ADDON="$GAME/ADDON"
BACKUPS="$INSTALL/backups"
LAST="$BACKUPS/LAST-STOCKTEX"
STOCK_I2AYJ_MD5="815380fe7a058e173553e769ba2e088e"   # GOG's own ADDON/i2ayj_13.map (= the Windows daily driver's)

say() { echo "  $*"; }
die() { echo "FATAL: $*"; exit 1; }
md5() { md5sum "$1" | cut -d' ' -f1; }
# "[i]" so the pattern does not match this pgrep's own command line
running() { pgrep -f "[i]76\.exe" >/dev/null 2>&1; }
keep() {
    case "$(echo "$1" | tr 'A-Z' 'a-z')" in
        dummy.txt|fullres.lst|i2ayj_13.map|loadgame.pcx|loadscr.pcx|*.vcf|*.vsf) return 0 ;;
    esac
    return 1
}

if [ "${1:-}" = "--revert" ]; then
    [ -f "$LAST" ] || die "no move recorded ($LAST missing)"
    B="$(cat "$LAST")"; [ -d "$B/ADDON" ] || die "backup folder gone: $B/ADDON"
    running && die "the game is running - quit it first"
    n=0
    for f in "$B/ADDON"/* "$B/ADDON"/.[!.]*; do
        [ -e "$f" ] || continue
        mv -f "$f" "$ADDON/"; n=$((n + 1))
    done
    say "moved $n files back into game/ADDON"
    [ -f "$B/i76-deck-launch.sh" ] && cp -pf "$B/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh" && say "restored i76-deck-launch.sh"
    rm -f "$LAST"; echo "Done (from $B)."; exit 0
fi

[ -f "$GAME/i76.exe" ] || die "no i76.exe in $GAME"
[ -d "$ADDON" ] || die "no $ADDON"
[ -f "$HERE/i76-deck-launch.sh" ] || die "payload missing: $HERE/i76-deck-launch.sh"
running && die "the game is running - quit it first"

TS="$(date +%Y%m%d-%H%M%S)"
B="$BACKUPS/hd-pack-$TS"
mkdir -p "$B/ADDON"
before="$(ls -1A "$ADDON" | wc -l)"
( cd "$ADDON" && ls -1A | sort ) > "$B/addon-before.txt"
[ -f "$INSTALL/i76-deck-launch.sh" ] && cp -p "$INSTALL/i76-deck-launch.sh" "$B/i76-deck-launch.sh"

moved=0
for f in "$ADDON"/* "$ADDON"/.[!.]*; do
    [ -e "$f" ] || continue
    keep "$(basename "$f")" && continue
    mv "$f" "$B/ADDON/"; moved=$((moved + 1))
done
after="$(ls -1A "$ADDON" | wc -l)"
say "game/ADDON: $before -> $after files ($moved moved to $B/ADDON)"

# i2ayj_13.map is GOG's own file; the pack shipped an identical copy. Stock content is what must stay.
if [ -f "$ADDON/i2ayj_13.map" ] && [ "$(md5 "$ADDON/i2ayj_13.map")" != "$STOCK_I2AYJ_MD5" ]; then
    if [ -f "$GAME/ADDON.pre-hd-pack/i2ayj_13.map" ] && [ "$(md5 "$GAME/ADDON.pre-hd-pack/i2ayj_13.map")" = "$STOCK_I2AYJ_MD5" ]; then
        mv "$ADDON/i2ayj_13.map" "$B/ADDON/" && cp -p "$GAME/ADDON.pre-hd-pack/i2ayj_13.map" "$ADDON/i2ayj_13.map"
        say "i2ayj_13.map was not stock - replaced from ADDON.pre-hd-pack"
    else
        say "WARNING: i2ayj_13.map is not GOG stock ($(md5 "$ADDON/i2ayj_13.map")) and no stock copy was found"
    fi
fi

cp -f "$HERE/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh"; chmod +x "$INSTALL/i76-deck-launch.sh"
say "launcher -> $(md5 "$INSTALL/i76-deck-launch.sh") (logs an 'addon:' line per launch)"
( cd "$ADDON" && ls -la ) | sed 's/^/    /'

if [ "$moved" -gt 0 ]; then
    echo "$B" > "$LAST"
else
    say "nothing to move - ADDON was already stock"
fi
cat > "$B/NOTE.txt" <<EOF
$TS  deck/setup-deck-stock-textures.sh (i76-everywhere)
Owner 2026-10-14: "the night mission on the steam deck is messed up, the textures seem wrong".
game/ADDON carried the retired July HD texture pack (palette-indexed .map tiles re-quantized against
the day palette t01 -> wrong colours on night missions). Moved here: $moved files ($before -> $after in ADDON).
Kept in ADDON: GOG stock files + *.vcf/*.vsf. addon-before.txt = the full listing before the move.
Undo: bash ~/i76-deploy/deck/setup-deck-stock-textures.sh --revert   (or mv ADDON/* back by hand)
EOF
echo "Done. Backup + note: $B"

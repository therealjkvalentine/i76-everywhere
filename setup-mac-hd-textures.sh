#!/bin/sh
# Install the Interstate '76 HD texture pack into every I76 Wine-wrapper's ADDON/ on macOS.
#
# The pack is engine-level loose-file override (renderer- and platform-independent) - the SAME
# built pack from the Windows box works here unchanged, because it's the same game files.
# It contains BOTH texture formats (VQM *m.pak for -gdi/DxWnd software, M16 *6.pak for -glide),
# so it covers whichever renderer you play. See docs/PORTING-WINDOWS-WINS-TO-MAC.md.
#
# Usage:  setup-mac-hd-textures.sh <PACK_DIR>
#   PACK_DIR = the built pack copied from Windows (C:\Games\_tools\i76-build-final) or built
#              natively (texture-lab/reencode_all.py output). A folder of *.pak/.pix/.cbk/.map/.m16.
#
# Reversible: each wrapper's original ADDON is backed up to ADDON.pre-hd once; --revert restores it.
set -e

PACK="$1"
REVERT=""
[ "$1" = "--revert" ] && REVERT=1

find_addons() {
    # every I76 wrapper prefix under the usual Sikarugir/Kegworks locations
    for base in "$HOME/Applications/Sikarugir" "$HOME/Applications" "/Applications"; do
        [ -d "$base" ] || continue
        find "$base" -maxdepth 8 -type d -path '*drive_c/GOG Games/Interstate 76' 2>/dev/null
    done | sort -u
}

ADDONS=$(find_addons | while read -r g; do echo "$g/ADDON"; done)
if [ -z "$ADDONS" ]; then
    echo "No Interstate '76 wrapper found under ~/Applications/Sikarugir (or /Applications)."
    echo "Expected a prefix path ending in  drive_c/GOG Games/Interstate 76 ."
    exit 1
fi

if [ -n "$REVERT" ]; then
    echo "$ADDONS" | while read -r addon; do
        [ -d "$addon" ] || continue
        gamedir=$(dirname "$addon")
        if [ -d "$gamedir/ADDON.pre-hd" ]; then
            rm -rf "$addon"; mv "$gamedir/ADDON.pre-hd" "$addon"
            echo "reverted: $addon"
        else
            echo "no backup for: $addon (skipped)"
        fi
    done
    echo "Revert done."
    exit 0
fi

[ -d "$PACK" ] || { echo "PACK_DIR not found: $PACK"; echo "Usage: $0 <PACK_DIR>   (or --revert)"; exit 1; }
NFILES=$(find "$PACK" -maxdepth 1 -type f \( -name '*.pak' -o -name '*.pix' -o -name '*.cbk' -o -name '*.map' -o -name '*.m16' \) | wc -l | tr -d ' ')
[ "$NFILES" -gt 0 ] || { echo "No pak/pix/cbk/map/m16 files in $PACK - is that the built pack?"; exit 1; }
echo "Pack: $PACK ($NFILES texture files)"

echo "$ADDONS" | while read -r addon; do
    [ -d "$(dirname "$addon")" ] || continue
    gamedir=$(dirname "$addon")
    mkdir -p "$addon"
    # one-time backup of the pristine ADDON (GOG ships loading screens etc. here)
    [ -d "$gamedir/ADDON.pre-hd" ] || cp -Rc "$addon" "$gamedir/ADDON.pre-hd" 2>/dev/null || cp -R "$addon" "$gamedir/ADDON.pre-hd"
    # copy the pack in; our pak/pix/cbk/map/m16 names never collide with GOG's *.PCX/*.LST/*.MAP loaders
    cp -f "$PACK"/*.pak "$PACK"/*.pix "$addon"/ 2>/dev/null || true
    cp -f "$PACK"/*.cbk "$addon"/ 2>/dev/null || true
    cp -f "$PACK"/*.map "$PACK"/*.m16 "$addon"/ 2>/dev/null || true
    # NIGHT VQM EXCLUSION: the pack ships night only as software VQM (nightm.pak/.pix),
    # and VQM is palette-indexed against each level's own 8-bit .ACT - the pack's night
    # texture was quantized against the wrong palette, so night missions (e.g. Mission 6)
    # come out color-shifted while every day world is fine. Drop the night override so
    # night falls back to the correct stock textures inside I76.ZFS. (Stashed, not deleted,
    # so you can A/B it.) See docs/HD-TEXTURES-RESEARCH.md "night palette mismatch".
    if [ -f "$addon/nightm.pak" ] || [ -f "$addon/nightm.pix" ]; then
        mkdir -p "$addon/.night-hd-disabled"
        mv -f "$addon"/nightm.pak "$addon"/nightm.pix "$addon/.night-hd-disabled"/ 2>/dev/null || true
        echo "  (night VQM excluded - color-mismatch on the software renderer; stashed in ADDON/.night-hd-disabled)"
    fi
    echo "installed -> $addon  (backup: $gamedir/ADDON.pre-hd)"
done

echo ""
echo "Done. Launch the game normally - HD textures load through the same ADDON override the"
echo "Windows box uses. Both -gdi (software) and -glide (OpenGLide) pick up the right format."
echo "Undo anytime:  $0 --revert"

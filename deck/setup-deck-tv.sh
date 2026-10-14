#!/bin/bash
# Interstate '76 - docked-to-a-TV fixes for the Deck (2026-10-13). RUNS ON THE DECK.
#
# Owner report, docked: "the screen renders in a non 16:9 aspect ratio and the controller can't be used
# to navigate the menu. Screen looks a little darker too." This installs:
#   * i76-deck-launch.sh with the display profile: reads the size of the X screen the game is given
#     (gamescope's Xwayland = Steam's per-game Game Resolution) and sets I76_ASPECT + dgVoodoo's
#     [Glide] Resolution to it; handheld / tv brightness profiles (docs/STEAMDECK.md, "Docked to a TV")
#   * the proxy with I76_PAD_MENU (music-fix/padmenu.c): left stick / D-pad move the menu pointer,
#     A clicks, B = Esc, Start = Enter, in the shell and the Esc menu only
#   * a block of tunables appended to i76-env.sh (marker: "display profiles + pad menu")
# Kept: everything else in i76-env.sh, input.map, the controller layout, dgVoodoo's other keys.
#
#   ./setup-deck-tv.sh            install (re-runnable; each run backs up what it replaces)
#   ./setup-deck-tv.sh --revert   restore the files as they were before the first install
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL="${I76_INSTALL:-$HOME/Games/Interstate76}"
GAME="${I76_GAMEDIR:-$INSTALL/game}"
BACKUPS="$INSTALL/backups"
LAST="$BACKUPS/LAST-TV"
PROXY="$HERE/Strlkup.deck-padmenu.dll"     # lab snapshot of 509c6df0's source + padmenu.c (MSVC x86)
PROXY_MD5="03bcb58916c4a29b14f28389a2cb2fab"

say() { echo "  $*"; }
die() { echo "FATAL: $*"; exit 1; }
md5() { md5sum "$1" | cut -d' ' -f1; }
# "[i]" so the pattern does not match this pgrep's own command line
running() { pgrep -f "[i]76\.exe" >/dev/null 2>&1; }

if [ "${1:-}" = "--revert" ]; then
    [ -f "$LAST" ] || die "no install recorded ($LAST missing)"
    B="$(cat "$LAST")"; [ -d "$B" ] || die "backup folder gone: $B"
    running && die "the game is running - quit it first"
    for rel in game/Strlkup.dll game/dgVoodoo.conf i76-env.sh i76-deck-launch.sh; do
        [ -f "$B/$rel" ] && cp -pf "$B/$rel" "$INSTALL/$rel" && say "restored $rel"
    done
    rm -f "$LAST"; echo "Done (from $B)."; exit 0
fi

[ -f "$GAME/i76.exe" ] || die "no i76.exe in $GAME"
[ -f "$PROXY" ] || die "payload missing: $PROXY"
[ "$(md5 "$PROXY")" = "$PROXY_MD5" ] || die "proxy md5 is not $PROXY_MD5"
[ -f "$HERE/i76-deck-launch.sh" ] || die "payload missing: $HERE/i76-deck-launch.sh"
[ -f "$INSTALL/i76-env.sh" ] || die "no $INSTALL/i76-env.sh - run setup-deck-wide.sh first"
grep -qa strlkup_orig "$GAME/Strlkup.dll" || die "game/Strlkup.dll is not our proxy - run setup-deck-wide.sh first"
running && die "the game is running - quit it first"

TS="$(date +%Y%m%d-%H%M%S)"
B="$BACKUPS/pre-tv-$TS"
mkdir -p "$B/game"
for rel in game/Strlkup.dll game/dgVoodoo.conf i76-env.sh i76-deck-launch.sh; do
    cp -p "$INSTALL/$rel" "$B/$rel"
done
( cd "$INSTALL" && md5sum game/Strlkup.dll game/dgVoodoo.conf i76-env.sh i76-deck-launch.sh ) > "$B/md5-before.txt"
# --revert goes back to the state before the FIRST install: a re-run keeps that backup as the target
if [ -f "$LAST" ] && [ -d "$(cat "$LAST")" ]; then
    echo "== backup -> $B (re-run: --revert still restores $(cat "$LAST")) =="
else
    echo "$B" > "$LAST"; echo "== backup -> $B =="
fi

cp -f "$PROXY" "$GAME/Strlkup.dll"
[ "$(md5 "$GAME/Strlkup.dll")" = "$PROXY_MD5" ] || die "proxy copy check failed (backup in $B)"
say "proxy -> $PROXY_MD5"
cp -f "$HERE/i76-deck-launch.sh" "$INSTALL/i76-deck-launch.sh"; chmod +x "$INSTALL/i76-deck-launch.sh"
say "launcher -> $(md5 "$INSTALL/i76-deck-launch.sh")"

if grep -q "display profiles + pad menu" "$INSTALL/i76-env.sh"; then
    say "i76-env.sh already has the display / pad-menu block - left as it is"
else
    cat >> "$INSTALL/i76-env.sh" <<'EOF'

# --- display profiles + pad menu (deck/setup-deck-tv.sh, 2026-10-13) -----------------------------
# i76-deck-launch.sh picks a profile per launch and overrides I76_ASPECT / I76_GLIDE_GAMMA above:
# I76_ASPECT and dgVoodoo's [Glide] Resolution follow the X screen the game is given (Steam > game
# Properties > Game Resolution), the brightness values follow the profile. Each value can also be put
# in front of the wrapper in Steam's launch options, e.g.  I76_DECK_DISPLAY=handheld "/home/deck/...".
export I76_DECK_DISPLAY="${I76_DECK_DISPLAY:-auto}"            # auto (TV when an HDMI/DP display is connected) | handheld | tv | off
export I76_HANDHELD_GAMMA="${I76_HANDHELD_GAMMA:-1.3}"          # 3D gamma lift on the panel (as before)
export I76_HANDHELD_BRIGHTNESS="${I76_HANDHELD_BRIGHTNESS:-100}" # dgVoodoo Brightness on the panel (as before)
export I76_TV_GAMMA="${I76_TV_GAMMA:-1.45}"                     # 3D gamma on the TV: higher = brighter mid-tones (try 1.3 .. 1.8)
export I76_TV_BRIGHTNESS="${I76_TV_BRIGHTNESS:-100}"            # dgVoodoo Brightness on the TV, menus too (105-115 if still dark; clips highlights)
export I76_TV_CONTRAST="${I76_TV_CONTRAST:-100}"                # dgVoodoo Contrast on the TV
export I76_TV_COLOR="${I76_TV_COLOR:-100}"                      # dgVoodoo Color (saturation) on the TV
export I76_TV_SS="${I76_TV_SS:-1}"                              # render at 1x the TV size (2 = supersample, if 60 fps holds)
export I76_TV_REFRESH="${I76_TV_REFRESH:-60}"                   # TVs are 60 Hz (the OLED panel's 90 is for handheld)
export I76_PAD_MENU="${I76_PAD_MENU:-1}"                        # controller moves the menu pointer (shell + Esc menu only)
export I76_PAD_MENU_LOG="${I76_PAD_MENU_LOG:-1}"                # pad-menu lines in mciproxy.log
EOF
    say "i76-env.sh: display / pad-menu block appended"
fi

cat > "$B/NOTE.txt" <<EOF
$TS deck/setup-deck-tv.sh (i76-everywhere): docked-TV fixes.
Replaced: game/Strlkup.dll (now $PROXY_MD5, I76_PAD_MENU), i76-deck-launch.sh (display profile),
appended the display / pad-menu block to i76-env.sh. dgVoodoo.conf is rewritten by the launcher on
each launch ([Glide] Resolution, [General] Brightness / Contrast / Color values only).
Before: see md5-before.txt. Revert: bash <repo>/deck/setup-deck-tv.sh --revert
EOF
echo "== done. Note: $B/NOTE.txt =="

#!/bin/bash
# Interstate '76 LAN pack on a Mac (game night, docs/GAME-NIGHT.md; pack built by tools/mp-pack.py).
#
#   tools/mp-mac-install.sh update APP PACK   replace APP's game folder with PACK/common + PACK/mac. The old folder is
#                                             MOVED (not copied) to "Interstate 76.pre-mp-<date>" beside it and kept;
#                                             its saves (savegame.dir, save*.cmp) are copied into the new folder.
#                                             user.reg (backed up first): IPXWrapper DLL overrides for i76.exe and
#                                             I76_COOP_AI=1, I76_COOP_CHAIN=1, I76_MUSIC_THREAD=1.
#   tools/mp-mac-install.sh clone APP DEST    a clean copy of an updated APP for another Mac account: no saves, no
#                                             backups, no debug tools (x64dbg, AutoHotkey scratch), no links into ~.
#   tools/mp-mac-install.sh adopt APP         on the target account: map that user to the prefix's profile
#                                             (drive_c/users/$USER -> Sikarugir, as the Sikarugir launcher does).
#   tools/mp-mac-install.sh verify APP PACK   md5 of every pack file in APP's game folder against PACK/common.md5 and
#                                             PACK/mac.md5; prints the mismatches and a count. Needs only md5/awk.
#
# Never run with the game open. update/clone use python3 (James's Mac); adopt/verify need nothing extra (kids' Macs).
set -euo pipefail
die() { echo "mp-mac-install: $*" >&2; exit 1; }
cmd="${1:-}"; APP="${2:-}"
[ -n "$cmd" ] && [ -n "$APP" ] || { sed -n '2,17p' "$0"; exit 2; }
APP="${APP%/}"
P="$APP/Contents/SharedSupport/prefix"
G="$P/drive_c/GOG Games/Interstate 76"
[ -d "$P" ] || die "no prefix in $APP"
running() { pgrep -f "$(printf '%s' "$APP" | sed 's/[][\.*^$()+?{}|]/\\&/g')/Contents" >/dev/null || pgrep -f 'i76\.exe' >/dev/null; }

case "$cmd" in
update)
    PACK="${3:?pack folder}"; PACK="${PACK%/}"
    [ -d "$PACK/common" ] && [ -d "$PACK/mac" ] || die "no common/ and mac/ in $PACK"
    running && die "the game (or this app) is running - quit it first"
    BAK="$G.pre-mp-$(date +%Y%m%d)"
    [ -e "$BAK" ] && die "$BAK exists already"
    mv "$G" "$BAK"
    mkdir "$G"
    cp -R "$PACK/common/." "$G/"
    cp -R "$PACK/mac/." "$G/"
    n=0
    for f in "$BAK"/savegame.dir "$BAK"/save[0-9][0-9][0-9].cmp; do [ -f "$f" ] && cp -p "$f" "$G/" && n=$((n+1)); done
    echo "game folder replaced; old one kept as $BAK; $n save files carried over"
    cp -p "$P/user.reg" "$P/user.reg.pre-mp-$(date +%Y%m%d)"
    python3 - "$P/user.reg" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
def setv(key, name, val):
    global s
    if key not in s:
        s = s.rstrip('\n') + '\n\n' + key + ' 1791000000\n'
    i = s.index(key); e = s.find('\n\n', i); e = len(s) if e < 0 else e
    lines = [l for l in s[i:e].split('\n') if not l.startswith('"%s"=' % name)]
    lines.insert(1 if len(lines) < 2 or not lines[1].startswith('#time') else 2, '"%s"=%s' % (name, val))
    s = s[:i] + '\n'.join(lines) + s[e:]
dll = '[Software\\\\Wine\\\\AppDefaults\\\\i76.exe\\\\DllOverrides]'
setv(dll, 'wsock32', '"native,builtin"')       # IPXWrapper (docs/MULTIPLAYER.md section 6, step 2)
setv(dll, 'mswsock', '"native,builtin"')
setv('[Environment]', 'I76_COOP_AI', '"1"')     # docs/COOP.md: shared enemies (only matters in the co-op missions)
setv('[Environment]', 'I76_COOP_CHAIN', '"1"')  # won -> next co-op mission, lost -> retry; melee arenas end normally
setv('[Environment]', 'I76_MUSIC_THREAD', '"1"')  # MP3 open off the game thread: without it the boot sat in mmdevapi for minutes (James's Mac, 2026-10-17)
open(p, 'w', encoding='utf-8').write(s)
print('user.reg: wsock32/mswsock native,builtin for i76.exe; I76_COOP_AI=1, I76_COOP_CHAIN=1, I76_MUSIC_THREAD=1 (backup user.reg.pre-mp-*)')
PY
    ;;
clone)
    DEST="${3:?destination .app}"; DEST="${DEST%/}"
    [ -e "$DEST" ] && die "$DEST exists"
    running && die "the source is running - quit it first"
    mkdir -p "$(dirname "$DEST")"
    # APFS clone (no extra disk until changed), then strip what is James's own
    cp -c -R "$APP" "$DEST"
    DP="$DEST/Contents/SharedSupport/prefix"; DG="$DP/drive_c/GOG Games/Interstate 76"
    rm -rf "$DP/drive_c/GOG Games/Interstate 76.pre-"* "$DP/drive_c/GOG Games/Interstate 76.mp-"* "$DP/drive_c/GOG Games/Interstate 76 Nitro Pack" "$DP/drive_c/x64dbg" "$DP"/user.reg.pre-* "$DP"/*.bak*
    find "$DG" -maxdepth 1 \( -name 'save*.cmp' -o -name 'savegame.dir*' -o -name '*.log' \) -delete
    find "$DP/drive_c/AutoHotkey" -mindepth 1 -maxdepth 1 ! -name AutoHotkeyU32.exe ! -name i76-remap.ahk ! -name license.txt -exec rm -rf {} +
    # links that leave the prefix (Templates -> ~/Templates) become plain folders
    find "$DP/drive_c/users" -type l | while read -r l; do case "$(readlink "$l")" in /*) rm "$l"; mkdir "$l";; esac; done
    /usr/libexec/PlistBuddy -c "Set :CFBundleName Interstate 76 MP" "$DEST/Contents/Info.plist" 2>/dev/null || true
    du -sh "$DEST"
    ;;
adopt)
    U="$P/drive_c/users"
    [ -d "$U/Sikarugir" ] || die "no users/Sikarugir profile in the prefix"
    if [ -e "$U/$USER" ] || [ -L "$U/$USER" ]; then echo "users/$USER exists ($(readlink "$U/$USER" || echo folder))"
    else ln -s Sikarugir "$U/$USER"; echo "users/$USER -> Sikarugir"; fi
    ;;
verify)
    PACK="${3:?pack folder}"; PACK="${PACK%/}"
    bad=0; n=0
    for part in common mac; do
        while IFS= read -r line; do
            h="${line%%  *}"; f="${line#*  }"; n=$((n+1))
            got=$(md5 -q "$G/$f" 2>/dev/null || echo missing)
            [ "$got" = "$h" ] || { echo "MISMATCH $part/$f ($got)"; bad=$((bad+1)); }
        done < "$PACK/$part.md5"
    done
    echo "verify: $n pack files, $bad mismatches ($G)"
    [ "$bad" -eq 0 ]
    ;;
*) die "unknown command $cmd (update | clone | adopt | verify)" ;;
esac
